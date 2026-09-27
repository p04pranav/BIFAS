import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED, TimeoutError as FuturesTimeout
from typing import Literal
from pydantic import BaseModel
import config
from llm import generate, extract_json_from_response
from bifas_agents import (
    ORCHESTRATOR_DECOMPOSITION_PROMPT,
    AGENT_TASK_PROMPT,
    ORCHESTRATOR_SYNTHESIS_PROMPT,
    AUDITOR_PROMPT,
    DEPTH_CONFIG
)
from data_fetcher import (
    detect_domains, extract_tickers, fetch_all_data,
    get_ticker_data_for_agent, market_snapshot
)

# Sprint Architecture Constants
TIMEOUT_SECONDS = 300  # 5-minute hard timeout
MAX_AGENTS = 12
MAX_WORKERS = 6
FINISH_RESERVE_SECONDS = 60  # time kept back from agents for synthesis + audit
POLL_SECONDS = 0.2  # how often waits check for cancellation
MAX_ANALYSES_CHARS = 60000


class Verdict(BaseModel):
    status: Literal["APPROVED", "REJECTED"]
    reason: str


class Task(BaseModel):
    agent_name: str
    task: str
    domain: str


class LocalBandSDK:
    """In-memory room/message simulation."""

    def __init__(self):
        self.rooms = {}
        self.room_counter = 0

    def create_room(self, name):
        self.room_counter += 1
        room_id = f"room_{self.room_counter}"
        self.rooms[room_id] = {"name": name, "messages": []}
        return room_id

    def send_message(self, room_id, sender, text, msg_type="contribution"):
        self.rooms[room_id]["messages"].append({
            "sender": sender,
            "text": text,
            "type": msg_type,
            "turn": len(self.rooms[room_id]["messages"])
        })

    def get_room_history(self, room_id):
        return self.rooms[room_id]["messages"]

    def get_history_formatted(self, room_id, max_chars=3000):
        history = self.get_room_history(room_id)
        formatted = []
        total = 0
        for msg in reversed(history):
            prefix = f"[{msg['type'].upper()}]" if msg.get('type') else ""
            entry = f"{prefix} {msg['sender']}: {msg['text'][:500]}"
            if total + len(entry) > max_chars:
                break
            formatted.insert(0, entry)
            total += len(entry)
        return "\n".join(formatted)


band = LocalBandSDK()


class DynamicAgentSquad:
    """Manages dynamically generated agent squad."""

    def __init__(self):
        self.agents = {}

    def add_agent(self, name, prompt):
        self.agents[name] = {"prompt": prompt, "active": True}

    def get_agent(self, name):
        return self.agents.get(name)

    def get_active_agents(self):
        return {k: v for k, v in self.agents.items() if v["active"]}

    def to_list(self):
        return [{"name": k, "prompt": v["prompt"]} for k, v in self.agents.items()]


def generate_tasks(user_query, max_agents):
    """Phase 1: Orchestrator decomposes query into micro-tasks. Returns (tasks, LLMResult)."""
    prompt = (
        ORCHESTRATOR_DECOMPOSITION_PROMPT.format(max_agents=max_agents)
        + f"\n\nDecompose this query into {max_agents} independent micro-tasks:\n\n{user_query}"
    )
    for attempt in range(2):
        response = generate(prompt, max_tokens=4096, schema=list[Task], thinking="low")
        tasks = response.parsed
        if tasks:
            break
    if not tasks:
        raise ValueError(f"Failed to parse tasks: {response.text[:200]}")

    valid_tasks = []
    seen = set()
    for t in tasks[:max_agents]:
        if t.agent_name and t.task and t.agent_name not in seen:
            seen.add(t.agent_name)
            valid_tasks.append(t.model_dump())

    if len(valid_tasks) == 0:
        raise ValueError("No valid tasks generated")

    return valid_tasks, response


def execute_agent_task(agent_name, task, query, market_data="No specific data available."):
    """Phase 2: Single agent executes one task with market data context.

    Returns (name, result, success, model)."""
    prompt = AGENT_TASK_PROMPT.format(
        name=agent_name, task=task, query=query, market_data=market_data
    ) + "\n\nProvide your analysis now."
    try:
        response = generate(prompt, max_tokens=2048, thinking="low")
        if response.text:
            return (agent_name, response.text, True, response.model)
    except Exception:
        pass
    return (agent_name, "[AGENT FAILED]", False, None)


def synthesize_report(analyses, user_query):
    """Phase 3: Orchestrator synthesizes all analyses into final report."""
    analyses_text = "\n\n".join([
        f"### {name}:\n{result}" for name, result in analyses.items()
    ])
    prompt = ORCHESTRATOR_SYNTHESIS_PROMPT.format(
        analyses=analyses_text[:MAX_ANALYSES_CHARS], query=user_query
    ) + (
        "\n\nGenerate the final BIFAS report in markdown."
        "\nCRITICAL: Complete the entire report fully without stopping mid-sentence."
    )
    return generate(prompt, max_tokens=8192, thinking="low").text


def audit_report(report, user_query):
    """Phase 4: Auditor validates the final report. Returns 'STATUS: X — reason'."""
    prompt = AUDITOR_PROMPT.format(query=user_query, report=report)
    try:
        verdict = generate(prompt, max_tokens=512, schema=Verdict, thinking="minimal").parsed
        if verdict:
            return f"STATUS: {verdict.status} — {verdict.reason}"
    except Exception:
        pass
    return "STATUS: UNVERIFIED — auditor unavailable"


class _Cancelled(Exception):
    """The caller asked the run to stop (e.g. the client disconnected)."""


def _check_cancel(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise _Cancelled()


def _run_before(deadline, fn, *args, cancel_event=None):
    """Run fn(*args), giving up (returning None) if it is still running at the deadline.

    Raises _Cancelled as soon as cancel_event is set."""
    if deadline - time.time() <= 0:
        return None
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn, *args)
    try:
        while True:
            _check_cancel(cancel_event)
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            try:
                return future.result(timeout=min(remaining, POLL_SECONDS))
            except FuturesTimeout:
                continue
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _event_emitter(on_event):
    """Wrap an optional progress callback so a failing listener never breaks a run."""
    def emit(event_type, **data):
        if on_event is None:
            return
        try:
            on_event(event_type, data)
        except Exception:
            pass
    return emit


def run_bifas_pipeline(user_query, depth="Standard", on_event=None, cancel_event=None):
    """
    Sprint-based pipeline with parallel execution.
    Hard 5-minute timeout. Agent count controls depth.

    on_event(type, data) is called as the run progresses:
    phase(name) when a phase starts, data(domains, tickers), market(assets), tasks(agents),
    agent(name, status, text, model), report(markdown), audit(status),
    and cancelled() if cancel_event (a threading.Event) is set mid-run. A cancelled
    run stops before its next model call and returns with result["cancelled"] = True.
    """
    emit = _event_emitter(on_event)
    start_time = time.time()
    max_agents = DEPTH_CONFIG[depth]["max_agents"]

    result = {
        "agent_squad": [],
        "tasks": [],
        "rounds": [],
        "final_report": "",
        "audit_status": "",
        "total_messages": 0,
        "guardrail_triggered": None,
        "execution_time": 0,
        "models_used": [],
        "fallback_used": False,
        "market_snapshot": [],
        "cancelled": False,
    }
    models = set()
    guardrails = []
    deadline = start_time + TIMEOUT_SECONDS

    try:
        # PHASE 0: Domain Detection + Data Pre-Fetch
        emit("phase", name="data")
        domains = detect_domains(user_query)
        tickers_map = extract_tickers(user_query, domains)
        market_data = fetch_all_data(domains, tickers_map)
        result["data_sources"] = list(tickers_map.keys())
        emit("data", domains=domains, tickers=tickers_map)
        result["market_snapshot"] = market_snapshot(market_data, domains, tickers_map)
        emit("market", assets=result["market_snapshot"])
        _check_cancel(cancel_event)

        # PHASE 1: Task Decomposition (1 call)
        emit("phase", name="decompose")
        decomposed = _run_before(deadline - FINISH_RESERVE_SECONDS, generate_tasks, user_query, max_agents,
                                 cancel_event=cancel_event)
        if decomposed is None:
            guardrails.append("Timeout during task decomposition")
            result["final_report"] = "No analysis completed before the time limit."
            result["audit_status"] = "Skipped - timeout"
            return result
        tasks, decomposition = decomposed
        models.add(decomposition.model)
        result["tasks"] = tasks
        result["agent_squad"] = [{"name": t["agent_name"], "prompt": t["task"]} for t in tasks]
        emit("tasks", agents=[{"name": t["agent_name"], "task": t["task"], "domain": t.get("domain")} for t in tasks])

        # Inject per-ticker market data into each task
        for task in tasks:
            task["market_data"] = get_ticker_data_for_agent(
                task["agent_name"], market_data, domains
            )

        # Initialize room
        room_id = band.create_room(name="BIFAS-Session")
        band.send_message(room_id, "System", f"BIFAS Query: {user_query}", msg_type="system")

        # PHASE 2: Parallel Sprint Execution (N calls, concurrent).
        # Agents must finish early enough to leave time for synthesis and audit.
        analyses = {}
        failed_agents = []
        agent_deadline = deadline - FINISH_RESERVE_SECONDS
        emit("phase", name="agents")

        def _record_agent(outcome):
            agent_name, result_text, success, model = outcome
            if success:
                models.add(model)
                analyses[agent_name] = result_text
                band.send_message(room_id, agent_name, result_text, msg_type="contribution")
                result["rounds"].append({
                    "round": len(result["rounds"]) + 1,
                    "next_agent": agent_name,
                    "contribution": result_text[:300],
                    "contribution_full": result_text,
                })
                emit("agent", name=agent_name, status="done", text=result_text, model=model)
            else:
                failed_agents.append(agent_name)
                emit("agent", name=agent_name, status="failed", text="", model=None)
                band.send_message(room_id, agent_name, "[FAILED]", msg_type="request")

        executor = ThreadPoolExecutor(max_workers=min(len(tasks), MAX_WORKERS))
        future_to_task = {
            executor.submit(execute_agent_task, t["agent_name"], t["task"], user_query, t.get("market_data", "No specific data available.")): t
            for t in tasks
        }
        pending = set(future_to_task)
        try:
            while pending:
                _check_cancel(cancel_event)
                remaining = agent_deadline - time.time()
                if remaining <= 0:
                    raise FuturesTimeout()
                done, pending = wait(pending, timeout=min(remaining, POLL_SECONDS), return_when=FIRST_COMPLETED)
                for future in done:
                    _record_agent(future.result())
        except FuturesTimeout:
            unfinished = [future_to_task[f]["agent_name"] for f in pending]
            guardrails.append(f"Timeout during agent execution — skipped: {', '.join(unfinished)}")
            for name in unfinished:
                emit("agent", name=name, status="skipped", text="", model=None)
        finally:
            # Never wait for stragglers: queued agents are cancelled, running ones are abandoned.
            executor.shutdown(wait=False, cancel_futures=True)

        if failed_agents:
            guardrails.append(f"Failed agents: {', '.join(failed_agents)}")

        # PHASE 3: Synthesis (1 call)
        if analyses:
            _check_cancel(cancel_event)
            emit("phase", name="synthesis")
            final_report = _run_before(deadline, synthesize_report, analyses, user_query, cancel_event=cancel_event)
            if final_report is None:
                guardrails.append("Timeout during synthesis — showing raw agent analyses")
                final_report = "\n\n".join(f"### {name}\n{text}" for name, text in analyses.items())
                result["audit_status"] = "Skipped - timeout"
            result["final_report"] = final_report
            emit("report", markdown=final_report)

            # PHASE 4: Audit (1 call)
            if not result["audit_status"]:
                _check_cancel(cancel_event)
                emit("phase", name="audit")
                audit = _run_before(deadline, audit_report, final_report, user_query, cancel_event=cancel_event)
                if audit is None:
                    guardrails.append("Timeout during audit")
                    audit = "Skipped - timeout"
                result["audit_status"] = audit
            emit("audit", status=result["audit_status"])
        else:
            result["final_report"] = "No agent analyses completed."
            result["audit_status"] = "FAILED - no analyses"

        result["total_messages"] = len(band.get_room_history(room_id))

    except _Cancelled:
        result["cancelled"] = True
        result["audit_status"] = "Cancelled"
        guardrails.append("Cancelled")
        emit("cancelled")
    except Exception as e:
        result["audit_status"] = f"Pipeline error: {str(e)}"
        raise
    finally:
        result["guardrail_triggered"] = "; ".join(guardrails) or None
        result["execution_time"] = time.time() - start_time
        result["models_used"] = sorted(models)
        result["fallback_used"] = any(m != config.PRIMARY_MODEL for m in models)

    return result
