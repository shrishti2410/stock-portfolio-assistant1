"""
dispatcher.py — Single entry point that fans out notifications to all
configured channels (in-app WebSocket, email, Telegram).

Usage:
    from notifications.dispatcher import notify_trade_alert, notify_daily_brief, notify_risk_alert

All functions are fire-and-forget async — they catch and log errors internally.
"""
import asyncio
from datetime import datetime


async def notify_trade_alert(proposal: dict) -> dict[str, bool]:
    """
    Fan out a trade alert to all enabled channels:
      - WebSocket (in-app, always attempted)
      - Email (if SMTP configured)
      - Telegram (if bot token configured)

    Returns {"websocket": bool, "email": bool, "telegram": bool}
    """
    results = {"websocket": False, "email": False, "telegram": False}

    # 1. WebSocket (in-app)
    try:
        from trading.engine import trading_engine
        await trading_engine._notify_clients({
            "type": "new_proposal",
            "proposal": proposal,
        })
        results["websocket"] = True
    except Exception as e:
        print(f"[dispatcher] WebSocket notify failed: {e}")

    # 2. Email
    try:
        from notifications.email_sender import send_trade_alert
        results["email"] = await send_trade_alert(proposal)
    except Exception as e:
        print(f"[dispatcher] Email notify failed: {e}")

    # 3. Telegram
    try:
        from notifications.telegram_bot import send_trade_alert_telegram
        results["telegram"] = await send_trade_alert_telegram(proposal)
    except Exception as e:
        print(f"[dispatcher] Telegram notify failed: {e}")

    channels_ok = [ch for ch, ok in results.items() if ok]
    print(f"[dispatcher] Trade alert sent via: {', '.join(channels_ok) or 'none'} "
          f"(symbol={proposal.get('symbol')}, strategy={proposal.get('strategy_id')})")

    return results


async def notify_daily_brief(brief_data: dict) -> dict[str, bool]:
    """
    Send daily morning brief to all channels.
    brief_data keys: thesis_score, regime, key_signals, open_positions,
                     unrealized_pnl, upcoming_earnings, date.
    """
    results = {"websocket": False, "email": False, "telegram": False}

    # WebSocket
    try:
        from trading.engine import trading_engine
        await trading_engine._notify_clients({
            "type": "daily_brief",
            "data": brief_data,
        })
        results["websocket"] = True
    except Exception as e:
        print(f"[dispatcher] WebSocket brief failed: {e}")

    # Email
    try:
        from notifications.email_sender import send_daily_brief
        results["email"] = await send_daily_brief(brief_data)
    except Exception as e:
        print(f"[dispatcher] Email brief failed: {e}")

    # Telegram
    try:
        from notifications.telegram_bot import send_daily_brief_telegram
        results["telegram"] = await send_daily_brief_telegram(brief_data)
    except Exception as e:
        print(f"[dispatcher] Telegram brief failed: {e}")

    return results


async def notify_risk_alert(message: str, severity: str = "high") -> dict[str, bool]:
    """
    Send urgent risk alert to all channels.
    severity: "high" | "medium" | "low"
    """
    results = {"websocket": False, "email": False, "telegram": False}

    severity_emoji = {"high": "🚨", "medium": "⚠️", "low": "ℹ️"}.get(severity, "⚠️")
    subject = f"[IT-Bear] {severity_emoji} Risk Alert — {severity.upper()}"

    # WebSocket
    try:
        from trading.engine import trading_engine
        await trading_engine._notify_clients({
            "type": "risk_alert",
            "severity": severity,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        })
        results["websocket"] = True
    except Exception as e:
        print(f"[dispatcher] WebSocket risk alert failed: {e}")

    # Email
    try:
        from notifications.email_sender import send_email
        body_html = f"""
        <html><body style="background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:20px;">
          <div style="max-width:500px;margin:0 auto;background:#1e293b;border:2px solid
                      {'#ef4444' if severity=='high' else '#f59e0b'};border-radius:12px;padding:24px;">
            <h2 style="margin:0 0 12px;color:{'#ef4444' if severity=='high' else '#f59e0b'};">
              {severity_emoji} Risk Alert — {severity.upper()}
            </h2>
            <p style="margin:0;line-height:1.6;">{message}</p>
            <p style="margin:16px 0 0;font-size:11px;color:#64748b;">{datetime.now().isoformat()}</p>
          </div>
        </body></html>"""
        results["email"] = await send_email(subject, body_html)
    except Exception as e:
        print(f"[dispatcher] Email risk alert failed: {e}")

    # Telegram
    try:
        from notifications.telegram_bot import send_telegram
        tg_msg = f"*{subject}*\n\n{message}\n\n_{datetime.now().strftime('%Y-%m-%d %H:%M')}_"
        results["telegram"] = await send_telegram(tg_msg)
    except Exception as e:
        print(f"[dispatcher] Telegram risk alert failed: {e}")

    return results


async def send_test_notification(channel: str) -> dict:
    """
    Send a test message to a specific channel.
    channel: "email" | "telegram" | "websocket" | "all"
    """
    test_proposal = {
        "symbol": "TEST",
        "strategy_id": "it_long_put_breakdown",
        "strategy_name": "Long Put (Technical Breakdown)",
        "direction": "bearish",
        "confidence": 0.75,
        "max_profit": 25000.0,
        "max_loss": -10000.0,
        "margin_needed": 10000.0,
        "reasoning": "This is a test notification. Your IT-Bear notification system is working correctly.",
        "legs": [
            {"action": "buy", "type": "PE", "strike": 3500, "qty": 100, "ltp": 100.0, "iv": 18.0}
        ],
        "intelligence": {"layer": "core", "strategy_theme": "it_bear_thesis"},
        "created_at": datetime.now().isoformat(),
    }

    results = {}

    if channel in ("email", "all"):
        try:
            from notifications.email_sender import send_trade_alert
            results["email"] = await send_trade_alert(test_proposal)
        except Exception as e:
            results["email"] = False
            print(f"[dispatcher] Test email failed: {e}")

    if channel in ("telegram", "all"):
        try:
            from notifications.telegram_bot import send_trade_alert_telegram
            results["telegram"] = await send_trade_alert_telegram(test_proposal)
        except Exception as e:
            results["telegram"] = False
            print(f"[dispatcher] Test Telegram failed: {e}")

    if channel in ("websocket", "all"):
        try:
            from trading.engine import trading_engine
            await trading_engine._notify_clients({
                "type": "test_notification",
                "message": "IT-Bear notification system is working.",
                "timestamp": datetime.now().isoformat(),
            })
            results["websocket"] = True
        except Exception as e:
            results["websocket"] = False
            print(f"[dispatcher] Test WebSocket failed: {e}")

    return results
