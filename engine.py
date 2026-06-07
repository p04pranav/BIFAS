import json
import re
from config import client
from bifas_agents import BIFAS_PERSONAS, ARCHITECT_USER_TEMPLATE

MODEL = "mimo-v2.5"
ARCHITECT_MODEL = "mimo-v2.5"


def extract_json_from_response(raw_text):
    """Extract JSON from response, handling markdown code blocks and empty responses."""
    if not raw_text:
        return None
    
    # Try direct parse first
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks (```json ... ``` or ``` ... ```)
    json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw_text, re.DOTALL)
    if json_match:
        content = json_match.group(1).strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
    
    # Try to find any JSON array in the text
    json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Try to find any JSON object with selected_agents key
    json_match = re.search(r'\{.*"selected_agents".*\}', raw_text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            if 'selected_agents' in parsed:
                return [item.get('agent', '') for item in parsed['selected_agents']]
        except json.JSONDecodeError:
            pass
    
    return None


class LocalBandSDK:
    """In-memory room/message simulation replacing external Band SDK."""

    def __init__(self):
        self.rooms = {}
        self.room_counter = 0

    def create_room(self, name):
        self.room_counter += 1
        room_id = f"room_{self.room_counter}"
        self.rooms[room_id] = {"name": name, "messages": []}
        return room_id

    def send_message(self, room_id, sender, text):
        self.rooms[room_id]["messages"].append({
            "sender": sender,
            "text": text
        })

    def get_room_history(self, room_id):
        return self.rooms[room_id]["messages"]


band = LocalBandSDK()


def run_bifas_pipeline(user_query):
    result = {
        "assigned_team": [],
        "final_report": "",
        "audit_status": ""
    }

    try:
        # --- STEP 1: Topology Generation ---
        architect_user_msg = ARCHITECT_USER_TEMPLATE.format(query=user_query)
        architect_response = client.chat.completions.create(
            model=ARCHITECT_MODEL,
            messages=[
                {"role": "system", "content": BIFAS_PERSONAS["The_Architect"]},
                {"role": "user", "content": architect_user_msg}
            ]
        )
        raw_output = architect_response.choices[0].message.content.strip()

        try:
            assigned_team = extract_json_from_response(raw_output)
            if assigned_team is None:
                raise ValueError("Could not extract JSON from response")
            # Handle both ["Agent1", "Agent2"] and [{"name": "Agent1"}, ...]
            if assigned_team and isinstance(assigned_team[0], dict):
                assigned_team = [item.get('name', item.get('agent', '')) for item in assigned_team]
            if not isinstance(assigned_team, list) or len(assigned_team) < 2 or len(assigned_team) > 5:
                raise ValueError("Invalid team size")
            if assigned_team[-1] != "Synthesizer":
                raise ValueError("Synthesizer must be last")
        except (json.JSONDecodeError, ValueError) as e:
            result["audit_status"] = f"Topology parsing failed: {e}"
            return result

        result["assigned_team"] = assigned_team

        # --- STEP 2: Room Initialization ---
        room_id = band.create_room(name="BIFAS-Session-Crypto")
        band.send_message(
            room_id=room_id,
            sender="System",
            text=f"BIFAS Query: {user_query}"
        )

        # --- STEP 3: Collaboration Loop ---
        for agent_name in assigned_team:
            persona = BIFAS_PERSONAS.get(agent_name)
            if not persona:
                continue

            room_history = band.get_room_history(room_id=room_id)

            agent_response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": persona},
                    {"role": "user", "content": f"Room History:\n{room_history}\n\nAnalyze and contribute your findings."}
                ]
            )
            response_text = agent_response.choices[0].message.content.strip()

            band.send_message(
                room_id=room_id,
                sender=agent_name,
                text=response_text
            )

        # --- STEP 4: Auditing ---
        final_history = band.get_room_history(room_id=room_id)

        auditor_response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": BIFAS_PERSONAS["The_Auditor"]},
                {"role": "user", "content": f"Final Room History:\n{final_history}"}
            ]
        )
        audit_text = auditor_response.choices[0].message.content.strip()

        # Extract Synthesizer output from history
        for entry in reversed(final_history):
            if entry.get("sender") == "Synthesizer":
                result["final_report"] = entry.get("text", "")
                break

        result["audit_status"] = audit_text

    except Exception as e:
        result["audit_status"] = f"Pipeline error: {e}"

    return result
