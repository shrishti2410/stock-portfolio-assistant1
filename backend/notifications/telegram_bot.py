"""
telegram_bot.py — Send notifications via Telegram Bot.

Setup:
  1. Create a bot via @BotFather on Telegram, get TELEGRAM_BOT_TOKEN.
  2. Send /start to your bot.
  3. Call GET https://api.telegram.org/bot{TOKEN}/getUpdates to get your chat_id.
  4. Set TELEGRAM_CHAT_ID in .env.

Environment variables:
  TELEGRAM_BOT_TOKEN  — Token from @BotFather
  TELEGRAM_CHAT_ID    — Your personal/group chat ID

Falls back to print() if not configured.
"""
import asyncio
import os
import traceback
from datetime import datetime

import httpx

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _is_configured() -> bool:
    """Check if Telegram is configured."""
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


async def send_telegram(message: str, parse_mode: str = "Markdown") -> bool:
    """
    Send a Telegram message. Returns True if sent.
    Falls back to print() if not configured.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print(f"[telegram_bot] Not configured. Would send:\n{message[:300]}")
        return False

    url = _TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if result.get("ok"):
                print(f"[telegram_bot] Sent message (chat_id={chat_id})")
                await _log_notification("telegram", "Telegram", message[:500], True)
                return True
            else:
                err = result.get("description", "Unknown error")
                print(f"[telegram_bot] API error: {err}")
                await _log_notification("telegram", "Telegram", message[:500], False, err)
                return False
    except httpx.HTTPStatusError as e:
        print(f"[telegram_bot] HTTP error: {e.response.status_code} {e.response.text}")
        await _log_notification("telegram", "Telegram", message[:500], False, str(e))
        return False
    except Exception as e:
        print(f"[telegram_bot] Send failed: {e}")
        await _log_notification("telegram", "Telegram", message[:500], False, str(e))
        return False


async def _log_notification(channel: str, subject: str, body: str,
                            success: bool, error_msg: str = "") -> None:
    """Log notification attempt to DB."""
    try:
        from db.database import _get_db
        async with _get_db() as db:
            await db.execute(
                """INSERT INTO notification_log (type, channel, subject, body, success, error_message)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("telegram", channel, subject[:500], body[:2000], 1 if success else 0, error_msg[:500] or None),
            )
            await db.commit()
    except Exception as e:
        print(f"[telegram_bot] Failed to log notification: {e}")


def _escape_md(text: str) -> str:
    """Escape MarkdownV2 special chars. Uses regular Markdown — no escaping needed."""
    return str(text)


async def send_trade_alert_telegram(proposal: dict) -> bool:
    """Send formatted trade alert with key fields."""
    symbol = proposal.get("symbol", "UNKNOWN")
    strategy = proposal.get("strategy_name", proposal.get("strategy_id", ""))
    direction = proposal.get("direction", "neutral").upper()
    confidence = round(float(proposal.get("confidence", 0)) * 100)
    max_profit = proposal.get("max_profit", 0)
    max_loss = proposal.get("max_loss", 0)
    margin = proposal.get("margin_needed", 0)
    reasoning = proposal.get("reasoning", "")
    legs = proposal.get("legs", [])
    layer = proposal.get("intelligence", {}).get("layer", "")
    created_at = proposal.get("created_at", datetime.now().isoformat())[:16]

    direction_emoji = "🔻" if direction in ("BEARISH", "SHORT") else "🔼" if direction == "BULLISH" else "↔️"

    # Format legs
    legs_text = ""
    for leg in legs[:4]:
        action = str(leg.get("action", "")).upper()
        opt_type = leg.get("type", leg.get("option_type", ""))
        strike = leg.get("strike", 0)
        qty = leg.get("qty", leg.get("quantity", 0))
        ltp = leg.get("ltp", 0)
        action_emoji = "🟢" if action == "BUY" else "🔴"
        legs_text += f"  {action_emoji} {action} {opt_type} {strike} x{qty} @ ₹{ltp:.1f}\n"

    # Truncate reasoning to 200 chars
    short_reasoning = reasoning[:200] + "..." if len(reasoning) > 200 else reasoning

    message = f"""*IT-Bear Trade Alert* {direction_emoji}

*{symbol}* — {strategy}
Layer: `{layer}` | Direction: `{direction}`

*P&L Range*
  Max Profit: ₹{max_profit:,.0f}
  Max Loss:   ₹{abs(max_loss):,.0f}
  Margin:     ₹{margin:,.0f}
  Confidence: {confidence}%

*Legs*
{legs_text}
*Reasoning*
_{short_reasoning}_

_Generated: {created_at}_"""

    return await send_telegram(message)


async def send_daily_brief_telegram(brief_data: dict) -> bool:
    """Send daily morning brief via Telegram."""
    date_str = brief_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    thesis_score = brief_data.get("thesis_score", 0)
    regime = brief_data.get("regime", "unknown").replace("_", " ").title()
    signals = brief_data.get("key_signals", [])[:5]
    open_positions = brief_data.get("open_positions", 0)
    unrealized_pnl = brief_data.get("unrealized_pnl", 0)
    upcoming_earnings = brief_data.get("upcoming_earnings", [])[:3]

    score_emoji = "🔥" if thesis_score >= 70 else "⚠️" if thesis_score >= 40 else "😐"
    pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"

    signals_text = "\n".join(f"  • {s}" for s in signals) if signals else "  No key signals"

    earnings_text = ""
    if upcoming_earnings:
        earnings_text = "\n\n*Upcoming Earnings*\n"
        for e in upcoming_earnings:
            earnings_text += f"  {e.get('symbol','')} — {e.get('date','')} ({e.get('days_away','')}d)\n"

    message = f"""*IT-Bear Daily Brief* {score_emoji}
{date_str}

*Thesis Score: {thesis_score}/100*
Regime: _{regime}_

*Portfolio*
  Open Positions: {open_positions}
  {pnl_emoji} Unrealized P&L: ₹{unrealized_pnl:+,.0f}

*Key Signals*
{signals_text}{earnings_text}"""

    return await send_telegram(message)


async def get_updates(limit: int = 10) -> list[dict]:
    """
    Fetch recent Telegram updates (messages sent to your bot).
    Useful for retrieving the chat_id when setting up.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return []

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"limit": limit})
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", [])
    except Exception as e:
        print(f"[telegram_bot] getUpdates failed: {e}")
        return []
