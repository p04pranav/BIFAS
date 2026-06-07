# BIFAS — Band Incorporated Finance Analytics System

A standalone, multi-agent financial and cryptocurrency analysis platform powered by **MiMo-V2.5pro** with an in-memory collaboration layer.

---

## Overview

BIFAS is a dynamic, multi-agent system that deploys specialized AI analysts to dissect financial queries in real time. Rather than relying on a single LLM response, BIFAS assembles a custom team of domain experts for each query — from trend analysis to on-chain data interpretation — then synthesizes their findings into a pristine executive report.

The entire pipeline is orchestrated sequentially by Streamlit, with agent collaboration logged in a local in-memory room for full transparency and auditability. **No external platform dependencies required.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        STREAMLIT UI                         │
│                   (Puppeteer / Orchestrator)                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   THE ARCHITECT (mimo-v2.5)                  │
│          Analyzes query → Returns agent topology (JSON)      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  LOCAL BAND SDK (In-Memory)                   │
│              (Collaboration & Message Log)                    │
│                                                              │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│   │  Agent 1  │→│  Agent 2  │→│  Agent 3  │→│Synthesizer│   │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│     (mimo-v2.5-pro)                                          │
│     Each agent reads room history, queries MiMo,             │
│        and posts findings back to the room                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    THE AUDITOR (mimo-v2.5-pro)                │
│          Reviews final report → APPROVED / REJECTED          │
└─────────────────────────────────────────────────────────────┘
```

### Execution Model: Sequential API Orchestration

BIFAS does **not** use background bots, websockets, or async threads. Streamlit acts as the puppeteer:

1. Streamlit queries MiMo (Architect) to generate agent topology
2. Posts the query to the LocalBandSDK room
3. For each agent: reads room history → queries MiMo → posts response
4. Auditor reviews the final report

This ensures deterministic execution, full observability, and zero race conditions.

### Dual-Model Strategy

| Component | Model | Reason |
|-----------|-------|--------|
| **The_Architect** | `mimo-v2.5` | Reliable JSON output for routing |
| **Specialist Agents** | `mimo-v2.5-pro` | Higher quality analysis and reasoning |
| **The_Auditor** | `mimo-v2.5-pro` | Thorough review of final reports |

---

## Agent Roster

| Agent | Specialty |
|-------|-----------|
| **The_Architect** | Routing engine — analyzes the user query and dynamically selects 2–5 specialist agents |
| **Trend_Analyst** | Price velocity, moving averages, momentum indicators |
| **Correlation_Detective** | Cross-asset pattern matching, overlapping date analysis |
| **OnChain_Sleuth** | Volume spikes, exchange inflows, whale activity |
| **Sentiment_Reader** | Market fear/greed index, news sentiment analysis |
| **Synthesizer** | Aggregates all agent findings into a pristine executive report |
| **The_Auditor** | Quality gate — reviews the final report and issues APPROVED or REJECTED |

The team is assembled dynamically per query. Not every query needs every agent.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **UI** | Streamlit |
| **LLM** | MiMo-V2.5pro / MiMo-V2.5 (via OpenAI-compatible API) |
| **Coordination** | LocalBandSDK (in-memory room simulation) |
| **Language** | Python 3.12+ |
| **Config** | python-dotenv |

---

## Project Structure

```
BIFAS/
├── requirements.txt      # Project dependencies
├── .env                  # API keys (not committed)
├── .gitignore            # Ignored files
├── config.py             # Environment loader + MiMo client setup
├── bifas_agents.py       # Agent persona definitions + routing template
├── engine.py             # LocalBandSDK + Sequential orchestration pipeline
├── app.py                # Streamlit UI
├── TEST_REPORT.md        # Comprehensive test results
└── README.md             # This file
```

### File Descriptions

- **`config.py`** — Loads `MIMO_API_KEY` from `.env`. Instantiates the OpenAI client pointing to `https://token-plan-sgp.xiaomimimo.com/v1`.

- **`bifas_agents.py`** — Contains `BIFAS_PERSONAS` (agent system prompts) and `ARCHITECT_USER_TEMPLATE` (routing instruction). No execution logic.

- **`engine.py`** — The brain. Contains `LocalBandSDK` class (in-memory room simulation) and `run_bifas_pipeline(user_query)` which executes the full sequential flow: topology generation → room init → collaboration loop → audit.

- **`app.py`** — Streamlit frontend with a dark enterprise terminal aesthetic. Handles user input, triggers the pipeline, and renders results in a two-column layout.

---

## Setup

### Prerequisites

- Python 3.10+
- A MiMo API key (from Xiaomi MiMo platform)

### Installation

```bash
git clone https://github.com/p04pranav/BIFAS.git
cd BIFAS
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
MIMO_API_KEY=your_mimo_api_key_here
```

### Run

```bash
streamlit run app.py
```

---

## Usage

1. Launch the app — you'll see the BIFAS terminal interface
2. Enter a financial analysis query, e.g.:
   - `Analyze BTC vs SOL price spikes over the last 7 days`
   - `Compare ETH volume trends with market sentiment`
   - `Is XRP showing accumulation patterns on-chain?`
3. Click **Initialize BIFAS Run**
4. Watch as the Architect assembles your team, agents collaborate in the room, and the Auditor validates the final report

---

## Example Query

```
Analyze BTC vs SOL price spikes and determine if SOL is decoupling from BTC correlation.
```

**Possible Agent Topology:**
1. Trend_Analyst
2. Correlation_Detective
3. OnChain_Sleuth
4. Sentiment_Reader
5. Synthesizer

---

## Test Results

See [TEST_REPORT.md](TEST_REPORT.md) for comprehensive test results.

**Summary:**
- ✅ LocalBandSDK unit tests — all pass
- ✅ JSON extraction — handles all formats
- ✅ Full pipeline — end-to-end success
- ✅ Audit validation — reports APPROVED

---

## License

Proprietary — All rights reserved.

---

Built with precision by **PranavS**
