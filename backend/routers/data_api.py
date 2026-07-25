"""
data_api.py — REST endpoints for the historical data layer.

  GET  /api/data/coverage        -> hist_meta rows (what we hold locally)
  POST /api/data/fetch           -> download bars from a provider + store
  GET  /api/data/bars/{symbol}   -> last N stored bars (preview)
  GET  /api/data/providers       -> which providers are configured
"""

import os

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from histdata import store
from histdata.fetchers import TIMEFRAMES, fetch_and_store

router = APIRouter(prefix="/api/data", tags=["data"])


class FetchRequest(BaseModel):
    symbols: list[str] = Field(..., min_length=1, description="Symbols to fetch (provider-specific)")
    timeframe: str = Field(default="5m", description="1m | 5m | 15m | 1d")
    days: int = Field(default=30, ge=1, le=3650)
    source: str = Field(default="auto", description="auto | yfinance | alpaca | dhan")


@router.get("/coverage")
async def coverage() -> list[dict]:
    """Local data coverage: one row per (symbol, timeframe) from hist_meta."""
    return await store.get_coverage()


@router.post("/fetch")
async def fetch(req: FetchRequest) -> list[dict]:
    """Fetch bars from a provider and persist. Per-symbol results with errors inline."""
    if req.timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=422, detail=f"timeframe must be one of {TIMEFRAMES}")
    symbols = [s.strip() for s in req.symbols if s and s.strip()]
    if not symbols:
        raise HTTPException(status_code=422, detail="symbols must contain at least one non-empty symbol")
    return await fetch_and_store(symbols, req.timeframe, req.days, req.source)


@router.get("/bars/{symbol}")
async def bars(
    symbol: str,
    timeframe: str = Query(default="5m"),
    limit: int = Query(default=300, ge=1, le=5000),
) -> list[dict]:
    """Last N stored bars (ascending, UTC ISO ts) for a quick chart preview."""
    return await store.get_last_bars(symbol, timeframe, limit)


@router.get("/providers")
async def providers() -> dict:
    """Which data providers are usable right now (env-key based)."""
    return {
        "yfinance": True,
        "alpaca": bool(
            os.environ.get("ALPACA_API_KEY", "").strip()
            and os.environ.get("ALPACA_API_SECRET", "").strip()
        ),
        "dhan": bool(
            os.environ.get("DHAN_CLIENT_ID", "").strip()
            and os.environ.get("DHAN_ACCESS_TOKEN", "").strip()
        ),
    }
