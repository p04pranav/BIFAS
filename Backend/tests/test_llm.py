import json
import time
from types import SimpleNamespace

import pytest
from google.genai.errors import ClientError, ServerError
from pydantic import BaseModel

import config
import llm
from conftest import fake_response


class Item(BaseModel):
    name: str


def _quota_error(per_day=True):
    quota = "GenerateRequestsPerDayPerProjectPerModel" if per_day else "GenerateRequestsPerMinutePerProjectPerModel"
    return ClientError(429, {"error": {"code": 429, "message": f"quotaId: {quota}", "status": "RESOURCE_EXHAUSTED"}})


class FakeModels:
    """Returns (or raises) queued outcomes and records which model each call used."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def fake_models(monkeypatch):
    def install(*outcomes):
        models = FakeModels(*outcomes)
        monkeypatch.setattr(llm, "client", SimpleNamespace(models=models))
        return models
    return install


def test_extract_text_ignores_thoughts():
    assert llm.extract_text(fake_response(text="answer", thought="thinking...")) == "answer"
    assert llm.extract_text(fake_response(thought="only thinking")) == ""


def test_thought_only_response_is_retried_with_bigger_budget(fake_models):
    models = fake_models(
        fake_response(thought="* Query: ...", finish_reason="MAX_TOKENS"),
        fake_response(text="STATUS: APPROVED"),
    )
    result = llm.generate("audit", max_tokens=256)
    assert result.text == "STATUS: APPROVED"
    assert [c["config"].max_output_tokens for c in models.calls] == [256, 512]


def test_thoughts_never_returned_even_after_retry(fake_models):
    fake_models(fake_response(thought="a"), fake_response(thought="b"))
    assert llm.generate("x", max_tokens=100).text == ""


def test_primary_uses_thinking_level_and_schema(fake_models):
    models = fake_models(fake_response(text='[{"name": "a"}]', parsed=[Item(name="a")]))
    result = llm.generate("x", max_tokens=100, schema=list[Item], thinking="minimal")
    cfg = models.calls[0]["config"]
    assert models.calls[0]["model"] == config.PRIMARY_MODEL
    assert cfg.thinking_config.thinking_level.lower() == "minimal"
    assert cfg.response_mime_type == "application/json"
    assert result.parsed == [Item(name="a")] and result.fallback is False


def test_daily_429_switches_to_fallback_for_the_day(fake_models):
    models = fake_models(_quota_error(per_day=True), fake_response(text='{"name": "b"}'), fake_response(text="next"))
    result = llm.generate("x", max_tokens=100, schema=Item)
    assert result.model == config.FALLBACK_MODEL and result.fallback
    # Schema is described in the prompt and parsed from text for the fallback.
    assert "JSON schema" in models.calls[1]["contents"]
    assert result.parsed == Item(name="b")
    assert llm.daily_counter.used() == llm.daily_counter.limit
    # Later calls skip the primary entirely.
    assert llm.generate("y", max_tokens=100).model == config.FALLBACK_MODEL
    assert llm.usage_snapshot()["fallback_active"] is True


def test_per_minute_429_falls_back_only_briefly(fake_models):
    fake_models(_quota_error(per_day=False), fake_response(text="ok"))
    result = llm.generate("x", max_tokens=100)
    assert result.fallback
    assert llm._fallback_until <= time.time() + llm.PER_MINUTE_BACKOFF_SECONDS + 1
    assert llm.daily_counter.used() < llm.daily_counter.limit


def test_daily_cap_reached_uses_fallback_without_calling_primary(fake_models, monkeypatch):
    monkeypatch.setattr(llm, "daily_counter", llm.DailyCounter(0, llm.daily_counter.path))
    models = fake_models(fake_response(text="ok"))
    assert llm.generate("x", max_tokens=100).model == config.FALLBACK_MODEL
    assert [c["model"] for c in models.calls] == [config.FALLBACK_MODEL]


def test_server_errors_are_retried_then_raised(fake_models):
    err = ServerError(500, {"error": {"code": 500, "message": "internal", "status": "INTERNAL"}})
    fake_models(err, fake_response(text="ok"))
    assert llm.generate("x", max_tokens=100).text == "ok"

    fake_models(err, err, err)
    with pytest.raises(ServerError):
        llm.generate("x", max_tokens=100)


def test_other_client_errors_propagate(fake_models):
    fake_models(ClientError(400, {"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}}))
    with pytest.raises(ClientError):
        llm.generate("x", max_tokens=100)


def test_daily_counter_persists_and_resets(tmp_path, monkeypatch):
    path = str(tmp_path / "u.json")
    counter = llm.DailyCounter(2, path)
    assert counter.try_acquire() and counter.try_acquire() and not counter.try_acquire()
    assert llm.DailyCounter(2, path).used() == 2
    monkeypatch.setattr(llm.DailyCounter, "_today", staticmethod(lambda: "2999-01-01"))
    assert counter.used() == 0


def test_rate_limiter_spaces_calls(monkeypatch):
    clock = {"now": 1000.0}
    sleeps = []
    monkeypatch.setattr(llm.time, "time", lambda: clock["now"])
    monkeypatch.setattr(llm.time, "sleep", lambda s: (sleeps.append(s), clock.__setitem__("now", clock["now"] + s)))
    limiter = llm.RateLimiter(15)
    limiter.wait()
    limiter.wait()
    assert sleeps == [pytest.approx(4.0)]


@pytest.mark.parametrize("raw, expected", [
    ('[{"a": 1}]', [{"a": 1}]),
    ('text ```json\n[{"a": 2}]\n``` more', [{"a": 2}]),
    ('blah [{"a": 3}] blah', [{"a": 3}]),
    ('{"a": 4} trailing', {"a": 4}),
    ("", None),
    ("no json here", None),
])
def test_extract_json_from_response(raw, expected):
    assert llm.extract_json_from_response(raw) == expected


def test_usage_file_lives_in_memory_dir():
    import config
    assert llm.USAGE_FILE == str(config.MEMORY_DIR / "usage.json")


def test_daily_counter_creates_missing_folder(tmp_path):
    path = tmp_path / "Memory" / "usage.json"
    counter = llm.DailyCounter(5, str(path))
    assert counter.try_acquire()
    assert json.loads(path.read_text())["count"] == 1


def test_legacy_usage_file_is_migrated_once(tmp_path):
    legacy, target = tmp_path / ".bifas_usage.json", tmp_path / "Memory" / "usage.json"
    legacy.write_text('{"day": "2026-09-27", "count": 42}')
    llm.migrate_legacy_usage(str(legacy), str(target))
    assert not legacy.exists() and json.loads(target.read_text())["count"] == 42
    # A second stray legacy file never overwrites the newer Memory/ copy.
    legacy.write_text('{"day": "2026-09-27", "count": 1}')
    llm.migrate_legacy_usage(str(legacy), str(target))
    assert not legacy.exists() and json.loads(target.read_text())["count"] == 42
