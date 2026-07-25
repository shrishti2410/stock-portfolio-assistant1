"""
telegram_listener.py — Long-polling listener for incoming Telegram messages.

Runs as an asyncio background task. Routes incoming messages to handlers:
  /start        — register chat_id, save to .env
  /help         — show command help
  /add SYMS     — add symbols to watchlist + run analysis
  /analyze SYM  — quick Buy/Sell/Hold analysis
  /list         — show current watchlist
  /remove SYM   — remove from watchlist
  free text     — auto-detect symbol-like tokens, treat as /add

Symbols accepted as plain (TCS, INFY, AAPL, MSFT). The validator tries
{SYMBOL}.NS first (NSE), then plain symbol (US), and picks whichever
yfinance has price data for.
"""
import asyncio
import os
import re
import time
from datetime import datetime

import httpx


_TELEGRAM_BASE = "https://api.telegram.org/bot{token}"
_OFFSET_FILE = "/tmp/telegram_update_offset.txt"  # tracks last processed update_id
_running = False
_poll_task = None


def _is_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN"))


def _get_offset() -> int:
    try:
        with open(_OFFSET_FILE, "r") as f:
            return int(f.read().strip())
    except Exception:
        return 0


def _save_offset(offset: int) -> None:
    try:
        with open(_OFFSET_FILE, "w") as f:
            f.write(str(offset))
    except Exception:
        pass


async def _api_get(method: str, params: dict = None) -> dict:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return {}
    url = f"{_TELEGRAM_BASE.format(token=token)}/{method}"
    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            resp = await client.get(url, params=params or {})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"[telegram_listener] {method} failed: {e}")
        return {}


async def _send_message(chat_id: int | str, text: str, parse_mode: str = "Markdown") -> bool:
    """Send a message to a specific chat_id (different from broadcast in telegram_bot.py)."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return False
    url = f"{_TELEGRAM_BASE.format(token=token)}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            })
            return resp.status_code < 400
    except Exception as e:
        print(f"[telegram_listener] sendMessage failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Symbol parsing
# ---------------------------------------------------------------------------

# A "symbol" is 1-10 uppercase letters/digits, possibly followed by `.NS` etc.
SYMBOL_RE = re.compile(r"\b([A-Z][A-Z0-9]{0,9}(?:\.[A-Z]{1,3})?)\b")
STOPWORDS = {
    "I", "A", "BUY", "SELL", "HOLD", "ADD", "ANALYZE", "LIST", "HELP",
    "STOCK", "STOCKS", "OK", "YES", "NO", "PLEASE", "NSE", "BSE", "USA",
    "INDIA", "US", "INDIAN", "AND", "OR", "THE", "FOR", "OF", "TO", "ON",
    "AT", "BY", "IS", "IT", "AM", "PM", "AI", "GO", "HI", "HELLO",
}


def extract_symbols(text: str) -> list[str]:
    """Extract symbol-like tokens from free text. Skips common stopwords."""
    # Normalize: uppercase, replace separators
    upper = re.sub(r"[,\n;|]", " ", text.upper())
    found = []
    seen = set()
    for m in SYMBOL_RE.findall(upper):
        sym = m.strip(".")
        if sym in STOPWORDS or sym in seen or len(sym) < 2:
            continue
        seen.add(sym)
        found.append(sym)
    return found


# ---------------------------------------------------------------------------
# Stock validator + analyzer
# ---------------------------------------------------------------------------

async def validate_symbol(symbol: str) -> dict | None:
    """
    Try {SYMBOL}.NS first (NSE), then plain (US).
    Returns {symbol, yf_ticker, country, name, current_price} or None.
    """
    import yfinance as yf

    sym = symbol.upper().strip().lstrip("$")

    def _try(yf_sym: str, country: str) -> dict | None:
        try:
            t = yf.Ticker(yf_sym)
            hist = t.history(period="5d")
            if hist.empty:
                return None
            price = float(hist["Close"].iloc[-1])
            info = {}
            try:
                info = t.info
            except Exception:
                pass
            return {
                "symbol": sym,
                "yf_ticker": yf_sym,
                "country": country,
                "name": info.get("longName") or info.get("shortName") or sym,
                "current_price": round(price, 2),
                "currency": info.get("currency", "INR" if country == "IN" else "USD"),
            }
        except Exception:
            return None

    # Try NSE first if symbol doesn't have a dot already
    if "." not in sym:
        result = await asyncio.to_thread(_try, f"{sym}.NS", "IN")
        if result:
            return result
        # Try BSE
        result = await asyncio.to_thread(_try, f"{sym}.BO", "IN")
        if result:
            return result

    # Try plain (US)
    result = await asyncio.to_thread(_try, sym, "US")
    return result


async def analyze_symbol(stock: dict) -> dict:
    """
    Return a quick Buy/Hold/Sell verdict for a validated stock.

    Uses yfinance history → 50/200 DMA, RSI, 1m/3m return → simple scoring.
    Adds a Reasoning string.
    """
    import yfinance as yf
    import pandas as pd

    sym = stock["yf_ticker"]
    name = stock.get("name", sym)
    country = stock.get("country", "")

    def _compute() -> dict:
        try:
            hist = yf.Ticker(sym).history(period="1y")
            if hist.empty or len(hist) < 50:
                return {"verdict": "Unknown", "reasoning": "Not enough price history."}

            close = hist["Close"]
            current = float(close.iloc[-1])

            # 50-DMA & 200-DMA
            dma50 = float(close.tail(50).mean())
            dma200 = float(close.tail(min(200, len(close))).mean()) if len(close) >= 50 else dma50

            # RSI(14)
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            rsi = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else 50

            # Returns
            ret_1m = (current / float(close.iloc[-21]) - 1) * 100 if len(close) > 21 else 0
            ret_3m = (current / float(close.iloc[-63]) - 1) * 100 if len(close) > 63 else 0
            ret_6m = (current / float(close.iloc[-126]) - 1) * 100 if len(close) > 126 else 0

            # Scoring
            score = 0
            signals = []

            if current > dma50: score += 1; signals.append("Price > 50-DMA")
            else: score -= 1; signals.append("Price < 50-DMA")

            if dma50 > dma200: score += 1; signals.append("50-DMA > 200-DMA (golden trend)")
            else: score -= 1; signals.append("50-DMA < 200-DMA (death trend)")

            if rsi < 30: score += 2; signals.append(f"RSI {rsi:.0f} — oversold (potential bounce)")
            elif rsi > 70: score -= 2; signals.append(f"RSI {rsi:.0f} — overbought")
            elif rsi > 55: score += 1; signals.append(f"RSI {rsi:.0f} — bullish momentum")
            elif rsi < 45: score -= 1; signals.append(f"RSI {rsi:.0f} — bearish momentum")

            if ret_3m > 10: score += 1
            elif ret_3m < -10: score -= 1

            # Verdict
            if score >= 3:
                verdict = "Buy"
                emoji = "🟢"
            elif score <= -3:
                verdict = "Sell"
                emoji = "🔴"
            else:
                verdict = "Hold"
                emoji = "🟡"

            return {
                "verdict": verdict,
                "emoji": emoji,
                "score": score,
                "current_price": round(current, 2),
                "dma50": round(dma50, 2),
                "dma200": round(dma200, 2),
                "rsi": round(rsi, 1),
                "ret_1m": round(ret_1m, 2),
                "ret_3m": round(ret_3m, 2),
                "ret_6m": round(ret_6m, 2),
                "signals": signals,
            }
        except Exception as e:
            return {"verdict": "Unknown", "reasoning": f"Analysis failed: {e}"}

    return await asyncio.to_thread(_compute)


# ---------------------------------------------------------------------------
# DB helpers — telegram_watchlist table
# ---------------------------------------------------------------------------

async def _ensure_watchlist_table():
    from db.database import _get_db
    async with _get_db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS telegram_watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                yf_ticker TEXT,
                name TEXT,
                country TEXT,
                added_via TEXT DEFAULT 'telegram',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_verdict TEXT,
                last_verdict_at TIMESTAMP
            )
        """)
        await db.commit()


async def _add_to_watchlist(stock: dict, verdict: str = None):
    from db.database import _get_db
    await _ensure_watchlist_table()
    async with _get_db() as db:
        await db.execute(
            """INSERT OR REPLACE INTO telegram_watchlist
               (symbol, yf_ticker, name, country, last_verdict, last_verdict_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (stock["symbol"], stock["yf_ticker"], stock.get("name"),
             stock.get("country"), verdict),
        )
        await db.commit()


async def _get_watchlist() -> list[dict]:
    from db.database import _get_db
    import aiosqlite
    await _ensure_watchlist_table()
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM telegram_watchlist ORDER BY added_at DESC LIMIT 100"
        )
        return [dict(r) for r in rows]


async def _remove_from_watchlist(symbol: str) -> bool:
    from db.database import _get_db
    async with _get_db() as db:
        cursor = await db.execute(
            "DELETE FROM telegram_watchlist WHERE symbol = ?", (symbol.upper(),)
        )
        await db.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

HELP_TEXT = (
    "*Stock Portfolio Bot* 🤖\n\n"
    "*Commands:*\n"
    "`/add TCS INFY AAPL` — add stocks to watchlist + auto-analyze\n"
    "`/analyze RELIANCE` — quick Buy/Sell/Hold for any stock\n"
    "`/list` — show your watchlist\n"
    "`/remove TCS` — remove from watchlist\n"
    "`/help` — this message\n\n"
    "_You can also paste a list of symbols (e.g. `TCS INFY ACN`) and I'll auto-detect them._\n\n"
    "Works for *Indian NSE/BSE* stocks (try `TCS`, `RELIANCE`, `HDFCBANK`) "
    "and *US* stocks (try `AAPL`, `MSFT`, `NVDA`)."
)


def _fmt_price(price: float, currency: str) -> str:
    if currency == "INR":
        return f"₹{price:,.2f}"
    return f"${price:,.2f}"


async def _format_analysis(stock: dict, analysis: dict) -> str:
    name = stock.get("name", stock["symbol"])
    country = stock.get("country", "")
    flag = "🇮🇳" if country == "IN" else "🇺🇸" if country == "US" else ""
    currency = stock.get("currency", "INR" if country == "IN" else "USD")
    emoji = analysis.get("emoji", "🟡")
    verdict = analysis.get("verdict", "Unknown")

    if verdict == "Unknown":
        return f"{flag} *{stock['symbol']}* — {analysis.get('reasoning', 'No data')}"

    signals = analysis.get("signals", [])
    signals_txt = "\n".join(f"  • {s}" for s in signals[:4])
    return (
        f"{flag} *{stock['symbol']}* ({name[:30]})\n"
        f"{emoji} *{verdict}* (score {analysis.get('score', 0):+d})\n"
        f"  Price: {_fmt_price(analysis['current_price'], currency)}\n"
        f"  RSI: {analysis['rsi']} | 50-DMA: {_fmt_price(analysis['dma50'], currency)}\n"
        f"  1m: {analysis['ret_1m']:+.1f}% | 3m: {analysis['ret_3m']:+.1f}% | 6m: {analysis['ret_6m']:+.1f}%\n"
        f"{signals_txt}"
    )


async def handle_start(chat_id: int, args: str) -> str:
    # Save chat_id to .env so broadcast notifications go to this user
    from zerodha.auth import _write_env_key
    try:
        _write_env_key("TELEGRAM_CHAT_ID", str(chat_id))
        os.environ["TELEGRAM_CHAT_ID"] = str(chat_id)
        return (
            "✅ *Connected!* Your chat is now linked.\n\n"
            f"`TELEGRAM_CHAT_ID={chat_id}` saved to `.env`\n\n"
            + HELP_TEXT
        )
    except Exception as e:
        return f"⚠️ Connected but couldn't save chat_id to .env: {e}\n\n{HELP_TEXT}"


async def handle_help(chat_id: int, args: str) -> str:
    return HELP_TEXT


async def handle_add(chat_id: int, args: str) -> str:
    symbols = extract_symbols(args)
    if not symbols:
        return "❌ No symbols found. Try: `/add TCS INFY AAPL`"

    await _send_message(chat_id, f"⏳ Looking up {len(symbols)} symbol(s)... (may take 10-30s)")

    results = []
    sem = asyncio.Semaphore(4)

    async def _process(sym: str):
        async with sem:
            stock = await validate_symbol(sym)
            if not stock:
                results.append(f"❌ *{sym}* — not found on NSE/BSE/US markets")
                return
            analysis = await analyze_symbol(stock)
            await _add_to_watchlist(stock, analysis.get("verdict"))
            results.append(await _format_analysis(stock, analysis))

    await asyncio.gather(*[_process(s) for s in symbols])

    header = f"📊 *Analysis ({len(symbols)} stocks)*\n\n"
    return header + "\n\n".join(results)


async def handle_analyze(chat_id: int, args: str) -> str:
    symbols = extract_symbols(args)
    if not symbols:
        return "❌ Usage: `/analyze SYMBOL` (e.g. `/analyze RELIANCE`)"

    sym = symbols[0]
    await _send_message(chat_id, f"⏳ Analyzing *{sym}*...")
    stock = await validate_symbol(sym)
    if not stock:
        return f"❌ *{sym}* — not found on NSE/BSE/US markets"
    analysis = await analyze_symbol(stock)
    return await _format_analysis(stock, analysis)


async def handle_list(chat_id: int, args: str) -> str:
    items = await _get_watchlist()
    if not items:
        return "📭 Watchlist is empty. Add stocks with `/add TCS INFY AAPL`"

    lines = [f"📋 *Watchlist ({len(items)} stocks)*\n"]
    for item in items:
        flag = "🇮🇳" if item["country"] == "IN" else "🇺🇸"
        verdict = item.get("last_verdict") or "—"
        emoji = "🟢" if verdict == "Buy" else "🔴" if verdict == "Sell" else "🟡"
        lines.append(f"{flag} *{item['symbol']}* {emoji} {verdict}")
    return "\n".join(lines)


async def handle_remove(chat_id: int, args: str) -> str:
    symbols = extract_symbols(args)
    if not symbols:
        return "❌ Usage: `/remove TCS`"
    removed = []
    not_found = []
    for sym in symbols:
        ok = await _remove_from_watchlist(sym)
        (removed if ok else not_found).append(sym)
    msg = ""
    if removed:
        msg += f"✅ Removed: {', '.join(removed)}\n"
    if not_found:
        msg += f"❌ Not in watchlist: {', '.join(not_found)}"
    return msg.strip()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

HANDLERS = {
    "/start": handle_start,
    "/help": handle_help,
    "/add": handle_add,
    "/analyze": handle_analyze,
    "/list": handle_list,
    "/remove": handle_remove,
}


async def _route_message(message: dict):
    """Dispatch incoming Telegram message to handler."""
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()
    if not chat_id or not text:
        return

    print(f"[telegram_listener] msg from {chat_id}: {text[:60]}")

    # Parse command
    parts = text.split(None, 1)
    cmd = parts[0].lower().split("@")[0]  # strip @botname mentions
    args = parts[1] if len(parts) > 1 else ""

    handler = HANDLERS.get(cmd)

    # If not a known command, try to extract symbols → treat as /add
    if not handler:
        symbols = extract_symbols(text)
        if symbols:
            response = (
                f"🔍 Detected symbols: `{', '.join(symbols)}`\n"
                f"Adding to watchlist and analyzing...\n\n"
                + await handle_add(chat_id, text)
            )
        else:
            response = "🤔 I didn't understand that. Send `/help` to see commands."
    else:
        try:
            response = await handler(chat_id, args)
        except Exception as e:
            response = f"⚠️ Error: {e}"
            import traceback; traceback.print_exc()

    # Telegram has a 4096 char limit per message — chunk if needed
    for chunk in _chunk_message(response):
        await _send_message(chat_id, chunk)


def _chunk_message(text: str, max_len: int = 3800) -> list[str]:
    """Split message into chunks respecting markdown boundaries."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current)
            current = line
        else:
            current += ("\n" if current else "") + line
    if current:
        chunks.append(current)
    return chunks


# ---------------------------------------------------------------------------
# Long-polling loop
# ---------------------------------------------------------------------------

async def _poll_loop():
    global _running
    print("[telegram_listener] 🚀 Long-polling started")
    consecutive_errors = 0

    while _running:
        if not _is_configured():
            await asyncio.sleep(30)
            continue

        offset = _get_offset()
        try:
            result = await _api_get("getUpdates", {
                "offset": offset + 1,
                "timeout": 25,  # long-poll
                "allowed_updates": ["message"],
            })
            consecutive_errors = 0

            if not result.get("ok"):
                print(f"[telegram_listener] API error: {result}")
                await asyncio.sleep(5)
                continue

            updates = result.get("result", [])
            for upd in updates:
                update_id = upd.get("update_id", 0)
                if update_id > offset:
                    _save_offset(update_id)
                msg = upd.get("message")
                if msg:
                    asyncio.create_task(_route_message(msg))

        except Exception as e:
            consecutive_errors += 1
            print(f"[telegram_listener] poll error #{consecutive_errors}: {e}")
            await asyncio.sleep(min(30, 2 ** consecutive_errors))


async def start_listener():
    """Start the long-polling listener as a background task."""
    global _running, _poll_task
    if _running:
        return {"status": "already_running"}
    if not _is_configured():
        return {"status": "not_configured", "message": "TELEGRAM_BOT_TOKEN missing"}
    _running = True
    _poll_task = asyncio.create_task(_poll_loop())
    return {"status": "started"}


async def stop_listener():
    """Stop the listener."""
    global _running, _poll_task
    _running = False
    if _poll_task:
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass
    return {"status": "stopped"}


def is_listening() -> bool:
    return _running
