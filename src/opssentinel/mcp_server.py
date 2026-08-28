import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from importlib.resources import files
from mcp.server.mcpserver import MCPServer
import subprocess
import os
SERVICE_HEALTH_URL = "http://127.0.0.1:8000/health"
CHECKOUT_URL = "http://127.0.0.1:8000/checkout"
DEPLOYMENT_HISTORY_PATH = files("opssentinel").joinpath(
    "data",
    "deployments.json",
)
mcp = MCPServer("OpsSentinel Tools")
DEFAULT_DOCKER_CONTAINER_NAME = "opssentinel-checkout"


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
if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8001,
        stateless_http=True,
        json_response=True,
    )