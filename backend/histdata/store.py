"""
store.py — async persistence layer for historical OHLCV bars.

Tables (created by db/schema.sql, applied in db.database.init_db):
  hist_bars(symbol, timeframe, ts UTC-ISO, open, high, low, close, volume, oi, source,
            PK(symbol, timeframe, ts))
  hist_meta(symbol, timeframe, first_ts, last_ts, bar_count, source, updated_at,
            PK(symbol, timeframe))

All timestamps are stored as UTC ISO-8601 strings (e.g. "2026-07-01T03:45:00+00:00"),
so lexicographic comparison in SQL == chronological comparison.
"""

import aiosqlite
import pandas as pd

from db.database import _get_db

BAR_COLUMNS = ["open", "high", "low", "close", "volume", "oi"]


def _to_utc_iso(value) -> str | None:
    """Normalize a str/datetime/Timestamp to a UTC ISO string (naive => UTC)."""
    if value is None:
        return None
    ts = pd.Timestamp(value)
    ts = ts.tz_localize("UTC") if ts.tz is None else ts.tz_convert("UTC")
    return ts.isoformat()


async def save_bars(symbol: str, timeframe: str, records: list[dict], source: str) -> int:
    """
    INSERT OR REPLACE a batch of bar records, then refresh hist_meta.

    records: list of dicts {ts (ISO UTC str), open, high, low, close, volume, oi}.
    Returns the number of records written.
    """
    if not records:
        # Still refresh meta so coverage stays truthful.
        await refresh_meta(symbol, timeframe, source)
        return 0

    rows = [
        (
            symbol,
            timeframe,
            r["ts"],
            r.get("open"),
            r.get("high"),
            r.get("low"),
            r.get("close"),
            r.get("volume", 0),
            r.get("oi"),
            source,
        )
        for r in records
    ]

    async with _get_db() as db:
        await db.executemany(
            """INSERT OR REPLACE INTO hist_bars
               (symbol, timeframe, ts, open, high, low, close, volume, oi, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        await db.commit()

    await refresh_meta(symbol, timeframe, source)
    return len(rows)


async def refresh_meta(symbol: str, timeframe: str, source: str | None = None) -> None:
    """Recompute MIN/MAX/COUNT over hist_bars and upsert into hist_meta."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """SELECT MIN(ts) AS first_ts, MAX(ts) AS last_ts, COUNT(*) AS bar_count
               FROM hist_bars WHERE symbol = ? AND timeframe = ?""",
            (symbol, timeframe),
        )
        stats = dict(rows[0]) if rows else {"first_ts": None, "last_ts": None, "bar_count": 0}

        await db.execute(
            """INSERT INTO hist_meta (symbol, timeframe, first_ts, last_ts, bar_count, source, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(symbol, timeframe) DO UPDATE SET
                   first_ts   = excluded.first_ts,
                   last_ts    = excluded.last_ts,
                   bar_count  = excluded.bar_count,
                   source     = COALESCE(excluded.source, hist_meta.source),
                   updated_at = CURRENT_TIMESTAMP""",
            (
                symbol,
                timeframe,
                stats.get("first_ts"),
                stats.get("last_ts"),
                stats.get("bar_count", 0),
                source,
            ),
        )
        await db.commit()


async def get_bars(
    symbol: str,
    timeframe: str,
    start=None,
    end=None,
    tz: str = "Asia/Kolkata",
) -> pd.DataFrame:
    """
    Load bars as a pandas DataFrame indexed by a tz-converted DatetimeIndex
    (default Asia/Kolkata), columns open/high/low/close/volume/oi, ascending.

    start/end accept ISO strings or datetimes (naive treated as UTC).
    """
    sql = """SELECT ts, open, high, low, close, volume, oi
             FROM hist_bars WHERE symbol = ? AND timeframe = ?"""
    params: list = [symbol, timeframe]

    start_iso = _to_utc_iso(start)
    end_iso = _to_utc_iso(end)
    if start_iso:
        sql += " AND ts >= ?"
        params.append(start_iso)
    if end_iso:
        sql += " AND ts <= ?"
        params.append(end_iso)
    sql += " ORDER BY ts ASC"

    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(sql, params)

    if not rows:
        return pd.DataFrame(columns=BAR_COLUMNS, index=pd.DatetimeIndex([], tz=tz, name="ts"))

    df = pd.DataFrame([dict(r) for r in rows])
    df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601")
    df = df.set_index("ts").sort_index()
    df.index = df.index.tz_convert(tz)
    return df[BAR_COLUMNS]


async def get_last_bars(symbol: str, timeframe: str, limit: int = 300) -> list[dict]:
    """Last N bars (ascending) as plain record dicts with UTC ISO ts — for previews."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """SELECT ts, open, high, low, close, volume, oi
               FROM hist_bars WHERE symbol = ? AND timeframe = ?
               ORDER BY ts DESC LIMIT ?""",
            (symbol, timeframe, int(limit)),
        )
    return [dict(r) for r in reversed(rows)]


async def get_coverage() -> list[dict]:
    """All hist_meta rows (local data coverage), ordered by symbol/timeframe."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM hist_meta ORDER BY symbol, timeframe"
        )
        return [dict(r) for r in rows]


async def bar_count(symbol: str, timeframe: str) -> int:
    """Number of stored bars for symbol+timeframe."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT COUNT(*) AS n FROM hist_bars WHERE symbol = ? AND timeframe = ?",
            (symbol, timeframe),
        )
        return int(rows[0]["n"]) if rows else 0
