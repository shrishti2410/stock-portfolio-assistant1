"""
nse_symbols.py — NSE symbol directory for autocomplete

Maintains a local cache of NSE-listed symbols + company names.
Fetched from jugaad-data's NSE symbol list on first use, then cached in memory.

Public API:
    search_symbols(query, limit=10) -> list[dict]
    refresh_symbol_list() -> int
"""

import time
from pathlib import Path

_symbols: list[dict] = []  # [{"symbol": "RELIANCE", "name": "Reliance Industries Limited"}]
_last_refresh: float = 0
_REFRESH_INTERVAL = 86400  # 24 hours

# Common NSE stocks as fallback (used if fetching fails)
_FALLBACK_SYMBOLS = [
    {"symbol": "RELIANCE", "name": "Reliance Industries Limited"},
    {"symbol": "TCS", "name": "Tata Consultancy Services Limited"},
    {"symbol": "HDFCBANK", "name": "HDFC Bank Limited"},
    {"symbol": "INFY", "name": "Infosys Limited"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank Limited"},
    {"symbol": "HINDUNILVR", "name": "Hindustan Unilever Limited"},
    {"symbol": "ITC", "name": "ITC Limited"},
    {"symbol": "SBIN", "name": "State Bank of India"},
    {"symbol": "BHARTIARTL", "name": "Bharti Airtel Limited"},
    {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank Limited"},
    {"symbol": "LT", "name": "Larsen & Toubro Limited"},
    {"symbol": "AXISBANK", "name": "Axis Bank Limited"},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance Limited"},
    {"symbol": "WIPRO", "name": "Wipro Limited"},
    {"symbol": "MARUTI", "name": "Maruti Suzuki India Limited"},
    {"symbol": "TATAMOTORS", "name": "Tata Motors Limited"},
    {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical Industries Limited"},
    {"symbol": "TITAN", "name": "Titan Company Limited"},
    {"symbol": "ULTRACEMCO", "name": "UltraTech Cement Limited"},
    {"symbol": "NESTLEIND", "name": "Nestle India Limited"},
    {"symbol": "BAJAJFINSV", "name": "Bajaj Finserv Limited"},
    {"symbol": "ONGC", "name": "Oil and Natural Gas Corporation Limited"},
    {"symbol": "NTPC", "name": "NTPC Limited"},
    {"symbol": "TATASTEEL", "name": "Tata Steel Limited"},
    {"symbol": "ADANIENT", "name": "Adani Enterprises Limited"},
    {"symbol": "ADANIPORTS", "name": "Adani Ports and SEZ Limited"},
    {"symbol": "POWERGRID", "name": "Power Grid Corporation of India Limited"},
    {"symbol": "M&M", "name": "Mahindra & Mahindra Limited"},
    {"symbol": "HCLTECH", "name": "HCL Technologies Limited"},
    {"symbol": "TECHM", "name": "Tech Mahindra Limited"},
    {"symbol": "JSWSTEEL", "name": "JSW Steel Limited"},
    {"symbol": "DRREDDY", "name": "Dr. Reddy's Laboratories Limited"},
    {"symbol": "INDUSINDBK", "name": "IndusInd Bank Limited"},
    {"symbol": "DIVISLAB", "name": "Divi's Laboratories Limited"},
    {"symbol": "CIPLA", "name": "Cipla Limited"},
    {"symbol": "EICHERMOT", "name": "Eicher Motors Limited"},
    {"symbol": "APOLLOHOSP", "name": "Apollo Hospitals Enterprise Limited"},
    {"symbol": "COALINDIA", "name": "Coal India Limited"},
    {"symbol": "BPCL", "name": "Bharat Petroleum Corporation Limited"},
    {"symbol": "GRASIM", "name": "Grasim Industries Limited"},
    {"symbol": "HINDALCO", "name": "Hindalco Industries Limited"},
    {"symbol": "HEROMOTOCO", "name": "Hero MotoCorp Limited"},
    {"symbol": "BRITANNIA", "name": "Britannia Industries Limited"},
    {"symbol": "TATACONSUM", "name": "Tata Consumer Products Limited"},
    {"symbol": "SBILIFE", "name": "SBI Life Insurance Company Limited"},
    {"symbol": "HDFCLIFE", "name": "HDFC Life Insurance Company Limited"},
    {"symbol": "BAJAJ-AUTO", "name": "Bajaj Auto Limited"},
    {"symbol": "ASIANPAINT", "name": "Asian Paints Limited"},
    {"symbol": "PIDILITIND", "name": "Pidilite Industries Limited"},
    {"symbol": "ZOMATO", "name": "Zomato Limited"},
]


def _ensure_loaded():
    """Load symbols if not loaded or stale."""
    global _symbols, _last_refresh

    if _symbols and (time.time() - _last_refresh) < _REFRESH_INTERVAL:
        return

    # Try fetching from NSE via jugaad-data
    try:
        _symbols = _fetch_nse_symbols()
        _last_refresh = time.time()
        print(f"[nse_symbols] Loaded {len(_symbols)} symbols from NSE")
        return
    except Exception as exc:
        print(f"[nse_symbols] Failed to fetch from NSE: {exc}")

    # Fallback to hardcoded list
    if not _symbols:
        _symbols = _FALLBACK_SYMBOLS.copy()
        _last_refresh = time.time()
        print(f"[nse_symbols] Using fallback list ({len(_symbols)} symbols)")


def _fetch_nse_symbols() -> list[dict]:
    """Fetch full symbol list from NSE."""
    try:
        from jugaad_data.nse import NSELive
        nse = NSELive()
        # Try to get all equity symbols
        data = nse.all_stock_data()
        symbols = []
        if isinstance(data, dict):
            for item in data.get("data", []):
                sym = item.get("symbol", "")
                name = item.get("meta", {}).get("companyName", "") or item.get("companyName", "")
                if sym:
                    symbols.append({"symbol": sym, "name": name})
        if symbols:
            return symbols
    except Exception:
        pass

    # Alternative: try fetching Nifty 500 constituent list
    try:
        from jugaad_data.nse import stock_df
        # If we can't get the full list, at least return the fallback
        return _FALLBACK_SYMBOLS.copy()
    except Exception:
        pass

    return _FALLBACK_SYMBOLS.copy()


def search_symbols(query: str, limit: int = 10) -> list[dict]:
    """
    Search NSE symbols by ticker or company name.
    Returns list of matches: [{"symbol": "RELIANCE", "name": "Reliance Industries Limited"}]
    """
    _ensure_loaded()

    query = query.upper().strip()
    if not query:
        return []

    exact = []
    prefix = []
    contains = []

    for item in _symbols:
        sym = item["symbol"].upper()
        name = item["name"].upper()

        if sym == query:
            exact.append(item)
        elif sym.startswith(query):
            prefix.append(item)
        elif query in sym or query in name:
            contains.append(item)

    # Exact matches first, then prefix matches, then contains matches
    results = exact + prefix + contains
    return results[:limit]


def refresh_symbol_list() -> int:
    """Force refresh the symbol list. Returns count of symbols loaded."""
    global _symbols, _last_refresh
    _last_refresh = 0  # Force reload
    _ensure_loaded()
    return len(_symbols)
