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

    Reads from DB cache first (fast). If today's data is not cached, fetches
    fresh from yfinance + saves to DB. Each row includes `earnings_date`
    (frontend alias for `date`) and `recent_quarters` (last 4 quarters).
    """
    from data.it_universe import get_all

    # 1. Try DB cache first
    cached = await _load_universe_from_db(days_ahead=days_ahead)
    if cached:
        return cached

    # 2. No cache → fetch fresh from yfinance
    await refresh_universe_earnings_cache()

    # 3. Read freshly populated cache
    return await _load_universe_from_db(days_ahead=days_ahead) or []


# ---------------------------------------------------------------------------
# Persistent cache (DB-backed) — survives restarts, refreshed once/day
# ---------------------------------------------------------------------------

async def _load_universe_from_db(days_ahead: int = 90) -> list[dict] | None:
    """
    Read cached earnings + quarterly history from SQLite.
    Returns None if cache is stale (not refreshed today).
    """
    from db.database import _get_db
    import aiosqlite

    today_str = date.today().isoformat()
    cutoff = (date.today() + timedelta(days=days_ahead)).isoformat()

    async with _get_db() as db:
        db.row_factory = aiosqlite.Row

        # Was the cache refreshed today?
        # We use a sentinel row: symbol='__last_refresh__'
        sentinel_rows = await db.execute_fetchall(
            "SELECT earnings_date FROM earnings_calendar WHERE symbol = '__last_refresh__'"
        )
        last_refresh = sentinel_rows[0]["earnings_date"] if sentinel_rows else None
        if last_refresh != today_str:
            return None  # Stale or never refreshed

        # Read all earnings rows within window
        rows = await db.execute_fetchall(
            """SELECT symbol, earnings_date FROM earnings_calendar
               WHERE symbol != '__last_refresh__'
                 AND earnings_date >= ?
                 AND earnings_date <= ?
               ORDER BY earnings_date ASC""",
            (today_str, cutoff),
        )
        earnings_rows = [dict(r) for r in rows]

        if not earnings_rows:
            return []

        # Bulk-load quarterly history for these symbols
        symbols_list = [r["symbol"] for r in earnings_rows]
        placeholders = ",".join("?" * len(symbols_list))
        hist_rows = await db.execute_fetchall(
            f"""SELECT symbol, period, revenue, earnings, eps, revenue_yoy_pct
                FROM earnings_history
                WHERE symbol IN ({placeholders})
                ORDER BY symbol, period DESC""",
            symbols_list,
        )

        # Group quarters by symbol
        quarters_by_sym: dict[str, list[dict]] = {}
        for h in hist_rows:
            d = dict(h)
            sym = d.pop("symbol")
            quarters_by_sym.setdefault(sym, []).append(d)

    # Augment with IT universe metadata + days_away + frontend aliases
    from data.it_universe import get_by_symbol
    today = date.today()
    out = []
    for r in earnings_rows:
        sym = r["symbol"]
        stock = get_by_symbol(sym) or {}
        try:
            ed = date.fromisoformat(r["earnings_date"])
            days_away = (ed - today).days
        except Exception:
            days_away = None

        quarters = quarters_by_sym.get(sym, [])[:4]
        # Add beat_miss label (if revenue_yoy_pct > 5: beat; < -5: miss; else in_line)
        for q in quarters:
            yoy = q.get("revenue_yoy_pct")
            if yoy is None:
                q["beat_miss"] = "unknown"
            elif yoy > 5:
                q["beat_miss"] = "beat"
            elif yoy < -5:
                q["beat_miss"] = "miss"
            else:
                q["beat_miss"] = "in_line"

        out.append({
            "symbol": sym,
            "name": stock.get("name", sym),
            "country": stock.get("country", ""),
            "tier": stock.get("tier", ""),
            "segment": stock.get("segment", ""),
            "date": r["earnings_date"],
            "earnings_date": r["earnings_date"],  # frontend alias
            "days_away": days_away,
            "is_estimated": True,
            "recent_quarters": quarters,
        })

    return out


async def refresh_universe_earnings_cache() -> dict:
    """
    Force-refresh earnings + last 4 quarters for the entire IT universe.
    Persists everything to SQLite. Returns a summary dict.

    This is the function the morning-startup script calls.
    """
    from data.it_universe import get_all
    from db.database import _get_db

    stocks = get_all()
    today_str = date.today().isoformat()

    print(f"[earnings_refresh] Refreshing {len(stocks)} stocks...")
    started = time.time()

    # Fetch all earnings + quarterly in parallel (bounded concurrency)
    sem = asyncio.Semaphore(8)

    async def _fetch_one(stock: dict) -> dict:
        sym = stock["symbol"]
        async with sem:
            try:
                earnings_task = get_next_earnings(sym)
                quarterly_task = get_quarterly_history(sym, num_quarters=4)
                earnings, quarters = await asyncio.gather(
                    earnings_task, quarterly_task, return_exceptions=True
                )
            except Exception as e:
                print(f"[earnings_refresh] {sym}: {e}")
                return {"symbol": sym, "earnings": None, "quarters": []}
        return {
            "symbol": sym,
            "earnings": earnings if not isinstance(earnings, Exception) else None,
            "quarters": quarters if not isinstance(quarters, Exception) else [],
        }

    results = await asyncio.gather(*[_fetch_one(s) for s in stocks])

    # Persist to DB
    earnings_written = 0
    quarters_written = 0
    async with _get_db() as db:
        # Clear stale data (rebuild fresh each time)
        await db.execute("DELETE FROM earnings_calendar WHERE symbol != '__last_refresh__'")
        await db.execute("DELETE FROM earnings_history")

        for r in results:
            sym = r["symbol"]
            earnings = r["earnings"]
            if earnings and earnings.get("date"):
                await db.execute(
                    """INSERT OR REPLACE INTO earnings_calendar
                       (symbol, earnings_date) VALUES (?, ?)""",
                    (sym, earnings["date"]),
                )
                earnings_written += 1

            for q in r["quarters"]:
                await db.execute(
                    """INSERT OR REPLACE INTO earnings_history
                       (symbol, period, revenue, earnings, eps, revenue_yoy_pct)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (sym, q.get("period"), q.get("revenue"),
                     q.get("earnings"), q.get("eps"), q.get("revenue_yoy_pct")),
                )
                quarters_written += 1

        # Update last-refresh sentinel
        await db.execute(
            """INSERT OR REPLACE INTO earnings_calendar
               (symbol, earnings_date) VALUES ('__last_refresh__', ?)""",
            (today_str,),
        )
        await db.commit()

    duration_s = round(time.time() - started, 1)
    summary = {
        "refreshed_at": datetime.now().isoformat(),
        "stocks_attempted": len(stocks),
        "earnings_dates_saved": earnings_written,
        "quarters_saved": quarters_written,
        "duration_seconds": duration_s,
    }
    print(f"[earnings_refresh] ✅ {earnings_written} earnings, {quarters_written} quarters in {duration_s}s")
    return summary


async def get_last_refresh_date() -> str | None:
    """Returns ISO date string of last full refresh, or None if never refreshed."""
    from db.database import _get_db
    import aiosqlite
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT earnings_date FROM earnings_calendar WHERE symbol = '__last_refresh__'"
        )
        return rows[0]["earnings_date"] if rows else None


async def is_cache_fresh_today() -> bool:
    """True if the cache was refreshed today."""
    last = await get_last_refresh_date()
    return last == date.today().isoformat()


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
