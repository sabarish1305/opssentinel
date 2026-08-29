import io

from opssentinel import mcp_server


class FakeResponse:
    def __init__(self, body: str, status: int = 200):
        self.status = status
        self.body = io.BytesIO(body.encode("utf-8"))

    def read(self, *args, **kwargs):
        return self.body.read(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_fetch_service_health(monkeypatch):
    def fake_urlopen(url, timeout):
        return FakeResponse(
            '{"service":"checkout-api","status":"healthy","version":"1.0.0"}'
        )

    monkeypatch.setattr(mcp_server, "urlopen", fake_urlopen)

    result = mcp_server.fetch_service_health()

    assert result["reachable"] is True
    assert result["http_status"] == 200
    assert result["service"]["status"] == "healthy"
    assert result["service"]["version"] == "1.0.0"


def test_fetch_service_health_timeout(monkeypatch):
    def fake_urlopen(url, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(mcp_server, "urlopen", fake_urlopen)

    result = mcp_server.fetch_service_health()

    assert result["reachable"] is False
    assert result["error"] == "Request timed out"


def test_fetch_service_health_invalid_json(monkeypatch):
    def fake_urlopen(url, timeout):
        return FakeResponse("this-is-not-json")

    monkeypatch.setattr(mcp_server, "urlopen", fake_urlopen)

    result = mcp_server.fetch_service_health()

    assert result["reachable"] is True
    assert result["http_status"] == 200
    assert "Invalid JSON response" in result["error"]


def test_measure_latency(monkeypatch):
    def fake_urlopen(url, timeout):
        return FakeResponse(
            '{"service":"checkout-api","version":"1.1.0","checkout":"completed"}'
        )

    times = iter(
        [
            0.0,
            0.1,
            0.1,
            0.2,
            0.2,
            0.3,
        ]
    )

    monkeypatch.setattr(mcp_server, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        mcp_server.time,
        "perf_counter",
        lambda: next(times),
    )

    result = mcp_server.measure_latency(samples=3)

    assert result["reachable"] is True
    assert result["samples"] == 3
    assert result["latencies_ms"] == [100.0, 100.0, 100.0]
    assert result["average_latency_ms"] == 100.0


def test_measure_latency_timeout(monkeypatch):
    def fake_urlopen(url, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(mcp_server, "urlopen", fake_urlopen)

    result = mcp_server.measure_latency(samples=1)

    assert result["reachable"] is False
    assert result["error"] == "Request timed out"


def test_measure_latency_invalid_json(monkeypatch):
    def fake_urlopen(url, timeout):
        return FakeResponse("broken-json")

    monkeypatch.setattr(mcp_server, "urlopen", fake_urlopen)

    result = mcp_server.measure_latency(samples=1)

    assert result["reachable"] is True
    assert result["http_status"] == 200
    assert "Invalid JSON response" in result["error"]


def test_measure_latency_rejects_zero_samples():
    result = mcp_server.measure_latency(samples=0)

    assert result["error"] == "samples must be greater than 0"


def test_measure_latency_rejects_negative_samples():
    result = mcp_server.measure_latency(samples=-1)

    assert result["error"] == "samples must be greater than 0"
def test_load_deployment_history(monkeypatch, tmp_path):
    history_file = tmp_path / "deployments.json"

    history_file.write_text(
        """
        [
          {
            "deployment_id": "deploy-001",
            "service": "checkout-api",
            "version": "1.0.0",
            "status": "healthy"
          },
          {
            "deployment_id": "deploy-002",
            "service": "checkout-api",
            "version": "1.1.0",
            "status": "degraded"
          }
        ]
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr(
        mcp_server,
        "DEPLOYMENT_HISTORY_PATH",
        history_file,
    )

    result = mcp_server.load_deployment_history()

    assert result["service"] == "checkout-api"
    assert result["deployment_count"] == 2
    assert result["deployments"][0]["version"] == "1.0.0"
    assert result["deployments"][1]["version"] == "1.1.0"


def test_load_deployment_history_missing_file(monkeypatch, tmp_path):
    missing_file = tmp_path / "missing.json"

    monkeypatch.setattr(
        mcp_server,
        "DEPLOYMENT_HISTORY_PATH",
        missing_file,
    )

    result = mcp_server.load_deployment_history()

    assert result["error"] == "Deployment history file not found"


def test_load_deployment_history_invalid_json(monkeypatch, tmp_path):
    history_file = tmp_path / "deployments.json"
    history_file.write_text("broken-json", encoding="utf-8")

    monkeypatch.setattr(
        mcp_server,
        "DEPLOYMENT_HISTORY_PATH",
        history_file,
    )

    result = mcp_server.load_deployment_history()

    assert "Invalid deployment history JSON" in result["error"]
def test_fetch_service_logs(monkeypatch):
    class FakeResult:
        returncode = 0
        stdout = (
            "[checkout-api] WARN version=1.1.0 "
            "degraded_mode=true checkout_delay_ms=800\n"
        )

    monkeypatch.setattr(
        mcp_server.subprocess,
        "run",
        lambda *args, **kwargs: FakeResult(),
    )

    result = mcp_server.fetch_service_logs(lines=50)

    assert result["container"] == "opssentinel-checkout"
    assert result["lines_requested"] == 50
    assert result["logs"] == [
        "[checkout-api] WARN version=1.1.0 "
        "degraded_mode=true checkout_delay_ms=800"
    ]


def test_fetch_service_logs_rejects_nonpositive_lines():
    result = mcp_server.fetch_service_logs(lines=0)

    assert result["error"] == "lines must be greater than 0"


def test_fetch_service_logs_docker_not_found(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(
        mcp_server.subprocess,
        "run",
        fake_run,
    )

    result = mcp_server.fetch_service_logs()

    assert result["error"] == "Docker CLI not found"


def test_fetch_service_logs_timeout(monkeypatch):
    def fake_run(*args, **kwargs):
        raise mcp_server.subprocess.TimeoutExpired(
            cmd="docker",
            timeout=5,
        )

    monkeypatch.setattr(
        mcp_server.subprocess,
        "run",
        fake_run,
    )

    result = mcp_server.fetch_service_logs()

    assert result["error"] == "Docker log collection timed out"


def test_fetch_service_logs_command_failure(monkeypatch):
    class FakeResult:
        returncode = 1
        stdout = "Error: No such container: opssentinel-checkout"

    monkeypatch.setattr(
        mcp_server.subprocess,
        "run",
        lambda *args, **kwargs: FakeResult(),
    )

    result = mcp_server.fetch_service_logs()

    assert "No such container" in result["error"]
def test_fetch_service_logs_uses_configured_container(monkeypatch):
    captured = {}

    class FakeResult:
        returncode = 0
        stdout = "checkout log\n"

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeResult()

    monkeypatch.setenv(
        "OPSSENTINEL_CONTAINER_NAME",
        "custom-checkout",
    )

    monkeypatch.setattr(
        mcp_server.subprocess,
        "run",
        fake_run,
    )

    result = mcp_server.fetch_service_logs()

    assert captured["command"][-1] == "custom-checkout"
    assert result["container"] == "custom-checkout"
def test_get_docker_container_name_uses_default_when_empty(monkeypatch):
    monkeypatch.setenv("OPSSENTINEL_CONTAINER_NAME", "")

    assert (
        mcp_server.get_docker_container_name()
        == mcp_server.DEFAULT_DOCKER_CONTAINER_NAME
    )
def test_prepare_rollback(monkeypatch):
    monkeypatch.setattr(
    mcp_server,
    "fetch_service_health",
    lambda: {
        "reachable": True,
        "http_status": 200,
        "service": {
            "service": "checkout-api",
            "status": "degraded",
            "version": "1.1.0",
        },
    },
)

    monkeypatch.setattr(
        mcp_server,
        "load_deployment_history",
        lambda: {
            "service": "checkout-api",
            "deployment_count": 2,
            "deployments": [
                {
                    "deployment_id": "deploy-001",
                    "version": "1.0.0",
                    "deployed_at": "2026-08-28T06:45:00Z",
                    "status": "healthy",
                },
                {
                    "deployment_id": "deploy-002",
                    "version": "1.1.0",
                    "deployed_at": "2026-08-28T07:50:00Z",
                    "status": "degraded",
                },
            ],
        },
    )

    result = mcp_server.prepare_rollback()

    assert result["ready"] is True
    assert result["rollback_needed"] is True
    assert result["current_version"] == "1.1.0"
    assert result["target_version"] == "1.0.0"
    assert result["requires_human_approval"] is True
    assert result["next_action"] == "execute_rollback"


def test_prepare_rollback_rejects_unreachable_service(monkeypatch):
    monkeypatch.setattr(
        mcp_server,
        "fetch_service_health",
        lambda: {
            "reachable": False,
            "error": "Request timed out",
        },
    )

    result = mcp_server.prepare_rollback()

    assert result["ready"] is False
    assert "health" in result["error"].lower()

def test_prepare_rollback_rejects_http_error_health(monkeypatch):
    monkeypatch.setattr(
        mcp_server,
        "fetch_service_health",
        lambda: {
            "reachable": True,
            "http_status": 500,
            "error": "Internal Server Error",
        },
    )

    result = mcp_server.prepare_rollback()

    assert result["ready"] is False
    assert "HTTP 200" in result["error"]

def test_prepare_rollback_rejects_invalid_health_payload(monkeypatch):
    monkeypatch.setattr(
        mcp_server,
        "fetch_service_health",
        lambda: {
            "reachable": True,
            "http_status": 200,
            "service": None,
        },
    )

    result = mcp_server.prepare_rollback()

    assert result["ready"] is False
    assert "payload" in result["error"].lower()

def test_prepare_rollback_rejects_missing_history(monkeypatch):
    monkeypatch.setattr(
        mcp_server,
        "fetch_service_health",
        lambda: {
            "reachable": True,
            "http_status": 200,
            "service": {
                "service": "checkout-api",
                "status": "degraded",
                "version": "1.1.0",
            },
        },
    ),

    monkeypatch.setattr(
        mcp_server,
        "load_deployment_history",
        lambda: {
            "error": "Deployment history file not found",
        },
    )

    result = mcp_server.prepare_rollback()

    assert result["ready"] is False
    assert "deployment history" in result["error"].lower()


def test_prepare_rollback_when_already_healthy_version(monkeypatch):
    monkeypatch.setattr(
        mcp_server,
        "fetch_service_health",
        lambda: {
            "reachable": True,
            "http_status": 200,
            "service": {
                "service": "checkout-api",
                "status": "healthy",
                "version": "1.0.0",
            },
        },
    ),


    monkeypatch.setattr(
        mcp_server,
        "load_deployment_history",
        lambda: {
            "deployments": [
                {
                    "deployment_id": "deploy-001",
                    "version": "1.0.0",
                    "deployed_at": "2026-08-28T06:45:00Z",
                    "status": "healthy",
                },
            ],
        },
    )

    result = mcp_server.prepare_rollback()

    assert result["ready"] is False
    assert result["rollback_needed"] is False
    assert result["current_version"] == "1.0.0"
def test_execute_rollback_success(monkeypatch):
    mcp_server.rollback_plans.clear()
    mcp_server.rollback_approvals.clear()

    monkeypatch.setenv(
        mcp_server.APPROVAL_SECRET_ENV,
    "test-approval-secret",
    )

    plan_id = "plan-success"
    mcp_server.rollback_plans[plan_id] = {
        "service": "checkout-api",
        "current_version": "1.1.0",
        "target_version": "1.0.0",
        "target_deployment_id": "deploy-001",
    }

    approval_token = mcp_server.create_rollback_approval_token(plan_id)

    monkeypatch.setattr(
        mcp_server,
        "fetch_service_health",
        lambda: {
            "reachable": True,
            "http_status": 200,
            "service": {
                "service": "checkout-api",
                "status": "degraded",
                "version": "1.1.0",
            },
        },
    )

    captured = {}

    class FakeResult:
        returncode = 0
        stdout = "container recreated\n"

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return FakeResult()

    monkeypatch.setattr(mcp_server.subprocess, "run", fake_run)

    result = mcp_server.execute_rollback(
    plan_id,
    approval_token,
    "1.0.0",
    )
    assert result["executed"] is True
    assert result["previous_version"] == "1.1.0"
    assert result["target_version"] == "1.0.0"
    assert result["verification_required"] is True

    assert captured["command"] == [
        "docker",
        "compose",
        "--file",
        str(mcp_server.DEFAULT_COMPOSE_FILE),
        "up",
        "-d",
        "--force-recreate",
        "--no-build",
        "checkout-api",
    ]

    assert captured["env"]["SERVICE_VERSION"] == "1.0.0"
    assert captured["env"]["DEGRADED"] == "false"


def test_execute_rollback_rejects_wrong_target(monkeypatch):
    mcp_server.rollback_plans.clear()
    mcp_server.rollback_approvals.clear()

    monkeypatch.setenv(
        mcp_server.APPROVAL_SECRET_ENV,
        "test-approval-secret",
    )

    plan_id = "plan-wrong-target"

    mcp_server.rollback_plans[plan_id] = {
        "service": "checkout-api",
        "current_version": "1.1.0",
        "target_version": "1.0.0",
        "target_deployment_id": "deploy-001",
    }
    approval_token = mcp_server.create_rollback_approval_token(plan_id)

    result = mcp_server.execute_rollback(
        plan_id,
        approval_token,
        "0.9.0",
    )

    assert result["executed"] is False
    assert "does not match" in result["error"]


def test_execute_rollback_rejects_unknown_plan(monkeypatch):
    mcp_server.rollback_plans.clear()
    mcp_server.rollback_approvals.clear()

    result = mcp_server.execute_rollback(
        "missing-plan",
        "unused-token",
        "1.0.0",
    )

    assert result["executed"] is False
    assert "unknown rollback plan" in result["error"].lower()


def test_execute_rollback_handles_docker_missing(monkeypatch):
    mcp_server.rollback_plans.clear()
    mcp_server.rollback_approvals.clear()

    monkeypatch.setenv(
        mcp_server.APPROVAL_SECRET_ENV,
        "test-approval-secret",
    )

    plan_id = "plan-docker-missing"
    mcp_server.rollback_plans[plan_id] = {
        "service": "checkout-api",
        "current_version": "1.1.0",
        "target_version": "1.0.0",
        "target_deployment_id": "deploy-001",
    }
    approval_token = mcp_server.create_rollback_approval_token(plan_id)

    monkeypatch.setattr(
        mcp_server,
        "fetch_service_health",
        lambda: {
            "reachable": True,
            "http_status": 200,
            "service": {
                "service": "checkout-api",
                "status": "degraded",
                "version": "1.1.0",
            },
        },
    )

    def fake_run(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(mcp_server.subprocess, "run", fake_run)

    result = mcp_server.execute_rollback(
    plan_id,
    approval_token,
    "1.0.0",
    )

    assert result["executed"] is False
    assert result["error"] == "Docker CLI not found."


def test_execute_rollback_handles_timeout(monkeypatch):
    mcp_server.rollback_plans.clear()
    mcp_server.rollback_approvals.clear()

    monkeypatch.setenv(
        mcp_server.APPROVAL_SECRET_ENV,
        "test-approval-secret",
    )

    plan_id = "plan-timeout"

    mcp_server.rollback_plans[plan_id] = {
        "service": "checkout-api",
        "current_version": "1.1.0",
        "target_version": "1.0.0",
        "target_deployment_id": "deploy-001",
    }
    approval_token = mcp_server.create_rollback_approval_token(plan_id)
    health_responses = iter(
        [
            {
                "reachable": True,
                "http_status": 200,
                "service": {
                    "service": "checkout-api",
                    "status": "degraded",
                    "version": "1.1.0",
                },
            },

            {
                "reachable": False,
                "error": "Service unavailable",
            },
        ]
    )

    monkeypatch.setattr(
        mcp_server,
        "fetch_service_health",
        lambda: next(health_responses),
    )



    def fake_run(*args, **kwargs):
        raise mcp_server.subprocess.TimeoutExpired(
            cmd="docker compose",
            timeout=30,
        )

    monkeypatch.setattr(mcp_server.subprocess, "run", fake_run)

    result = mcp_server.execute_rollback(
    plan_id,
    approval_token,
    "1.0.0",
    )

    assert result["executed"] is None
    assert result["outcome"] == "indeterminate"
    assert result["verification_required"] is True
    assert "timed out" in result["error"].lower()
    assert "could not be confirmed" in result["error"].lower()

def test_execute_rollback_timeout_but_target_is_running(monkeypatch):
    mcp_server.rollback_plans.clear()
    mcp_server.rollback_approvals.clear()

    monkeypatch.setenv(
        mcp_server.APPROVAL_SECRET_ENV,
        "test-approval-secret",
    )

    plan_id = "plan-timeout-success"

    mcp_server.rollback_plans[plan_id] = {
        "service": "checkout-api",
        "current_version": "1.1.0",
        "target_version": "1.0.0",
        "target_deployment_id": "deploy-001",
    }

    approval_token = mcp_server.create_rollback_approval_token(plan_id)

    health_responses = iter(
        [
            {
                "reachable": True,
                "http_status": 200,
                "service": {
                    "service": "checkout-api",
                    "status": "degraded",
                    "version": "1.1.0",
                },
            },
            {
                "reachable": True,
                "http_status": 200,
                "service": {
                    "service": "checkout-api",
                    "status": "healthy",
                    "version": "1.0.0",
                },
            },
        ]
    )

    monkeypatch.setattr(
        mcp_server,
        "fetch_service_health",
        lambda: next(health_responses),
    )

    def fake_run(*args, **kwargs):
        raise mcp_server.subprocess.TimeoutExpired(
            cmd="docker compose",
            timeout=30,
        )

    monkeypatch.setattr(
        mcp_server.subprocess,
        "run",
        fake_run,
    )

    result = mcp_server.execute_rollback(
        plan_id,
        approval_token,
        "1.0.0",
    )

    assert result["executed"] is True
    assert result["outcome"] == "succeeded_after_timeout"
    assert result["target_version"] == "1.0.0"
    assert result["observed_version"] == "1.0.0"
    assert result["verification_required"] is True

def test_execute_rollback_rejects_missing_approval(monkeypatch):
    mcp_server.rollback_plans.clear()
    mcp_server.rollback_approvals.clear()

    plan_id = "plan-missing-approval"

    mcp_server.rollback_plans[plan_id] = {
        "service": "checkout-api",
        "current_version": "1.1.0",
        "target_version": "1.0.0",
        "target_deployment_id": "deploy-001",
    }

    result = mcp_server.execute_rollback(
        plan_id,
        "missing-token",
        "1.0.0",
    )

    assert result["executed"] is False
    assert "approval" in result["error"].lower()

def test_execute_rollback_rejects_expired_approval(monkeypatch):
    mcp_server.rollback_plans.clear()
    mcp_server.rollback_approvals.clear()

    monkeypatch.setenv(
        mcp_server.APPROVAL_SECRET_ENV,
        "test-approval-secret",
    )

    current_time = [1000.0]

    monkeypatch.setattr(
        mcp_server.time,
        "time",
        lambda: current_time[0],
    )

    plan_id = "plan-expired"

    mcp_server.rollback_plans[plan_id] = {
        "service": "checkout-api",
        "current_version": "1.1.0",
        "target_version": "1.0.0",
        "target_deployment_id": "deploy-001",
    }

    approval_token = mcp_server.create_rollback_approval_token(plan_id)

    current_time[0] += mcp_server.ROLLBACK_APPROVAL_TTL_SECONDS + 1

    result = mcp_server.execute_rollback(
        plan_id,
        approval_token,
        "1.0.0",
    )

    assert result["executed"] is False
    assert "expired" in result["error"].lower()

def test_execute_rollback_rejects_reused_approval(monkeypatch):
    mcp_server.rollback_plans.clear()
    mcp_server.rollback_approvals.clear()

    monkeypatch.setenv(
        mcp_server.APPROVAL_SECRET_ENV,
        "test-approval-secret",
    )

    plan_id = "plan-reused"

    mcp_server.rollback_plans[plan_id] = {
        "service": "checkout-api",
        "current_version": "1.1.0",
        "target_version": "1.0.0",
        "target_deployment_id": "deploy-001",
    }

    approval_token = mcp_server.create_rollback_approval_token(plan_id)

    mcp_server.rollback_approvals[approval_token]["used"] = True

    result = mcp_server.execute_rollback(
        plan_id,
        approval_token,
        "1.0.0",
    )

    assert result["executed"] is False
    assert "already been used" in result["error"].lower()

def test_execute_rollback_rejects_mismatched_plan(monkeypatch):
    mcp_server.rollback_plans.clear()
    mcp_server.rollback_approvals.clear()

    monkeypatch.setenv(
        mcp_server.APPROVAL_SECRET_ENV,
        "test-approval-secret",
    )

    plan_a = "plan-a"
    plan_b = "plan-b"

    mcp_server.rollback_plans[plan_a] = {
        "service": "checkout-api",
        "current_version": "1.1.0",
        "target_version": "1.0.0",
        "target_deployment_id": "deploy-001",
    }

    mcp_server.rollback_plans[plan_b] = {
        "service": "checkout-api",
        "current_version": "1.1.0",
        "target_version": "1.0.0",
        "target_deployment_id": "deploy-001",
    }

    approval_token = mcp_server.create_rollback_approval_token(plan_a)

    result = mcp_server.execute_rollback(
        plan_b,
        approval_token,
        "1.0.0",
    )

    assert result["executed"] is False
    assert "signature is invalid" in result["error"].lower()

def test_execute_rollback_rejects_forged_approval(monkeypatch):
    mcp_server.rollback_plans.clear()
    mcp_server.rollback_approvals.clear()

    monkeypatch.setenv(
        mcp_server.APPROVAL_SECRET_ENV,
        "test-approval-secret",
    )

    plan_id = "plan-forged"

    mcp_server.rollback_plans[plan_id] = {
        "service": "checkout-api",
        "current_version": "1.1.0",
        "target_version": "1.0.0",
        "target_deployment_id": "deploy-001",
    }

    approval_token = mcp_server.create_rollback_approval_token(plan_id)

    expires_at, nonce, _signature = approval_token.split(".", 2)

    forged_token = (
        f"{expires_at}.{nonce}."
        f"{'0' * 64}"
    )

    # Simulate a token that exists in approval state but has been tampered with.
    mcp_server.rollback_approvals[forged_token] = {
        "plan_id": plan_id,
        "expires_at": int(expires_at),
        "used": False,
    }

    result = mcp_server.execute_rollback(
        plan_id,
        forged_token,
        "1.0.0",
    )

    assert result["executed"] is False
    assert "signature" in result["error"].lower()

def test_execute_rollback_rejects_changed_service_state(monkeypatch):
    mcp_server.rollback_plans.clear()
    mcp_server.rollback_approvals.clear()

    monkeypatch.setenv(
        mcp_server.APPROVAL_SECRET_ENV,
        "test-approval-secret",
    )

    plan_id = "plan-state-changed"

    mcp_server.rollback_plans[plan_id] = {
        "service": "checkout-api",
        "current_version": "1.1.0",
        "target_version": "1.0.0",
        "target_deployment_id": "deploy-001",
    }

    approval_token = mcp_server.create_rollback_approval_token(plan_id)

    monkeypatch.setattr(
        mcp_server,
        "fetch_service_health",
        lambda: {
            "reachable": True,
            "http_status": 200,
            "service": {
                "service": "checkout-api",
                "status": "degraded",
                "version": "1.2.0",
            },
        },
    )

    def fail_if_docker_runs(*args, **kwargs):
        raise AssertionError("Docker must not run for a stale approval.")

    monkeypatch.setattr(
        mcp_server.subprocess,
        "run",
        fail_if_docker_runs,
    )

    result = mcp_server.execute_rollback(
        plan_id,
        approval_token,
        "1.0.0",
    )

    assert result["executed"] is False
    assert "state changed" in result["error"].lower()