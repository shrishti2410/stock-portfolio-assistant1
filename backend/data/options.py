"""
options.py — NSE Option Chain data fetcher using nsepython

Public API:
    get_option_chain(symbol) -> dict   (full option chain for stock/index)
    get_option_symbols() -> list       (symbols that have options)
"""

import time
import json

_cache: dict[str, dict] = {}
_CACHE_TTL = 180  # 3 minutes (NSE rate-limits aggressively)


def get_option_chain(symbol: str) -> dict:
    """
    Fetch the full NSE option chain for a stock or index.

    Returns dict with:
        symbol, expiry_dates, spot_price, records (list of strike data)
    Each record: strikePrice, CE/PE with OI, changeInOI, volume, IV, LTP, bid/ask
    """
    symbol = symbol.upper().strip()

    # Cache check
    cached = _cache.get(symbol)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    data = _fetch_option_chain(symbol)
    _cache[symbol] = {"data": data, "ts": time.time()}
    return data


def _fetch_option_chain(symbol: str) -> dict:
    """Fetch from NSE via nsepython."""
    from nsepython import nse_optionchain_scrapper

    print(f"[options] Fetching option chain for {symbol}…")
    raw = nse_optionchain_scrapper(symbol)

    if not raw or "records" not in raw or not raw.get("records", {}).get("data"):
        return {
            "symbol": symbol,
            "spot_price": raw.get("records", {}).get("underlyingValue", 0) if raw else 0,
            "expiry_dates": [],
            "total_ce_oi": 0,
            "total_pe_oi": 0,
            "pcr": 0,
            "strikes": [],
            "strike_count": 0,
            "market_closed": True,
            "message": f"No option chain data for {symbol} — market may be closed (weekends/holidays).",
        }

    records = raw.get("records", {})
    filtered = raw.get("filtered", {})

    # Extract expiry dates
    expiry_dates = records.get("expiryDates", [])

    # Spot price
    spot = records.get("underlyingValue", 0)

    # Get totals
    ce_total_oi = filtered.get("CE", {}).get("totOI", 0)
    pe_total_oi = filtered.get("PE", {}).get("totOI", 0)
    pcr = round(pe_total_oi / ce_total_oi, 3) if ce_total_oi > 0 else 0

    # Process strike data
    strikes = []
    for row in records.get("data", []):
        strike = {
            "strikePrice": row.get("strikePrice", 0),
            "expiryDate": row.get("expiryDate", ""),
        }

        # Call (CE) data
        ce = row.get("CE")
        if ce:
            strike["CE"] = {
                "oi": ce.get("openInterest", 0),
                "changeInOI": ce.get("changeinOpenInterest", 0),
                "volume": ce.get("totalTradedVolume", 0),
                "iv": ce.get("impliedVolatility", 0),
                "ltp": ce.get("lastPrice", 0),
                "change": ce.get("change", 0),
                "bidPrice": ce.get("bidprice", 0),
                "askPrice": ce.get("askprice", 0),
            }

        # Put (PE) data
        pe = row.get("PE")
        if pe:
            strike["PE"] = {
                "oi": pe.get("openInterest", 0),
                "changeInOI": pe.get("changeinOpenInterest", 0),
                "volume": pe.get("totalTradedVolume", 0),
                "iv": pe.get("impliedVolatility", 0),
                "ltp": pe.get("lastPrice", 0),
                "change": pe.get("change", 0),
                "bidPrice": pe.get("bidprice", 0),
                "askPrice": pe.get("askprice", 0),
            }

        strikes.append(strike)

    return {
        "symbol": symbol,
        "spot_price": spot,
        "expiry_dates": expiry_dates,
        "total_ce_oi": ce_total_oi,
        "total_pe_oi": pe_total_oi,
        "pcr": pcr,
        "strikes": strikes,
        "strike_count": len(strikes),
    }


# Common symbols with active options
OPTION_SYMBOLS = [
    # Indices
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY",
    # Large caps
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT",
    "AXISBANK", "BAJFINANCE", "HINDUNILVR", "MARUTI",
    "TATAMOTORS", "SUNPHARMA", "TITAN", "WIPRO",
    "ADANIENT", "ADANIPORTS", "TATASTEEL", "JSWSTEEL",
    "NTPC", "POWERGRID", "ONGC", "COALINDIA",
    "HCLTECH", "TECHM", "M&M", "BAJAJFINSV",
]


def get_option_symbols() -> list[dict]:
    """Return list of symbols that have active NSE options."""
    return [{"symbol": s, "type": "Index" if s in ("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY") else "Stock"}
            for s in OPTION_SYMBOLS]
