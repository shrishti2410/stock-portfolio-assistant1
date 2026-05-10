"""
earnings_calendar.py — Earnings dates + last 4 quarters fundamentals
for IT universe stocks.

Uses yfinance (works for both NSE-listed Indian and US stocks).
Caches per-symbol with 6-hour TTL since earnings dates rarely change intraday.
"""
import asyncio
import time
from datetime import date, datetime, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# In-memory cache: {symbol: {"data": ..., "ts": float}}
# ---------------------------------------------------------------------------
_earnings_cache: dict[str, dict] = {}
_EARNINGS_TTL = 6 * 3600  # 6 hours


def _is_cache_fresh(symbol: str) -> bool:
    entry = _earnings_cache.get(symbol)
    if not entry:
        return False
    return (time.time() - entry["ts"]) < _EARNINGS_TTL


def _cache_set(symbol: str, key: str, data) -> None:
    if symbol not in _earnings_cache:
        _earnings_cache[symbol] = {"ts": time.time()}
    _earnings_cache[symbol][key] = data
    _earnings_cache[symbol]["ts"] = time.time()


def _cache_get(symbol: str, key: str):
    entry = _earnings_cache.get(symbol, {})
    age = time.time() - entry.get("ts", 0)
    if age < _EARNINGS_TTL:
        return entry.get(key)
    return None


# ---------------------------------------------------------------------------
# yfinance helpers (blocking — always wrap in asyncio.to_thread)
# ---------------------------------------------------------------------------

def _yf_get_calendar(yf_ticker_sym: str) -> dict | None:
    """Blocking: fetch earnings calendar from yfinance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(yf_ticker_sym)
        cal = ticker.calendar
        if cal is None:
            return None

        # yfinance returns a dict or DataFrame depending on version
        if hasattr(cal, "to_dict"):
            cal = cal.to_dict()

        # Expected keys: "Earnings Date", "Earnings Average", etc.
        earnings_dates = cal.get("Earnings Date") or cal.get("earnings_date")
        if not earnings_dates:
            return None

        # earnings_dates may be a list of Timestamps
        if isinstance(earnings_dates, list):
            next_date = earnings_dates[0]
        elif hasattr(earnings_dates, "iloc"):
            next_date = earnings_dates.iloc[0]
        else:
            next_date = earnings_dates

        if hasattr(next_date, "date"):
            next_date = next_date.date()
        elif isinstance(next_date, str):
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S"):
                try:
                    next_date = datetime.strptime(next_date[:10], "%Y-%m-%d").date()
                    break
                except ValueError:
                    continue

        if not isinstance(next_date, date):
            return None

        return {"date": next_date, "is_estimated": True}

    except Exception as e:
        print(f"[earnings_calendar] Calendar fetch failed for {yf_ticker_sym}: {e}")
        return None


def _yf_get_quarterly(yf_ticker_sym: str, num_quarters: int = 4) -> list[dict]:
    """Blocking: fetch last N quarterly financials from yfinance."""
    results = []
    try:
        import yfinance as yf
        ticker = yf.Ticker(yf_ticker_sym)

        qf = ticker.quarterly_financials
        qi = ticker.quarterly_income_stmt if hasattr(ticker, "quarterly_income_stmt") else None

        # Try both attribute names (yfinance version compatibility)
        if qf is None or (hasattr(qf, "empty") and qf.empty):
            qf = qi

        if qf is None or (hasattr(qf, "empty") and qf.empty):
            return []

        # qf is a DataFrame: columns = periods (Timestamps), rows = line items
        cols = list(qf.columns)[:num_quarters]

        prev_revenue = None
        for i, col in enumerate(cols):
            period_str = col.strftime("%Y-Q%q") if hasattr(col, "strftime") else str(col)[:10]

            # Revenue
            revenue = None
            for key in ("Total Revenue", "Revenue", "Net Revenue", "TotalRevenue"):
                try:
                    val = qf.loc[key, col] if key in qf.index else None
                    if val is not None and not (hasattr(val, "__float__") and val != val):  # not NaN
                        revenue = float(val)
                        break
                except Exception:
                    pass

            # Net Income / Earnings
            earnings = None
            for key in ("Net Income", "Net Income Common Stockholders", "NetIncome"):
                try:
                    val = qf.loc[key, col] if key in qf.index else None
                    if val is not None and not (hasattr(val, "__float__") and val != val):
                        earnings = float(val)
                        break
                except Exception:
                    pass

            # EPS — try from quarterly_earnings first
            eps = None
            try:
                qe = ticker.quarterly_earnings
                if qe is not None and not qe.empty and i < len(qe):
                    eps_row = qe.iloc[i]
                    eps = float(eps_row.get("EPS", eps_row.get("Reported EPS", None)) or 0) or None
            except Exception:
                pass

            # Revenue YoY — compare to same quarter last year (4 quarters later in list)
            revenue_yoy_pct = None
            if revenue is not None and prev_revenue is not None and prev_revenue != 0:
                revenue_yoy_pct = round((revenue - prev_revenue) / abs(prev_revenue) * 100, 2)

            prev_revenue = revenue

            results.append({
                "period": period_str,
                "revenue": revenue,
                "earnings": earnings,
                "eps": eps,
                "revenue_yoy_pct": revenue_yoy_pct,
            })

    except Exception as e:
        print(f"[earnings_calendar] Quarterly fetch failed for {yf_ticker_sym}: {e}")

    return results


def _resolve_yf_symbol(symbol: str) -> str:
    """Map IT universe symbol to yfinance ticker."""
    from data.it_universe import get_by_symbol, get_all, SECTOR_ETFS
    stock = get_by_symbol(symbol)
    if stock:
        return stock.get("yf", symbol)
    # ETFs
    for etf in SECTOR_ETFS:
        if etf["symbol"] == symbol:
            return etf.get("yf", symbol)
    return symbol


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def get_next_earnings(symbol: str) -> dict | None:
    """
    Returns {"symbol", "date", "days_away", "is_estimated"}
    or None if not available.
    Uses yfinance Ticker.calendar.
    """
    symbol = symbol.upper().strip()
    cached = _cache_get(symbol, "next_earnings")
    if cached is not None:
        return cached

    yf_sym = _resolve_yf_symbol(symbol)
    cal = await asyncio.to_thread(_yf_get_calendar, yf_sym)

    if cal is None:
        _cache_set(symbol, "next_earnings", None)
        return None

    earnings_date = cal["date"]
    today = date.today()
    days_away = (earnings_date - today).days

    result = {
        "symbol": symbol,
        "date": earnings_date.isoformat(),
        "days_away": days_away,
        "is_estimated": cal.get("is_estimated", True),
    }

    _cache_set(symbol, "next_earnings", result)
    return result


async def get_quarterly_history(symbol: str, num_quarters: int = 4) -> list[dict]:
    """
    Last N quarterly results.
    Returns list of {"period", "revenue", "earnings", "revenue_yoy_pct", "eps", ...}
    """
    symbol = symbol.upper().strip()
    cache_key = f"quarterly_{num_quarters}"
    cached = _cache_get(symbol, cache_key)
    if cached is not None:
        return cached

    yf_sym = _resolve_yf_symbol(symbol)
    results = await asyncio.to_thread(_yf_get_quarterly, yf_sym, num_quarters)

    _cache_set(symbol, cache_key, results)
    return results


async def get_universe_earnings_calendar(days_ahead: int = 90) -> list[dict]:
    """
    For all stocks in IT universe (use data.it_universe.get_all()),
    return upcoming earnings within next N days sorted by date.
    """
    from data.it_universe import get_all

    stocks = get_all()
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    tasks = [get_next_earnings(s["symbol"]) for s in stocks]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    upcoming = []
    for stock, result in zip(stocks, results):
        if isinstance(result, Exception) or result is None:
            continue
        try:
            earnings_date = date.fromisoformat(result["date"])
            if today <= earnings_date <= cutoff:
                upcoming.append({
                    **result,
                    "name": stock.get("name", stock["symbol"]),
                    "country": stock.get("country", ""),
                    "tier": stock.get("tier", ""),
                    "segment": stock.get("segment", ""),
                })
        except Exception:
            continue

    # Sort by date ascending
    upcoming.sort(key=lambda x: x["date"])
    return upcoming


async def is_pre_earnings_window(symbol: str, days_before: int = 21) -> tuple[bool, int]:
    """
    Returns (in_window, days_to_earnings) for pre-earnings strategy timing.
    in_window is True if earnings are within days_before days.
    """
    info = await get_next_earnings(symbol)
    if info is None:
        return False, -1

    days_away = info["days_away"]
    in_window = 0 < days_away <= days_before
    return in_window, days_away
