import numpy as np
import pandas as pd
import pytest

import data_fetcher as d


@pytest.mark.parametrize("query, domains", [
    ("Analyze NVDA, AAPL, MSFT stock outlook with technicals and valuation", ["stocks"]),
    ("Bitcoin and Ethereum price trends, on-chain metrics, and sentiment", ["crypto"]),
    ("EUR/USD, GBP/USD, USD/JPY forex correlations and macro factors", ["forex"]),
    ("Gold and crude oil price analysis with dollar correlation", ["commodities", "forex"]),
    ("Solana vs Cardano", ["crypto"]),
    # Former substring false positives ('v', 'eth', 'sol', 'eur').
    ("What is a good investment strategy?", ["stocks"]),
    ("Whether to diversify my portfolio", ["stocks"]),
    ("European market solutions", ["stocks"]),
])
def test_detect_domains(query, domains):
    assert d.detect_domains(query) == domains


@pytest.mark.parametrize("query, expected", [
    ("Analyze NVDA, AAPL, MSFT stock outlook", {"stocks": ["NVDA", "AAPL", "MSFT"]}),
    ("What is the outlook for Visa and the S&P 500?", {"stocks": ["V", "SPY"]}),
    ("Analyze V and JPM stocks vs the USD and GDP", {"stocks": ["JPM", "V"]}),
    ("Solana vs Cardano", {"crypto": ["solana", "cardano"]}),
    ("Gold and silver outlook", {"forex": ["EURUSD=X", "GBPUSD=X", "JPY=X"], "commodities": ["GC=F", "SI=F"]}),
])
def test_extract_tickers(query, expected):
    assert d.extract_tickers(query, d.detect_domains(query)) == expected


def _ohlcv(n=90, start=100.0):
    close = start + np.cumsum(np.sin(np.arange(n) / 3.0))
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": 1000}, index=idx)


def test_compute_technicals_columns_are_mapped_correctly():
    t = d.compute_technicals(_ohlcv())
    assert t["bb_lower"] < t["bb_mid"] < t["bb_upper"]
    assert t["macd"] - t["macd_signal"] == pytest.approx(t["macd_hist"], abs=1e-3)
    assert 0 <= t["rsi"] <= 100


def test_commodity_context_has_name_price_and_technicals():
    hist = _ohlcv()
    last = hist.iloc[-1]
    data = {"name": "Gold", "symbol": "GC=F", "price": float(last["Close"]), "open": float(last["Open"]),
            "high": float(last["High"]), "low": float(last["Low"]), "hist": hist}
    ctx = d.format_commodity_context("GC=F", data, d.compute_technicals(hist))
    assert ctx.startswith("REAL MARKET DATA — Gold (GC=F):")
    assert "RSI (14)" in ctx and "1-Month Change" in ctx


@pytest.fixture
def market_data():
    return {
        "stocks": {"V": {"context": "CTX-V"}, "JPM": {"context": "CTX-JPM"}},
        "commodities": {"contexts": {"GC=F": "CTX-GOLD", "CL=F": "CTX-OIL"}},
        "forex": {"contexts": {"EURUSD=X": "CTX-EURUSD", "JPY=X": "CTX-USDJPY"}},
        "crypto": {"contexts": {"bitcoin": "CTX-BTC", "ethereum": "CTX-ETH"}},
    }


@pytest.mark.parametrize("agent, domains, expected", [
    ("Gold_Price_Analyst", ["commodities", "forex"], "CTX-GOLD"),
    ("Crude_Oil_Technical", ["commodities", "forex"], "CTX-OIL"),
    ("EUR_USD_Macro", ["commodities", "forex"], "CTX-EURUSD"),
    ("BTC_OnChain", ["crypto"], "CTX-BTC"),
    ("Ethereum_Sentiment", ["crypto"], "CTX-ETH"),
    ("Visa_Valuation", ["stocks"], "CTX-V"),
    ("JPM_Technical", ["stocks"], "CTX-JPM"),
])
def test_agent_gets_its_own_asset(market_data, agent, domains, expected):
    assert d.get_ticker_data_for_agent(agent, market_data, domains) == expected


def test_single_letter_ticker_needs_whole_word(market_data):
    # 'V' must not match the 'v' inside 'Overview'.
    ctx = d.get_ticker_data_for_agent("Banking_Overview", market_data, ["stocks"])
    assert ctx == "CTX-V\n\nCTX-JPM"


def test_unmatched_agent_gets_all_detected_domains(market_data):
    ctx = d.get_ticker_data_for_agent("Dollar_Correlation", market_data, ["commodities", "forex"])
    for part in ("CTX-GOLD", "CTX-OIL", "CTX-EURUSD", "CTX-USDJPY"):
        assert part in ctx
    assert "CTX-BTC" not in ctx


def test_no_data_message(market_data):
    assert d.get_ticker_data_for_agent("X", {}, ["stocks"]).startswith("No specific market data")
