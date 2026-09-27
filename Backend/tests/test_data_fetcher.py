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


def _stock_bundle(ticker, hist):
    last = float(hist["Close"].iloc[-1])
    return {"data": {"ticker": ticker, "name": f"{ticker} Inc.", "price": last, "hist": hist},
            "technicals": d.compute_technicals(hist), "context": f"CTX-{ticker}"}


def test_market_snapshot_shapes_every_domain():
    hist = _ohlcv(60)
    market_data = {
        "stocks": {"AAPL": _stock_bundle("AAPL", hist), "NVDA": _stock_bundle("NVDA", hist)},
        "crypto": {"market": {"bitcoin": {"name": "Bitcoin", "symbol": "BTC", "price": 84700.0, "change_24h": 0.79}},
                   "ohlcv": {"bitcoin": hist}, "technicals": {"bitcoin": {"rsi": 61.2}}},
        "forex": {"ohlcv": {"EURUSD=X": hist}},
        "commodities": {"data": {"GC=F": {"name": "Gold", "price": 4321.2, "hist": hist}}},
    }
    tickers = {"stocks": ["NVDA", "AAPL"]}
    snap = d.market_snapshot(market_data, ["stocks", "crypto", "forex", "commodities"], tickers)
    assert [e["symbol"] for e in snap] == ["NVDA", "AAPL", "BTC", "EURUSD=X", "GC=F"]
    by = {e["symbol"]: e for e in snap}
    assert by["BTC"]["price"] == 84700.0 and by["BTC"]["change_pct"] == 0.79 and by["BTC"]["rsi"] == 61.2
    assert by["EURUSD=X"]["name"] == "EUR/USD" and by["GC=F"]["name"] == "Gold"
    for e in snap:
        assert set(e) == {"symbol", "name", "domain", "price", "change_pct", "rsi", "closes"}
        assert len(e["closes"]) == d.SNAPSHOT_POINTS
        assert e["closes"][-1][1] == pytest.approx(float(hist["Close"].iloc[-1]))
        assert 0 <= e["rsi"] <= 100


def test_market_snapshot_skips_errors_and_is_json_safe():
    import json
    nan_hist = _ohlcv(3)
    nan_hist.loc[nan_hist.index[-1], "Close"] = float("nan")
    market_data = {"stocks": {"BAD": {"data": {"ticker": "BAD", "error": "not found"}},
                              "ODD": _stock_bundle("ODD", _ohlcv(60))},
                   "forex": {"ohlcv": {"EURUSD=X": None, "JPY=X": nan_hist}}}
    snap = d.market_snapshot(market_data, ["stocks", "forex"])
    assert [e["symbol"] for e in snap] == ["ODD", "JPY=X"]
    json.dumps(snap, allow_nan=False)  # no NaN/inf leaks into the API
    assert d.market_snapshot({}, ["stocks", "crypto"]) == []
