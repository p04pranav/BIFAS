"""Sessions and their briefings, persisted as JSON files in Memory/sessions/.

One file per session: Memory/sessions/<session_id>.json holding the session's
title, timestamps and its briefings in order. Writes are atomic and each
session has a lock, so concurrent runs can't corrupt a file.
"""
import datetime
import json
import os
import re
import secrets
import threading
from pathlib import Path

import config

ROOT = config.MEMORY_DIR
MAX_SESSIONS = int(os.getenv("BIFAS_MAX_SESSIONS", "100"))
MAX_BRIEFINGS_PER_SESSION = 50
MAX_TITLE_CHARS = 80
AUTO_TITLE_CHARS = 60
DEFAULT_TITLE = "New session"

# IDs are generated here and validated before touching the filesystem (no path traversal).
ID_PATTERN = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")

_locks = {}
_locks_guard = threading.Lock()


class NotFound(Exception):
    """No session (or briefing) with that id."""


def _sessions_dir():
    return Path(ROOT) / "sessions"


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")


def new_id():
    return f"{datetime.datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"


def _path(session_id):
    if not isinstance(session_id, str) or not ID_PATTERN.match(session_id):
        raise NotFound(session_id)
    return _sessions_dir() / f"{session_id}.json"


def _lock(session_id):
    with _locks_guard:
        return _locks.setdefault(session_id, threading.Lock())


def _read(session_id):
    path = _path(session_id)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise NotFound(session_id)
    except (OSError, ValueError):
        raise NotFound(session_id)  # unreadable or corrupt files are treated as missing
    if not isinstance(data, dict) or data.get("id") != session_id:
        raise NotFound(session_id)
    return data


def _write(session):
    path = _path(session["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _clean_title(title):
    title = " ".join(str(title or "").split())
    if not title:
        raise ValueError("Enter a session name.")
    if len(title) > MAX_TITLE_CHARS:
        raise ValueError(f"Session names can be up to {MAX_TITLE_CHARS} characters.")
    return title


def _auto_title(query):
    text = " ".join(query.split())
    return text if len(text) <= AUTO_TITLE_CHARS else text[:AUTO_TITLE_CHARS - 1].rstrip() + "…"


def _verdict(audit_status):
    text = str(audit_status or "")
    for word in ("APPROVED", "REJECTED", "UNVERIFIED"):
        if word in text:
            return word.lower()
    return "none"


def summarize(session):
    briefings = session.get("briefings", [])
    last = briefings[-1] if briefings else {}
    return {
        "id": session["id"],
        "title": session.get("title", DEFAULT_TITLE),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
        "briefing_count": len(briefings),
        "last_query": last.get("query"),
        "last_verdict": _verdict(last.get("audit_status")) if last else None,
    }


def create_session(title=None):
    now = _now()
    session = {
        "id": new_id(),
        "title": _clean_title(title) if title else DEFAULT_TITLE,
        "auto_title": not title,
        "created_at": now,
        "updated_at": now,
        "briefings": [],
    }
    _write(session)
    _prune()
    return session


def list_sessions():
    """Summaries of all readable sessions, most recently updated first."""
    directory = _sessions_dir()
    if not directory.is_dir():
        return []
    summaries = []
    for path in directory.glob("*.json"):
        try:
            summaries.append(summarize(_read(path.stem)))
        except NotFound:
            continue
    return sorted(summaries, key=lambda s: s.get("updated_at") or "", reverse=True)


def get_session(session_id):
    return _read(session_id)


def rename_session(session_id, title):
    title = _clean_title(title)
    with _lock(session_id):
        session = _read(session_id)
        session["title"] = title
        session["auto_title"] = False
        session["updated_at"] = _now()
        _write(session)
    return session


def delete_session(session_id):
    path = _path(session_id)
    with _lock(session_id):
        try:
            path.unlink()
        except FileNotFoundError:
            raise NotFound(session_id)


def append_briefing(session_id, briefing):
    """Add a finished briefing to a session and return it with its new id."""
    with _lock(session_id):
        session = _read(session_id)
        record = {"id": new_id(), "created_at": _now(), **briefing}
        session["briefings"] = (session.get("briefings", []) + [record])[-MAX_BRIEFINGS_PER_SESSION:]
        if session.get("auto_title", False) and briefing.get("query"):
            session["title"] = _auto_title(session["briefings"][0]["query"])
        session["updated_at"] = record["created_at"]
        _write(session)
    return record


def delete_briefing(session_id, briefing_id):
    with _lock(session_id):
        session = _read(session_id)
        remaining = [b for b in session.get("briefings", []) if b.get("id") != briefing_id]
        if len(remaining) == len(session.get("briefings", [])):
            raise NotFound(briefing_id)
        session["briefings"] = remaining
        session["updated_at"] = _now()
        _write(session)
    return session


def delete_if_empty(session_id):
    """Remove a session that never received a briefing (e.g. its first run was cancelled)."""
    try:
        with _lock(session_id):
            if not _read(session_id).get("briefings"):
                _path(session_id).unlink(missing_ok=True)
    except NotFound:
        pass


def _prune():
    sessions = list_sessions()
    for summary in sessions[MAX_SESSIONS:]:
        try:
            delete_session(summary["id"])
        except NotFound:
            pass


def briefing_record(query, depth, result, used_context=False):
    """What to store for a finished pipeline run."""
    texts = {r["next_agent"]: r.get("contribution_full") or r.get("contribution", "") for r in result.get("rounds", [])}
    agents = []
    for task in result.get("tasks", []):
        name = task.get("agent_name")
        agents.append({
            "name": name,
            "task": task.get("task", ""),
            "status": "done" if name in texts else "not finished",
            "text": texts.get(name, ""),
        })
    return {
        "query": query,
        "depth": depth,
        "used_context": used_context,
        "final_report": result.get("final_report", ""),
        "audit_status": result.get("audit_status", ""),
        "agents": agents,
        "market_snapshot": result.get("market_snapshot", []),
        "domains": result.get("domains", []),
        "tickers": result.get("tickers", {}),
        "execution_time": result.get("execution_time", 0),
        "models_used": result.get("models_used", []),
        "guardrail_triggered": result.get("guardrail_triggered"),
    }
