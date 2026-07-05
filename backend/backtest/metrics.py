"""
metrics.py — performance metrics for backtest runs (pure sync, no I/O).

compute(trades, equity, capital) -> summary dict persisted into
backtest_runs.metrics. Trades must already be sorted by exit_ts and carry
NET pnl (costs applied by the engine).
"""

import math

import numpy as np


def _r(value, digits: int = 4) -> float:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return 0.0


def compute(
    trades: list[dict],
    equity: list,
    capital: float,
    assumptions: list[str] | None = None,
) -> dict:
    """Compute summary metrics.

    trades  : trade dicts (net pnl), sorted by exit_ts ascending
    equity  : [[exit_ts_iso, equity_value], ...] (post-trade equity points)
    capital : initial capital the equity curve started from
    """
    capital = float(capital or 0.0)
    pnls = [float(t.get("pnl") or 0.0) for t in trades]
    total = len(pnls)

    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = sum(p for p in pnls if p < 0)  # negative number
    net_pnl = sum(pnls)

    win_rate_pct = (wins / total * 100.0) if total else 0.0
    profit_factor = (gross_profit / abs(gross_loss)) if gross_loss < 0 else None
    avg_win = (gross_profit / wins) if wins else 0.0
    avg_loss = (gross_loss / losses) if losses else 0.0  # negative number
    expectancy = (net_pnl / total) if total else 0.0

    # Max drawdown on the equity curve (peak-to-trough, % of running peak).
    max_dd = 0.0
    peak = None
    for value in [capital] + [float(pt[1]) for pt in (equity or [])]:
        peak = value if peak is None else max(peak, value)
        if peak and peak > 0:
            dd = (value - peak) / peak * 100.0
            max_dd = min(max_dd, dd)
    max_drawdown_pct = abs(max_dd)

    # Longest run of consecutive losing trades (chronological order).
    max_losing_streak = 0
    streak = 0
    for p in pnls:
        streak = streak + 1 if p < 0 else 0
        max_losing_streak = max(max_losing_streak, streak)

    # Per-trade Sharpe, annualized with sqrt(252). Guard div-by-zero / n<2.
    sharpe = 0.0
    if total >= 2:
        arr = np.asarray(pnls, dtype=float)
        std = float(arr.std(ddof=1))
        if std > 0 and not math.isnan(std):
            sharpe = float(arr.mean()) / std * math.sqrt(252)

    # Monthly breakdown keyed by exit month.
    monthly: dict[str, dict] = {}
    for t in trades:
        key = str(t.get("exit_ts") or "")[:7]  # "YYYY-MM"
        if len(key) != 7:
            continue
        bucket = monthly.setdefault(key, {"trades": 0, "pnl": 0.0})
        bucket["trades"] += 1
        bucket["pnl"] = _r(bucket["pnl"] + float(t.get("pnl") or 0.0))

    final_equity = capital + net_pnl

    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": _r(win_rate_pct, 2),
        "gross_profit": _r(gross_profit),
        "gross_loss": _r(gross_loss),
        "net_pnl": _r(net_pnl),
        "profit_factor": _r(profit_factor) if profit_factor is not None else None,
        "avg_win": _r(avg_win),
        "avg_loss": _r(avg_loss),
        "expectancy": _r(expectancy),
        "max_drawdown_pct": _r(max_drawdown_pct),
        "max_losing_streak": max_losing_streak,
        "sharpe": _r(sharpe, 3),
        "monthly": dict(sorted(monthly.items())),
        "final_equity": _r(final_equity, 2),
        "return_pct": _r((net_pnl / capital * 100.0) if capital else 0.0),
        "assumptions": list(assumptions or []),
    }
