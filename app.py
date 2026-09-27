import streamlit as st
import config
from engine import run_bifas_pipeline
from bifas_agents import DEPTH_CONFIG
from llm import usage_snapshot

st.set_page_config(
    page_title="BIFAS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp {
        background-color: #0a0a0f;
    }
    .main-header {
        font-family: 'Courier New', monospace;
        font-size: 2.4rem;
        font-weight: 700;
        color: #00f0ff;
        text-align: center;
        padding: 1.2rem 0;
        border-bottom: 2px solid #1a1a2e;
        letter-spacing: 3px;
        text-transform: uppercase;
    }
    .sub-header {
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        color: #555577;
        text-align: center;
        letter-spacing: 5px;
        margin-bottom: 2rem;
    }
    div[data-testid="stTextArea"] textarea {
        background-color: #0f0f1a;
        color: #e0e0e0;
        border: 1px solid #1a1a2e;
        font-family: 'Courier New', monospace;
    }
    div[data-testid="stTextArea"] textarea:focus {
        border-color: #00f0ff;
        box-shadow: 0 0 8px rgba(0, 240, 255, 0.3);
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">BIFAS</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Sprint Architecture — Parallel Agent Execution · Gemini 3.5 Flash Lite</div>', unsafe_allow_html=True)

query = st.text_area(
    "ENTER ANALYSIS DIRECTIVE",
    placeholder="e.g., Analyze Forex correlations between EUR/USD, GBP/USD, and USD/JPY",
    height=100
)

col_depth, col_button = st.columns([1, 3])
with col_depth:
    depth = st.selectbox(
        "ANALYSIS DEPTH",
        options=list(DEPTH_CONFIG.keys()),
        index=1,
        format_func=lambda x: f"{x} — {DEPTH_CONFIG[x]['description']}"
    )
with col_button:
    st.write("")
    run_clicked = st.button("Initialize BIFAS Sprint", type="primary", use_container_width=True)

usage = usage_snapshot()
st.caption(
    f"Model: {usage['primary_model']} · Requests today: {usage['used']} / {usage['limit']}"
    + (f" · Daily quota reached — using fallback {usage['fallback_model']}" if usage["fallback_active"] else "")
)

if run_clicked:
    if not query.strip():
        st.warning("Enter a query to initiate analysis.")
    else:
        with st.spinner(f"Executing Sprint Analysis ({depth} mode, {DEPTH_CONFIG[depth]['max_agents']} agents)..."):
            try:
                result = run_bifas_pipeline(query, depth=depth)
            except Exception as e:
                st.error(f"Pipeline failed: {str(e)}")
                st.stop()

        # Guardrail Warning
        if result.get("guardrail_triggered"):
            st.warning(f"⚠️ {result['guardrail_triggered']}")
        if result.get("fallback_used"):
            st.info(
                f"ℹ️ {config.PRIMARY_MODEL} quota was exhausted, so part or all of this run "
                f"used the fallback model ({', '.join(result.get('models_used', []))})."
            )

        col_left, col_right = st.columns([1, 2])

        with col_left:
            st.subheader("Agent Squad")
            for agent in result.get("agent_squad", []):
                with st.expander(f"🤖 {agent['name']}", expanded=False):
                    st.caption(agent['prompt'])

            st.subheader("Audit Verdict")
            audit = result.get("audit_status", "N/A")
            if "APPROVED" in audit:
                st.success(audit)
            elif "REJECTED" in audit:
                st.error(audit)
            else:
                st.warning(audit)

            # Metrics
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.metric("Agents", len(result.get("agent_squad", [])))
                st.metric("Messages", result.get("total_messages", 0))
            with col_m2:
                st.metric("Time", f"{result.get('execution_time', 0):.1f}s")
                st.metric("Rounds", len(result.get("rounds", [])))

        with col_right:
            st.subheader("Agent Contributions")
            for round_data in result.get("rounds", []):
                agent_name = round_data.get("next_agent", "Unknown")
                contribution = round_data.get("contribution_full") or round_data.get("contribution", "N/A")
                with st.expander(f"📊 {agent_name}", expanded=False):
                    st.markdown(contribution)

            st.subheader("Final Report")
            report = result.get("final_report", "No report generated.")
            with st.container(border=True):
                st.markdown(report)
