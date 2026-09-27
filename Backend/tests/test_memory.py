import json

import pytest

import memory


def test_create_list_get_rename_delete():
    a = memory.create_session()
    b = memory.create_session("Crypto week")
    assert a["title"] == "New session" and b["title"] == "Crypto week"
    assert memory.get_session(a["id"])["briefings"] == []
    memory.rename_session(a["id"], "Gold macro")
    titles = [s["title"] for s in memory.list_sessions()]
    assert titles[0] == "Gold macro"  # most recently updated first
    memory.delete_session(b["id"])
    assert [s["id"] for s in memory.list_sessions()] == [a["id"]]
    with pytest.raises(memory.NotFound):
        memory.get_session(b["id"])


def test_first_briefing_names_an_unnamed_session():
    s = memory.create_session()
    memory.append_briefing(s["id"], {"query": "Gold and crude oil price analysis with dollar correlation today please"})
    memory.append_briefing(s["id"], {"query": "What about silver?"})
    session = memory.get_session(s["id"])
    assert session["title"].startswith("Gold and crude oil") and len(session["title"]) <= memory.AUTO_TITLE_CHARS
    summary = memory.summarize(session)
    assert summary["briefing_count"] == 2 and summary["last_query"] == "What about silver?"


def test_briefings_are_capped_per_session(monkeypatch):
    monkeypatch.setattr(memory, "MAX_BRIEFINGS_PER_SESSION", 3)
    s = memory.create_session("Cap")
    for i in range(5):
        memory.append_briefing(s["id"], {"query": f"q{i}"})
    assert [b["query"] for b in memory.get_session(s["id"])["briefings"]] == ["q2", "q3", "q4"]


def test_oldest_sessions_are_pruned(monkeypatch):
    monkeypatch.setattr(memory, "MAX_SESSIONS", 2)
    first = memory.create_session("one")
    memory.create_session("two")
    memory.create_session("three")
    ids = [s["id"] for s in memory.list_sessions()]
    assert len(ids) == 2 and first["id"] not in ids


def test_corrupt_files_are_skipped(isolated_memory):
    good = memory.create_session("good")
    (isolated_memory / "sessions" / "20260101-000000-abcdef.json").write_text("{not json")
    (isolated_memory / "sessions" / "notes.json").write_text("{}")
    assert [s["id"] for s in memory.list_sessions()] == [good["id"]]
    with pytest.raises(memory.NotFound):
        memory.get_session("20260101-000000-abcdef")


@pytest.mark.parametrize("bad", ["../x", "", None, "20260927-173012-ABCDEF", "20260927-173012-a1b2c3/../../x"])
def test_invalid_ids_never_touch_the_filesystem(bad):
    with pytest.raises(memory.NotFound):
        memory.get_session(bad)
    with pytest.raises(memory.NotFound):
        memory.delete_session(bad)


def test_title_validation():
    s = memory.create_session()
    with pytest.raises(ValueError):
        memory.rename_session(s["id"], "   ")
    with pytest.raises(ValueError):
        memory.rename_session(s["id"], "x" * 81)


def test_writes_are_atomic_json(isolated_memory):
    s = memory.create_session("atomic")
    memory.append_briefing(s["id"], {"query": "q", "final_report": "Price $4,321.20"})
    files = list((isolated_memory / "sessions").iterdir())
    assert [f.suffix for f in files] == [".json"]  # no leftover temp files
    assert json.loads(files[0].read_text())["briefings"][0]["final_report"] == "Price $4,321.20"


def test_delete_if_empty_keeps_sessions_with_briefings():
    empty, used = memory.create_session(), memory.create_session()
    memory.append_briefing(used["id"], {"query": "q"})
    memory.delete_if_empty(empty["id"])
    memory.delete_if_empty(used["id"])
    assert [s["id"] for s in memory.list_sessions()] == [used["id"]]


def test_briefing_record_from_pipeline_result():
    result = {
        "tasks": [{"agent_name": "Gold", "task": "t1"}, {"agent_name": "Oil", "task": "t2"}],
        "rounds": [{"next_agent": "Gold", "contribution": "short", "contribution_full": "full text"}],
        "final_report": "# R", "audit_status": "STATUS: APPROVED — ok", "market_snapshot": [{"symbol": "GC=F"}],
        "domains": ["commodities"], "tickers": {"commodities": ["GC=F"]}, "execution_time": 22.5,
        "models_used": ["m"], "guardrail_triggered": None,
    }
    rec = memory.briefing_record("Gold?", "Quick", result, used_context=True)
    assert rec["agents"] == [
        {"name": "Gold", "task": "t1", "status": "done", "text": "full text"},
        {"name": "Oil", "task": "t2", "status": "not finished", "text": ""},
    ]
    assert rec["used_context"] is True and rec["tickers"] == {"commodities": ["GC=F"]}


def _briefing(query, report, tickers=None, verdict="STATUS: APPROVED — ok"):
    return {"query": query, "final_report": report, "audit_status": verdict,
            "tickers": tickers or {}, "domains": list(tickers or {})}


def test_build_context_uses_last_three_summaries():
    s = memory.create_session()
    for i in range(5):
        memory.append_briefing(s["id"], _briefing(
            f"Question {i}", f"# Title\n\n## Executive Summary\n**Point {i}** holds.\n\n## Key Findings\n- detail {i}"))
    context = memory.build_context(memory.get_session(s["id"]))
    assert "Question 0" not in context and "Question 1" not in context
    for i in (2, 3, 4):
        assert f"Question {i}" in context and f"Point {i} holds." in context
    assert "detail" not in context and "**" not in context
    assert memory.build_context({"briefings": []}) == ""


def test_build_context_is_capped():
    s = memory.create_session()
    for i in range(3):
        memory.append_briefing(s["id"], _briefing(f"Q{i}", "## Executive Summary\n" + "word " * 500))
    context = memory.build_context(memory.get_session(s["id"]))
    assert len(context) <= memory.CONTEXT_TOTAL_CHARS
    assert all(len(line) <= memory.CONTEXT_SUMMARY_CHARS + 20 for line in context.splitlines())


def test_last_assets():
    s = memory.create_session()
    assert memory.last_assets(memory.get_session(s["id"])) is None
    memory.append_briefing(s["id"], _briefing("Gold?", "r", {"commodities": ["GC=F"]}))
    assert memory.last_assets(memory.get_session(s["id"])) == {"domains": ["commodities"], "tickers": {"commodities": ["GC=F"]}}
