import time

import pytest

import engine
from llm import LLMResult


def _result(text="", parsed=None, model="gemini-3.5-flash-lite"):
    return LLMResult(text=text, parsed=parsed, model=model, finish_reason="STOP", fallback=False)


def make_fake_generate(agent_names, slow_agent=None, verdict=("APPROVED", "covers the query")):
    def fake_generate(prompt, *, max_tokens, schema=None, thinking="low"):
        if schema is engine.Verdict:
            return _result(parsed=engine.Verdict(status=verdict[0], reason=verdict[1]))
        if schema is not None:
            return _result(parsed=[engine.Task(agent_name=n, task=f"analyze {n}", domain="stocks") for n in agent_names])
        if "BIFAS Report Synthesizer" in prompt:
            return _result(text="# Report\nSynthesized.")
        if slow_agent and f"You are {slow_agent}," in prompt:
            time.sleep(5)
        return _result(text=f"analysis from prompt with {len(prompt)} chars")
    return fake_generate


@pytest.fixture
def offline_pipeline(monkeypatch):
    monkeypatch.setattr(engine, "fetch_all_data", lambda domains, tickers: {})

    def install(**kwargs):
        monkeypatch.setattr(engine, "generate", make_fake_generate(**kwargs))
    return install


def test_full_pipeline_with_mocked_llm(offline_pipeline):
    offline_pipeline(agent_names=["NVDA_Technical", "AAPL_Valuation", "Macro"])
    result = engine.run_bifas_pipeline("Analyze NVDA and AAPL stock", depth="Quick")
    assert [a["name"] for a in result["agent_squad"]] == ["NVDA_Technical", "AAPL_Valuation", "Macro"]
    assert len(result["rounds"]) == 3
    assert all(r["contribution_full"] for r in result["rounds"])
    assert result["final_report"] == "# Report\nSynthesized."
    assert result["audit_status"] == "STATUS: APPROVED — covers the query"
    assert result["guardrail_triggered"] is None
    assert result["models_used"] == ["gemini-3.5-flash-lite"] and result["fallback_used"] is False


def test_rejected_verdict_is_reported(offline_pipeline):
    offline_pipeline(agent_names=["A"], verdict=("REJECTED", "off topic"))
    result = engine.run_bifas_pipeline("Analyze NVDA", depth="Quick")
    assert result["audit_status"].startswith("STATUS: REJECTED")


def test_depth_caps_agent_count_and_dedupes(offline_pipeline):
    offline_pipeline(agent_names=["A", "A", "B", "C", "D"])
    result = engine.run_bifas_pipeline("Analyze NVDA", depth="Quick")
    assert [a["name"] for a in result["agent_squad"]] == ["A", "B"]


def test_slow_agent_does_not_break_hard_timeout(offline_pipeline, monkeypatch):
    offline_pipeline(agent_names=["Fast_1", "Slow", "Fast_2"], slow_agent="Slow")
    monkeypatch.setattr(engine, "TIMEOUT_SECONDS", 3)
    monkeypatch.setattr(engine, "FINISH_RESERVE_SECONDS", 1)
    start = time.time()
    result = engine.run_bifas_pipeline("Analyze NVDA", depth="Quick")
    assert time.time() - start < 3
    assert "Slow" in result["guardrail_triggered"]
    assert {r["next_agent"] for r in result["rounds"]} == {"Fast_1", "Fast_2"}
    assert result["audit_status"].startswith("STATUS: APPROVED")


def test_failed_agents_reported(offline_pipeline, monkeypatch):
    offline_pipeline(agent_names=["Good", "Bad"])
    real = engine.generate

    def flaky(prompt, **kw):
        if "You are Bad," in prompt:
            raise RuntimeError("boom")
        return real(prompt, **kw)
    monkeypatch.setattr(engine, "generate", flaky)
    result = engine.run_bifas_pipeline("Analyze NVDA", depth="Standard")
    assert result["guardrail_triggered"] == "Failed agents: Bad"
    assert len(result["rounds"]) == 1


def test_auditor_failure_is_unverified_not_approved(monkeypatch):
    def broken(*a, **kw):
        raise RuntimeError("down")
    monkeypatch.setattr(engine, "generate", broken)
    assert engine.audit_report("report", "query").startswith("STATUS: UNVERIFIED")
