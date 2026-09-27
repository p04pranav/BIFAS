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


def fake_pipeline(query, depth, on_event=None, **kwargs):
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
    def broken(query, depth, on_event=None, **kwargs):
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


def test_preview_reports_assets_and_costs(client):
    body = client.get("/api/preview", params={"query": "Analyze NVDA and gold"}).json()
    assert body["domains"] == ["stocks", "commodities"]
    assert body["named"]["stocks"] == ["NVDA"] and body["named"]["commodities"] == ["GC=F"]
    assert body["estimates"] == {"Quick": 6, "Standard": 9, "Deep": 15}


def test_preview_separates_defaults_from_named_assets(client):
    body = client.get("/api/preview", params={"query": "How is crypto sentiment?"}).json()
    assert body["tickers"]["crypto"] == ["bitcoin", "ethereum"]  # what would be analyzed
    assert body["named"] == {}                                    # nothing was actually named


def test_preview_empty_query(client):
    body = client.get("/api/preview", params={"query": "  "}).json()
    assert body["domains"] == [] and body["estimates"]["Deep"] == 15


def test_client_disconnect_cancels_the_run(client, monkeypatch):
    import threading
    import time
    from starlette.requests import Request
    started, seen_cancel = threading.Event(), threading.Event()

    def slow_pipeline(query, depth, on_event=None, cancel_event=None, **kwargs):
        on_event("phase", {"name": "data"})
        started.set()
        if cancel_event.wait(timeout=10):
            seen_cancel.set()
            return {"cancelled": True}
        return {"cancelled": False}

    async def gone(self):
        # Simulate the browser leaving once the run has started (TestClient can't hang up mid-stream).
        return started.is_set()
    monkeypatch.setattr(server, "run_bifas_pipeline", slow_pipeline)
    monkeypatch.setattr(Request, "is_disconnected", gone)

    res = client.get("/api/analyze", params={"query": "NVDA", "depth": "Quick"})
    assert res.status_code == 200
    assert seen_cancel.wait(5), "pipeline was not told to cancel after the client left"
    assert "event: done" not in res.text  # cancelled runs never report done
    for _ in range(50):  # the run slot is released once the cancelled pipeline returns
        if server._run_slots.acquire(blocking=False):
            server._run_slots.release()
            break
        time.sleep(0.1)
    else:
        raise AssertionError("run slot was not released")
