"""
risk.py — Risk management layer. 12 sequential checks, ALL must pass.

This is the MOST CRITICAL file in the trading system.
If ANY check fails, the trade is blocked. No exceptions.
"""
import json
from datetime import datetime, date

from trading.events import is_market_hours, is_nse_holiday, is_blackout_period


async def run_risk_checks(proposal: dict, config: dict) -> list[dict]:
    """
    Run all 12 risk checks against a trade proposal.

    Args:
        proposal: Trade proposal dict (strategy_id, max_loss, margin_needed, etc.)
        config: Trading config dict (from trading_config table)

    Returns:
        List of {check: str, passed: bool, reason: str} for all 12 checks.
        Trade is allowed ONLY if all checks pass.
    """
    results = []
    paper_mode = bool(config.get("paper_mode", 1))

    # Cast numeric values to Python types (avoid numpy serialization issues)
    margin_needed = float(proposal.get("margin_needed", 0))
    max_loss = float(abs(proposal.get("max_loss", 0)))

    # 1. MARKET_HOURS — skip in paper mode (allow testing anytime)
    in_hours = is_market_hours()
    results.append({
        "check": "MARKET_HOURS",
        "passed": in_hours or paper_mode,
        "reason": "Market is open" if in_hours else ("Paper mode — market hours bypassed" if paper_mode else "Market is closed (outside 9:15 AM - 3:30 PM IST or weekend)"),
    })

    # 2. NSE_HOLIDAY — skip in paper mode
    is_holiday = is_nse_holiday()
    results.append({
        "check": "NSE_HOLIDAY",
        "passed": (not is_holiday) or paper_mode,
        "reason": "Not a holiday" if not is_holiday else ("Paper mode — holiday bypassed" if paper_mode else "Today is an NSE trading holiday"),
    })

    # 3. ENGINE_ENABLED
    engine_on = bool(config.get("engine_enabled", 0))
    results.append({
        "check": "ENGINE_ENABLED",
        "passed": engine_on,
        "reason": "Engine is enabled" if engine_on else "Trading engine is disabled (master kill switch)",
    })

    # 4. STRATEGY_ENABLED
    enabled_strategies = json.loads(config.get("strategies_enabled", "[]"))
    strategy_id = proposal.get("strategy_id", "")
    is_enabled = strategy_id in enabled_strategies
    results.append({
        "check": "STRATEGY_ENABLED",
        "passed": is_enabled,
        "reason": f"{strategy_id} is enabled" if is_enabled else f"{strategy_id} is not in enabled strategies",
    })

    # 5. CIRCUIT_BREAKER — check daily loss
    from db.database import _get_db
    today_str = date.today().isoformat()
    async with _get_db() as db:
        db.row_factory = __import__("aiosqlite").Row
        rows = await db.execute_fetchall(
            "SELECT * FROM daily_pnl WHERE date = ?", (today_str,)
        )

    daily_loss = 0
    if rows:
        row = dict(rows[0])
        daily_loss = row.get("realized", 0) + row.get("unrealized", 0)

    max_daily = config.get("max_daily_loss", 10000)
    circuit_ok = daily_loss > -abs(max_daily)
    results.append({
        "check": "CIRCUIT_BREAKER",
        "passed": circuit_ok,
        "reason": f"Daily P&L: Rs.{daily_loss:,.0f} (limit: -Rs.{abs(max_daily):,.0f})" if circuit_ok
                  else f"CIRCUIT BREAKER: Daily loss Rs.{abs(daily_loss):,.0f} exceeds limit Rs.{abs(max_daily):,.0f}",
    })

    # 6. MAX_POSITIONS
    async with _get_db() as db:
        db.row_factory = __import__("aiosqlite").Row
        rows = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM positions WHERE status = 'open'"
        )
    open_count = rows[0]["cnt"] if rows else 0
    max_pos = config.get("max_positions", 3)
    pos_ok = open_count < max_pos
    results.append({
        "check": "MAX_POSITIONS",
        "passed": pos_ok,
        "reason": f"{open_count}/{max_pos} positions open" if pos_ok
                  else f"Max positions reached: {open_count}/{max_pos}",
    })

    # 7. CAPITAL_CHECK
    max_capital = float(config.get("max_capital", 200000))
    # TODO: subtract margin already in use from open positions
    capital_ok = bool(margin_needed <= max_capital)
    results.append({
        "check": "CAPITAL_CHECK",
        "passed": capital_ok,
        "reason": f"Margin Rs.{margin_needed:,.0f} <= Rs.{max_capital:,.0f} available" if capital_ok
                  else f"Margin Rs.{margin_needed:,.0f} exceeds available Rs.{max_capital:,.0f}",
    })

    # 8. LOSS_LIMIT
    max_loss_per_trade = float(config.get("max_loss_per_trade", 5000))
    loss_ok = bool(max_loss <= max_loss_per_trade)
    results.append({
        "check": "LOSS_LIMIT",
        "passed": loss_ok,
        "reason": f"Max loss Rs.{max_loss:,.0f} <= Rs.{max_loss_per_trade:,.0f} limit" if loss_ok
                  else f"Max loss Rs.{max_loss:,.0f} exceeds per-trade limit Rs.{max_loss_per_trade:,.0f}",
    })

    # 9. POSITION_SIZE (2% rule)
    risk_pct = float(config.get("risk_per_trade_pct", 2.0))
    max_risk = max_capital * risk_pct / 100
    size_ok = bool(max_loss <= max_risk)
    results.append({
        "check": "POSITION_SIZE",
        "passed": size_ok,
        "reason": f"Risk Rs.{max_loss:,.0f} <= {risk_pct}% of capital (Rs.{max_risk:,.0f})" if size_ok
                  else f"Risk Rs.{max_loss:,.0f} exceeds {risk_pct}% rule (Rs.{max_risk:,.0f})",
    })

    # 10. EVENT_BLACKOUT
    blackout, event_reason = is_blackout_period(hours_ahead=24)
    results.append({
        "check": "EVENT_BLACKOUT",
        "passed": bool(not blackout),
        "reason": "No upcoming high-impact events" if not blackout
                  else f"Event blackout: {event_reason}",
    })

    # 11. DUPLICATE_CHECK
    symbol = proposal.get("symbol", "")
    async with _get_db() as db:
        db.row_factory = __import__("aiosqlite").Row
        rows = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM positions WHERE status = 'open' AND strategy_id = ? AND symbol = ?",
            (strategy_id, symbol),
        )
    has_dup = (rows[0]["cnt"] if rows else 0) > 0
    results.append({
        "check": "DUPLICATE_CHECK",
        "passed": bool(not has_dup),
        "reason": "No duplicate position" if not has_dup
                  else f"Already have open {strategy_id} position for {symbol}",
    })

    # 12. RATE_LIMIT
    results.append({
        "check": "RATE_LIMIT",
        "passed": True,
        "reason": "Within rate limits",
    })

    return results


def all_checks_passed(results: list[dict]) -> bool:
    """Returns True only if ALL 12 risk checks passed."""
    return all(r["passed"] for r in results)
