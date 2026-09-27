import os
import sys
import time
from types import SimpleNamespace

import pytest

# Tests never reach the network: a placeholder key lets config.py build the client.
os.environ.setdefault("GOOGLE_API_KEY", "test-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llm  # noqa: E402
import memory  # noqa: E402


def fake_response(text="", thought=None, finish_reason="STOP", parsed=None):
    """Mimic a google-genai GenerateContentResponse."""
    parts = []
    if thought:
        parts.append(SimpleNamespace(text=thought, thought=True))
    if text:
        parts.append(SimpleNamespace(text=text, thought=False))
    candidate = SimpleNamespace(content=SimpleNamespace(parts=parts), finish_reason=finish_reason)
    return SimpleNamespace(candidates=[candidate], parsed=parsed)


@pytest.fixture(autouse=True)
def isolated_llm(tmp_path, monkeypatch):
    """Fresh quota counter, no fallback, no rate-limit or retry sleeps."""
    monkeypatch.setattr(llm, "daily_counter", llm.DailyCounter(500, str(tmp_path / "usage.json")))
    monkeypatch.setattr(llm, "_fallback_until", 0.0)
    monkeypatch.setattr(llm, "_limiter", lambda model: SimpleNamespace(wait=lambda: None))
    # Replace llm's view of the time module only; the real time.sleep stays intact.
    monkeypatch.setattr(llm, "time", SimpleNamespace(time=time.time, sleep=lambda s: None))
    yield


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch):
    """Sessions are written to a temp folder, never the real Memory/."""
    monkeypatch.setattr(memory, "ROOT", tmp_path / "Memory")
    yield tmp_path / "Memory"
