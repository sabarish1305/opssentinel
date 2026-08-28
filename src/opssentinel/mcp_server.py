import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import time
from mcp.server.mcpserver import MCPServer


SERVICE_HEALTH_URL = "http://127.0.0.1:8000/health"
CHECKOUT_URL = "http://127.0.0.1:8000/checkout"
mcp = MCPServer("OpsSentinel Tools")


def fetch_service_health() -> dict:
    """Fetch the health state of the local Checkout API."""

    try:
        with urlopen(SERVICE_HEALTH_URL, timeout=2) as response:
            body = json.load(response)

            return {
                "reachable": True,
                "http_status": response.status,
                "service": body,
            }

    except HTTPError as error:
        return {
            "reachable": True,
            "http_status": error.code,
            "error": str(error),
        }

    except URLError as error:
        return {
            "reachable": False,
            "error": str(error.reason),
        }

def measure_latency(samples: int = 3) -> dict:
    """Measure response latency of the Checkout API."""

    latencies = []
    responses = []

    for _ in range(samples):
        start = time.perf_counter()

        try:
            with urlopen(CHECKOUT_URL, timeout=3) as response:
                body = json.load(response)

            elapsed_ms = (time.perf_counter() - start) * 1000

            latencies.append(round(elapsed_ms, 2))
            responses.append(body)

        except HTTPError as error:
            return {
                "reachable": True,
                "http_status": error.code,
                "error": str(error),
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
@mcp.tool()
def get_service_health() -> dict:
    """Check whether the local Checkout API is reachable and healthy."""
    
    return fetch_service_health()

@mcp.tool()
def measure_checkout_latency() -> dict:
    """Measure the current response latency of the Checkout API."""

    return measure_latency()
if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8001,
        stateless_http=True,
        json_response=True,
    )