"""
engine.py — async backtest engine.

Flow: start_run(payload) inserts a backtest_runs row (status 'running') and
schedules run_backtest(run_id) as a background task. run_backtest loads the
strategy definition from the marketplace registry, deep-merges its config
with the run's config_overrides, feeds per-IST-day bar frames to the
strategy implementation's run_day(), applies costs, computes metrics and
persists everything back into backtest_runs / backtest_trades.

Strategy implementations are plain sync classes (pandas math); the per-day
loop runs inside asyncio.to_thread so the event loop stays responsive.
"""

import asyncio
import json
import traceback
from datetime import date, timedelta

import aiosqlite
import pandas as pd

from backtest.metrics import compute
from backtest.strategies.mcx_reversal import McxReversal
from backtest.strategies.premium_expansion import PremiumExpansion
from db.database import _get_db
from histdata.store import get_bars
from marketplace.registry import get_strategy

# slug -> implementation class. Only slugs listed here can be backtested.
STRATEGY_IMPLS: dict[str, type] = {
    McxReversal.slug: McxReversal,
    PremiumExpansion.slug: PremiumExpansion,
}

VIX_SYMBOL = "^INDIAVIX"

# Keep strong references to fire-and-forget tasks (else GC may cancel them).
_TASKS: set = set()


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (returns a new dict).

    Nested dicts merge key-by-key; any other value type in override replaces
    the base value outright.
    """
    out = dict(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------

async def create_run_row(payload: dict) -> int:
    """Insert a 'running' backtest_runs row from a run payload; return run_id.

    The config column initially stores the raw config_overrides; run_backtest
    replaces it with the fully merged 'config used' once resolved.
    """
    slug = payload["strategy_slug"]
    symbols = payload.get("symbols") or []
    timeframe = payload.get("timeframe") or "5m"
    start = payload.get("start") or (date.today() - timedelta(days=45)).isoformat()
    end = payload.get("end") or date.today().isoformat()
    capital = float(payload.get("initial_capital") or 100000)
    overrides = payload.get("config_overrides") or {}

    async with _get_db() as db:
        cursor = await db.execute(
            """INSERT INTO backtest_runs
                   (strategy_slug, config, universe, timeframe, start_date,
                    end_date, initial_capital, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'running')""",
            (slug, json.dumps(overrides), json.dumps(symbols), timeframe,
             start, end, capital),
        )
        await db.commit()
        return cursor.lastrowid


async def start_run(payload: dict) -> int:
    """Insert the run row and execute the backtest in the background.

    Returns the run_id immediately; poll GET /api/backtest/runs/{id} for
    status running -> done | error.
    """
    run_id = await create_run_row(payload)
    task = asyncio.create_task(run_backtest(run_id))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return run_id


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------

async def _load_run(run_id: int) -> dict | None:
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM backtest_runs WHERE id = ?", (run_id,)
        )
        return dict(rows[0]) if rows else None


async def _load_vix_series() -> pd.Series:
    """Daily ^INDIAVIX close as a Series indexed by IST calendar date.

    May be empty — strategies fall back to a default sigma / skip the filter.
    """
    df = await get_bars(VIX_SYMBOL, "1d")
    if df is None or df.empty:
        return pd.Series(dtype=float)
    return pd.Series(
        df["close"].to_numpy(dtype=float),
        index=pd.Index([ts.date() for ts in df.index]),
    )


def _run_symbol_days(impl, df: pd.DataFrame, symbol: str, config: dict, ctx: dict) -> list[dict]:
    """Sync helper: split a symbol's bars into IST calendar days, run each day."""
    trades: list[dict] = []
    for _day, day_df in df.groupby(df.index.date):
        result = impl.run_day(day_df, symbol, config, ctx)
        if result:
            trades.extend(result)
    return trades


def _apply_costs(trades: list[dict], config: dict) -> None:
    """Subtract flat per-trade cost + slippage (bps on entry+exit notional).

    NOTE for the MCX proxy: trade pnl is in price POINTS of the proxy symbol
    and costs are in INR — 1 point is treated as 1 INR (documented in the
    run's metrics.assumptions).
    """
    costs = (config or {}).get("costs") or {}
    per_trade = float(costs.get("per_trade_inr") or 0)
    slip_bps = float(costs.get("slippage_bps") or 0)
    for t in trades:
        meta = t.setdefault("meta", {})
        notional = (abs(float(t["entry_price"])) + abs(float(t["exit_price"]))) * float(t["qty"])
        slippage = notional * slip_bps / 10000.0
        gross = float(t["pnl"])
        meta["gross_pnl"] = round(gross, 4)
        meta["costs_inr"] = round(per_trade + slippage, 4)
        t["pnl"] = round(gross - per_trade - slippage, 4)


def _assumptions(slug: str, config: dict) -> list[str]:
    """Human-readable model caveats persisted with the metrics."""
    costs = (config or {}).get("costs") or {}
    notes = [
        (
            f"Costs: flat ₹{costs.get('per_trade_inr', 0)} per round-trip trade + "
            f"{costs.get('slippage_bps', 0)} bps slippage on entry+exit notional, "
            "subtracted from each trade's P&L (meta.gross_pnl keeps the pre-cost figure)."
        ),
    ]
    if slug == PremiumExpansion.slug:
        pricing = (config or {}).get("pricing") or {}
        notes.insert(0, (
            "Option premiums are SYNTHETIC: Black-Scholes marks priced off the index "
            "proxy close with daily India VIX close as sigma (flat IV — no skew/term "
            "structure). Bid/ask is MODELED at ±"
            f"{pricing.get('spread_pct_each_side', 0.75)}% (min ₹{pricing.get('min_spread_rs', 0.3)}) "
            "around the mark; entries fill at ask, exits at bid. Real market premiums "
            "and spreads will differ."
        ))
        notes.append(
            "Expiry modeled as the next configured expiry weekday in calendar days; "
            "exchange-holiday expiry shifts are ignored."
        )
    if slug == McxReversal.slug:
        notes.insert(0, (
            "MCX proxy backtest: trades run on COMEX/NYMEX proxy symbols (GC=F, CL=F, …) "
            "with qty=1, so P&L is in proxy price POINTS and 1 point is treated as 1 INR. "
            "Real MCX contract multipliers, INR conversion and MCX session prices are "
            "NOT applied — treat results as signal-quality evidence, not INR P&L."
        ))
    return notes


async def run_backtest(run_id: int) -> dict:
    """Execute one backtest run end-to-end and persist results.

    Safe to await directly (used by tests/verification) — start_run wraps it
    in a background task. Returns a small summary dict.
    """
    try:
        run = await _load_run(run_id)
        if run is None:
            return {"run_id": run_id, "status": "missing", "error": "run row not found"}

        slug = run["strategy_slug"]
        impl_cls = STRATEGY_IMPLS.get(slug)
        if impl_cls is None:
            raise ValueError(f"no engine implementation for strategy '{slug}'")

        strategy = await get_strategy(slug)
        if strategy is None:
            raise ValueError(f"strategy '{slug}' not found in registry")

        try:
            overrides = json.loads(run.get("config") or "{}")
        except (TypeError, ValueError):
            overrides = {}
        config = deep_merge(strategy.get("config") or {}, overrides)

        try:
            symbols = json.loads(run.get("universe") or "[]")
        except (TypeError, ValueError):
            symbols = []
        timeframe = run.get("timeframe") or "5m"
        start = run.get("start_date")
        end = run.get("end_date")
        end_ts = f"{end}T23:59:59" if end and "T" not in str(end) else end
        capital = float(run.get("initial_capital") or 100000)

        ctx = {"vix": await _load_vix_series()}
        impl = impl_cls()

        trades: list[dict] = []
        for symbol in symbols:
            df = await get_bars(symbol, timeframe, start, end_ts)
            if df is None or df.empty:
                continue
            # pandas day-loop is CPU work — keep it off the event loop.
            trades.extend(
                await asyncio.to_thread(_run_symbol_days, impl, df, symbol, config, ctx)
            )

        _apply_costs(trades, config)
        trades.sort(key=lambda t: str(t["exit_ts"]))

        equity_curve: list[list] = []
        equity = capital
        for t in trades:
            equity += float(t["pnl"])
            equity_curve.append([t["exit_ts"], round(equity, 2)])

        metrics = compute(trades, equity_curve, capital, _assumptions(slug, config))

        async with _get_db() as db:
            await db.execute(
                """UPDATE backtest_runs
                   SET status = 'done', config = ?, metrics = ?, equity_curve = ?,
                       error = NULL, finished_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (json.dumps(config), json.dumps(metrics),
                 json.dumps(equity_curve), run_id),
            )
            # Re-run safety: wipe any previous trades for this run_id.
            await db.execute("DELETE FROM backtest_trades WHERE run_id = ?", (run_id,))
            await db.executemany(
                """INSERT INTO backtest_trades
                       (run_id, symbol, direction, entry_ts, entry_price,
                        exit_ts, exit_price, qty, pnl, pnl_pct, exit_reason, meta)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (run_id, t["symbol"], t["direction"], t["entry_ts"],
                     t["entry_price"], t["exit_ts"], t["exit_price"], t["qty"],
                     t["pnl"], t["pnl_pct"], t["exit_reason"],
                     json.dumps(t.get("meta") or {}))
                    for t in trades
                ],
            )
            await db.commit()

        return {"run_id": run_id, "status": "done",
                "trades": len(trades), "metrics": metrics}

    except Exception:
        error_text = traceback.format_exc()
        try:
            async with _get_db() as db:
                await db.execute(
                    """UPDATE backtest_runs
                       SET status = 'error', error = ?, finished_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (error_text, run_id),
                )
                await db.commit()
        except Exception:
            pass  # persisting the failure failed — the return value still reports it
        return {"run_id": run_id, "status": "error", "error": error_text}
