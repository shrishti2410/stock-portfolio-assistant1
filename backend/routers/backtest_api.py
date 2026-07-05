"""
backtest_api.py — REST endpoints for the backtest engine.

  POST   /api/backtest/run                -> start a run, returns {run_id}
  GET    /api/backtest/runs               -> recent 50 runs (light rows)
  GET    /api/backtest/runs/{id}          -> full run: metrics + equity + trades
  DELETE /api/backtest/runs/{id}          -> delete a run and its trades
  GET    /api/backtest/engine-strategies  -> slugs with an engine implementation
"""

import json
from datetime import date, timedelta

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backtest.engine import STRATEGY_IMPLS, start_run
from db.database import _get_db
from marketplace.registry import get_strategy

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class RunRequest(BaseModel):
    strategy_slug: str
    symbols: list[str] = Field(..., min_length=1, description="Proxy symbols to backtest")
    timeframe: str = Field(default="5m")
    start: str | None = Field(default=None, description="YYYY-MM-DD (default: 45 days ago)")
    end: str | None = Field(default=None, description="YYYY-MM-DD (default: today)")
    initial_capital: float = Field(default=100000, gt=0)
    config_overrides: dict = Field(default_factory=dict)


def _parse_json(raw, default):
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


@router.post("/run")
async def run_backtest_endpoint(req: RunRequest) -> dict:
    """Kick off a backtest in the background. Poll GET /runs/{run_id} for status."""
    if req.strategy_slug not in STRATEGY_IMPLS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"engine plugin not available for strategy '{req.strategy_slug}' — "
                f"backtestable slugs: {sorted(STRATEGY_IMPLS)}"
            ),
        )
    if await get_strategy(req.strategy_slug) is None:
        raise HTTPException(
            status_code=404,
            detail=f"strategy '{req.strategy_slug}' not found in registry",
        )

    symbols = [s.strip() for s in req.symbols if s and s.strip()]
    if not symbols:
        raise HTTPException(
            status_code=422,
            detail="symbols must contain at least one non-empty symbol",
        )

    run_id = await start_run({
        "strategy_slug": req.strategy_slug,
        "symbols": symbols,
        "timeframe": req.timeframe or "5m",
        "start": req.start or (date.today() - timedelta(days=45)).isoformat(),
        "end": req.end or date.today().isoformat(),
        "initial_capital": req.initial_capital,
        "config_overrides": req.config_overrides or {},
    })
    return {"run_id": run_id}


@router.get("/runs")
async def list_runs() -> list[dict]:
    """Recent 50 runs — light rows (no equity curve, no trades)."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """SELECT id, strategy_slug, universe, timeframe, start_date, end_date,
                      initial_capital, status, metrics, error, created_at, finished_at
               FROM backtest_runs
               ORDER BY id DESC
               LIMIT 50"""
        )
    out = []
    for row in rows:
        r = dict(row)
        r["universe"] = _parse_json(r.get("universe"), [])
        r["metrics"] = _parse_json(r.get("metrics"), None)
        out.append(r)
    return out


@router.get("/runs/{run_id}")
async def get_run(run_id: int) -> dict:
    """Full run detail: parsed config/metrics/equity_curve + trades list."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM backtest_runs WHERE id = ?", (run_id,)
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"backtest run {run_id} not found")
        run = dict(rows[0])
        trade_rows = await db.execute_fetchall(
            """SELECT * FROM backtest_trades WHERE run_id = ?
               ORDER BY exit_ts ASC, id ASC""",
            (run_id,),
        )

    run["config"] = _parse_json(run.get("config"), {})
    run["universe"] = _parse_json(run.get("universe"), [])
    run["metrics"] = _parse_json(run.get("metrics"), None)
    run["equity_curve"] = _parse_json(run.get("equity_curve"), [])

    trades = []
    for row in trade_rows:
        t = dict(row)
        t["meta"] = _parse_json(t.get("meta"), {})
        trades.append(t)
    run["trades"] = trades
    return run


@router.delete("/runs/{run_id}")
async def delete_run(run_id: int) -> dict:
    """Delete a run and its trades."""
    async with _get_db() as db:
        await db.execute("DELETE FROM backtest_trades WHERE run_id = ?", (run_id,))
        cursor = await db.execute("DELETE FROM backtest_runs WHERE id = ?", (run_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"backtest run {run_id} not found")
        await db.commit()
    return {"deleted": True, "run_id": run_id}


@router.get("/engine-strategies")
async def engine_strategies() -> list[str]:
    """Strategy slugs that have an engine implementation (backtestable)."""
    return sorted(STRATEGY_IMPLS)
