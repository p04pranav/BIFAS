# BIFAS — Band Incorporated Finance Analytics System

A standalone, multi-agent financial analysis platform featuring **Sprint Architecture** with parallel agent execution and **live market data integration**, powered by MiMo-V2.5pro.

---

## Overview

BIFAS is a dynamic, multi-agent system that decomposes financial queries into independent micro-tasks, fetches real-time market data from public APIs, executes analysis in parallel using specialized AI agents, and synthesizes the results into a pristine executive report.

**Key Innovations:**
- Sprint Architecture with parallel execution — completes analysis in ~1 minute
- Live market data from 7 keyless public APIs — agents analyze real numbers, not guesses
- Auto-detection of query domain (stocks, crypto, forex, commodities)
- Per-ticker data injection — each agent sees only their assigned asset's data
- MVRV approximation with ~70% accuracy label for crypto valuations

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER QUERY                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         PHASE 0: DOMAIN DETECTION + DATA PRE-FETCH          │
│                  (parallel HTTP calls, ~2-3s)                │
│                                                             │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│   │yfinance  │ │ Kraken   │ │CoinGecko │ │Frankfurter│     │
│   │(stocks/  │ │(crypto   │ │(crypto   │ │(forex    │      │
│   │forex/    │ │ OHLCV)   │ │ market)  │ │ rates)   │      │
│   │commodity)│ │          │ │          │ │          │      │
│   └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘      │
│        │            │            │            │              │
│        ▼            ▼            ▼            ▼              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │         pandas-ta: RSI, MACD, SMA, Bollinger        │   │
│   └─────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         PHASE 1: ORCHESTRATOR TASK DECOMPOSITION             │
│                    (1 LLM call)                              │
│    Split query into N independent micro-tasks (max 12)       │
│    Inject per-ticker data into each task                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              PHASE 2: PARALLEL SPRINT EXECUTION              │
│                   (N LLM calls, concurrent)                  │
│                                                             │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│   │ Agent 1  │ │ Agent 2  │ │ Agent 3  │ │ Agent N  │      │
│   │ NVDA     │ │ AAPL     │ │ MSFT     │ │ Macro    │      │
│   │ +data    │ │ +data    │ │ +data    │ │ +data    │      │
│   └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘      │
│        ▼            ▼            ▼            ▼              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              LOCALBANDSDK ROOM                       │   │
│   └─────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              PHASE 3: SYNTHESIS ENGINE (1 LLM call)          │
│              PHASE 4: AUDIT VALIDATION (1 LLM call)          │
└─────────────────────────────────────────────────────────────┘
```

---

## Live Data Sources (All Keyless — No API Keys Required)

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
| **Technicals** | pandas-ta (local) | RSI, MACD, SMA(50/200), Bollinger Bands | Computed from OHLCV |
| **MVRV Approx** | CoinGecko + Blockchain.com | Price/1Y VWAP proxy (~70% accuracy) | Calculated |

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Live Market Data** | Agents analyze real prices, not hallucinated numbers |
| **Auto Domain Detection** | Query automatically classified as stocks/crypto/forex/commodities |
| **Per-Ticker Injection** | Each agent receives only their assigned asset's data |
| **Parallel Execution** | All agents run simultaneously via ThreadPoolExecutor |
| **5-Minute Hard Timeout** | Pipeline never exceeds 300 seconds |
| **Dynamic Task Decomposition** | Orchestrator splits queries into independent micro-tasks |
| **Hybrid Agent Generation** | Mix of domain-based and asset-based agents |
| **Retry Logic** | Failed agents retry once before skipping |
| **Partial Results** | Uses whatever agents complete before timeout |
| **MVRV Approximation** | VWAP-based proxy with ~70% accuracy label |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **UI** | Streamlit |
| **LLM** | MiMo-V2.5pro (agents) / MiMo-V2.5 (orchestrator) |
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

## Project Structure

```
BIFAS/
├── requirements.txt      # Project dependencies
├── .env                  # API keys (not committed)
├── .gitignore            # Ignored files
├── config.py             # Environment loader + MiMo client
├── data_fetcher.py       # Live data fetching, domain detection, technicals
├── bifas_agents.py       # Task decomposition + agent prompts
├── engine.py             # Sprint architecture with parallel execution
├── app.py                # Streamlit UI
├── test_runner.py        # Automated test suite
├── RAW_TEST_OUTPUT.md    # Full raw test output (9 runs)
├── TEST_REPORT.md        # Test results summary
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

No other API keys needed — all data sources are keyless public APIs.

### Run

```bash
streamlit run app.py
```

---

## Usage

1. Launch the app
2. Select analysis depth:
   - **Quick** — 3 agents, ~50s
   - **Standard** — 6 agents, ~55s
   - **Deep** — 12 agents, ~60s
3. Enter a financial query (stocks, crypto, forex, or commodities)
4. Click **Initialize BIFAS Sprint**
5. Watch agents execute in parallel with live data
6. Review the synthesized report with real market numbers

### Example Queries

- "Analyze NVDA, AAPL, MSFT stock outlook with technicals and valuation"
- "Bitcoin and Ethereum price trends, on-chain metrics, and sentiment"
- "EUR/USD, GBP/USD, USD/JPY forex correlations and macro factors"
- "Gold and crude oil price analysis with dollar correlation"

---

## Pipeline Budget

| Depth | Agents | Phase 0 | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Total | Time |
|-------|--------|---------|---------|---------|---------|---------|-------|------|
| Quick | 3 | ~3s (data) | 1 LLM | 3 parallel LLM | 1 LLM | 1 LLM | 6 LLM + data | ~50s |
| Standard | 6 | ~3s (data) | 1 LLM | 6 parallel LLM | 1 LLM | 1 LLM | 9 LLM + data | ~55s |
| Deep | 12 | ~3s (data) | 1 LLM | 12 parallel LLM | 1 LLM | 1 LLM | 15 LLM + data | ~60s |

---

## Test Results

All 9 test configurations (3 domains x 3 depths) passed with live data.

| # | Domain | Depth | Agents | Time | Audit |
|---|--------|-------|--------|------|-------|
| 1 | Stocks | Quick | 3 | 80.1s | APPROVED |
| 2 | Stocks | Standard | 6 | 52.3s | APPROVED |
| 3 | Stocks | Deep | 12 | 60.8s | APPROVED |
| 4 | Crypto | Quick | 3 | 58.4s | APPROVED |
| 5 | Crypto | Standard | 6 | 49.0s | APPROVED |
| 6 | Crypto | Deep | 12 | 59.4s | APPROVED |
| 7 | Forex | Quick | 3 | 54.2s | APPROVED |
| 8 | Forex | Standard | 6 | 54.8s | APPROVED |
| 9 | Forex | Deep | 12 | 59.5s | APPROVED |

See [RAW_TEST_OUTPUT.md](RAW_TEST_OUTPUT.md) for full raw output of all 9 runs.

---

## Data Accuracy Comparison

| Metric | v4.0 (no data) | v5.0 (live data) |
|--------|----------------|-------------------|
| Stock prices | Hallucinated (3 different values) | Real (consistent) |
| P/E, PEG, EPS | Fabricated | Real (yfinance) |
| Technical indicators | Made up | Computed from real OHLCV |
| Crypto prices | Invented | Real (Kraken/CoinGecko) |
| Fear & Greed | "70 (Greed)" | "8 (Extreme Fear)" — real |
| On-chain metrics | Fabricated | Real (Blockchain.com) |
| MVRV ratio | Not mentioned | 0.675 (approx, ~70% accuracy) |
| Forex rates | Hallucinated | Real (yfinance/Frankfurter) |
| Commodities | None | Gold $4,362, Oil $91, Silver $68 |

---

## Credits

| Role | Contributor |
|------|-------------|
| **Finance Concepts & Research** | Kushal H |
| **Implementation & Testing** | Pranav S |

---

## License

Proprietary — All rights reserved.

---

Built with precision by **PranavS** & **KushalH**
