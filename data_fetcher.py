import re
import time
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    import pandas_ta as ta
except ImportError:
    ta = None

import requests


DOMAIN_KEYWORDS = {
    "stocks": [
        "stock", "equity", "share", "ticker", "p/e", "earnings", "dividend",
        "valuation", "market cap", "eps", "peg", "52-week",
        "nvda", "nvidia", "aapl", "apple", "msft", "microsoft",
        "googl", "google", "amzn", "amazon", "meta", "tesla", "tsla",
        "jpm", "jpmorgan", "v", "visa", "wmt", "walmart", "unh",
        "spy", "qqq", "dia", "index", "s&p", "nasdaq", "dow"
    ],
    "crypto": [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "on-chain",
        "blockchain", "defi", "hash rate", "staking", "altcoin", "token",
        "coin", "binance", "coinbase", "solana", "sol", "xrp", "ada",
        "doge", "avax", "dot", "matic", "polygon", "uniswap", "aave",
        "fear & greed", "halving", "mining", "wallet"
    ],
    "forex": [
        "forex", "eur/usd", "gbp/usd", "usd/jpy", "usd/chf", "aud/usd",
        "nzd/usd", "usd/cad", "currency", "exchange rate", "fx", "pip",
        "dollar", "euro", "pound", "yen", "franc", "aussie", "kiwi",
        "loonie", "gbp", "eur", "jpy", "chf", "aud", "nzd", "cad",
        "interest rate", "central bank", "fed", "ecb", "boj", "boe"
    ],
    "commodities": [
        "gold", "silver", "oil", "crude", "copper", "platinum", "palladium",
        "natural gas", "commodity", "commodities", "xau", "xag", "wti",
        "brent", "gc=f", "si=f", "cl=f"
    ]
}

TICKER_MAP = {
    "nvidia": "NVDA", "nvda": "NVDA",
    "apple": "AAPL", "aapl": "AAPL",
    "microsoft": "MSFT", "msft": "MSFT",
    "google": "GOOGL", "googl": "GOOGL",
    "amazon": "AMZN", "amzn": "AMZN",
    "meta": "META",
    "tesla": "TSLA", "tsla": "TSLA",
    "jpmorgan": "JPM", "jpm": "JPM",
    "visa": "V", "walmart": "WMT", "wmt": "WMT",
    "unitedhealth": "UNH", "unh": "UNH",
    "spy": "SPY", "qqq": "QQQ",
}

CRYPTO_MAP = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana",
    "ripple": "ripple", "xrp": "ripple",
    "cardano": "cardano", "ada": "cardano",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "avalanche": "avalanche-2", "avax": "avalanche-2",
    "polkadot": "polkadot", "dot": "polkadot",
    "polygon": "matic-network", "matic": "matic-network",
}

KRAKEN_PAIR_MAP = {
    "bitcoin": "XBTUSD", "btc": "XBTUSD",
    "ethereum": "ETHUSD", "eth": "ETHUSD",
    "solana": "SOLUSD", "sol": "SOLUSD",
    "ripple": "XRPUSD", "xrp": "XRPUSD",
    "cardano": "ADAUSD", "ada": "ADAUSD",
    "dogecoin": "DOGEUSD", "doge": "DOGEUSD",
}

FOREX_YF_MAP = {
    "eur/usd": "EURUSD=X", "eurusd": "EURUSD=X",
    "gbp/usd": "GBPUSD=X", "gbpusd": "GBPUSD=X",
    "usd/jpy": "JPY=X", "usdjpy": "JPY=X", "usd-jpy": "JPY=X",
    "usd/chf": "CHF=X", "usdchf": "CHF=X",
    "aud/usd": "AUDUSD=X", "audusd": "AUDUSD=X",
    "nzd/usd": "NZDUSD=X", "nzdusd": "NZDUSD=X",
    "usd/cad": "CAD=X", "usdcad": "CAD=X",
}

COMMODITY_YF_MAP = {
    "gold": "GC=F", "xau": "GC=F",
    "silver": "SI=F", "xag": "SI=F",
    "crude oil": "CL=F", "oil": "CL=F", "wti": "CL=F",
    "brent": "BZ=F",
    "copper": "HG=F",
    "natural gas": "NG=F",
    "platinum": "PL=F",
    "palladium": "PA=F",
}


def detect_domains(query):
    q = query.lower()
    detected = []
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in q)
        if score > 0:
            scores[domain] = score
    if scores:
        detected = sorted(scores, key=scores.get, reverse=True)
    if not detected:
        detected = ["stocks"]
    if "commodities" in detected and len(detected) == 1:
        detected = ["forex", "commodities"]
    return detected


def extract_tickers(query, domains):
    q = query.lower()
    tickers = {}
    if "stocks" in domains or "commodities" in domains:
        stocks = []
        for name, symbol in TICKER_MAP.items():
            if name in q:
                stocks.append(symbol)
        mentioned_caps = re.findall(r'\b([A-Z]{2,5})\b', query)
        for t in mentioned_caps:
            if t not in stocks and t not in ("THE", "AND", "FOR", "WITH", "FROM"):
                stocks.append(t)
        if stocks:
            tickers["stocks"] = list(dict.fromkeys(stocks))
    if "crypto" in domains:
        cryptos = []
        for name, cg_id in CRYPTO_MAP.items():
            if name in q:
                cryptos.append(cg_id)
        if not cryptos:
            cryptos = ["bitcoin", "ethereum"]
        tickers["crypto"] = list(dict.fromkeys(cryptos))
    if "forex" in domains:
        pairs = []
        for name, yf_sym in FOREX_YF_MAP.items():
            if name in q:
                pairs.append(yf_sym)
        if not pairs:
            pairs = ["EURUSD=X", "GBPUSD=X", "JPY=X"]
        tickers["forex"] = list(dict.fromkeys(pairs))
    if "commodities" in domains:
        commodities = []
        for name, yf_sym in COMMODITY_YF_MAP.items():
            if name in q:
                commodities.append(yf_sym)
        if not commodities:
            commodities = ["GC=F", "CL=F"]
        tickers["commodities"] = list(dict.fromkeys(commodities))
    return tickers


def fetch_stock_data(ticker):
    if yf is None:
        return {"ticker": ticker, "error": "yfinance not installed"}
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        hist = t.history(period="3mo")
        if hist.empty:
            hist = t.history(period="1mo")
        return {
            "ticker": ticker,
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "pe_trailing": info.get("trailingPE"),
            "pe_forward": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "eps_trailing": info.get("trailingEps"),
            "eps_forward": info.get("forwardEps"),
            "market_cap": info.get("marketCap"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "high_52w": info.get("fiftyTwoWeekHigh"),
            "low_52w": info.get("fiftyTwoWeekLow"),
            "sma_50": info.get("fiftyDayAverage"),
            "sma_200": info.get("twoHundredDayAverage"),
            "avg_volume": info.get("averageVolume"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "hist": hist,
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def compute_technicals(hist_df):
    if hist_df is None or hist_df.empty or ta is None:
        return {}
    try:
        close = hist_df["Close"]
        rsi_series = ta.rsi(close, length=14)
        macd_result = ta.macd(close)
        bb_result = ta.bbands(close, length=20)
        sma_50 = ta.sma(close, length=50)
        sma_200 = ta.sma(close, length=200)
        result = {
            "rsi": round(float(rsi_series.iloc[-1]), 2) if rsi_series is not None and len(rsi_series) > 0 else None,
            "sma_50": round(float(sma_50.iloc[-1]), 2) if sma_50 is not None and len(sma_50) > 0 else None,
        }
        if macd_result is not None and len(macd_result) > 0:
            result["macd"] = round(float(macd_result.iloc[-1, 0]), 4)
            result["macd_signal"] = round(float(macd_result.iloc[-1, 1]), 4)
            result["macd_hist"] = round(float(macd_result.iloc[-1, 2]), 4)
        if bb_result is not None and len(bb_result) > 0:
            result["bb_upper"] = round(float(bb_result.iloc[-1, 0]), 2)
            result["bb_mid"] = round(float(bb_result.iloc[-1, 1]), 2)
            result["bb_lower"] = round(float(bb_result.iloc[-1, 2]), 2)
        if sma_200 is not None and len(sma_200) > 0 and not pd.isna(sma_200.iloc[-1]):
            result["sma_200"] = round(float(sma_200.iloc[-1]), 2)
        return result
    except Exception:
        return {}


def format_stock_context(ticker, data, technicals):
    if data.get("error"):
        return f"[{ticker}] Data unavailable: {data['error']}"
    lines = [f"REAL MARKET DATA — {ticker}:"]
    lines.append("")
    lines.append("Price & Volume:")
    if data.get("price"):
        lines.append(f"  Current Price: ${data['price']:,.2f}")
    if data.get("high_52w") and data.get("low_52w"):
        lines.append(f"  52-Week Range: ${data['low_52w']:,.2f} - ${data['high_52w']:,.2f}")
    if data.get("avg_volume"):
        lines.append(f"  Avg Volume: {data['avg_volume']:,.0f}")
    lines.append("")
    lines.append("Fundamentals:")
    if data.get("pe_trailing"):
        lines.append(f"  Trailing P/E: {data['pe_trailing']:.2f}")
    if data.get("pe_forward"):
        lines.append(f"  Forward P/E: {data['pe_forward']:.2f}")
    if data.get("peg_ratio"):
        lines.append(f"  PEG Ratio: {data['peg_ratio']:.2f}")
    if data.get("market_cap"):
        mc = data["market_cap"]
        if mc >= 1e12:
            lines.append(f"  Market Cap: ${mc/1e12:.2f}T")
        else:
            lines.append(f"  Market Cap: ${mc/1e9:.2f}B")
    if data.get("eps_trailing"):
        lines.append(f"  Trailing EPS: ${data['eps_trailing']:.2f}")
    if data.get("eps_forward"):
        lines.append(f"  Forward EPS: ${data['eps_forward']:.2f}")
    if data.get("dividend_yield"):
        lines.append(f"  Dividend Yield: {data['dividend_yield']*100:.2f}%")
    if data.get("beta"):
        lines.append(f"  Beta: {data['beta']:.3f}")
    if technicals:
        lines.append("")
        lines.append("Technical Indicators (computed from OHLCV):")
        if technicals.get("rsi"):
            lines.append(f"  RSI (14): {technicals['rsi']}")
        if technicals.get("macd") is not None:
            lines.append(f"  MACD: {technicals['macd']} (Signal: {technicals.get('macd_signal', 'N/A')})")
        if technicals.get("sma_50"):
            lines.append(f"  SMA (50): ${technicals['sma_50']:,.2f}")
        if technicals.get("sma_200"):
            lines.append(f"  SMA (200): ${technicals['sma_200']:,.2f}")
        if technicals.get("bb_upper"):
            lines.append(f"  Bollinger: ${technicals['bb_lower']:,.2f} - ${technicals['bb_upper']:,.2f}")
    hist = data.get("hist")
    if hist is not None and not hist.empty:
        lines.append("")
        lines.append("Recent Price Action (last 5 days):")
        for idx, row in hist.tail(5).iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            lines.append(f"  {date_str}: O={row['Open']:.2f} H={row['High']:.2f} L={row['Low']:.2f} C={row['Close']:.2f}")
    return "\n".join(lines)


def fetch_crypto_ohlcv(pair, days=30):
    try:
        interval = 1440
        r = requests.get("https://api.kraken.com/0/public/OHLC", params={
            "pair": pair, "interval": interval, "limit": min(days, 720)
        }, timeout=10)
        data = r.json()
        if data.get("error"):
            return None
        result_key = list(data["result"].keys())[0]
        candles = data["result"][result_key]
        df = pd.DataFrame(candles, columns=[
            "timestamp", "open", "high", "low", "close", "vwap", "volume", "count"
        ])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        df = df.set_index("timestamp")
        return df[["open", "high", "low", "close", "volume"]].rename(
            columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
        )
    except Exception:
        return None


def fetch_crypto_market(coin_ids):
    try:
        ids_str = ",".join(coin_ids)
        r = requests.get("https://api.coingecko.com/api/v3/simple/price", params={
            "ids": ids_str,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_24hr_vol": "true",
            "include_market_cap": "true"
        }, timeout=10)
        price_data = r.json()
        r2 = requests.get("https://api.coingecko.com/api/v3/coins/markets", params={
            "vs_currency": "usd",
            "ids": ids_str,
            "order": "market_cap_desc",
            "per_page": len(coin_ids),
            "page": 1,
            "sparkline": "false"
        }, timeout=10)
        market_data = r2.json()
        result = {}
        for coin in market_data:
            cid = coin["id"]
            result[cid] = {
                "name": coin.get("name"),
                "symbol": coin.get("symbol", "").upper(),
                "price": coin.get("current_price"),
                "market_cap": coin.get("market_cap"),
                "volume_24h": coin.get("total_volume"),
                "change_24h": coin.get("price_change_percentage_24h"),
                "circulating_supply": coin.get("circulating_supply"),
                "max_supply": coin.get("max_supply"),
                "ath": coin.get("ath"),
                "ath_change_pct": coin.get("ath_change_percentage"),
            }
        return result
    except Exception:
        return {}


def fetch_crypto_onchain():
    result = {}
    try:
        r = requests.get("https://api.blockchain.info/stats", timeout=10)
        stats = r.json()
        result["btc"] = {
            "price_usd": stats.get("market_price_usd"),
            "hash_rate": stats.get("hash_rate"),
            "difficulty": stats.get("difficulty"),
            "total_btc": stats.get("totalbc", 0) / 1e8,
            "n_blocks": stats.get("n_blocks_total"),
            "tx_volume_usd": stats.get("estimated_transaction_volume_usd"),
            "miners_revenue": stats.get("miners_revenue"),
            "trade_volume": stats.get("trade_volume_usd"),
        }
    except Exception:
        pass
    try:
        r = requests.get("https://api.blockchain.info/charts/n-transactions", params={
            "timespan": "30days", "format": "json", "rollingAverage": "1days"
        }, timeout=10)
        tx_data = r.json()
        if tx_data.get("values"):
            result["btc"]["tx_per_day"] = tx_data["values"][-1].get("y")
    except Exception:
        pass
    try:
        r = requests.get("https://api.blockchain.info/charts/n-unique-addresses", params={
            "timespan": "30days", "format": "json", "rollingAverage": "1days"
        }, timeout=10)
        addr_data = r.json()
        if addr_data.get("values"):
            result["btc"]["active_addresses"] = addr_data["values"][-1].get("y")
    except Exception:
        pass
    return result


def fetch_crypto_sentiment():
    try:
        r = requests.get("https://api.alternative.me/fng/", params={
            "limit": "1", "format": "json"
        }, timeout=10)
        data = r.json()["data"][0]
        return {
            "value": int(data["value"]),
            "classification": data["value_classification"]
        }
    except Exception:
        return {"value": None, "classification": "Unknown"}


def fetch_crypto_mvrv(coin_id="bitcoin"):
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart", params={
            "vs_currency": "usd", "days": 365
        }, timeout=10)
        chart = r.json()
        prices = chart.get("prices", [])
        volumes = chart.get("total_volumes", [])
        if not prices or not volumes:
            return {"mvrv_approx": None, "nvt_ratio": None, "confidence": "~70% (VWAP proxy)"}
        total_weighted = 0
        total_vol = 0
        for i in range(len(prices)):
            p = prices[i][1]
            v = volumes[i][1] if i < len(volumes) else 1
            total_weighted += p * v
            total_vol += v
        vwap_1y = total_weighted / total_vol if total_vol > 0 else 0
        current_price = prices[-1][1] if prices else 0
        mvrv_approx = current_price / vwap_1y if vwap_1y > 0 else None
        stats = {}
        try:
            r2 = requests.get("https://api.blockchain.info/stats", timeout=10)
            stats = r2.json()
        except Exception:
            pass
        market_cap = stats.get("market_price_usd", 0) * (stats.get("totalbc", 0) / 1e8)
        tx_vol = stats.get("estimated_transaction_volume_usd", 0)
        nvt = market_cap / tx_vol if tx_vol > 0 else None
        return {
            "mvrv_approx": round(mvrv_approx, 3) if mvrv_approx else None,
            "nvt_ratio": round(nvt, 2) if nvt else None,
            "vwap_1y": round(vwap_1y, 2),
            "confidence": "~70% (VWAP proxy)"
        }
    except Exception:
        return {"mvrv_approx": None, "nvt_ratio": None, "confidence": "~70% (VWAP proxy)"}


def format_crypto_context(coin_id, market, technicals, onchain, sentiment, mvrv):
    lines = [f"REAL MARKET DATA — {market.get('name', coin_id)} ({market.get('symbol', '?')}):"]
    lines.append("")
    lines.append("Market Data (CoinGecko):")
    if market.get("price"):
        lines.append(f"  Price: ${market['price']:,.2f}")
    if market.get("market_cap"):
        mc = market["market_cap"]
        if mc >= 1e12:
            lines.append(f"  Market Cap: ${mc/1e12:.2f}T")
        else:
            lines.append(f"  Market Cap: ${mc/1e9:.2f}B")
    if market.get("volume_24h"):
        lines.append(f"  24h Volume: ${market['volume_24h']:,.0f}")
    if market.get("change_24h") is not None:
        lines.append(f"  24h Change: {market['change_24h']:+.2f}%")
    if market.get("circulating_supply"):
        lines.append(f"  Circulating Supply: {market['circulating_supply']:,.0f}")
    if market.get("max_supply"):
        lines.append(f"  Max Supply: {market['max_supply']:,.0f}")
    if technicals:
        lines.append("")
        lines.append("Technical Indicators (Kraken OHLCV):")
        if technicals.get("rsi"):
            lines.append(f"  RSI (14): {technicals['rsi']}")
        if technicals.get("macd") is not None:
            lines.append(f"  MACD: {technicals['macd']} (Signal: {technicals.get('macd_signal', 'N/A')})")
        if technicals.get("sma_50"):
            lines.append(f"  SMA (50): ${technicals['sma_50']:,.2f}")
        if technicals.get("sma_200"):
            lines.append(f"  SMA (200): ${technicals['sma_200']:,.2f}")
    if onchain and coin_id == "bitcoin" and onchain.get("btc"):
        btc = onchain["btc"]
        lines.append("")
        lines.append("On-Chain Metrics (Blockchain.com):")
        if btc.get("hash_rate"):
            hr = btc["hash_rate"]
            if hr >= 1e9:
                lines.append(f"  Hash Rate: {hr/1e9:.0f} EH/s")
            else:
                lines.append(f"  Hash Rate: {hr:,.0f} GH/s")
        if btc.get("difficulty"):
            lines.append(f"  Mining Difficulty: {btc['difficulty']:,.0f}")
        if btc.get("tx_per_day"):
            lines.append(f"  Transactions/Day: {btc['tx_per_day']:,.0f}")
        if btc.get("active_addresses"):
            lines.append(f"  Active Addresses: {btc['active_addresses']:,.0f}")
    if sentiment and sentiment.get("value") is not None:
        lines.append("")
        lines.append("Sentiment:")
        lines.append(f"  Fear & Greed Index: {sentiment['value']} ({sentiment['classification']})")
    if mvrv and mvrv.get("mvrv_approx") is not None:
        lines.append("")
        lines.append(f"MVRV Analysis (approx, {mvrv.get('confidence', '~70%')}):")
        lines.append(f"  MVRV Proxy (Price / 1Y VWAP): {mvrv['mvrv_approx']:.3f}")
        if mvrv.get("nvt_ratio"):
            lines.append(f"  NVT Ratio: {mvrv['nvt_ratio']:.2f}")
        mvrv_val = mvrv["mvrv_approx"]
        if mvrv_val > 3.5:
            lines.append("  Interpretation: Significantly overvalued (MVRV > 3.5)")
        elif mvrv_val > 2.0:
            lines.append("  Interpretation: Moderately overvalued (MVRV 2.0-3.5)")
        elif mvrv_val > 1.0:
            lines.append("  Interpretation: Slightly above fair value (MVRV 1.0-2.0)")
        elif mvrv_val > 0.8:
            lines.append("  Interpretation: Near fair value (MVRV ~1.0)")
        else:
            lines.append("  Interpretation: Undervalued (MVRV < 0.8)")
    return "\n".join(lines)


def fetch_forex_ohlcv(pairs):
    result = {}
    if yf is None:
        return result
    for pair_sym in pairs:
        try:
            t = yf.Ticker(pair_sym)
            hist = t.history(period="1mo")
            if hist.empty:
                hist = t.history(period="5d")
            result[pair_sym] = hist
        except Exception:
            result[pair_sym] = None
    return result


def fetch_forex_rates(base="USD"):
    try:
        r = requests.get("https://api.frankfurter.dev/v1/latest", params={
            "base": base
        }, timeout=10)
        data = r.json()
        return data.get("rates", {})
    except Exception:
        return {}


def fetch_commodity_data(symbols=None):
    if symbols is None:
        symbols = ["GC=F", "CL=F", "SI=F"]
    result = {}
    if yf is None:
        return result
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="5d")
            info = t.info or {}
            if not hist.empty:
                latest = hist.iloc[-1]
                result[sym] = {
                    "name": COMMODITY_YF_MAP.get(sym, sym),
                    "symbol": sym,
                    "price": float(latest["Close"]),
                    "open": float(latest["Open"]),
                    "high": float(latest["High"]),
                    "low": float(latest["Low"]),
                }
        except Exception:
            pass
    return result


def format_forex_context(pair_yf_sym, ohlcv_df, rates, commodities):
    pair_name = pair_yf_sym.replace("=X", "").replace("=F", "")
    if pair_name == "JPY":
        pair_name = "USD/JPY"
    lines = [f"REAL MARKET DATA — {pair_name}:"]
    lines.append("")
    if ohlcv_df is not None and not ohlcv_df.empty:
        lines.append("Price (yfinance, 15-min delayed):")
        latest = ohlcv_df.iloc[-1]
        lines.append(f"  Current: {latest['Close']:.4f}")
        if len(ohlcv_df) >= 2:
            prev = ohlcv_df.iloc[-2]
            change = ((latest["Close"] - prev["Close"]) / prev["Close"]) * 100
            lines.append(f"  Daily Change: {change:+.2f}%")
        lines.append("")
        lines.append("Technical Indicators:")
        technicals = compute_technicals(ohlcv_df)
        if technicals.get("rsi"):
            lines.append(f"  RSI (14): {technicals['rsi']}")
        if technicals.get("macd") is not None:
            lines.append(f"  MACD: {technicals['macd']} (Signal: {technicals.get('macd_signal', 'N/A')})")
        lines.append("")
        lines.append("Recent Price Action (last 5 days):")
        for idx, row in ohlcv_df.tail(5).iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            lines.append(f"  {date_str}: O={row['Open']:.4f} H={row['High']:.4f} L={row['Low']:.4f} C={row['Close']:.4f}")
    if rates:
        lines.append("")
        lines.append("ECB Exchange Rates (Frankfurter):")
        for currency in ["EUR", "GBP", "JPY", "CHF", "AUD", "CAD"]:
            if currency in rates:
                lines.append(f"  USD/{currency}: {rates[currency]}")
    if commodities:
        lines.append("")
        lines.append("Correlation Context (Commodities):")
        for sym, data in commodities.items():
            if data.get("price"):
                name = data.get("name", sym)
                lines.append(f"  {name}: ${data['price']:,.2f}")
    return "\n".join(lines)


def fetch_all_data(domains, tickers_map):
    market_data = {}
    futures = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        if "stocks" in tickers_map:
            for ticker in tickers_map["stocks"]:
                futures[executor.submit(_fetch_stock_bundle, ticker)] = ("stock", ticker)
        if "crypto" in tickers_map:
            futures[executor.submit(_fetch_crypto_bundle, tickers_map["crypto"])] = ("crypto", None)
        if "forex" in tickers_map:
            futures[executor.submit(_fetch_forex_bundle, tickers_map["forex"])] = ("forex", None)
        if "commodities" in tickers_map:
            futures[executor.submit(fetch_commodity_data, tickers_map.get("commodities"))] = ("commodities", None)
        for future in as_completed(futures):
            key, subkey = futures[future]
            try:
                result = future.result()
                if key == "stock" and subkey:
                    if "stocks" not in market_data:
                        market_data["stocks"] = {}
                    market_data["stocks"][subkey] = result
                elif key == "crypto":
                    market_data["crypto"] = result
                elif key == "forex":
                    market_data["forex"] = result
                elif key == "commodities":
                    market_data["commodities"] = result
            except Exception:
                pass
    return market_data


def _fetch_stock_bundle(ticker):
    data = fetch_stock_data(ticker)
    technicals = compute_technicals(data.get("hist"))
    return {"data": data, "technicals": technicals, "context": format_stock_context(ticker, data, technicals)}


def _fetch_crypto_bundle(coin_ids):
    market = fetch_crypto_market(coin_ids)
    sentiment = fetch_crypto_sentiment()
    mvrv = fetch_crypto_mvrv("bitcoin") if "bitcoin" in coin_ids else {}
    onchain = fetch_crypto_onchain()
    contexts = {}
    for cid in coin_ids:
        kraken_pair = KRAKEN_PAIR_MAP.get(cid)
        technicals = {}
        if kraken_pair:
            ohlcv = fetch_crypto_ohlcv(kraken_pair, 30)
            if ohlcv is not None:
                technicals = compute_technicals(ohlcv)
        coin_market = market.get(cid, {})
        contexts[cid] = format_crypto_context(cid, coin_market, technicals, onchain, sentiment, mvrv)
    return {"market": market, "onchain": onchain, "sentiment": sentiment, "mvrv": mvrv, "contexts": contexts}


def _fetch_forex_bundle(pairs):
    ohlcv = fetch_forex_ohlcv(pairs)
    rates = fetch_forex_rates("USD")
    commodities = fetch_commodity_data(["GC=F", "CL=F", "SI=F"])
    contexts = {}
    for pair_sym in pairs:
        df = ohlcv.get(pair_sym)
        contexts[pair_sym] = format_forex_context(pair_sym, df, rates, commodities)
    return {"ohlcv": ohlcv, "rates": rates, "commodities": commodities, "contexts": contexts}


def get_ticker_data_for_agent(agent_name, market_data, domains):
    name_lower = agent_name.lower()
    if "stocks" in domains and market_data.get("stocks"):
        for ticker, bundle in market_data["stocks"].items():
            if ticker.lower() in name_lower:
                return bundle.get("context", "No data available")
        all_contexts = []
        for ticker, bundle in market_data["stocks"].items():
            ctx = bundle.get("context", "")
            if ctx:
                all_contexts.append(ctx)
        if all_contexts:
            return "\n\n".join(all_contexts)
    if "crypto" in domains and market_data.get("crypto"):
        crypto = market_data["crypto"]
        for cid, ctx in crypto.get("contexts", {}).items():
            symbol = cid.replace("bitcoin", "btc").replace("ethereum", "eth")
            if symbol in name_lower or cid in name_lower:
                return ctx
        all_contexts = list(crypto.get("contexts", {}).values())
        if all_contexts:
            return "\n\n".join(all_contexts)
    if "forex" in domains and market_data.get("forex"):
        forex = market_data["forex"]
        for pair_sym, ctx in forex.get("contexts", {}).items():
            pair_short = pair_sym.replace("=X", "").replace("=F", "").lower()
            if pair_short in name_lower or pair_short.replace("/", "") in name_lower:
                return ctx
        all_contexts = list(forex.get("contexts", {}).values())
        if all_contexts:
            return "\n\n".join(all_contexts)
    return "No specific market data available for this agent."
