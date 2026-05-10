"""
email_sender.py — Send transactional emails via SMTP.

Configurable via env:
  SMTP_HOST     — SMTP server hostname (e.g. smtp.gmail.com)
  SMTP_PORT     — Port (default 587 for STARTTLS)
  SMTP_USER     — Sender email / username
  SMTP_PASS     — SMTP password or app password
  NOTIFY_EMAIL  — Recipient email (defaults to SMTP_USER if not set)

Falls back to print() if not configured — never raises.
"""
import asyncio
import os
import smtplib
import traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _is_configured() -> bool:
    """Check if SMTP is configured."""
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"))


def _get_recipient(to_email: str | None) -> str:
    """Determine recipient email."""
    if to_email:
        return to_email
    return os.getenv("NOTIFY_EMAIL") or os.getenv("SMTP_USER") or ""


def _blocking_send(subject: str, body_html: str, to_email: str) -> bool:
    """Blocking SMTP send. Run via asyncio.to_thread."""
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASS", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_email

    # Plain-text fallback
    import re
    plain = re.sub(r"<[^>]+>", " ", body_html).strip()
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [to_email], msg.as_string())

    return True


async def _log_notification(channel: str, subject: str, body: str,
                            success: bool, error_msg: str = "") -> None:
    """Log notification attempt to DB."""
    try:
        from db.database import _get_db
        async with _get_db() as db:
            await db.execute(
                """INSERT INTO notification_log (type, channel, subject, body, success, error_message)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("email", channel, subject[:500], body[:2000], 1 if success else 0, error_msg[:500] or None),
            )
            await db.commit()
    except Exception as e:
        print(f"[email_sender] Failed to log notification: {e}")


async def send_email(subject: str, body_html: str, to_email: str = None) -> bool:
    """
    Send an email. Returns True if sent, False if not configured or failed.
    If SMTP is not configured, prints the message to stdout (development mode).
    """
    recipient = _get_recipient(to_email)

    if not _is_configured():
        print(f"[email_sender] SMTP not configured. Would send to {recipient}:")
        print(f"  Subject: {subject}")
        print(f"  Body: {body_html[:300]}...")
        return False

    if not recipient:
        print("[email_sender] No recipient configured (set NOTIFY_EMAIL env var)")
        return False

    try:
        await asyncio.to_thread(_blocking_send, subject, body_html, recipient)
        print(f"[email_sender] Sent '{subject}' to {recipient}")
        await _log_notification("email", subject, body_html, True)
        return True
    except Exception as e:
        err = traceback.format_exc()
        print(f"[email_sender] Failed to send email: {e}")
        await _log_notification("email", subject, body_html, False, str(e)[:500])
        return False


def _format_legs_html(legs: list[dict]) -> str:
    """Format option legs as an HTML table."""
    if not legs:
        return "<p>No legs</p>"
    rows = ""
    for leg in legs:
        action = str(leg.get("action", "")).upper()
        opt_type = leg.get("type", leg.get("option_type", ""))
        strike = leg.get("strike", 0)
        qty = leg.get("qty", leg.get("quantity", 0))
        ltp = leg.get("ltp", 0)
        color = "#22c55e" if action == "BUY" else "#ef4444"
        rows += f"""
        <tr>
          <td style="padding:6px 12px;border-bottom:1px solid #334155;">
            <span style="color:{color};font-weight:600;">{action}</span>
          </td>
          <td style="padding:6px 12px;border-bottom:1px solid #334155;">{opt_type}</td>
          <td style="padding:6px 12px;border-bottom:1px solid #334155;">{strike}</td>
          <td style="padding:6px 12px;border-bottom:1px solid #334155;">{qty}</td>
          <td style="padding:6px 12px;border-bottom:1px solid #334155;">Rs.{ltp:.2f}</td>
        </tr>"""
    return f"""
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead>
        <tr style="background:#1e293b;color:#94a3b8;text-align:left;">
          <th style="padding:6px 12px;">Action</th>
          <th style="padding:6px 12px;">Type</th>
          <th style="padding:6px 12px;">Strike</th>
          <th style="padding:6px 12px;">Qty</th>
          <th style="padding:6px 12px;">LTP</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


async def send_trade_alert(proposal: dict) -> bool:
    """Send formatted trade alert email with key fields."""
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
    created_at = proposal.get("created_at", datetime.now().isoformat())

    direction_color = "#ef4444" if direction in ("BEARISH", "SHORT") else "#22c55e" if direction == "BULLISH" else "#f59e0b"

    subject = f"[IT-Bear] Trade Alert: {strategy} on {symbol} ({confidence}% confidence)"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#1e293b;border:1px solid #334155;
                  border-radius:12px;overflow:hidden;">
        <div style="background:#0f172a;padding:16px 24px;border-bottom:1px solid #334155;">
          <h1 style="margin:0;font-size:16px;color:#f8fafc;">
            IT-Bear Trade Signal
          </h1>
          <p style="margin:4px 0 0;font-size:12px;color:#64748b;">{created_at}</p>
        </div>
        <div style="padding:24px;">
          <table style="width:100%;margin-bottom:20px;">
            <tr>
              <td style="padding:4px 0;">
                <span style="color:#94a3b8;font-size:12px;">Symbol</span><br>
                <span style="font-size:20px;font-weight:700;">{symbol}</span>
              </td>
              <td style="padding:4px 0;text-align:right;">
                <span style="background:{direction_color};color:#fff;padding:4px 10px;
                              border-radius:20px;font-size:13px;font-weight:600;">{direction}</span>
              </td>
            </tr>
          </table>
          <p style="margin:0 0 4px;color:#94a3b8;font-size:12px;">Strategy</p>
          <p style="margin:0 0 16px;font-weight:600;">{strategy}
            {f'<span style="color:#64748b;font-size:12px;"> ({layer} layer)</span>' if layer else ""}
          </p>
          <div style="display:flex;gap:16px;margin-bottom:20px;">
            <div style="flex:1;background:#0f172a;border-radius:8px;padding:12px;">
              <p style="margin:0;color:#94a3b8;font-size:11px;">Max Profit</p>
              <p style="margin:4px 0 0;color:#22c55e;font-weight:700;">Rs.{max_profit:,.0f}</p>
            </div>
            <div style="flex:1;background:#0f172a;border-radius:8px;padding:12px;">
              <p style="margin:0;color:#94a3b8;font-size:11px;">Max Loss</p>
              <p style="margin:4px 0 0;color:#ef4444;font-weight:700;">Rs.{abs(max_loss):,.0f}</p>
            </div>
            <div style="flex:1;background:#0f172a;border-radius:8px;padding:12px;">
              <p style="margin:0;color:#94a3b8;font-size:11px;">Confidence</p>
              <p style="margin:4px 0 0;font-weight:700;">{confidence}%</p>
            </div>
          </div>
          <p style="margin:0 0 8px;color:#94a3b8;font-size:12px;">Legs</p>
          {_format_legs_html(legs)}
          <p style="margin:16px 0 8px;color:#94a3b8;font-size:12px;">Reasoning</p>
          <p style="margin:0;font-size:13px;line-height:1.6;color:#cbd5e1;">{reasoning}</p>
          <p style="margin:16px 0 0;font-size:11px;color:#475569;">
            Margin required: Rs.{margin:,.0f}
          </p>
        </div>
      </div>
    </body>
    </html>"""

    return await send_email(subject, body_html)


async def send_daily_brief(brief_data: dict) -> bool:
    """Send daily morning brief email."""
    date_str = brief_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    thesis_score = brief_data.get("thesis_score", 0)
    regime = brief_data.get("regime", "unknown")
    signals = brief_data.get("key_signals", [])
    open_positions = brief_data.get("open_positions", 0)
    unrealized_pnl = brief_data.get("unrealized_pnl", 0)
    upcoming_earnings = brief_data.get("upcoming_earnings", [])

    subject = f"[IT-Bear] Daily Brief — {date_str} | Thesis Score: {thesis_score}/100"

    signals_html = "".join(
        f'<li style="margin:4px 0;color:#cbd5e1;font-size:13px;">{s}</li>'
        for s in signals[:8]
    )

    earnings_html = ""
    if upcoming_earnings:
        rows = "".join(
            f'<tr><td style="padding:4px 12px;border-bottom:1px solid #1e293b;">{e.get("symbol","")}</td>'
            f'<td style="padding:4px 12px;border-bottom:1px solid #1e293b;">{e.get("date","")}</td>'
            f'<td style="padding:4px 12px;border-bottom:1px solid #1e293b;">{e.get("days_away","")}d</td></tr>'
            for e in upcoming_earnings[:5]
        )
        earnings_html = f"""
        <p style="margin:16px 0 8px;color:#94a3b8;font-size:12px;">Upcoming Earnings</p>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
          <tr style="color:#64748b;font-size:11px;">
            <td style="padding:4px 12px;">Symbol</td>
            <td style="padding:4px 12px;">Date</td>
            <td style="padding:4px 12px;">Days Away</td>
          </tr>{rows}
        </table>"""

    pnl_color = "#22c55e" if unrealized_pnl >= 0 else "#ef4444"
    score_color = "#ef4444" if thesis_score >= 60 else "#f59e0b" if thesis_score >= 40 else "#22c55e"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:20px;">
      <div style="max-width:600px;margin:0 auto;background:#1e293b;border:1px solid #334155;
                  border-radius:12px;overflow:hidden;">
        <div style="background:#0f172a;padding:16px 24px;border-bottom:1px solid #334155;">
          <h1 style="margin:0;font-size:16px;">IT-Bear Daily Brief</h1>
          <p style="margin:4px 0 0;font-size:12px;color:#64748b;">{date_str}</p>
        </div>
        <div style="padding:24px;">
          <div style="display:flex;gap:16px;margin-bottom:20px;">
            <div style="flex:1;background:#0f172a;border-radius:8px;padding:12px;text-align:center;">
              <p style="margin:0;color:#94a3b8;font-size:11px;">Thesis Score</p>
              <p style="margin:4px 0 0;color:{score_color};font-size:24px;font-weight:700;">{thesis_score}</p>
              <p style="margin:2px 0 0;font-size:11px;color:#64748b;">/100</p>
            </div>
            <div style="flex:1;background:#0f172a;border-radius:8px;padding:12px;text-align:center;">
              <p style="margin:0;color:#94a3b8;font-size:11px;">Regime</p>
              <p style="margin:4px 0 0;font-size:14px;font-weight:600;">{regime.replace("_", " ").title()}</p>
            </div>
            <div style="flex:1;background:#0f172a;border-radius:8px;padding:12px;text-align:center;">
              <p style="margin:0;color:#94a3b8;font-size:11px;">Open Positions</p>
              <p style="margin:4px 0 0;font-size:24px;font-weight:700;">{open_positions}</p>
            </div>
          </div>
          <div style="background:#0f172a;border-radius:8px;padding:12px;margin-bottom:20px;">
            <p style="margin:0;color:#94a3b8;font-size:11px;">Unrealized P&amp;L</p>
            <p style="margin:4px 0 0;color:{pnl_color};font-size:18px;font-weight:700;">
              Rs.{unrealized_pnl:+,.0f}
            </p>
          </div>
          <p style="margin:0 0 8px;color:#94a3b8;font-size:12px;">Key Signals</p>
          <ul style="margin:0;padding:0 0 0 16px;">{signals_html}</ul>
          {earnings_html}
        </div>
      </div>
    </body>
    </html>"""

    return await send_email(subject, body_html)
