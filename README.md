# BIFAS — Band Incorporated Finance Analytics System

A standalone, multi-agent financial analysis platform featuring **Sprint Architecture** with parallel agent execution powered by MiMo-V2.5pro.

---

## Overview

BIFAS is a dynamic, multi-agent system that decomposes financial queries into independent micro-tasks, executes them in parallel using specialized AI agents, and synthesizes the results into a pristine executive report.

**Key Innovation:** Sprint Architecture with parallel execution completes analysis in ~1 minute regardless of complexity, with a hard 5-minute timeout guarantee.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER QUERY                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         PHASE 1: ORCHESTRATOR TASK DECOMPOSITION             │
│                    (1 API call)                              │
│    Split query into N independent micro-tasks (max 12)       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              PHASE 2: PARALLEL SPRINT EXECUTION              │
│                   (N API calls, concurrent)                  │
│                                                              │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│   │ Agent 1  │ │ Agent 2  │ │ Agent 3  │ │ Agent N  │      │
│   │ Task A   │ │ Task B   │ │ Task C   │ │ Task N   │      │
│   └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘      │
│        │            │            │            │              │
│        ▼            ▼            ▼            ▼              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              LOCALBANDSDK ROOM                       │   │
│   │         All results posted here                      │   │
│   └─────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              PHASE 3: SYNTHESIS ENGINE                       │
│                    (1 API call)                              │
│          Orchestrator reads all results, creates report      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              PHASE 4: AUDIT VALIDATION                       │
│                    (1 API call)                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Parallel Execution** | All agents run simultaneously via ThreadPoolExecutor |
| **5-Minute Hard Timeout** | Pipeline never exceeds 300 seconds |
| **Dynamic Task Decomposition** | Orchestrator splits queries into independent micro-tasks |
| **Hybrid Agent Generation** | Mix of domain-based and asset-based agents |
| **Retry Logic** | Failed agents retry once before skipping |
| **Partial Results** | Uses whatever agents complete before timeout |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **UI** | Streamlit |
| **LLM** | MiMo-V2.5pro (agents) / MiMo-V2.5 (orchestrator) |
| **Coordination** | LocalBandSDK (in-memory rooms) |
| **Parallelism** | ThreadPoolExecutor |
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
├── bifas_agents.py       # Task decomposition + agent prompts
├── engine.py             # Sprint architecture with parallel execution
├── app.py                # Streamlit UI
├── TEST_REPORT.md        # Test results
└── README.md             # This file
```

---

## Setup

### Prerequisites

- Python 3.10+
- A MiMo API key

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

1. Launch the app
2. Select analysis depth:
   - **Quick** — 3 agents, ~1 minute
   - **Standard** — 6 agents, ~1 minute
   - **Deep** — 12 agents, ~1 minute
3. Enter a financial query
4. Click **Initialize BIFAS Sprint**
5. Watch agents execute in parallel
6. Review the synthesized report

---

## API Call Budget

| Depth | Agents | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Total | Time |
|-------|--------|---------|---------|---------|---------|-------|------|
| Quick | 3 | 1 | 3 (parallel) | 1 | 1 | 6 | ~48s |
| Standard | 6 | 1 | 6 (parallel) | 1 | 1 | 9 | ~48s |
| Deep | 12 | 1 | 12 (parallel) | 1 | 1 | 15 | ~48s |

---

## Test Results

See [TEST_REPORT.md](TEST_REPORT.md) for comprehensive test results.

---

## License

Proprietary — All rights reserved.

---

Built with precision by **PranavS**
