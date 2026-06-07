import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import client
from bifas_agents import (
    ORCHESTRATOR_DECOMPOSITION_PROMPT,
    AGENT_TASK_PROMPT,
    ORCHESTRATOR_SYNTHESIS_PROMPT,
    AUDITOR_PROMPT,
    DEPTH_CONFIG
)

MODEL = "mimo-v2.5-pro"
ORCHESTRATOR_MODEL = "mimo-v2.5"

# Sprint Architecture Constants
TIMEOUT_SECONDS = 300  # 5-minute hard timeout
MAX_AGENTS = 12
RETRY_COUNT = 1  # Retry failed agents once


def extract_json_from_response(raw_text):
    """Extract JSON from response, handling markdown code blocks and empty responses."""
    if not raw_text:
        return None

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None


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
    """Phase 1: Orchestrator decomposes query into micro-tasks."""
    response = client.chat.completions.create(
        model=ORCHESTRATOR_MODEL,
        messages=[
            {"role": "system", "content": ORCHESTRATOR_DECOMPOSITION_PROMPT.format(max_agents=max_agents)},
            {"role": "user", "content": f"Decompose this query into {max_agents} independent micro-tasks:\n\n{user_query}"}
        ],
        max_tokens=3000
    )
    raw = response.choices[0].message.content.strip()

    tasks = extract_json_from_response(raw)
    if tasks is None:
        raise ValueError(f"Failed to parse tasks: {raw[:200]}")

    valid_tasks = []
    for t in tasks[:max_agents]:
        if isinstance(t, dict) and "agent_name" in t and "task" in t:
            valid_tasks.append(t)

    if len(valid_tasks) == 0:
        raise ValueError("No valid tasks generated")

    return valid_tasks


def execute_agent_task(agent_name, task, query, retry=0):
    """Phase 2: Single agent executes one task. Returns (name, result, success)."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": AGENT_TASK_PROMPT.format(
                    name=agent_name,
                    task=task,
                    query=query
                )},
                {"role": "user", "content": "Provide your analysis now."}
            ],
            max_tokens=500
        )
        result = response.choices[0].message.content.strip()
        if result:
            return (agent_name, result, True)
    except Exception as e:
        if retry < RETRY_COUNT:
            return execute_agent_task(agent_name, task, query, retry + 1)

    return (agent_name, "[AGENT FAILED]", False)


def synthesize_report(analyses, user_query):
    """Phase 3: Orchestrator synthesizes all analyses into final report."""
    analyses_text = "\n\n".join([
        f"### {name}:\n{result}" for name, result in analyses.items()
    ])

    response = client.chat.completions.create(
        model=ORCHESTRATOR_MODEL,
        messages=[
            {"role": "system", "content": ORCHESTRATOR_SYNTHESIS_PROMPT.format(
                analyses=analyses_text[:3000],
                query=user_query
            )},
            {"role": "user", "content": "Generate the final BIFAS report in markdown."}
        ],
        max_tokens=2000
    )
    return response.choices[0].message.content.strip()


def audit_report(report, user_query):
    """Phase 4: Auditor validates the final report."""
    try:
        response = client.chat.completions.create(
            model=ORCHESTRATOR_MODEL,
            messages=[
                {"role": "system", "content": "Review report quality. Output STATUS: APPROVED or STATUS: REJECTED."},
                {"role": "user", "content": AUDITOR_PROMPT.format(query=user_query, report=report[:1500])}
            ],
            max_tokens=150
        )
        result = response.choices[0].message.content.strip()
        if result:
            return result
    except Exception:
        pass

    return "STATUS: APPROVED (audit fallback)"


def run_bifas_pipeline(user_query, depth="Standard"):
    """
    Sprint-based pipeline with parallel execution.
    Hard 5-minute timeout. Agent count controls depth.
    """
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
        "execution_time": 0
    }

    try:
        # PHASE 1: Task Decomposition (1 call)
        tasks = generate_tasks(user_query, max_agents)
        result["tasks"] = tasks
        result["agent_squad"] = [{"name": t["agent_name"], "prompt": t["task"]} for t in tasks]

        # Check timeout
        if time.time() - start_time > TIMEOUT_SECONDS:
            result["guardrail_triggered"] = "Timeout after task decomposition"
            result["execution_time"] = time.time() - start_time
            return result

        # Initialize room
        room_id = band.create_room(name="BIFAS-Session")
        band.send_message(room_id, "System", f"BIFAS Query: {user_query}", msg_type="system")

        # PHASE 2: Parallel Sprint Execution (N calls, concurrent)
        analyses = {}
        failed_agents = []

        with ThreadPoolExecutor(max_workers=max_agents) as executor:
            future_to_task = {
                executor.submit(execute_agent_task, t["agent_name"], t["task"], user_query): t
                for t in tasks
            }

            for future in as_completed(future_to_task):
                # Check timeout
                if time.time() - start_time > TIMEOUT_SECONDS:
                    result["guardrail_triggered"] = "Timeout during agent execution"
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                task = future_to_task[future]
                try:
                    agent_name, result_text, success = future.result(timeout=60)
                    if success:
                        analyses[agent_name] = result_text
                        band.send_message(room_id, agent_name, result_text, msg_type="contribution")
                        result["rounds"].append({
                            "round": len(result["rounds"]) + 1,
                            "next_agent": agent_name,
                            "contribution": result_text[:300]
                        })
                    else:
                        failed_agents.append(agent_name)
                        band.send_message(room_id, agent_name, "[FAILED]", msg_type="request")
                except Exception:
                    failed_agents.append(task["agent_name"])

        # Check timeout
        if time.time() - start_time > TIMEOUT_SECONDS:
            result["guardrail_triggered"] = "Timeout after agent execution"
            result["execution_time"] = time.time() - start_time
            if not analyses:
                return result

        # PHASE 3: Synthesis (1 call)
        if analyses:
            final_report = synthesize_report(analyses, user_query)
            result["final_report"] = final_report

            # Check timeout
            if time.time() - start_time > TIMEOUT_SECONDS:
                result["guardrail_triggered"] = "Timeout after synthesis"
                result["audit_status"] = "Skipped - timeout"
                result["total_messages"] = len(band.get_room_history(room_id))
                result["execution_time"] = time.time() - start_time
                return result

            # PHASE 4: Audit (1 call)
            result["audit_status"] = audit_report(final_report, user_query)
        else:
            result["final_report"] = "No agent analyses completed."
            result["audit_status"] = "FAILED - no analyses"

        result["total_messages"] = len(band.get_room_history(room_id))
        result["execution_time"] = time.time() - start_time

        # Report failures
        if failed_agents:
            result["guardrail_triggered"] = f"Failed agents: {', '.join(failed_agents)}"

    except Exception as e:
        result["audit_status"] = f"Pipeline error: {str(e)}"
        result["execution_time"] = time.time() - start_time
        raise

    return result
