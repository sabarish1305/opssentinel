import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from importlib.resources import files
from mcp.server.mcpserver import MCPServer
import subprocess
import os
from mcp.types import ToolAnnotations
from pathlib import Path
import secrets
import time
import hashlib
import hmac
SERVICE_HEALTH_URL = "http://127.0.0.1:8000/health"
CHECKOUT_URL = "http://127.0.0.1:8000/checkout"
DEFAULT_COMPOSE_FILE = Path(__file__).resolve().parents[2] / "compose.yaml"
DEPLOYMENT_HISTORY_PATH = files("opssentinel").joinpath(
    "data",
    "deployments.json",
)
mcp = MCPServer("OpsSentinel Tools")
DEFAULT_DOCKER_CONTAINER_NAME = "opssentinel-checkout"
ROLLBACK_APPROVAL_TTL_SECONDS = 300
APPROVAL_SECRET_ENV = "OPSSENTINEL_APPROVAL_SECRET"
rollback_plans: dict[str, dict] = {}
rollback_approvals: dict[str, dict] = {}

def get_docker_container_name() -> str:
    container_name = os.getenv("OPSSENTINEL_CONTAINER_NAME")
    return container_name or DEFAULT_DOCKER_CONTAINER_NAME

def fetch_service_health() -> dict:
    """Fetch the health state of the local Checkout API."""

    try:
        with urlopen(SERVICE_HEALTH_URL, timeout=2) as response:
            http_status = response.status

            try:
                body = json.load(response)

            except json.JSONDecodeError as error:
                return {
                    "reachable": True,
                    "http_status": http_status,
                    "error": f"Invalid JSON response: {error.msg}",
                }

            return {
                "reachable": True,
                "http_status": http_status,
                "service": body,
            }

    except HTTPError as error:
        return {
            "reachable": True,
            "http_status": error.code,
            "error": str(error),
        }

    except TimeoutError:
        return {
            "reachable": False,
            "error": "Request timed out",
        }

    except URLError as error:
        return {
            "reachable": False,
            "error": str(error.reason),
        }


def measure_latency(samples: int = 3) -> dict:
    """Measure response latency of the Checkout API."""

    if samples <= 0:
        return {
            "error": "samples must be greater than 0",
        }

    latencies = []
    responses = []

    for _ in range(samples):
        start = time.perf_counter()

        try:
            with urlopen(CHECKOUT_URL, timeout=3) as response:
                http_status = response.status

                try:
                    body = json.load(response)

                except json.JSONDecodeError as error:
                    return {
                        "reachable": True,
                        "http_status": http_status,
                        "error": f"Invalid JSON response: {error.msg}",
                    }

            elapsed_ms = (time.perf_counter() - start) * 1000

            latencies.append(round(elapsed_ms, 2))
            responses.append(body)

        except HTTPError as error:
            return {
                "reachable": True,
                "http_status": error.code,
                "error": str(error),
            }

        except TimeoutError:
            return {
                "reachable": False,
                "error": "Request timed out",
            }

        except URLError as error:
            return {
                "reachable": False,
                "error": str(error.reason),
            }

    return {
        "reachable": True,
        "samples": samples,
        "latencies_ms": latencies,
        "average_latency_ms": round(sum(latencies) / len(latencies), 2),
        "service": responses[-1],
    }

def load_deployment_history() -> dict:
    """Load the synthetic Checkout API deployment history."""

    try:
        with DEPLOYMENT_HISTORY_PATH.open("r", encoding="utf-8") as file:
            deployments = json.load(file)

        return {
            "service": "checkout-api",
            "deployment_count": len(deployments),
            "deployments": deployments,
        }

    except FileNotFoundError:
        return {
            "error": "Deployment history file not found",
        }

    except json.JSONDecodeError as error:
        return {
            "error": f"Invalid deployment history JSON: {error.msg}",
        }

def fetch_service_logs(lines: int = 50) -> dict:
    """Fetch recent logs from the Checkout API Docker container."""

    if lines <= 0:
        return {
            "error": "lines must be greater than 0",
        }
    container_name = get_docker_container_name()
    try:
        result = subprocess.run(
            [
                "docker",
                "logs",
                "--tail",
                str(lines),
                container_name,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
            check=False,
        )

    except FileNotFoundError:
        return {
            "error": "Docker CLI not found",
        }

    except subprocess.TimeoutExpired:
        return {
            "error": "Docker log collection timed out",
        }

    if result.returncode != 0:
        return {
            "error": result.stdout.strip() or "Failed to read container logs",
        }

    return {
        "container": container_name,
        "lines_requested": lines,
        "logs": result.stdout.strip().splitlines(),
    }

def prepare_rollback() -> dict:
    health = fetch_service_health()

    if not health.get("reachable"):
        return {
            "ready": False,
            "error": "Service health is unavailable; rollback cannot be prepared safely.",
        }

    if health.get("http_status") != 200:
        return {
            "ready": False,
            "error": "Service health request did not return HTTP 200.",
        }

    service = health.get("service")

    if not isinstance(service, dict):
        return {
            "ready": False,
            "error": "Service health payload is missing or invalid.",
        }

    if service.get("service") != "checkout-api":
        return {
            "ready": False,
            "error": "Unexpected service identity in health response.",
        }

    current_version = service.get("version")

    if not isinstance(current_version, str) or not current_version.strip():
        return {
            "ready": False,
            "error": "Current service version is unavailable.",
        }

    history = load_deployment_history()
    deployments = history.get("deployments")

    if not isinstance(deployments, list):
        return {
            "ready": False,
            "error": history.get(
                "error",
                "Deployment history is unavailable.",
            ),
        }

    healthy_deployments = [
        deployment
        for deployment in deployments
        if deployment.get("status") == "healthy"
    ]

    if not healthy_deployments:
        return {
            "ready": False,
            "error": "No known healthy deployment is available for rollback.",
        }

    target = max(
        healthy_deployments,
        key=lambda deployment: deployment.get("deployed_at", ""),
    )

    target_version = target.get("version")

    if current_version == target_version:
        return {
            "ready": False,
            "rollback_needed": False,
            "current_version": current_version,
            "message": "Service is already running the latest known healthy version.",
        }
    plan_id = secrets.token_urlsafe(16)

    rollback_plans[plan_id] = {
        "service": service.get("service"),
        "current_version": current_version,
        "target_version": target_version,
        "target_deployment_id": target.get("deployment_id"),
        "created_at": time.time(),
    }
    return {
        "ready": True,
        "rollback_needed": True,
        "plan_id": plan_id,
        "service": service.get("service"),
        "current_version": current_version,
        "target_version": target_version,
        "target_deployment_id": target.get("deployment_id"),
        "risk": (
            "Rollback will recreate the checkout-api container and may cause "
            "a brief service interruption."
        ),
        "requires_human_approval": True,
        "next_action": "execute_rollback",
    }

def get_approval_secret() -> bytes:
    secret = os.getenv(APPROVAL_SECRET_ENV)

    if not secret:
        raise RuntimeError(
            f"{APPROVAL_SECRET_ENV} is not configured."
        )

    return secret.encode("utf-8")

def sign_rollback_approval_token(plan_id: str) -> str:
    expires_at = int(time.time()) + ROLLBACK_APPROVAL_TTL_SECONDS
    nonce = secrets.token_urlsafe(16)

    message = f"{plan_id}:{expires_at}:{nonce}".encode("utf-8")

    signature = hmac.new(
        get_approval_secret(),
        message,
        hashlib.sha256,
    ).hexdigest()

    return f"{expires_at}.{nonce}.{signature}"


def create_rollback_approval_token(plan_id: str) -> str:
    if plan_id not in rollback_plans:
        raise ValueError("Unknown rollback plan.")

    approval_token = sign_rollback_approval_token(plan_id)

    expires_at = int(approval_token.split(".", 1)[0])

    rollback_approvals[approval_token] = {
        "plan_id": plan_id,
        "expires_at": expires_at,
        "used": False,
    }

    return approval_token

def validate_rollback_approval(
    plan_id: str,
    approval_token: str,
) -> dict:
    approval = rollback_approvals.get(approval_token)

    if approval and approval.get("used"):
        return {
            "valid": False,
            "error": "Approval token has already been used.",
        }

    try:
        expires_text, nonce, supplied_signature = approval_token.split(".", 2)
        expires_at = int(expires_text)
    except (ValueError, TypeError):
        return {
            "valid": False,
            "error": "Malformed approval token.",
        }

    if time.time() > expires_at:
        return {
            "valid": False,
            "error": "Approval token has expired.",
        }

    message = f"{plan_id}:{expires_at}:{nonce}".encode("utf-8")

    expected_signature = hmac.new(
        get_approval_secret(),
        message,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        supplied_signature,
        expected_signature,
    ):
        return {
            "valid": False,
            "error": "Approval token signature is invalid.",
        }

    return {
        "valid": True,
        "plan_id": plan_id,
        "expires_at": expires_at,
    }

def execute_rollback(
    plan_id: str,
    approval_token: str,
    target_version: str,
) -> dict:
    plan = rollback_plans.get(plan_id)

    if plan is None:
        return {
            "executed": False,
            "error": "Unknown rollback plan.",
        }

    approval = validate_rollback_approval(
        plan_id,
        approval_token,
    )

    if not approval.get("valid"):
        return {
            "executed": False,
            "error": approval.get(
                "error",
                "Rollback approval is invalid.",
            ),
        }

    expected_target = plan.get("target_version")

    if target_version != expected_target:
        return {
            "executed": False,
            "error": (
                f"Requested rollback target {target_version!r} does not match "
                f"the approved plan target {expected_target!r}."
            ),
        }

    health = fetch_service_health()
    service = health.get("service")

    if (
        not health.get("reachable")
        or health.get("http_status") != 200
        or not isinstance(service, dict)
    ):
        return {
            "executed": False,
            "error": (
                "Current service state could not be verified before rollback."
            ),
        }

    if service.get("service") != plan.get("service"):
        return {
            "executed": False,
            "error": "Service identity no longer matches the approved plan.",
        }

    current_version = service.get("version")

    if current_version != plan.get("current_version"):
        return {
            "executed": False,
            "error": (
                "Service state changed after rollback preparation; "
                "a new plan and approval are required."
            ),
        }

    rollback_approvals[approval_token] = {
    "plan_id": plan_id,
    "expires_at": approval.get("expires_at"),
    "used": True,
    }
    environment = os.environ.copy()
    environment["SERVICE_VERSION"] = target_version
    environment["DEGRADED"] = "false"

    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--file",
                str(DEFAULT_COMPOSE_FILE),
                "up",
                "-d",
                "--force-recreate",
                "--no-build",
                "checkout-api",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
            check=False,
            env=environment,
        )

    except FileNotFoundError:
        return {
            "executed": False,
            "error": "Docker CLI not found.",
        }

    except subprocess.TimeoutExpired:
        post_timeout_health = fetch_service_health()
        service = post_timeout_health.get("service")

        observed_version = (
            service.get("version")
            if isinstance(service, dict)
            else None
        )

        if (
            post_timeout_health.get("reachable")
            and post_timeout_health.get("http_status") == 200
            and observed_version == target_version
        ):
            return {
                "executed": True,
                "outcome": "succeeded_after_timeout",
                "service": plan.get("service"),
                "previous_version": plan.get("current_version"),
                "target_version": target_version,
                "observed_version": observed_version,
                "verification_required": True,
                "message": (
                    "Rollback command timed out, but the target version "
                    "is now running."
                ),
            }

        return {
            "executed": None,
            "outcome": "indeterminate",
            "target_version": target_version,
            "observed_version": observed_version,
            "verification_required": True,
            "error": (
                "Rollback command timed out and the resulting service "
                "state could not be confirmed."
            ),
        }

    if result.returncode != 0:
        return {
            "executed": False,
            "error": result.stdout.strip(),
        }

    return {
        "executed": True,
        "service": plan.get("service"),
        "previous_version": plan.get("current_version"),
        "target_version": target_version,
        "target_deployment_id": plan.get("target_deployment_id"),
        "verification_required": True,
        "next_action": (
            "Verify service health and checkout latency before declaring recovery."
        ),
        "output": result.stdout.strip(),
    }

@mcp.tool()
def get_service_health() -> dict:
    """Check whether the local Checkout API is reachable and healthy."""

    return fetch_service_health()


@mcp.tool()
def measure_checkout_latency() -> dict:
    """Measure the current response latency of the Checkout API."""

    return measure_latency()

@mcp.tool()
def get_deployment_history() -> dict:
    """Return recent deployment history for the Checkout API."""

    return load_deployment_history()

@mcp.tool()
def get_service_logs() -> dict:
    """Return recent runtime logs from the Checkout API container."""

    return fetch_service_logs()

@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
    )
)
def prepare_service_rollback() -> dict:
    """Prepare a safe rollback plan without changing the running service."""
    return prepare_rollback()

@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=True,
    )
)
def execute_service_rollback(
    plan_id: str,
    approval_token: str,
    target_version: str,
) -> dict:
    """Execute an approved rollback for the Checkout API."""
    return execute_rollback(
        plan_id,
        approval_token,
        target_version,
    )

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8001,
        stateless_http=True,
        json_response=True,
    )