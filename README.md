# BIFAS — Band Incorporated Finance Analytics System

A standalone, multi-agent financial and cryptocurrency analysis platform featuring a **Supervised Dynamic Group Chat Matrix** powered by MiMo-V2.5pro.

---

## Overview

BIFAS is a dynamic, multi-agent system that deploys specialized AI analysts to dissect financial queries through collaborative multi-turn discussions. Rather than relying on a single LLM response, BIFAS dynamically generates a custom team of domain experts for each query, orchestrates their collaborative debate, and synthesizes their findings into a pristine executive report.

**Key Innovation:** The Orchestrator acts as a group chat moderator, dynamically selecting which agent speaks next and judging when the discussion has converged — all within a 5-minute budget enforced by adaptive guardrails.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        STREAMLIT UI                         │
│              [Quick] [Standard] [Deep]                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              ORCHESTRATOR: AGENT SQUAD GENERATION            │
│    Dynamically creates N agents with custom names/prompts    │
│    Output: [{"name": "...", "prompt": "..."}, ...]           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 GROUP CHAT DISCUSSION LOOP                   │
│                   (2 calls per turn)                         │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  Turn N:                                             │   │
│   │    CALL 1: Orchestrator reads history, picks agent   │   │
│   │    CALL 2: Selected agent contributes analysis       │   │
│   │    → Loop detection check                            │   │
│   │    → Convergence check                               │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                              │
│   [REPEAT until convergence or max_turns]                    │
│                                                              │
│   Adaptive Guardrails:                                       │
│     • Dynamic Turn Scaling: max_turns = min(depth, 11)       │
│     • Loop Detection: A->B->A->B or A->A->A->A patterns     │
│     • Soft-Cap Fallback: Synthesize with warning if max hit  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    SYNTHESIS ENGINE                          │
│          Orchestrator compiles final report                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    AUDIT VALIDATION                          │
│          Reviews final report → APPROVED / REJECTED          │
└─────────────────────────────────────────────────────────────┘
```

### 2-Call-Per-Turn Model

Each discussion turn uses exactly 2 API calls:
1. **Orchestrator** reads room history, selects next speaker
2. **Selected agent** reads history, contributes analysis

This ensures predictable performance within the 5-minute budget.

### Adaptive Guardrails

| Guardrail | Mechanism | Action |
|-----------|-----------|--------|
| **Dynamic Turn Scaling** | `max_turns = min(depth, 11)` | Scales with analysis depth |
| **Loop Detection** | Track last 4 speakers | Force convergence if A->B->A->B |
| **Soft-Cap Fallback** | max_turns reached | Synthesize with warning badge |
| **Agent Exhaustion** | All agents return CONVERGED | Natural convergence |
| **Orchestrator Failure** | Empty/invalid response | Fallback to round-robin |

---

## Agent Roster

Agents are **dynamically generated** per query. Example squad for "Analyze BTC trends":

| Agent | Domain |
|-------|--------|
| BTC_Technical_Analyst | Price action, RSI, support/resistance |
| OnChain_Analyst | Exchange flows, whale activity |
| Macro_Economist | Fed policy, inflation, DXY |
| Market_Sentiment_Analyst | Fear/greed, news sentiment |
| Derivatives_Market_Analyst | Options, futures, funding rates |

The Orchestrator designs the optimal squad for each specific query.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **UI** | Streamlit |
| **LLM** | MiMo-V2.5pro (agents) / MiMo-V2.5 (orchestrator) |
| **Coordination** | LocalBandSDK (in-memory rooms) |
| **Language** | Python 3.12+ |
| **Config** | python-dotenv |

---

## Project Structure

```
BIFAS/
├── requirements.txt      # Project dependencies
├── .env                  # API keys (not committed)
├── .gitignore            # Ignored files
├── config.py             # Environment loader + MiMo client
├── bifas_agents.py       # Orchestrator prompts + depth config
├── engine.py             # 2-call pipeline + adaptive guardrails
├── app.py                # Streamlit UI with depth selector
├── TEST_REPORT.md        # Comprehensive test results
└── README.md             # This file
```

### File Descriptions

- **`config.py`** — Loads `MIMO_API_KEY` from `.env`. Instantiates OpenAI client at `https://token-plan-sgp.xiaomimimo.com/v1`.

- **`bifas_agents.py`** — Contains `ORCHESTRATOR_GENERATOR_PROMPT` (squad generation), `AGENT_SPEAK_PROMPT` (agent contribution), `ORCHESTRATOR_SYNTHESIS_PROMPT` (final report), and `DEPTH_CONFIG` (Quick/Standard/Deep).

- **`engine.py`** — The brain. Contains `LocalBandSDK` (in-memory rooms), `DynamicAgentSquad`, `orchestrate_next_agent()`, `agent_speak()`, `detect_loop()`, and `run_bifas_pipeline()` with adaptive guardrails.

- **`app.py`** — Streamlit frontend with depth selector, expandable round display, and guardrail warnings.

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

Create a `.env` file:

```env
MIMO_API_KEY=your_mimo_api_key_here
```

### Run

```bash
streamlit run app.py
```

---

## Usage

1. Launch the app — see the BIFAS terminal interface
2. Select analysis depth:
   - **Quick** (~1.5 min) — 4 turns, fast analysis
   - **Standard** (~3 min) — 7 turns, balanced
   - **Deep** (~5 min) — 11 turns, thorough
3. Enter a financial query, e.g.:
   - `Analyze BTC vs SOL price spikes over the last 7 days`
   - `Perform M&A due diligence on Ethereum ecosystem`
   - `Evaluate DeFi token risks for institutional investment`
4. Click **Initialize BIFAS Run**
5. Watch the group discussion unfold in expandable rounds
6. Review the final synthesized report

---

## API Call Budget

| Depth | Turns | Total Calls | Est. Time |
|-------|-------|-------------|-----------|
| Quick | 4 | 11 | ~2 min |
| Standard | 7 | 17 | ~3.4 min |
| Deep | 11 | 25 | ~5 min |

Budget formula: `3 fixed + (2 × turns) = total calls`

---

## Test Results

See [TEST_REPORT.md](TEST_REPORT.md) for comprehensive test results.

**Summary:**
- ✅ All unit tests pass (LocalBandSDK, DynamicAgentSquad, JSON extraction, loop detection)
- ✅ Full pipeline completes in ~2.2 minutes (Quick depth)
- ✅ Loop detection correctly triggers
- ✅ Deadlock prevention verified for all scenarios
- ✅ 5-minute budget enforced

---

## License

Proprietary — All rights reserved.

---

Built with precision by **PranavS**
