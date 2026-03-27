"""
analyzer.py — Multi-agent AI analysis using Groq + yfinance

Public API:
    analyze_stock_ai(symbol, pnl_pct) → called by /api/analysis/ai/{symbol}

Pipeline (blocking, runs in asyncio.to_thread):
    Agent 1 — Technical  : last 10 days closing prices → Groq prompt (~100 tokens out)
    Agent 2 — Fundamental: PE, 52W high/low, P&L      → Groq prompt (~100 tokens out)
    Agent 3 — Synthesis  : combines both → DECISION/REASON format (~150 tokens out)

Model: llama-3.3-70b-versatile via Groq (free tier, 128k context)
Each agent call sends <500 tokens total — well within free limits.

Fallback: Gemini three-agent analysis on data/symbol errors.
Cache: per-symbol, 1 hour TTL (only successful results are cached).
Requires: GROQ_API_KEY in .env  (https://console.groq.com)
          GOOGLE_API_KEY in .env (fallback only)
"""

import asyncio
import os
import re
import time

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_ai_cache: dict[str, dict] = {}          # {SYMBOL: {"result": dict, "timestamp": float}}
_CACHE_TTL_SECONDS: int = 3600           # 1 hour

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TREND_MAP = {"Buy": "Bullish", "Sell": "Bearish", "Hold": "Neutral"}

_NSE_SYMBOLS = {
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "WIPRO",
    "ICICIBANK", "HINDUNILVR", "SBIN", "BHARTIARTL",
    "ITC", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE",
}


def get_nse_symbol(symbol: str) -> str:
    """Return Yahoo Finance format for Indian NSE stocks (appends .NS)."""
    if symbol.upper() in _NSE_SYMBOLS:
        return symbol.upper() + ".NS"
    return symbol.upper()


def _is_symbol_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(k in msg for k in ("delisted", "no timezone", "no data", "not found", "invalid symbol"))


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in str(exc) or "quota" in msg or "rate" in msg or "exhausted" in msg


# ---------------------------------------------------------------------------
# Primary: Groq multi-agent analysis
# ---------------------------------------------------------------------------

def run_multi_agent_analysis(symbol: str, holding_data: dict) -> dict:
    """
    Three focused Groq calls — each under 500 tokens total.

    Agent 1 — Technical  : last 10 days prices
    Agent 2 — Fundamental: PE, 52W range, current P&L
    Agent 3 — Synthesis  : final DECISION + REASON
    """
    import yfinance as yf
    from groq import Groq

    load_dotenv(override=True)
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in .env. Get a free key at https://console.groq.com")

    client     = Groq(api_key=api_key)
    nse_symbol = get_nse_symbol(symbol)
    print(f"[MultiAgent] Using symbol: {nse_symbol}")

    ticker = yf.Ticker(nse_symbol)
    hist   = ticker.history(period="1mo")
    info   = ticker.info

    prices  = hist["Close"].tail(10).round(2).to_dict()
    pnl_pct = holding_data.get("pnl_percentage", 0)
    metrics = {
        "pe_ratio":      info.get("trailingPE",       "N/A"),
        "52w_high":      info.get("fiftyTwoWeekHigh", "N/A"),
        "52w_low":       info.get("fiftyTwoWeekLow",  "N/A"),
        "current_price": info.get("currentPrice",     "N/A"),
        "pnl_pct":       pnl_pct,
    }

    # ── Agent 1: Technical ───────────────────────────────────────────────────
    print(f"[MultiAgent] Agent 1 (Technical) for {symbol}…")
    tech_resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": (
                f"You are a technical analyst. Analyze {symbol} stock. "
                f"Last 10 days closing prices: {prices}. "
                "Give Buy/Sell/Hold with one sentence reason."
            ),
        }],
        max_tokens=100,
    )
    tech_result = tech_resp.choices[0].message.content
    print(f"[MultiAgent] Technical: {tech_result[:80]}…")

    # ── Agent 2: Fundamental ─────────────────────────────────────────────────
    print(f"[MultiAgent] Agent 2 (Fundamental) for {symbol}…")
    fund_resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": (
                f"You are a fundamental analyst. {symbol} metrics: "
                f"PE={metrics['pe_ratio']}, "
                f"52W High={metrics['52w_high']}, "
                f"52W Low={metrics['52w_low']}, "
                f"Current P&L={metrics['pnl_pct']}%. "
                "Give Buy/Sell/Hold with one sentence reason."
            ),
        }],
        max_tokens=100,
    )
    fund_result = fund_resp.choices[0].message.content
    print(f"[MultiAgent] Fundamental: {fund_result[:80]}…")

    # ── Agent 3: Synthesis ───────────────────────────────────────────────────
    print(f"[MultiAgent] Agent 3 (Synthesis) for {symbol}…")
    final_resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": (
                f"You are a portfolio manager. For {symbol} stock:\n"
                f"Technical says: {tech_result}\n"
                f"Fundamental says: {fund_result}\n"
                "Reply with exactly:\n"
                "DECISION: [Buy/Sell/Hold]\n"
                "REASON: [one sentence]"
            ),
        }],
        max_tokens=150,
    )
    final_result = final_resp.choices[0].message.content
    print(f"[MultiAgent] Synthesis raw: {final_result}")

    # ── Parse output ─────────────────────────────────────────────────────────
    upper = final_result.upper()
    if "BUY" in upper:
        recommendation = "Buy"
    elif "SELL" in upper:
        recommendation = "Sell"
    else:
        recommendation = "Hold"

    reasoning = final_result.replace("DECISION:", "").replace("REASON:", "").strip()
    if len(reasoning) > 200:
        reasoning = reasoning[:200].rsplit(" ", 1)[0] + "…"

    print(f"[MultiAgent] {symbol} → {recommendation}")

    return {
        "recommendation": recommendation,
        "reasoning":      reasoning,
        "trend":          _TREND_MAP.get(recommendation, "Neutral"),
        "confidence":     0.78,
        "source":         "multi_agent_groq",
    }


# ---------------------------------------------------------------------------
# Fallback: Gemini three-agent analysis (on data/symbol errors)
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str) -> str:
    import google.generativeai as genai

    load_dotenv(override=True)
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY is not set in .env. "
            "Get a free key at https://aistudio.google.com/"
        )
    genai.configure(api_key=api_key)

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        return model.generate_content(prompt).text
    except Exception as exc:
        if not _is_rate_limit(exc):
            raise
        print("[analyzer] gemini-2.5-flash rate limited, waiting 10 s…")
        time.sleep(10)

    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    return model.generate_content(prompt).text


def _fetch_price_data(symbol: str) -> str:
    import yfinance as yf
    hist = yf.Ticker(f"{symbol}.NS").history(period="30d")
    if hist.empty:
        return f"No price data found for {symbol}.NS"
    lines = [f"{d.strftime('%Y-%m-%d')}: ₹{c:.2f}"
             for d, c in hist["Close"].items()]
    return "\n".join(lines)


def _fetch_fundamental_metrics(symbol: str) -> str:
    import yfinance as yf
    info      = yf.Ticker(f"{symbol}.NS").info
    pe        = info.get("trailingPE",       "N/A")
    mktcap    = info.get("marketCap",        "N/A")
    week_high = info.get("fiftyTwoWeekHigh", "N/A")
    week_low  = info.get("fiftyTwoWeekLow",  "N/A")
    sector    = info.get("sector",           "N/A")
    if isinstance(mktcap, (int, float)):
        mktcap = f"₹{mktcap / 1e7:.1f} Cr"
    return (
        f"Sector: {sector} | PE Ratio: {pe} | Market Cap: {mktcap} | "
        f"52W High: ₹{week_high} | 52W Low: ₹{week_low}"
    )


def _parse_synthesis(text: str) -> tuple[str, str]:
    rec_match = re.search(r"RECOMMENDATION\s*:\s*(Buy|Sell|Hold)", text, re.IGNORECASE)
    rea_match = re.search(r"REASONING\s*:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    recommendation = rec_match.group(1).capitalize() if rec_match else "Hold"
    if rea_match:
        reasoning = rea_match.group(1).strip()
        if len(reasoning) > 150:
            reasoning = reasoning[:150].rsplit(" ", 1)[0] + "…"
    else:
        reasoning = text.strip()[:150]
    return recommendation, reasoning


def _signals_agree(tech: str, fund: str, final: str) -> bool:
    def extract(t: str) -> str:
        t = t.lower()
        if "buy"  in t: return "buy"
        if "sell" in t: return "sell"
        return "hold"
    return extract(tech) == extract(final) and extract(fund) == extract(final)


def _run_gemini_analysis(symbol: str, pnl_pct: float) -> dict:
    """Gemini three-agent fallback — used when Groq/data fetch fails."""
    print(f"[analyzer] Gemini fallback — Agent 1 (Technical) for {symbol}…")
    price_data  = _fetch_price_data(symbol)
    tech_result = _call_gemini(
        f"You are a stock technical analyst. Analyze this 30-day closing price data "
        f"for {symbol} (NSE India):\n\n{price_data}\n\n"
        "Give a Buy/Sell/Hold signal with 2 sentence reasoning."
    )
    print(f"[analyzer] Technical: {tech_result[:80]}…")

    print(f"[analyzer] Gemini fallback — Agent 2 (Fundamental) for {symbol}…")
    metrics     = _fetch_fundamental_metrics(symbol)
    fund_result = _call_gemini(
        f"You are a fundamental analyst. Given these metrics for {symbol} (NSE India):\n"
        f"{metrics}\n\n"
        "Is it overvalued or undervalued? Give Buy/Sell/Hold with 2 sentence reasoning."
    )
    print(f"[analyzer] Fundamental: {fund_result[:80]}…")

    print(f"[analyzer] Gemini fallback — Agent 3 (Synthesis) for {symbol}…")
    synth_result = _call_gemini(
        f"You are a senior portfolio manager reviewing {symbol} stock.\n\n"
        f"Technical analysis: {tech_result}\n\n"
        f"Fundamental analysis: {fund_result}\n\n"
        f"Current unrealised P&L: {pnl_pct:+.2f}%\n\n"
        "Give ONE final recommendation: Buy, Sell, or Hold.\n"
        "Then give a 2-3 sentence summary of your reasoning.\n"
        "Format your response exactly as:\n"
        "RECOMMENDATION: [Buy/Sell/Hold]\n"
        "REASONING: [your reasoning here]"
    )
    print(f"[analyzer] Synthesis raw: {synth_result[:120]}…")

    recommendation, reasoning = _parse_synthesis(synth_result)
    confidence = 0.85 if _signals_agree(tech_result, fund_result, recommendation) else 0.65

    return {
        "recommendation": recommendation,
        "reasoning":      reasoning,
        "trend":          _TREND_MAP.get(recommendation, "Neutral"),
        "confidence":     confidence,
        "source":         "gemini",
    }


# ---------------------------------------------------------------------------
# Rule-based fallback (used when both Groq and Gemini fail)
# ---------------------------------------------------------------------------

def _rule_based_fallback(symbol: str, reason: str = "") -> dict:
    msg = f"AI unavailable for {symbol}"
    if reason:
        msg += f": {reason[:80]}"
    return {
        "recommendation": "Hold",
        "reasoning":      msg,
        "trend":          "Neutral",
        "confidence":     0.4,
        "source":         "rule_based",
    }


# ---------------------------------------------------------------------------
# Public API — called by /api/analysis/ai/{symbol}
# ---------------------------------------------------------------------------

async def analyze_stock_ai(symbol: str, pnl_pct: float = 0.0) -> dict:
    """
    Return a multi-agent Groq recommendation for a single stock.
    Falls back to Gemini three-agent analysis, then to rule-based Hold.

    Args:
        symbol : NSE ticker, e.g. "RELIANCE"
        pnl_pct: unrealised P&L % from the portfolio

    Returns:
        {recommendation, reasoning, trend, confidence, source}

    Never raises — always returns a usable dict.
    """
    symbol = symbol.upper().strip()
    now    = time.time()

    # ── Cache hit ─────────────────────────────────────────────────────────────
    cached = _ai_cache.get(symbol)
    if cached and (now - cached["timestamp"]) < _CACHE_TTL_SECONDS:
        print(f"[analyzer] Cache hit for {symbol}")
        return cached["result"]

    # ── Run Groq multi-agent in a thread (blocking) ───────────────────────────
    holding_data = {"pnl_percentage": pnl_pct}
    try:
        result = await asyncio.to_thread(run_multi_agent_analysis, symbol, holding_data)
    except Exception as exc:
        print(f"[analyzer] Groq multi-agent failed for {symbol}: {exc}")
        if _is_symbol_error(exc):
            print(f"[analyzer] Switching to Gemini fallback for {symbol}…")
            try:
                result = await asyncio.to_thread(_run_gemini_analysis, symbol, pnl_pct)
            except Exception as exc2:
                print(f"[analyzer] Gemini fallback also failed: {exc2}")
                result = _rule_based_fallback(symbol, str(exc2))
        else:
            result = _rule_based_fallback(symbol, str(exc))

    # Only cache successful results
    if result.get("source") not in ("rule_based", "error"):
        _ai_cache[symbol] = {"result": result, "timestamp": now}

    return result
