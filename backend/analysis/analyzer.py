"""
analyzer.py — Multi-agent AI analysis using Groq + jugaad-data/pandas_ta

Public API:
    analyze_stock_ai(symbol, pnl_pct) → called by /api/analysis/ai/{symbol}

Pipeline (blocking, runs in asyncio.to_thread):
    Agent 1 — Technical  : RSI, MACD, EMA, Bollinger, ADX from screener → Groq prompt
    Agent 2 — Fundamental: PE, 52W high/low, P&L (yfinance fallback)   → Groq prompt
    Agent 3 — Synthesis  : combines both → DECISION/REASON format      → Groq prompt

Data sources:
    - Price data: jugaad-data (direct NSE) via screener.py, yfinance fallback
    - Fundamentals: yfinance (jugaad-data doesn't have PE, market cap etc.)
    - Technical indicators: pandas_ta via screener.py

Model: llama-3.3-70b-versatile via Groq (free tier, 128k context)

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
    Three focused Groq calls enriched with PKScreener-style technical indicators.

    Agent 1 — Technical  : RSI, MACD, EMA crossovers, Bollinger, ADX, volume
    Agent 2 — Fundamental: PE, 52W range, sector, current P&L
    Agent 3 — Synthesis  : final DECISION + REASON
    """
    from groq import Groq
    from analysis.screener import get_price_summary_for_prompt, get_fundamental_data

    load_dotenv(override=True)
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in .env. Get a free key at https://console.groq.com")

    client = Groq(api_key=api_key)
    print(f"[MultiAgent] Analyzing {symbol} with screener data…")

    # Fetch technical data from screener (jugaad-data + pandas_ta)
    tech_summary = get_price_summary_for_prompt(symbol)

    # Fetch fundamental data (yfinance fallback)
    fund_data = get_fundamental_data(symbol)
    pnl_pct = holding_data.get("pnl_percentage", 0)

    # ── Agent 1: Technical ───────────────────────────────────────────────────
    print(f"[MultiAgent] Agent 1 (Technical) for {symbol}…")
    tech_resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": (
                f"You are a technical analyst specializing in Indian NSE stocks. "
                f"Analyze {symbol} based on these technical indicators:\n\n"
                f"{tech_summary}\n\n"
                "Based on these indicators, give a Buy/Sell/Hold recommendation "
                "with 3-4 sentences explaining your reasoning."
            ),
        }],
        max_tokens=300,
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
                f"You are a fundamental analyst. {symbol} (NSE India) metrics:\n"
                f"PE Ratio: {fund_data['pe_ratio']}\n"
                f"Market Cap: {fund_data['market_cap_display']}\n"
                f"52W High: {fund_data['52w_high']}\n"
                f"52W Low: {fund_data['52w_low']}\n"
                f"Sector: {fund_data['sector']}\n"
                f"Book Value: {fund_data['book_value']}\n"
                f"Dividend Yield: {fund_data['dividend_yield']}\n"
                f"Current Unrealised P&L: {pnl_pct:+.1f}%\n\n"
                "Is it overvalued or undervalued? Give Buy/Sell/Hold with 3-4 sentences."
            ),
        }],
        max_tokens=300,
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
                f"You are a senior portfolio manager reviewing {symbol} stock (NSE India).\n\n"
                f"Technical analysis says: {tech_result}\n\n"
                f"Fundamental analysis says: {fund_result}\n\n"
                "Give ONE final recommendation. Reply with exactly:\n"
                "DECISION: [Buy/Sell/Hold]\n"
                "REASON: [4-5 sentences combining both technical and fundamental perspectives. "
                "Be specific about the indicators and metrics that led to your decision.]"
            ),
        }],
        max_tokens=500,
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
    """Fetch price data using screener (jugaad-data), fallback to yfinance."""
    try:
        from analysis.screener import get_price_summary_for_prompt
        return get_price_summary_for_prompt(symbol)
    except Exception:
        pass

    # Fallback to yfinance
    try:
        import yfinance as yf
        hist = yf.Ticker(f"{symbol}.NS").history(period="30d")
        if hist.empty:
            return f"No price data found for {symbol}.NS"
        lines = [f"{d.strftime('%Y-%m-%d')}: ₹{c:.2f}"
                 for d, c in hist["Close"].items()]
        return "\n".join(lines)
    except Exception as exc:
        return f"Price data unavailable for {symbol}: {exc}"


def _fetch_fundamental_metrics(symbol: str) -> str:
    """Fetch fundamental metrics using screener, fallback to yfinance."""
    try:
        from analysis.screener import get_fundamental_data
        data = get_fundamental_data(symbol)
        return (
            f"Sector: {data['sector']} | PE Ratio: {data['pe_ratio']} | "
            f"Market Cap: {data['market_cap_display']} | "
            f"52W High: ₹{data['52w_high']} | 52W Low: ₹{data['52w_low']} | "
            f"Book Value: {data['book_value']} | Dividend Yield: {data['dividend_yield']}"
        )
    except Exception:
        pass

    # Fallback to direct yfinance
    try:
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
    except Exception as exc:
        return f"Fundamental data unavailable for {symbol}: {exc}"


def _parse_synthesis(text: str) -> tuple[str, str]:
    rec_match = re.search(r"RECOMMENDATION\s*:\s*(Buy|Sell|Hold)", text, re.IGNORECASE)
    rea_match = re.search(r"REASONING\s*:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    recommendation = rec_match.group(1).capitalize() if rec_match else "Hold"
    if rea_match:
        reasoning = rea_match.group(1).strip()
    else:
        reasoning = text.strip()
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
