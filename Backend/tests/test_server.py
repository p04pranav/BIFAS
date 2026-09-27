import json

import pytest
from fastapi.testclient import TestClient

import server


def parse_sse(text):
    """Return [(event, data)] from an SSE body, skipping keep-alive comments."""
    events = []
    for block in text.strip().split("\n\n"):
        event, data = "message", None
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        if data is not None:
            events.append((event, data))
    return events


@pytest.fixture
def client():
    return TestClient(server.app)


def fake_pipeline(query, depth, on_event=None):
    on_event("phase", {"name": "data"})
    on_event("data", {"domains": ["stocks"], "tickers": {"stocks": ["NVDA"]}})
    on_event("tasks", {"agents": [{"name": "NVDA_Tech", "task": "t", "domain": "stocks"}]})
    on_event("agent", {"name": "NVDA_Tech", "status": "done", "text": "Price $225.07", "model": "m"})
    on_event("report", {"markdown": "# Report"})
    on_event("audit", {"status": "STATUS: APPROVED — ok"})
    return {
        "tasks": [{"agent_name": "NVDA_Tech", "task": "t", "market_data": "BIG CONTEXT"}],
        "final_report": "# Report", "audit_status": "STATUS: APPROVED — ok", "execution_time": 1.0,
    }


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_meta(client):
    meta = client.get("/api/meta").json()
    assert set(meta["depths"]) == {"Quick", "Standard", "Deep"}
    assert {"used", "limit", "primary_model", "fallback_active"} <= set(meta["usage"])
    assert len(meta["examples"]) == 4


@pytest.mark.parametrize("params, message", [
    ({"query": "   ", "depth": "Quick"}, "Enter a query"),
    ({"query": "NVDA", "depth": "Huge"}, "Depth must be one of"),
])
def test_analyze_validation(client, params, message):
    res = client.get("/api/analyze", params=params)
    assert res.status_code == 422
    assert message in res.json()["detail"]


def test_analyze_rejects_overlong_query(client):
    res = client.get("/api/analyze", params={"query": "x" * (server.MAX_QUERY_CHARS + 1), "depth": "Quick"})
    assert res.status_code == 422


def test_analyze_streams_events_in_order(client, monkeypatch):
    monkeypatch.setattr(server, "run_bifas_pipeline", fake_pipeline)
    res = client.get("/api/analyze", params={"query": "Analyze NVDA", "depth": "Quick"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(res.text)
    assert [e for e, _ in events] == ["phase", "data", "tasks", "agent", "report", "audit", "done"]
    done = events[-1][1]
    assert done["result"]["audit_status"].startswith("STATUS: APPROVED")
    assert "market_data" not in done["result"]["tasks"][0]  # bulky context is stripped
    assert "used" in done["usage"]


def test_analyze_reports_pipeline_errors(client, monkeypatch):
    def broken(query, depth, on_event=None):
        raise RuntimeError("model down")
    monkeypatch.setattr(server, "run_bifas_pipeline", broken)
    events = parse_sse(client.get("/api/analyze", params={"query": "NVDA", "depth": "Quick"}).text)
    assert events == [("error", {"message": "Analysis failed: model down"})]


def test_busy_server_returns_429_and_frees_slots(client, monkeypatch):
    monkeypatch.setattr(server, "run_bifas_pipeline", fake_pipeline)
    held = [server._run_slots.acquire(blocking=False) for _ in range(server.MAX_CONCURRENT_RUNS)]
    try:
        assert all(held)
        res = client.get("/api/analyze", params={"query": "NVDA", "depth": "Quick"})
        assert res.status_code == 429
    finally:
        for _ in held:
            server._run_slots.release()
    # Slots are released after each run, so later runs are accepted.
    for _ in range(server.MAX_CONCURRENT_RUNS + 1):
        assert client.get("/api/analyze", params={"query": "NVDA", "depth": "Quick"}).status_code == 200


def test_frontend_is_served(client):
    if not server.FRONTEND_DIR.is_dir():
        pytest.skip("Frontend/ not present")
    res = client.get("/")
    assert res.status_code == 200 and "BIFAS" in res.text
    assert client.get("/app.js").status_code == 200
