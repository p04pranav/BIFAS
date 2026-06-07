import json
import band_sdk
from config import client
from bifas_agents import BIFAS_PERSONAS

MODEL = "MiMo-V2.5pro"


def run_bifas_pipeline(user_query):
    result = {
        "assigned_team": [],
        "final_report": "",
        "audit_status": ""
    }

    try:
        # --- STEP 1: Topology Generation ---
        architect_response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": BIFAS_PERSONAS["The_Architect"]},
                {"role": "user", "content": user_query}
            ]
        )
        raw_output = architect_response.choices[0].message.content.strip()

        try:
            assigned_team = json.loads(raw_output)
            if not isinstance(assigned_team, list) or len(assigned_team) < 2 or len(assigned_team) > 5:
                raise ValueError("Invalid team size")
            if assigned_team[-1] != "Synthesizer":
                raise ValueError("Synthesizer must be last")
        except (json.JSONDecodeError, ValueError) as e:
            result["audit_status"] = f"Topology parsing failed: {e}"
            return result

        result["assigned_team"] = assigned_team

        # --- STEP 2: Room Initialization ---
        room_id = band_sdk.create_room(name="BIFAS-Session-Crypto")
        band_sdk.send_message(
            room_id=room_id,
            sender="System",
            text=f"BIFAS Query: {user_query}"
        )

        # --- STEP 3: Collaboration Loop ---
        for agent_name in assigned_team:
            persona = BIFAS_PERSONAS.get(agent_name)
            if not persona:
                continue

            room_history = band_sdk.get_room_history(room_id=room_id)

            agent_response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": persona},
                    {"role": "user", "content": f"Room History:\n{room_history}\n\nAnalyze and contribute your findings."}
                ]
            )
            response_text = agent_response.choices[0].message.content.strip()

            band_sdk.send_message(
                room_id=room_id,
                sender=agent_name,
                text=response_text
            )

        # --- STEP 4: Auditing ---
        final_history = band_sdk.get_room_history(room_id=room_id)

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
