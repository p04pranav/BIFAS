import streamlit as st
from engine import run_bifas_pipeline

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
    .report-block {
        background-color: #0f0f1a;
        border: 1px solid #1a1a2e;
        border-radius: 6px;
        padding: 1.5rem;
        font-family: 'Courier New', monospace;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">BIFAS</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Dynamic Multi-Agent Financial Analytics</div>', unsafe_allow_html=True)

query = st.text_area(
    "ENTER ANALYSIS DIRECTIVE",
    placeholder="e.g., Analyze BTC vs SOL price spikes over the last 7 days",
    height=100
)

if st.button("Initialize BIFAS Run", type="primary", use_container_width=True):
    if not query.strip():
        st.warning("Enter a query to initiate analysis.")
    else:
        with st.spinner("Architecting agent topology via MiMo-V2.5pro..."):
            result = run_bifas_pipeline(query)

        col_left, col_right = st.columns([1, 2])

        with col_left:
            st.subheader("Audit Verdict")
            audit = result.get("audit_status", "N/A")
            if "APPROVED" in audit:
                st.success(audit)
            elif "REJECTED" in audit:
                st.error(audit)
            else:
                st.warning(audit)

            st.subheader("Agent Topology")
            team = result.get("assigned_team", [])
            if team:
                for i, agent in enumerate(team, 1):
                    icon = "🔗" if agent == "Synthesizer" else "▶"
                    st.markdown(f"`{i}.` **{agent}** {icon}")
            else:
                st.info("No agents assigned.")

        with col_right:
            st.subheader("Final Report")
            report = result.get("final_report", "No report generated.")
            st.markdown(f'<div class="report-block">{report}</div>', unsafe_allow_html=True)
