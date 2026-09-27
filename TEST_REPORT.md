# BIFAS Test Report

## v7.1 — Backend / Frontend split

**Date:** September 27, 2026
**Stack:** FastAPI + Server-Sent Events backend (`Backend/`), vanilla HTML/CSS/JS frontend (`Frontend/`)
**Model:** `gemini-3.5-flash-lite` (fallback `gemma-4-26b-a4b-it`)
**Environment:** Python 3.13, Linux, headless Chromium (Playwright)

### Offline suite

`cd Backend && pytest -q` → **60 passed** (about 6s, no API key or network needed). The 48 v7.0 tests are unchanged; 12 new tests cover:

| Area | What is checked |
|------|-----------------|
| API | `/api/health`, `/api/meta` (depths, usage, examples) |
| Validation | 422 for an empty query, an unknown depth, and a query over 2,000 characters |
| Streaming | SSE events arrive in order (`phase`, `data`, `tasks`, `agent`, `report`, `audit`, `done`); bulky per-agent market data is stripped from the result |
| Errors | A pipeline exception becomes a single `error` event |
| Concurrency | 429 when all run slots are busy; slots are freed after every run |
| Frontend | `Frontend/` is served at `/` |
| Engine events | Phase order, timed-out agents reported as `skipped`, and a crashing listener doesn't break the run |

### Live API run

`curl -N "/api/analyze?query=Gold and crude oil price analysis with dollar correlation&depth=Quick"` streamed data, tasks, three agent results, the report and the audit, then `done`, in **22.3s**. The verdict was APPROVED. A bad depth and an empty query both returned 422.

### Live browser runs

Same query, Quick depth, driven through the dashboard at `http://localhost:5050/`:

| Run | Viewport | Time | Analysts | Steps | Verdict |
|-----|----------|------|----------|-------|---------|
| 1 | 1440×900 | 22.8s | 3/3 done | all 5 done | ✅ Approved |
| 2 | 1440×900 | 23.3s | 3/3 done | all 5 done | ✅ Approved |

- Dollar amounts render correctly in the report (e.g. `$4,321.20`, `$92.41`, `$4,354.55`). The Streamlit UI had mangled these as LaTeX.
- There were no console errors or page errors, and no horizontal scroll at 1440px (desktop) or 1280px (laptop).
- The idle page shows no empty panels. After a run starts, the intro collapses and the page scrolls to the progress timeline.
- The model pill and quota meter showed Gemini 3.5 Flash Lite and the running request count.

The layout targets desktop and laptop screens; phone layouts were intentionally not built or tested.

---

## v7.0 — Gemini 3.5 Flash Lite

**Date:** September 27, 2026
**Model:** `gemini-3.5-flash-lite` (fallback `gemma-4-26b-a4b-it`)
**Environment:** Python 3.13, Linux

### Offline suite

`pytest -q` → **48 passed** at v7.0 (about 4s, no API key or network needed; 60 as of v7.1). Covers domain and ticker detection, indicator column mapping, per-agent data routing, LLM thought and truncation handling, 429 fallback, daily-cap fallback, 5xx retry, rate limiting, auditor verdicts, and the hard timeout with a stuck agent.

### Live runs

| # | Query | Depth | Agents | Time | Model | Audit |
|---|-------|-------|--------|------|-------|-------|
| 1 | NVDA, AAPL, MSFT outlook | Quick | 3/3 | 23.0s | Flash Lite | ✅ APPROVED |
| 2 | Bitcoin & Ethereum trends | Quick | 3/3 | 24.0s | Flash Lite | ✅ APPROVED |
| 3 | EUR/USD, GBP/USD, USD/JPY | Quick | 3/3 | 24.3s | Flash Lite | ✅ APPROVED |
| 4 | Gold & crude oil vs dollar | Quick | 3/3 | 23.7s | Flash Lite | ✅ APPROVED |
| 5 | NVDA, AAPL, MSFT outlook | Deep | 12/12 | 61.2s | Flash Lite | ✅ APPROVED |
| 6 | Bitcoin & Ethereum trends | Standard | 6/6 | 36.2s | Flash Lite | ✅ APPROVED |

No guardrails were triggered. Every agent received its own asset's data (for example, the gold agent got only GC=F data). Reports cited 24–49 real figures each.

**Before (v6.0, Gemma 4 31B), same stocks Quick query:** 356s. It overran the 300s limit without a warning, and the audit returned the model's reasoning instead of a verdict.

**Fallback:** forcing the quota to 0 switched the run to Gemma and the hard timeout held (returned at 240s). Gemma 4 31B was too slow to finish any agent in that window, so the default fallback is now Gemma 4 26B A4B, which was about 4× faster per call. The fallback switching logic is covered by the offline tests; a live end-to-end fallback run on 26B was not completed.

---

# Historical: v5.0

## Sprint Architecture with Live Market Data

**Date:** June 8, 2026  
**Version:** 5.0.0 — Sprint Architecture + Live Data Integration  
**Environment:** Python 3.12, Linux  

---

## Executive Summary

BIFAS v5.0 integrates **live market data from 7 keyless public APIs** into the Sprint Architecture pipeline. Agents now analyze real prices, technical indicators, on-chain metrics, and sentiment data instead of relying on LLM training knowledge. All 9 test configurations (3 domains x 3 depths) pass with APPROVED audit status.

**Overall Status: ALL 9 TESTS PASSED**

---

## Architecture: v4.0 → v5.0 Changes

### New: Phase 0 — Domain Detection + Data Pre-Fetch

| Component | Implementation |
|-----------|---------------|
| Domain Detection | Keyword-based classifier (stocks/crypto/forex/commodities) |
| Ticker Extraction | Regex + keyword map for auto-detecting assets from query |
| Data Pre-Fetch | Parallel HTTP calls via ThreadPoolExecutor (~2-3s) |
| Technical Computation | pandas-ta: RSI, MACD, SMA(50/200), Bollinger Bands |
| Per-Ticker Injection | Each agent receives only their assigned asset's data |
| MVRV Approximation | VWAP proxy (~70% accuracy) with confidence label |

### Data Sources (All Keyless — No API Keys)

| Source | Domain | Endpoint | Auth |
|--------|--------|----------|------|
| yfinance | Stocks, Forex, Commodities | Yahoo Finance internal | None |
| Kraken | Crypto OHLCV | api.kraken.com/0/public/ | None |
| CoinGecko | Crypto Market | api.coingecko.com/api/v3/ | None |
| Blockchain.com | BTC On-Chain | api.blockchain.info/ | None |
| Alternative.me | Sentiment | api.alternative.me/fng/ | None |
| Frankfurter | Forex Rates | api.frankfurter.dev/v1/ | None |
| pandas-ta | Technical Indicators | Local computation | None |

---

## Test Results

### Pipeline Performance

| # | Domain | Depth | Agents | Time | Audit | Data Sources |
|---|--------|-------|--------|------|-------|-------------|
| 1 | Stocks | Quick | 3 | 80.1s | APPROVED | stocks |
| 2 | Stocks | Standard | 6 | 52.3s | APPROVED | stocks |
| 3 | Stocks | Deep | 12 | 60.8s | APPROVED | stocks |
| 4 | Crypto | Quick | 3 | 58.4s | APPROVED | crypto |
| 5 | Crypto | Standard | 6 | 49.0s | APPROVED | crypto |
| 6 | Crypto | Deep | 12 | 59.4s | APPROVED | crypto |
| 7 | Forex | Quick | 3 | 54.2s | APPROVED | forex |
| 8 | Forex | Standard | 6 | 54.8s | APPROVED | forex |
| 9 | Forex | Deep | 12 | 59.5s | APPROVED | forex |

**Total Duration:** 528.6s (8.8 min)  
**Average per Run:** 58.7s

### Data Accuracy: v4.0 vs v5.0

| Metric | v4.0 (no data) | v5.0 (live data) |
|--------|----------------|-------------------|
| NVDA price | Hallucinated ($131, $903, $131) | Real ($208.92, consistent) |
| BTC price | Hallucinated ($52K-$57K) | Real ($63,353) |
| EUR/USD | Hallucinated (1.0815) | Real (1.1538) |
| RSI values | Fabricated | Computed from real OHLCV |
| P/E ratios | Made up | Real (yfinance) |
| Fear & Greed | "70 (Greed)" | "8 (Extreme Fear)" — real |
| MVRV | Not mentioned | 0.675 (approx, labeled ~70%) |
| Commodities | None | Gold $4,362, Oil $91, Silver $68 |

---

## Bugs Fixed in v5.0

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| Unescaped `{}` in prompts | JSON examples in ORCHESTRATOR_DECOMPOSITION_PROMPT conflicted with `.format()` | Escaped to `{{}}` in bifas_agents.py |
| Token truncation | `max_tokens=3000` too low for 6/12-agent JSON | Increased to `6000` in engine.py |
| Quick mode data injection | Generic agent names didn't match tickers, fell back to first ticker only | Changed fallback to return ALL tickers' data |

---

## Dependencies

### requirements.txt

```
streamlit
openai
python-dotenv
yfinance>=1.4.0
pandas-ta>=0.3.14b
requests>=2.31.0
```

### Environment Variables

```env
MIMO_API_KEY=your_mimo_api_key_here
```

No other API keys required.

---

## File Compliance

| File | Status | Changes |
|------|--------|---------|
| requirements.txt | Updated | Added yfinance, pandas-ta, requests |
| .env | OK | MIMO_API_KEY only |
| config.py | OK | MiMo client configured |
| data_fetcher.py | NEW | Domain detection, 7 API integrations, technicals, formatting |
| bifas_agents.py | Updated | Added {market_data} to AGENT_TASK_PROMPT |
| engine.py | Updated | Phase 0 data pre-fetch, modified execute_agent_task |
| app.py | OK | Streamlit UI |
| test_runner.py | Updated | v5.0 headers, data sources in metrics |
| TEST_REPORT.md | Updated | This file |
| README.md | Updated | v5.0 architecture, data sources, examples |

---

## Test Queries

| Domain | Query |
|--------|-------|
| Stocks | "Analyze the current outlook for NVIDIA (NVDA), Apple (AAPL), and Microsoft (MSFT) stocks including technical indicators, valuation metrics, and growth prospects" |
| Crypto | "Analyze Bitcoin (BTC) and Ethereum (ETH) price trends, on-chain metrics, and market sentiment for the current quarter" |
| Forex | "Analyze Forex correlations and trends between EUR/USD, GBP/USD, and USD/JPY pairs including macroeconomic factors" |

---

## Conclusion

BIFAS v5.0 successfully integrates live market data from 7 keyless public APIs:

- **Stocks:** Real prices, P/E, PEG, EPS, technical indicators from yfinance + pandas-ta
- **Crypto:** Real prices from Kraken/CoinGecko, on-chain from Blockchain.com, sentiment from Alternative.me
- **Forex:** Real rates from yfinance/Frankfurter, commodity correlation context
- **MVRV:** Approximate VWAP proxy with ~70% accuracy label

All 9 test configurations pass. Reports now cite consistent, verifiable, real market data. The Sprint Architecture maintains ~58s average execution time with the addition of ~2-3s data pre-fetch.

---

**Built in collaboration with:**  
- **Kushal H** — Finance Concepts & Research  
- **Pranav S** — Implementation & Testing  

**Test Engineer:** Pranav S  
**Date:** June 8, 2026
