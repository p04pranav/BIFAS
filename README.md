<div align="center">

# 📊 BIFAS

### Band Incorporated Finance Analytics System

**Multi-agent financial intelligence with Sprint Architecture — live market data, parallel execution, zero cost.**

![Python](https://img.shields.io/badge/Python_3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![Gemma 4](https://img.shields.io/badge/Gemma_4_31B-4285F4?style=flat-square&logo=google&logoColor=white)
![License](https://img.shields.io/badge/License-Proprietary-red?style=flat-square)
![APIs](https://img.shields.io/badge/Data_Sources-7_Keyless_APIs-00C853?style=flat-square)
![Tests](https://img.shields.io/badge/Tests-9%2F9_Passed-brightgreen?style=flat-square)
![Cost](https://img.shields.io/badge/Cost-%240-gold?style=flat-square)

<br/>

*A dynamic multi-agent system that decomposes financial queries into independent micro-tasks, fetches real-time market data from **7 keyless public APIs** (stocks, crypto, forex, commodities), executes analysis in parallel using specialized AI agents powered by **Google Gemma 4 31B**, and synthesizes results into executive-grade reports — all for **\$0**.*

</div>

---

## 🔑 Key Innovations

| | Innovation | Detail |
|---|-----------|--------|
| ⚡ | **Sprint Architecture** | Parallel agent execution — completes analysis in ~3-5 minutes |
| 📡 | **7 Keyless APIs** | Live market data — agents analyze real numbers, not hallucinations |
| 💸 | **100% Free** | Google AI free tier (Gemma 4 31B), no paid API keys required |
| 🎯 | **Auto Domain Detection** | Queries auto-classified as stocks / crypto / forex / commodities |
| 💉 | **Per-Ticker Injection** | Each agent sees only their assigned asset's real data |
| 📈 | **MVRV Approximation** | VWAP-based proxy with ~70% accuracy label for crypto valuations |
| 🛡️ | **Rate Limiter** | Built-in 15 req/min throttle respects free-tier API quotas |

---

## 🏗️ Architecture

### Sprint Pipeline Overview

```mermaid
graph TB
    User(("👤 User Query"))

    subgraph Phase0["⚡ PHASE 0 — Domain Detection + Data Pre-Fetch (~2-3s)"]
        direction TB
        DD["🎯 Domain Detector<br/>Keyword Classifier"]
        TE["🔍 Ticker Extractor<br/>Regex + Keyword Map"]
        
        subgraph DataSources["📡 Parallel HTTP Calls"]
            direction LR
            YF["📈 yfinance<br/>Stocks / Forex /<br/>Commodities"]
            KR["🔷 Kraken<br/>Crypto OHLCV"]
            CG["🟢 CoinGecko<br/>Crypto Market"]
            FR["🇪🇺 Frankfurter<br/>Forex Rates"]
            BC["⛓️ Blockchain.com<br/>BTC On-Chain"]
            AM["😱 Alternative.me<br/>Fear & Greed"]
        end

        TA["📊 pandas-ta<br/>RSI · MACD · SMA · Bollinger"]
    end

    subgraph Phase1["🧠 PHASE 1 — Orchestrator Decomposition (1 LLM call)"]
        ORC["🎭 Orchestrator<br/>Split → N micro-tasks (max 12)<br/>Inject per-ticker data"]
    end

    subgraph Phase2["🚀 PHASE 2 — Parallel Sprint Execution (N LLM calls)"]
        direction LR
        A1["🤖 Agent 1<br/>NVDA + data"]
        A2["🤖 Agent 2<br/>AAPL + data"]
        A3["🤖 Agent 3<br/>MSFT + data"]
        AN["🤖 Agent N<br/>Macro + data"]
    end

    subgraph Phase3["📝 PHASE 3 — Synthesis + Audit (2 LLM calls)"]
        SYN["✍️ Synthesis Engine<br/>Executive Report"]
        AUD["🔍 Auditor<br/>Quality Validation"]
    end

    ROOM["💬 LocalBandSDK Room<br/>In-Memory Message Bus"]
    Report(("📋 Final Report"))

    User --> DD
    DD --> TE
    TE --> DataSources
    DataSources --> TA
    TA --> Phase1
    ORC --> Phase2
    A1 & A2 & A3 & AN --> ROOM
    ROOM --> SYN
    SYN --> AUD
    AUD --> Report

    style Phase0 fill:#0d1117,stroke:#00d4aa,stroke-width:2px,color:#fff
    style Phase1 fill:#0d1117,stroke:#a78bfa,stroke-width:2px,color:#fff
    style Phase2 fill:#0d1117,stroke:#f59e0b,stroke-width:2px,color:#fff
    style Phase3 fill:#0d1117,stroke:#60a5fa,stroke-width:2px,color:#fff
    style DataSources fill:#1a1a2e,stroke:#00d4aa,stroke-width:1px,color:#fff
    style User fill:#4285F4,stroke:#fff,stroke-width:2px,color:#fff
    style Report fill:#00C853,stroke:#fff,stroke-width:2px,color:#fff
    style ROOM fill:#1e3a5f,stroke:#60a5fa,stroke-width:1px,color:#fff
    style DD fill:#1a3c34,stroke:#34d399,stroke-width:1px,color:#fff
    style TE fill:#1a3c34,stroke:#34d399,stroke-width:1px,color:#fff
    style TA fill:#1a3c34,stroke:#34d399,stroke-width:1px,color:#fff
    style ORC fill:#2d1b69,stroke:#a78bfa,stroke-width:1px,color:#fff
    style A1 fill:#3b2f1e,stroke:#fbbf24,stroke-width:1px,color:#fff
    style A2 fill:#3b2f1e,stroke:#fbbf24,stroke-width:1px,color:#fff
    style A3 fill:#3b2f1e,stroke:#fbbf24,stroke-width:1px,color:#fff
    style AN fill:#3b2f1e,stroke:#fbbf24,stroke-width:1px,color:#fff
    style SYN fill:#1e3a5f,stroke:#60a5fa,stroke-width:1px,color:#fff
    style AUD fill:#1e3a5f,stroke:#60a5fa,stroke-width:1px,color:#fff
    style YF fill:#1a3c34,stroke:#34d399,stroke-width:1px,color:#fff
    style KR fill:#1a3c34,stroke:#34d399,stroke-width:1px,color:#fff
    style CG fill:#1a3c34,stroke:#34d399,stroke-width:1px,color:#fff
    style FR fill:#1a3c34,stroke:#34d399,stroke-width:1px,color:#fff
    style BC fill:#1a3c34,stroke:#34d399,stroke-width:1px,color:#fff
    style AM fill:#1a3c34,stroke:#34d399,stroke-width:1px,color:#fff
```

### Agent Execution Model

```mermaid
flowchart LR
    subgraph Input["📥 Input"]
        Q["User Query"]
    end

    subgraph Detection["🎯 Detection"]
        D1["Stocks"]
        D2["Crypto"]
        D3["Forex"]
        D4["Commodities"]
    end

    subgraph Depth["⚙️ Depth Config"]
        Quick["⚡ Quick<br/>3 agents · ~50s"]
        Standard["📊 Standard<br/>6 agents · ~55s"]
        Deep["🔬 Deep<br/>12 agents · ~60s"]
    end

    subgraph Execution["🚀 ThreadPoolExecutor"]
        P["Parallel LLM Calls<br/>+ Rate Limiter (15/min)<br/>+ Retry (2 attempts)<br/>+ 5-min Hard Timeout"]
    end

    subgraph Output["📋 Output"]
        R["Executive Report<br/>with Real Data"]
    end

    Q --> D1 & D2 & D3 & D4
    D1 & D2 & D3 & D4 --> Quick & Standard & Deep
    Quick & Standard & Deep --> P
    P --> R

    style Input fill:#0d1117,stroke:#a78bfa,stroke-width:2px,color:#fff
    style Detection fill:#0d1117,stroke:#00d4aa,stroke-width:2px,color:#fff
    style Depth fill:#0d1117,stroke:#f59e0b,stroke-width:2px,color:#fff
    style Execution fill:#0d1117,stroke:#ef4444,stroke-width:2px,color:#fff
    style Output fill:#0d1117,stroke:#60a5fa,stroke-width:2px,color:#fff
    style Q fill:#2d1b69,stroke:#a78bfa,stroke-width:1px,color:#fff
    style D1 fill:#1a3c34,stroke:#34d399,stroke-width:1px,color:#fff
    style D2 fill:#1a3c34,stroke:#34d399,stroke-width:1px,color:#fff
    style D3 fill:#1a3c34,stroke:#34d399,stroke-width:1px,color:#fff
    style D4 fill:#1a3c34,stroke:#34d399,stroke-width:1px,color:#fff
    style Quick fill:#3b2f1e,stroke:#fbbf24,stroke-width:1px,color:#fff
    style Standard fill:#3b2f1e,stroke:#fbbf24,stroke-width:1px,color:#fff
    style Deep fill:#3b2f1e,stroke:#fbbf24,stroke-width:1px,color:#fff
    style P fill:#3b1c1c,stroke:#ef4444,stroke-width:1px,color:#fff
    style R fill:#1e3a5f,stroke:#60a5fa,stroke-width:1px,color:#fff
```

### Module Dependency Graph

```mermaid
graph TD
    APP["🖥️ app.py<br/>Streamlit UI"]
    ENG["⚙️ engine.py<br/>Sprint Architecture"]
    AGT["🤖 bifas_agents.py<br/>Prompts + Config"]
    DAT["📡 data_fetcher.py<br/>7 API Integrations"]
    CFG["🔧 config.py<br/>Google AI Client"]

    APP -->|"run_bifas_pipeline()"| ENG
    APP -->|"DEPTH_CONFIG"| AGT
    ENG -->|"prompts"| AGT
    ENG -->|"fetch data"| DAT
    ENG -->|"LLM client"| CFG

    subgraph External["☁️ External Services"]
        GEMMA["🧠 Google Gemma 4 31B"]
        APIS["📡 7 Keyless APIs"]
    end

    CFG -.->|"google.genai"| GEMMA
    DAT -.->|"HTTP requests"| APIS

    style APP fill:#2d1b69,stroke:#a78bfa,stroke-width:2px,color:#fff
    style ENG fill:#1a3c34,stroke:#34d399,stroke-width:2px,color:#fff
    style AGT fill:#3b2f1e,stroke:#fbbf24,stroke-width:1px,color:#fff
    style DAT fill:#3b2f1e,stroke:#fbbf24,stroke-width:1px,color:#fff
    style CFG fill:#3b2f1e,stroke:#fbbf24,stroke-width:1px,color:#fff
    style External fill:#0d1117,stroke:#60a5fa,stroke-width:2px,color:#fff
    style GEMMA fill:#1e3a5f,stroke:#60a5fa,stroke-width:1px,color:#fff
    style APIS fill:#1e3a5f,stroke:#60a5fa,stroke-width:1px,color:#fff
```

---

## 📡 Live Data Sources

> All data sources are **keyless** — no API keys, no sign-ups, no cost.

| Domain | Provider | Data | Freshness |
|--------|----------|------|-----------|
| **Stocks** | yfinance | Price, P/E, PEG, EPS, market cap, 52wk range, OHLCV | 15-min delayed |
| **Crypto OHLCV** | Kraken | BTC/ETH candles (real-time) | Real-time |
| **Crypto Market** | CoinGecko | Price, mcap, volume, supply, 24h change | ~60s cache |
| **Crypto On-Chain** | Blockchain.com | Hash rate, tx count, difficulty, active addresses | ~10min |
| **Crypto Sentiment** | Alternative.me | Fear & Greed Index (0-100) | Daily |
| **Forex OHLCV** | yfinance | EUR/USD, GBP/USD, USD/JPY candles | 15-min delayed |
| **Forex Rates** | Frankfurter | ECB rates, 30 currencies, historical from 1948 | Daily |
| **Commodities** | yfinance | Gold, Oil, Silver (GC=F, CL=F, SI=F) | 15-min delayed |
| **Technicals** | pandas-ta (local) | RSI, MACD, SMA(50/200), Bollinger Bands | Computed |
| **MVRV Approx** | CoinGecko + Blockchain.com | Price/1Y VWAP proxy (~70% accuracy) | Calculated |

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📡 **Live Market Data** | Agents analyze real prices, not hallucinated numbers |
| 🎯 **Auto Domain Detection** | Query automatically classified as stocks/crypto/forex/commodities |
| 💉 **Per-Ticker Injection** | Each agent receives only their assigned asset's data |
| 🚀 **Parallel Execution** | All agents run simultaneously via `ThreadPoolExecutor` |
| ⏱️ **5-Minute Hard Timeout** | Pipeline never exceeds 300 seconds |
| 🧠 **Dynamic Task Decomposition** | Orchestrator splits queries into independent micro-tasks |
| 🔄 **Hybrid Agent Generation** | Mix of domain-based and asset-based agents |
| 🛡️ **Retry Logic** | Failed agents retry twice with `ServerError` backoff |
| 📊 **Partial Results** | Uses whatever agents complete before timeout |
| 📈 **MVRV Approximation** | VWAP-based proxy with ~70% accuracy label |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **UI** | Streamlit |
| **LLM** | Google **Gemma 4 31B** (free tier, \$0) |
| **Stock/Forex/Commodity Data** | yfinance |
| **Crypto OHLCV** | Kraken API |
| **Crypto Market Data** | CoinGecko API |
| **BTC On-Chain** | Blockchain.com API |
| **Sentiment** | Alternative.me API |
| **Forex Rates** | Frankfurter API |
| **Technical Indicators** | pandas-ta |
| **Coordination** | LocalBandSDK (in-memory rooms) |
| **Parallelism** | ThreadPoolExecutor |
| **Language** | Python 3.10+ |
| **Config** | python-dotenv |

---

## 📁 Project Structure

```
BIFAS/
├── app.py                 # Streamlit UI — dark terminal aesthetic
├── engine.py              # Sprint architecture — orchestration, parallel execution, synthesis
├── bifas_agents.py        # Prompt templates + depth config (Quick/Standard/Deep)
├── data_fetcher.py        # 7 API integrations, domain detection, ticker extraction, technicals
├── config.py              # Google AI client initialization + env loader
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable template
├── .gitignore             # Ignored files
├── TEST_REPORT.md         # Test results summary (9/9 passed)
├── RAW_TEST_OUTPUT.md     # Full raw test output (9 runs)
└── README.md              # This file
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- A free **Google Gemini API key** — [Get one here](https://aistudio.google.com/apikey) (no credit card required)

> **That's it.** No other API keys needed — all 7 financial data sources are keyless public APIs.

### Installation

```bash
# Clone the repository
git clone https://github.com/p04pranav/BIFAS.git
cd BIFAS

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your Google AI Studio API key
```

### Run

```bash
streamlit run app.py
```

---

## 🎮 Usage

1. **Launch** the app — opens a dark terminal-styled interface
2. **Select depth:**

   | Depth | Agents | Time | Best For |
   |-------|--------|------|----------|
   | ⚡ **Quick** | 3 | ~50s | Fast overviews |
   | 📊 **Standard** | 6 | ~55s | Balanced analysis |
   | 🔬 **Deep** | 12 | ~60s | Comprehensive research |

3. **Enter a query** — natural language, any financial domain
4. **Click** "Initialize BIFAS Sprint"
5. **Watch** agents execute in parallel with live data injection
6. **Review** the synthesized executive report with real market numbers

### Example Queries

```
📈 "Analyze NVDA, AAPL, MSFT stock outlook with technicals and valuation"
₿  "Bitcoin and Ethereum price trends, on-chain metrics, and sentiment"
💱 "EUR/USD, GBP/USD, USD/JPY forex correlations and macro factors"
🥇 "Gold and crude oil price analysis with dollar correlation"
```

---

## ⏱️ Pipeline Budget

| Depth | Agents | Phase 0 | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Total LLM | Time |
|-------|--------|---------|---------|---------|---------|---------|-----------|------|
| ⚡ Quick | 3 | ~3s (data) | 1 LLM | 3 parallel | 1 LLM | 1 LLM | 6 + data | ~3 min |
| 📊 Standard | 6 | ~3s (data) | 1 LLM | 6 parallel | 1 LLM | 1 LLM | 9 + data | ~4 min |
| 🔬 Deep | 12 | ~3s (data) | 1 LLM | 12 parallel | 1 LLM | 1 LLM | 15 + data | ~5 min |

> ⏱️ Times include built-in rate limiting (15 req/min) to respect free-tier API quotas.

---

## ✅ Test Results

### v5.0 (Sprint + Live Data) — 9/9 PASSED

All 9 test configurations (3 domains × 3 depths) passed with live data using Google Gemma 4 31B.

| # | Domain | Depth | Agents | Time | Audit |
|---|--------|-------|--------|------|-------|
| 1-3 | 📈 Stocks | Quick / Standard / Deep | 3 / 6 / 12 | 52-81s | ✅ APPROVED |
| 4-6 | ₿ Crypto | Quick / Standard / Deep | 3 / 6 / 12 | 49-60s | ✅ APPROVED |
| 7-9 | 💱 Forex | Quick / Standard / Deep | 3 / 6 / 12 | 54-60s | ✅ APPROVED |

**Total Duration:** 528.6s (8.8 min) · **Average per Run:** 58.7s

### Data Accuracy: v4.0 → v5.0 → v6.0

| Metric | v4.0 (no data) | v5.0+ (live data) |
|--------|----------------|-------------------|
| Stock prices | ❌ Hallucinated | ✅ Real (consistent) |
| P/E, PEG, EPS | ❌ Guessed | ✅ Real (yfinance) |
| Technical indicators | ❌ None | ✅ Computed from real OHLCV |
| Crypto prices | ❌ Hallucinated | ✅ Real (Kraken/CoinGecko) |
| Fear & Greed | ❌ None | ✅ Real (Alternative.me) |
| On-chain metrics | ❌ None | ✅ Real (Blockchain.com) |
| MVRV ratio | ❌ None | ✅ Per-coin accurate |
| Forex rates | ❌ Guessed | ✅ Real (yfinance/Frankfurter) |
| Commodities | ❌ Hallucinated | ✅ Real prices |
| **API Cost** | — | **\$0 (free tier)** |

See [TEST_REPORT.md](TEST_REPORT.md) and [RAW_TEST_OUTPUT.md](RAW_TEST_OUTPUT.md) for full details.

---

## 📋 Changelog

### v5.1 — Resilience & Reliability

| Change | Description |
|--------|-------------|
| **Thought Part Handling** | `_extract_text()` handles Gemma 4's internal chain-of-thought parts |
| **ServerError Retry** | HTTP 500 handling with 10s backoff across all 4 pipeline phases |
| **JSON Truncation Fix** | `max_output_tokens` increased 2048 → 4096 for 12-agent arrays |
| **Agent Retry Count** | `RETRY_COUNT` increased 1 → 2 for better resilience |
| **Synthesis Robustness** | 3-attempt retry loop on `synthesize_report()` |
| **Analyses Buffer** | `analyses_text` limit 6000 → 12000 chars |
| **Parallelism** | `max_workers` increased 3 → 6 for Deep mode throughput |

### v6.0 — Google Gemma 4 31B Migration

Migrated from MiMo to Google Gemma 4 31B — same live data pipeline, **\$0 cost**.

---

## 🤝 Contributing

Contributions are welcome! Feel free to:

- 🐛 Report bugs via [GitHub Issues](https://github.com/p04pranav/BIFAS/issues)
- 🔀 Submit pull requests for new features
- 💡 Suggest new data sources or analysis domains

---

## 📄 License

Proprietary — All rights reserved.

---

## 👨‍💻 Credits

| Role | Contributor |
|------|-------------|
| **Finance Concepts & Research** | **Kushal H** |
| **Implementation & Testing** | **Pranav S** |

---

<div align="center">

**Built with precision by Pranav S & Kushal H**

[⬆ Back to Top](#-bifas)

</div>
