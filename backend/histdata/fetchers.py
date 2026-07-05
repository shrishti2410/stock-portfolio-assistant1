"""
fetchers.py — provider workers that download historical OHLCV bars.

fetch_yfinance / fetch_alpaca / fetch_dhan are SYNC functions (blocking HTTP)
meant to be called via asyncio.to_thread from async contexts.
fetch_and_store is the async orchestrator: fetch -> histdata.store.save_bars.

All records are normalized to:
    {"ts": UTC ISO str, "open", "high", "low", "close", "volume", "oi"}
"""

import asyncio
import math
import os
from datetime import datetime, timedelta, timezone

import httpx

from histdata import store

TIMEFRAMES = ("1m", "5m", "15m", "1d")

_YF_INTERVAL = {"1m": "1m", "5m": "5m", "15m": "15m", "1d": "1d"}
# Yahoo hard limits on intraday history depth.
_YF_MAX_DAYS = {"1m": 7, "5m": 59, "15m": 59, "1d": 3650}

_ALPACA_TIMEFRAME = {"1m": "1Min", "5m": "5Min", "15m": "15Min", "1d": "1Day"}
_DHAN_INTERVAL = {"1m": "1", "5m": "5", "15m": "15"}


def _clean(value) -> float | None:
    """float(value), mapping None/NaN/garbage to None so SQLite gets NULL."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


# ---------------------------------------------------------------------------
# yfinance
# ---------------------------------------------------------------------------

def fetch_yfinance(symbol: str, timeframe: str, days: int) -> list[dict]:
    """
    Download bars from Yahoo Finance. SYNC — call via asyncio.to_thread.

    Caps days per Yahoo limits: 1m -> 7d, 5m/15m -> 59d, 1d -> 3650d.
    Returns [] when Yahoo has no data for the symbol/interval.
    """
    import yfinance as yf

    if timeframe not in _YF_INTERVAL:
        raise ValueError(f"Unsupported timeframe {timeframe!r}; use one of {TIMEFRAMES}")

    days = max(1, min(int(days), _YF_MAX_DAYS[timeframe]))
    df = yf.Ticker(symbol).history(
        period=f"{days}d", interval=_YF_INTERVAL[timeframe], auto_adjust=False
    )
    if df is None or df.empty:
        return []

    idx = df.index
    idx = idx.tz_convert("UTC") if idx.tz is not None else idx.tz_localize("UTC")

    opens = df["Open"].to_numpy()
    highs = df["High"].to_numpy()
    lows = df["Low"].to_numpy()
    closes = df["Close"].to_numpy()
    volumes = df["Volume"].to_numpy() if "Volume" in df.columns else [0] * len(df)

    records: list[dict] = []
    for i, ts in enumerate(idx):
        close = _clean(closes[i])
        if close is None:  # skip empty/holiday rows Yahoo sometimes pads in
            continue
        records.append(
            {
                "ts": ts.isoformat(),
                "open": _clean(opens[i]),
                "high": _clean(highs[i]),
                "low": _clean(lows[i]),
                "close": close,
                "volume": _clean(volumes[i]) or 0,
                "oi": None,
            }
        )
    return records


# ---------------------------------------------------------------------------
# Alpaca (US stocks, IEX feed)
# ---------------------------------------------------------------------------

def fetch_alpaca(symbol: str, timeframe: str, days: int) -> list[dict] | None:
    """
    Download bars from Alpaca Market Data v2. SYNC — call via asyncio.to_thread.

    Returns None when ALPACA_API_KEY / ALPACA_API_SECRET are not configured.
    Paginates via next_page_token until exhausted.
    """
    api_key = os.environ.get("ALPACA_API_KEY", "").strip()
    api_secret = os.environ.get("ALPACA_API_SECRET", "").strip()
    if not api_key or not api_secret:
        return None

    if timeframe not in _ALPACA_TIMEFRAME:
        raise ValueError(f"Unsupported timeframe {timeframe!r}; use one of {TIMEFRAMES}")

    start = (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}
    base_params = {
        "timeframe": _ALPACA_TIMEFRAME[timeframe],
        "start": start,
        "limit": 10000,
        "feed": "iex",
    }

    records: list[dict] = []
    page_token: str | None = None
    with httpx.Client(timeout=30.0) as client:
        while True:
            params = dict(base_params)
            if page_token:
                params["page_token"] = page_token
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            for bar in data.get("bars") or []:
                # Alpaca t is RFC-3339 like "2026-07-01T13:30:00Z"
                ts = datetime.fromisoformat(str(bar["t"]).replace("Z", "+00:00"))
                records.append(
                    {
                        "ts": ts.astimezone(timezone.utc).isoformat(),
                        "open": _clean(bar.get("o")),
                        "high": _clean(bar.get("h")),
                        "low": _clean(bar.get("l")),
                        "close": _clean(bar.get("c")),
                        "volume": _clean(bar.get("v")) or 0,
                        "oi": None,
                    }
                )

            page_token = data.get("next_page_token")
            if not page_token:
                break
    return records


# ---------------------------------------------------------------------------
# Dhan (NSE intraday, best-effort)
# ---------------------------------------------------------------------------

def fetch_dhan(symbol: str, timeframe: str, days: int) -> list[dict] | None:
    """
    Best-effort intraday bars from Dhan API v2. SYNC — call via asyncio.to_thread.

    IMPORTANT: `symbol` must be a Dhan *securityId* (numeric instrument id from
    Dhan's scrip master), NOT a trading symbol. Only NSE_EQ equity intraday is
    wired up here; index (IDX_I) and MCX commodity segment mapping will be added
    once the user provides a working Dhan API key to test against.

    Supports intraday timeframes only (1m/5m/15m). Returns None when
    DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN are not configured.
    """
    client_id = os.environ.get("DHAN_CLIENT_ID", "").strip()
    access_token = os.environ.get("DHAN_ACCESS_TOKEN", "").strip()
    if not client_id or not access_token:
        return None

    if timeframe not in _DHAN_INTERVAL:
        raise ValueError(
            f"Dhan fetcher supports intraday timeframes {tuple(_DHAN_INTERVAL)} only, got {timeframe!r}"
        )

    # Dhan intraday history serves at most ~90 days back.
    days = max(1, min(int(days), 90))
    to_date = datetime.now(timezone.utc).date()
    from_date = to_date - timedelta(days=days)

    body = {
        "securityId": str(symbol),
        "exchangeSegment": "NSE_EQ",
        "instrument": "EQUITY",
        "interval": _DHAN_INTERVAL[timeframe],
        "oi": True,
        "fromDate": from_date.isoformat(),
        "toDate": to_date.isoformat(),
    }
    headers = {
        "access-token": access_token,
        "client-id": client_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    with httpx.Client(timeout=30.0) as client:
        resp = client.post("https://api.dhan.co/v2/charts/intraday", json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    timestamps = data.get("timestamp") or []
    opens = data.get("open") or []
    highs = data.get("high") or []
    lows = data.get("low") or []
    closes = data.get("close") or []
    volumes = data.get("volume") or []
    ois = data.get("open_interest") or data.get("oi") or []

    records: list[dict] = []
    for i, epoch_sec in enumerate(timestamps):
        close = _clean(closes[i]) if i < len(closes) else None
        if close is None:
            continue
        records.append(
            {
                "ts": datetime.fromtimestamp(float(epoch_sec), tz=timezone.utc).isoformat(),
                "open": _clean(opens[i]) if i < len(opens) else None,
                "high": _clean(highs[i]) if i < len(highs) else None,
                "low": _clean(lows[i]) if i < len(lows) else None,
                "close": close,
                "volume": (_clean(volumes[i]) if i < len(volumes) else 0) or 0,
                "oi": _clean(ois[i]) if i < len(ois) else None,
            }
        )
    return records


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def fetch_and_store(
    symbols: list[str],
    timeframe: str,
    days: int,
    source: str = "auto",
) -> list[dict]:
    """
    Fetch bars for each symbol and persist via store.save_bars.

    source: "auto" (tries yfinance) | "yfinance" | "alpaca" | "dhan".
    Returns per-symbol results: {symbol, fetched, stored, source, error}.
    """
    results: list[dict] = []

    for symbol in symbols:
        used_source = "yfinance" if source == "auto" else source
        result = {"symbol": symbol, "fetched": 0, "stored": 0, "source": used_source, "error": None}
        try:
            if source in ("auto", "yfinance"):
                records = await asyncio.to_thread(fetch_yfinance, symbol, timeframe, days)
            elif source == "alpaca":
                records = await asyncio.to_thread(fetch_alpaca, symbol, timeframe, days)
                if records is None:
                    result["error"] = "alpaca not configured (set ALPACA_API_KEY / ALPACA_API_SECRET)"
                    results.append(result)
                    continue
            elif source == "dhan":
                records = await asyncio.to_thread(fetch_dhan, symbol, timeframe, days)
                if records is None:
                    result["error"] = "dhan not configured (set DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN)"
                    results.append(result)
                    continue
            else:
                result["error"] = f"unknown source {source!r}; use auto|yfinance|alpaca|dhan"
                results.append(result)
                continue

            result["fetched"] = len(records)
            if records:
                result["stored"] = await store.save_bars(symbol, timeframe, records, used_source)
            else:
                result["error"] = "no data returned"
        except Exception as exc:  # network/provider errors -> per-symbol error, keep going
            result["error"] = str(exc)

        results.append(result)

    return results
