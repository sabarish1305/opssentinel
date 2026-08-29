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
            "service": "checkout-api",
            "status": "degraded",
            "version": "1.1.0",
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


def test_prepare_rollback_rejects_missing_history(monkeypatch):
    monkeypatch.setattr(
        mcp_server,
        "fetch_service_health",
        lambda: {
            "reachable": True,
            "service": "checkout-api",
            "version": "1.1.0",
        },
    )

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
            "service": "checkout-api",
            "status": "healthy",
            "version": "1.0.0",
        },
    )

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
    monkeypatch.setattr(
        mcp_server,
        "prepare_rollback",
        lambda: {
            "ready": True,
            "service": "checkout-api",
            "current_version": "1.1.0",
            "target_version": "1.0.0",
            "target_deployment_id": "deploy-001",
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

    result = mcp_server.execute_rollback("1.0.0")

    assert result["executed"] is True
    assert result["previous_version"] == "1.1.0"
    assert result["target_version"] == "1.0.0"
    assert result["verification_required"] is True

    assert captured["command"] == [
        "docker",
        "compose",
        "up",
        "-d",
        "--force-recreate",
        "--no-build",
        "checkout-api",
    ]

    assert captured["env"]["SERVICE_VERSION"] == "1.0.0"
    assert captured["env"]["DEGRADED"] == "false"


def test_execute_rollback_rejects_wrong_target(monkeypatch):
    monkeypatch.setattr(
        mcp_server,
        "prepare_rollback",
        lambda: {
            "ready": True,
            "target_version": "1.0.0",
        },
    )

    result = mcp_server.execute_rollback("0.9.0")

    assert result["executed"] is False
    assert "does not match" in result["error"]


def test_execute_rollback_rejects_unready_plan(monkeypatch):
    monkeypatch.setattr(
        mcp_server,
        "prepare_rollback",
        lambda: {
            "ready": False,
            "error": "No known healthy deployment is available for rollback.",
        },
    )

    result = mcp_server.execute_rollback("1.0.0")

    assert result["executed"] is False
    assert "healthy deployment" in result["error"].lower()


def test_execute_rollback_handles_docker_missing(monkeypatch):
    monkeypatch.setattr(
        mcp_server,
        "prepare_rollback",
        lambda: {
            "ready": True,
            "target_version": "1.0.0",
        },
    )

    def fake_run(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(mcp_server.subprocess, "run", fake_run)

    result = mcp_server.execute_rollback("1.0.0")

    assert result["executed"] is False
    assert result["error"] == "Docker CLI not found."


def test_execute_rollback_handles_timeout(monkeypatch):
    monkeypatch.setattr(
        mcp_server,
        "prepare_rollback",
        lambda: {
            "ready": True,
            "target_version": "1.0.0",
        },
    )

    def fake_run(*args, **kwargs):
        raise mcp_server.subprocess.TimeoutExpired(
            cmd="docker compose",
            timeout=30,
        )

    monkeypatch.setattr(mcp_server.subprocess, "run", fake_run)

    result = mcp_server.execute_rollback("1.0.0")

    assert result["executed"] is False
    assert result["error"] == "Rollback command timed out."