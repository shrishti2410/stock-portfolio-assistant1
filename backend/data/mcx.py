"""
mcx.py — Commodity data fetcher

Uses yfinance for international commodity futures (COMEX/NYMEX) which are
always available. Also fetches Indian Gold/Silver ETF prices from NSE.

For MCX-specific prices, tvdatafeed is attempted first but falls back to
international prices with approximate INR conversion.

Public API:
    get_commodity_prices() -> list[dict]
    get_commodity_history(symbol, days) -> dict
"""

import time

import yfinance as yf

_cache: dict[str, dict] = {}
_CACHE_TTL = 300  # 5 minutes

# Commodity definitions with yfinance tickers
COMMODITIES = [
    {"symbol": "GOLD", "yf_ticker": "GC=F", "name": "Gold", "unit": "per troy oz", "currency": "USD", "category": "Precious Metals"},
    {"symbol": "SILVER", "yf_ticker": "SI=F", "name": "Silver", "unit": "per troy oz", "currency": "USD", "category": "Precious Metals"},
    {"symbol": "CRUDEOIL", "yf_ticker": "CL=F", "name": "Crude Oil (WTI)", "unit": "per barrel", "currency": "USD", "category": "Energy"},
    {"symbol": "BRENTOIL", "yf_ticker": "BZ=F", "name": "Brent Crude Oil", "unit": "per barrel", "currency": "USD", "category": "Energy"},
    {"symbol": "NATURALGAS", "yf_ticker": "NG=F", "name": "Natural Gas", "unit": "per mmBtu", "currency": "USD", "category": "Energy"},
    {"symbol": "COPPER", "yf_ticker": "HG=F", "name": "Copper", "unit": "per lb", "currency": "USD", "category": "Base Metals"},
    {"symbol": "PLATINUM", "yf_ticker": "PL=F", "name": "Platinum", "unit": "per troy oz", "currency": "USD", "category": "Precious Metals"},
    {"symbol": "PALLADIUM", "yf_ticker": "PA=F", "name": "Palladium", "unit": "per troy oz", "currency": "USD", "category": "Precious Metals"},
    # Indian ETFs (INR prices, trade on NSE)
    {"symbol": "GOLDBEES", "yf_ticker": "GOLDBEES.NS", "name": "Gold ETF (India)", "unit": "per unit", "currency": "INR", "category": "India ETF"},
    {"symbol": "SILVERBEES", "yf_ticker": "SILVERBEES.NS", "name": "Silver ETF (India)", "unit": "per unit", "currency": "INR", "category": "India ETF"},
]


def get_commodity_list() -> list[dict]:
    """Return list of available commodities."""
    return [{"symbol": c["symbol"], "name": c["name"], "unit": c["unit"],
             "currency": c["currency"], "category": c["category"]}
            for c in COMMODITIES]


def get_commodity_prices() -> list[dict]:
    """Fetch current prices for all commodities."""
    cached = _cache.get("_all_prices")
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    print("[mcx] Fetching commodity prices…")
    results = []

    for commodity in COMMODITIES:
        try:
            ticker = yf.Ticker(commodity["yf_ticker"])
            hist = ticker.history(period="5d")

            if hist.empty:
                results.append({**_base(commodity), "ltp": 0, "error": "No data"})
                continue

            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else latest
            ltp = float(latest["Close"])
            prev_close = float(prev["Close"])
            change = ltp - prev_close
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0

            results.append({
                **_base(commodity),
                "ltp": round(ltp, 2),
                "open": round(float(latest["Open"]), 2),
                "high": round(float(latest["High"]), 2),
                "low": round(float(latest["Low"]), 2),
                "volume": int(latest.get("Volume", 0)),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
            })
        except Exception as exc:
            print(f"[mcx] Error fetching {commodity['symbol']}: {exc}")
            results.append({**_base(commodity), "ltp": 0, "error": str(exc)[:100]})

    _cache["_all_prices"] = {"data": results, "ts": time.time()}
    print(f"[mcx] Fetched {len(results)} commodities")
    return results


def get_commodity_history(symbol: str, days: int = 90) -> dict:
    """Fetch OHLCV history for a single commodity."""
    symbol = symbol.upper().strip()
    cache_key = f"{symbol}_{days}"

    cached = _cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    meta = next((c for c in COMMODITIES if c["symbol"] == symbol), None)
    if not meta:
        valid = [c["symbol"] for c in COMMODITIES]
        raise ValueError(f"Unknown commodity: {symbol}. Valid: {valid}")

    print(f"[mcx] Fetching {days}-day history for {symbol}…")

    period = "3mo" if days <= 90 else ("6mo" if days <= 180 else "1y")
    ticker = yf.Ticker(meta["yf_ticker"])
    hist = ticker.history(period=period)

    if hist.empty:
        raise ValueError(f"No data available for {symbol}")

    hist = hist.tail(days)
    candles = []
    for idx, row in hist.iterrows():
        candles.append({
            "date": idx.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row.get("Volume", 0)),
        })

    ltp = candles[-1]["close"] if candles else 0
    prev = candles[-2]["close"] if len(candles) > 1 else ltp
    change_pct = ((ltp - prev) / prev * 100) if prev > 0 else 0

    result = {
        **_base(meta),
        "ltp": ltp,
        "change_pct": round(change_pct, 2),
        "high_period": round(max(c["high"] for c in candles), 2) if candles else 0,
        "low_period": round(min(c["low"] for c in candles), 2) if candles else 0,
        "candles": candles,
        "data_points": len(candles),
    }

    _cache[cache_key] = {"data": result, "ts": time.time()}
    return result


def _base(commodity: dict) -> dict:
    """Extract base fields from commodity definition."""
    return {
        "symbol": commodity["symbol"],
        "name": commodity["name"],
        "unit": commodity["unit"],
        "currency": commodity["currency"],
        "category": commodity["category"],
    }
