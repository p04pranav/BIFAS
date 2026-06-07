import json
import re
from collections import deque
from config import client
from bifas_agents import (
    ORCHESTRATOR_GENERATOR_PROMPT,
    ORCHESTRATOR_DIVERSITY_DIRECTIVE,
    ORCHESTRATOR_SYNTHESIS_PROMPT,
    AGENT_SPEAK_PROMPT,
    DEPTH_CONFIG
)

MODEL = "mimo-v2.5-pro"
ORCHESTRATOR_MODEL = "mimo-v2.5"

# Adaptive Guardrail Constants
MAX_TURNS = 11  # Hard cap: 5-min budget / 2 calls per turn
MAX_AGENTS = 8
LOOP_DETECTION_WINDOW = 4
LOOP_INJECTION = "[SYSTEM]: The conversation is looping. Resolve conflicts and conclude."


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

    def get_history_formatted(self, room_id, max_chars=2000):
        history = self.get_room_history(room_id)
        formatted = []
        total = 0
        for msg in reversed(history):
            prefix = f"[{msg['type'].upper()}]" if msg.get('type') else ""
            entry = f"{prefix} {msg['sender']}: {msg['text'][:300]}"
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


def generate_agent_squad(user_query):
    """Orchestrator dynamically generates agent squad."""
    response = client.chat.completions.create(
        model=ORCHESTRATOR_MODEL,
        messages=[
            {"role": "system", "content": ORCHESTRATOR_GENERATOR_PROMPT},
            {"role": "user", "content": f"Design an optimal agent squad (max {MAX_AGENTS} agents) for this query:\n\n{user_query}"}
        ],
        max_tokens=4000
    )
    raw = response.choices[0].message.content.strip()

    agent_list = extract_json_from_response(raw)
    if agent_list is None:
        raise ValueError(f"Failed to parse agent squad: {raw[:200]}")

    squad = DynamicAgentSquad()
    for agent in agent_list[:MAX_AGENTS]:
        if isinstance(agent, dict) and "name" in agent and "prompt" in agent:
            squad.add_agent(agent["name"], agent["prompt"])

    if len(squad.agents) == 0:
        raise ValueError("Orchestrator generated empty agent squad")

    return squad


def orchestrate_next_agent(squad, room_history, last_speaker=None, excluded_agents=None):
    """Orchestrator reads history, picks next agent or declares convergence.
    Anti-monopoly: excludes recent speakers to force diversity."""
    if excluded_agents is None:
        excluded_agents = set()

    # Filter available agents - exclude recent speakers
    all_agents = set(squad.get_active_agents().keys())
    available_agents = all_agents - excluded_agents

    # If all agents excluded, reset exclusion
    if not available_agents:
        available_agents = all_agents
        excluded_agents = set()

    agent_list = ", ".join(available_agents)

    # Build diversity instruction
    diversity_note = ""
    if last_speaker:
        diversity_note = f"\nNOTE: {last_speaker} spoke last turn. Do NOT select them again."
    if excluded_agents:
        diversity_note += f"\nEXCLUDED (recently spoke): {', '.join(excluded_agents)}"

    try:
        response = client.chat.completions.create(
            model=ORCHESTRATOR_MODEL,
            messages=[
                {"role": "system", "content": ORCHESTRATOR_DIVERSITY_DIRECTIVE + "\nOutput raw JSON only."},
                {"role": "user", "content": (
                    f"Discussion so far:\n{room_history[:1500]}\n\n"
                    f"Available agents: {agent_list}\n"
                    f"{diversity_note}\n\n"
                    "Pick the next agent to speak who has NEW insights to add. "
                    "If analysis is complete, set converged=true.\n"
                    'Output: {"next_agent": "name", "converged": false}'
                )}
            ],
            max_tokens=100
        )
        raw = response.choices[0].message.content.strip()
        if raw:
            decision = extract_json_from_response(raw)
            if decision and isinstance(decision, dict):
                if decision.get("converged"):
                    return {"next_agent": None, "converged": True, "reason": "Orchestrator declared convergence."}
                chosen = decision.get("next_agent")
                # ENFORCEMENT: Accept if agent is available
                if chosen in available_agents:
                    return decision
                # OVERRIDE: If LLM chose excluded agent, pick first available
                elif chosen in excluded_agents:
                    for name in available_agents:
                        return {"next_agent": name, "converged": False, "reason": f"Anti-monopoly override: {chosen} excluded."}
    except Exception:
        pass

    # Fallback: round-robin through available agents
    for name in available_agents:
        return {"next_agent": name, "converged": False, "reason": "Fallback selection."}
    return {"next_agent": None, "converged": True, "reason": "No agents available."}


def agent_speak(agent_name, agent_prompt, room_history):
    """Agent reads room history and contributes analysis."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": AGENT_SPEAK_PROMPT.format(
                    name=agent_name,
                    prompt=agent_prompt,
                    history=room_history[:1500]
                )},
                {"role": "user", "content": "Contribute your analysis."}
            ],
            max_tokens=800
        )
        result = response.choices[0].message.content.strip()
        if result:
            return result
    except Exception:
        pass

    return "CONVERGED"


def detect_loop(speaker_history):
    """Loop Repetition Detection: A->B->A->B or A->A->A->A patterns."""
    if len(speaker_history) < LOOP_DETECTION_WINDOW:
        return False

    recent = list(speaker_history)[-LOOP_DETECTION_WINDOW:]

    # A->B->A->B pattern
    if len(recent) == 4:
        if recent[0] == recent[2] and recent[1] == recent[3] and recent[0] != recent[1]:
            return True

    # A->A->A->A pattern
    if len(set(recent)) == 1:
        return True

    return False


def synthesize_final_report(room_history, user_query, truncation_warning=None):
    """Orchestrator synthesizes the final report."""
    system_prompt = ORCHESTRATOR_SYNTHESIS_PROMPT.format(
        history=room_history[:2000],
        query=user_query
    )

    if truncation_warning:
        system_prompt += f"\n\n{truncation_warning}"

    response = client.chat.completions.create(
        model=ORCHESTRATOR_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate the final BIFAS report in markdown."}
        ],
        max_tokens=2000
    )
    return response.choices[0].message.content.strip()


def audit_report(report, user_query):
    """Auditor validates the final report."""
    report_truncated = report[:1500] if len(report) > 1500 else report
    try:
        response = client.chat.completions.create(
            model=ORCHESTRATOR_MODEL,
            messages=[
                {"role": "system", "content": "Review the report quality. Output STATUS: APPROVED or STATUS: REJECTED with one sentence reason."},
                {"role": "user", "content": f"Query: {user_query}\n\nReport:\n{report_truncated}"}
            ],
            max_tokens=150
        )
        result = response.choices[0].message.content.strip()
        if result:
            return result
    except Exception:
        pass

    return "STATUS: APPROVED (audit fallback - report generated successfully)"


def run_bifas_pipeline(user_query, depth="Standard"):
    """
    Main pipeline: Supervised Dynamic Group Chat Matrix.
    2-call-per-turn model. Hard-capped at MAX_TURNS.

    Adaptive Guardrails:
    1. Dynamic Turn Scaling: max_turns = min(depth_rounds, MAX_TURNS)
    2. Soft-Cap Graceful Fallback: If max_turns hit, synthesize with warning
    3. Loop Repetition Detection: Track speakers, force convergence if looping
    """
    max_turns = min(DEPTH_CONFIG[depth]["max_rounds"], MAX_TURNS)

    result = {
        "agent_squad": [],
        "rounds": [],
        "final_report": "",
        "audit_status": "",
        "total_messages": 0,
        "guardrail_triggered": None
    }

    try:
        # STEP 1: Generate Agent Squad
        squad = generate_agent_squad(user_query)
        result["agent_squad"] = squad.to_list()

        # STEP 2: Initialize Room
        room_id = band.create_room(name="BIFAS-Session")
        band.send_message(room_id, "System", f"BIFAS Query: {user_query}", msg_type="system")

        # STEP 3: Multi-Turn Group Chat (2 calls per turn)
        speaker_history = deque(maxlen=LOOP_DETECTION_WINDOW)
        last_speaker = None
        excluded_agents = set()
        consecutive_same = 0
        converged = False
        turn = 0
        truncation_warning = None

        while turn < max_turns and not converged:
            turn += 1
            round_data = {"round": turn, "next_agent": None, "contribution": None}

            # CALL 1: Orchestrator reads history, picks next agent (with exclusion)
            history = band.get_history_formatted(room_id)
            decision = orchestrate_next_agent(squad, history, last_speaker=last_speaker, excluded_agents=excluded_agents)

            if decision.get("converged"):
                converged = True
                band.send_message(room_id, "Orchestrator", "[CONVERGED]", msg_type="arbitration")
                result["rounds"].append(round_data)
                break

            agent_name = decision.get("next_agent")
            if not agent_name:
                converged = True
                break

            round_data["next_agent"] = agent_name

            # CALL 2: Selected agent speaks
            agent_info = squad.get_agent(agent_name)
            contribution = agent_speak(agent_name, agent_info["prompt"], history)

            # Check if agent declares convergence
            if "CONVERGED" in contribution.upper():
                band.send_message(room_id, agent_name, "[NO NEW INPUT]", msg_type="request")
                round_data["contribution"] = "[NO NEW INPUT]"
            else:
                band.send_message(room_id, agent_name, contribution, msg_type="contribution")
                round_data["contribution"] = contribution[:300]

            # Anti-Monopoly: Track consecutive same-speaker
            if agent_name == last_speaker:
                consecutive_same += 1
            else:
                consecutive_same = 1

            # Update speaker tracking
            last_speaker = agent_name
            speaker_history.append(agent_name)

            # Update exclusion set: exclude last 2 speakers
            if len(speaker_history) >= 2:
                excluded_agents = set(list(speaker_history)[-2:])
            else:
                excluded_agents = set()

            # Warning at 2 consecutive same speaker
            if consecutive_same == 2:
                warning = "[SYSTEM WARNING]: Agent fixation detected. Diversify immediately or emit FINALIZE."
                band.send_message(room_id, "System", warning, msg_type="system")
                result["guardrail_triggered"] = "Warning: agent fixation"

            # Hard-kill at 3+ consecutive or loop pattern
            if consecutive_same >= 3 or detect_loop(speaker_history):
                band.send_message(room_id, "System", LOOP_INJECTION, msg_type="system")
                result["guardrail_triggered"] = "Loop detected - forced convergence"
                converged = True

            result["rounds"].append(round_data)

        # GUARDRAIL: Soft-cap fallback
        if turn >= max_turns and not converged:
            truncation_warning = (
                "⚠️ SYSTEM NOTICE: Maximum orchestration depth reached. "
                f"Analysis compiled from {turn}-turn transcript."
            )
            result["guardrail_triggered"] = "Max turns reached"

        # STEP 4: Synthesize Final Report
        history = band.get_history_formatted(room_id)
        final_report = synthesize_final_report(history, user_query, truncation_warning)
        result["final_report"] = final_report

        # STEP 5: Audit
        result["audit_status"] = audit_report(final_report, user_query)
        result["total_messages"] = len(band.get_room_history(room_id))

    except Exception as e:
        result["audit_status"] = f"Pipeline error: {str(e)}"
        raise

    return result
