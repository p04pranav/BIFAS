"""BIFAS HTTP API.

Serves the pipeline over REST + Server-Sent Events and, when present, the
static Frontend/ folder, so one process runs the whole app:

    cd Backend && uvicorn server:app --port 5050
"""
import json
import os
import queue
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from bifas_agents import DEPTH_CONFIG
from engine import run_bifas_pipeline
from llm import usage_snapshot

MAX_QUERY_CHARS = 2000
MAX_CONCURRENT_RUNS = int(os.getenv("BIFAS_MAX_CONCURRENT_RUNS", "2"))
KEEPALIVE_SECONDS = 15
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "Frontend"

EXAMPLE_QUERIES = [
    "Analyze NVDA, AAPL, MSFT stock outlook with technicals and valuation",
    "Bitcoin and Ethereum price trends, on-chain metrics, and sentiment",
    "EUR/USD, GBP/USD, USD/JPY forex correlations and macro factors",
    "Gold and crude oil price analysis with dollar correlation",
]

app = FastAPI(title="BIFAS API", version="7.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("BIFAS_CORS_ORIGINS", "*").split(",")],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Each run makes several model calls; cap concurrent runs to stay inside the RPM quota.
_run_slots = threading.BoundedSemaphore(MAX_CONCURRENT_RUNS)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    return {"depths": DEPTH_CONFIG, "usage": usage_snapshot(), "examples": EXAMPLE_QUERIES}


def _public_result(result):
    """The pipeline result without the bulky per-agent market data."""
    tasks = [{k: v for k, v in t.items() if k != "market_data"} for t in result.get("tasks", [])]
    return {**result, "tasks": tasks}


def _sse(event_type, data):
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


@app.get("/api/analyze")
def analyze(
    query: str = Query(..., max_length=MAX_QUERY_CHARS),
    depth: str = Query("Standard"),
):
    """Run the pipeline and stream its progress as Server-Sent Events.

    Events: phase, data, tasks, agent, report, audit, then done (full result
    and updated usage) or error.
    """
    query = query.strip()
    if not query:
        raise HTTPException(422, "Enter a query to analyze.")
    if depth not in DEPTH_CONFIG:
        raise HTTPException(422, f"Depth must be one of: {', '.join(DEPTH_CONFIG)}.")
    if not _run_slots.acquire(blocking=False):
        raise HTTPException(429, "Too many analyses are running. Try again in a minute.")

    events = queue.Queue()

    def worker():
        try:
            result = run_bifas_pipeline(query, depth, on_event=lambda t, d: events.put((t, d)))
            events.put(("done", {"result": _public_result(result), "usage": usage_snapshot()}))
        except Exception as e:
            events.put(("error", {"message": f"Analysis failed: {e}"}))
        finally:
            # The slot is held until the pipeline itself ends, even if the client left.
            _run_slots.release()
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            try:
                item = events.get(timeout=KEEPALIVE_SECONDS)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            if item is None:
                return
            yield _sse(*item)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("BIFAS_HOST", "127.0.0.1"), port=int(os.getenv("BIFAS_PORT", "5050")))
