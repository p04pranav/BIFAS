# BIFAS — Band Incorporated Finance Analytics System

A high-performance, multi-agent financial and cryptocurrency analysis platform powered by **MiMo-V2.5pro** and orchestrated through **Band.ai** shared rooms.

---

## Overview

BIFAS is a dynamic, multi-agent system that deploys specialized AI analysts to dissect financial queries in real time. Rather than relying on a single LLM response, BIFAS assembles a custom team of domain experts for each query — from trend analysis to on-chain data interpretation — then synthesizes their findings into a pristine executive report.

The entire pipeline is orchestrated sequentially by Streamlit, with agent collaboration logged in a shared Band room for full transparency and auditability.

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
│                   THE ARCHITECT (MiMo)                      │
│          Analyzes query → Returns agent topology            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  BAND.SHARED ROOM                            │
│              (Collaboration & Message Log)                   │
│                                                             │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│   │  Agent 1  │→│  Agent 2  │→│  Agent 3  │→│Synthesizer│  │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│        Each agent reads room history, queries MiMo,         │
│           and posts findings back to the room               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    THE AUDITOR (MiMo)                        │
│          Reviews final report → APPROVED / REJECTED          │
└─────────────────────────────────────────────────────────────┘
```

### Execution Model: Sequential API Orchestration

BIFAS does **not** use background bots, websockets, or async threads. Streamlit acts as the puppeteer:

1. Streamlit queries MiMo-V2.5pro
2. Posts the response to the Band room
3. Reads the updated room history
4. Passes it to the next agent in sequence

This ensures deterministic execution, full observability, and zero race conditions.

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
| **LLM** | MiMo-V2.5pro (via OpenAI-compatible API) |
| **Coordination** | Band SDK (shared rooms) |
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
├── bifas_agents.py       # Agent persona definitions (system prompts)
├── engine.py             # Sequential orchestration pipeline
├── app.py                # Streamlit UI
└── README.md             # This file
```

### File Descriptions

- **`config.py`** — Loads `MIMO_API_KEY` and `BAND_API_KEY` from `.env`. Instantiates the OpenAI client pointing to `https://token-plan-sgp.xiaomimimo.com/v1`.

- **`bifas_agents.py`** — Contains `BIFAS_PERSONAS`, a dictionary mapping agent names to their system prompts. No execution logic.

- **`engine.py`** — The brain. `run_bifas_pipeline(user_query)` executes the full sequential flow: topology generation → room init → collaboration loop → audit.

- **`app.py`** — Streamlit frontend with a dark enterprise terminal aesthetic. Handles user input, triggers the pipeline, and renders results in a two-column layout.

---

## Setup

### Prerequisites

- Python 3.10+
- A MiMo-V2.5pro API key
- A Band.ai API key

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
BAND_API_KEY=your_band_api_key_here
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
4. Watch as the Architect assembles your team, agents collaborate in the Band room, and the Auditor validates the final report

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

## License

Proprietary — All rights reserved.

---

Built with precision by **PranavS**
