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