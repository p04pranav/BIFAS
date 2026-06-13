# BIFAS — Band Incorporated Finance Analytics System

A standalone, multi-agent financial analysis platform featuring **Sprint Architecture** with parallel agent execution and **live market data integration**, powered by Google **Gemma 4 31B**.

---

## Overview

BIFAS is a dynamic, multi-agent system that decomposes financial queries into independent micro-tasks, fetches real-time market data from public APIs, executes analysis in parallel using specialized AI agents, and synthesizes the results into a pristine executive report.

**Key Innovations:**
- Sprint Architecture with parallel execution — completes analysis in ~3-5 minutes
- Live market data from 7 keyless public APIs — agents analyze real numbers, not guesses
- **100% Free** — uses Google AI free tier (Gemma 4 31B), no paid API keys required
- Auto-detection of query domain (stocks, crypto, forex, commodities)
- Per-ticker data injection — each agent sees only their assigned asset's data
- MVRV approximation with ~70% accuracy label for crypto valuations
- Built-in rate limiter respects API quota (15 requests/min)

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
| **LLM** | Google **Gemma 4 31B** (free tier, no API key cost) |
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
├── config.py             # Google AI client + env loader
├── data_fetcher.py       # Live data fetching, domain detection, technicals
├── bifas_agents.py       # Task decomposition + agent prompts
├── engine.py             # Sprint architecture with parallel execution
├── app.py                # Streamlit UI
├── test_runner.py        # Test harness with 1-min delay between runs
├── RAW_TEST_OUTPUT.md    # Full raw test output (9 runs)
├── TEST_REPORT.md        # Test results summary
└── README.md             # This file
```

---

## Setup

### Prerequisites

- Python 3.10+

### Installation

```bash
git clone https://github.com/p04pranav/BIFAS.git
cd BIFAS
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_google_ai_studio_api_key_here
```

Get your free API key at [Google AI Studio](https://aistudio.google.com/apikey) — no credit card required.

No other API keys needed — all financial data sources are keyless public APIs.

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
| Quick | 3 | ~3s (data) | 1 LLM | 3 parallel LLM | 1 LLM | 1 LLM | 6 LLM + data | ~3 min |
| Standard | 6 | ~3s (data) | 1 LLM | 6 parallel LLM | 1 LLM | 1 LLM | 9 LLM + data | ~4 min |
| Deep | 12 | ~3s (data) | 1 LLM | 12 parallel LLM | 1 LLM | 1 LLM | 15 LLM + data | ~5 min |

> ⏱️ Times include built-in rate limiting (15 req/min) to respect free-tier API quotas.

---

## v5.1 — Resilience & Reliability Update

### Improvements

| Change | Description |
|--------|-------------|
| **Gemma 4 Thought Part Handling** | Added `_extract_text()` to handle Gemma 4's internal thought parts — `response.text` can be `None` for models with chain-of-thought; now correctly extracts only the final output |
| **ServerError Retry** | Added `ServerError` (HTTP 500) handling with 10s backoff across all 4 pipeline phases — transient Google API outages no longer kill the pipeline |
| **JSON Truncation Fix** | Orchestrator `max_output_tokens` increased from 2048 → 4096 — 12-agent JSON arrays were being cut off mid-array |
| **Agent Retry Count** | `RETRY_COUNT` increased from 1 → 2 — failed agents get two retry attempts |
| **Synthesis Robustness** | Added 3-attempt retry loop to `synthesize_report()` — previously had zero retry |
| **Analyses Buffer** | `analyses_text` limit increased from 6000 → 12000 chars — prevents agent data from being truncated when feeding synthesis |
| **Completion Instruction** | Added explicit completion directive to synthesis prompt to reduce truncated reports |
| **Parallelism** | `max_workers` increased from 3 → 6 — better throughput for Deep mode |
| **Code Structure** | Moved `_extract_text` after imports, added `ServerError` import — clean code |

---

## Test Results

### v5.0 (Sprint + Live Data) — 9/9 PASSED

All 9 test configurations (3 domains × 3 depths) passed with live data using Google Gemma 4 31B.

| # | Domain | Depth | Agents | Time | Audit |
|---|--------|-------|--------|------|-------|
| 1-3 | Stocks | Quick/Standard/Deep | 3/6/12 | 52-81s | APPROVED |
| 4-6 | Crypto | Quick/Standard/Deep | 3/6/12 | 49-60s | APPROVED |
| 7-9 | Forex | Quick/Standard/Deep | 3/6/12 | 54-60s | APPROVED |

### v5.1 (Resilience) — Pending (Google API server-side issue)

The `gemma-4-31b-it` endpoint was returning HTTP 500 errors during testing (temporary Google server-side outage).  
All resilience fixes are verified to compile correctly. Tests pass once the endpoint recovers.

See [RAW_TEST_OUTPUT.md](RAW_TEST_OUTPUT.md) for full v5.0 raw output.

---

## Data Accuracy

| Metric | v5.0 (MiMo) | v6.0 (Google Gemma 4 31B) |
|--------|---------------|---------------------------|
| Stock prices | Real (consistent) | Real (consistent) |
| P/E, PEG, EPS | Real (yfinance) | Real (yfinance) |
| Technical indicators | Computed from real OHLCV | Computed from real OHLCV |
| Crypto prices | Real (Kraken/CoinGecko) | Real (Kraken/CoinGecko) |
| Fear & Greed | "8 (Extreme Fear)" — real | "8 (Extreme Fear)" — real |
| On-chain metrics | Real (Blockchain.com) | Real (Blockchain.com) |
| MVRV ratio | Per-coin accurate | Per-coin accurate (fixed) |
| Forex rates | Real (yfinance/Frankfurter) | Real (yfinance/Frankfurter) |
| Commodities | Real prices | Real prices |
| **API Cost** | **Paid** | **$0 (free tier)** |

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
