"""
main.py — FastAPI entry point for Stock Portfolio Assistant

Endpoints
---------
GET /health                            → liveness check
GET /api/portfolio                     → raw holdings from Zerodha (or dummy data)
GET /api/analysis/{symbol}             → rule-based Buy/Sell/Hold for a single stock
GET /api/analysis/ai/{symbol}          → TradingAgents + Gemini AI analysis (slow, 120s timeout)
GET /api/dashboard                     → holdings + rule-based analysis merged per stock
GET /api/auth/login                    → returns Zerodha login URL
GET /api/auth/callback?request_token=  → exchanges token, saves to .env

/api/dashboard stays fast (rule-based).
/api/analysis/ai/{symbol} is the slow AI path — called on explicit user request only.
"""

import asyncio
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from zerodha.client import get_holdings
from zerodha.auth import get_login_url, exchange_token
from analysis.analyzer import analyze_stock_ai, _ai_cache

load_dotenv()

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Stock Portfolio Assistant", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Rule-based analysis (no external API calls)
# ---------------------------------------------------------------------------
#
# Thresholds based on pnl_percentage:
#
#   pnl_pct ≥ 15%          → Sell   (Bullish → take profit)
#   5% ≤ pnl_pct < 15%     → Hold   (Bullish, moderate gain — let it run)
#  -5% ≤ pnl_pct <  5%     → Hold   (Neutral, near breakeven)
# -15% ≤ pnl_pct < -5%     → Hold   (Bearish, await recovery)
#   pnl_pct < -15%         → Sell   (Bearish, cut significant loss)

def _rule_based_analysis(symbol: str, pnl_pct: float) -> dict:
    """
    Derive a Buy/Sell/Hold recommendation purely from the unrealised P&L percentage.

    Args:
        symbol : stock ticker (used only to personalise the reasoning string)
        pnl_pct: unrealised P&L as a percentage, e.g. 8.5 or -12.3

    Returns:
        {
            "recommendation": "Buy" | "Sell" | "Hold",
            "reasoning":      str,
            "trend":          "Bullish" | "Neutral" | "Bearish",
            "confidence":     float (0.0–1.0),
        }
    """
    if pnl_pct >= 15.0:
        return {
            "recommendation": "Sell",
            "reasoning": (
                f"{symbol} is up {pnl_pct:.1f}% — strong gains achieved. "
                "Consider locking in profits; further upside may be limited at current levels."
            ),
            "trend":      "Bullish",
            "confidence": 0.75,
        }

    if pnl_pct >= 5.0:
        return {
            "recommendation": "Hold",
            "reasoning": (
                f"{symbol} is up {pnl_pct:.1f}% — moderate gain in progress. "
                "Momentum looks positive; hold and review if gains accelerate past 15%."
            ),
            "trend":      "Bullish",
            "confidence": 0.65,
        }

    if pnl_pct >= -5.0:
        return {
            "recommendation": "Hold",
            "reasoning": (
                f"{symbol} is near breakeven ({pnl_pct:+.1f}%). "
                "No strong signal either way; continue monitoring for a clearer directional move."
            ),
            "trend":      "Neutral",
            "confidence": 0.55,
        }

    if pnl_pct >= -15.0:
        return {
            "recommendation": "Hold",
            "reasoning": (
                f"{symbol} is down {abs(pnl_pct):.1f}%. "
                "Loss is within tolerable range; await a potential recovery before acting."
            ),
            "trend":      "Bearish",
            "confidence": 0.60,
        }

    # pnl_pct < -15 %
    return {
        "recommendation": "Sell",
        "reasoning": (
            f"{symbol} is down {abs(pnl_pct):.1f}% — significant loss. "
            "Consider cutting the position to prevent further downside."
        ),
        "trend":      "Bearish",
        "confidence": 0.70,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_holding_for_symbol(symbol: str) -> dict:
    """
    Return the holdings dict for a single symbol, or raise 404.
    Looks up from the full holdings list so dummy-data mode works too.
    """
    holdings = await get_holdings()
    symbol_upper = symbol.upper().strip()
    for h in holdings:
        if h["symbol"].upper() == symbol_upper:
            return h
    raise HTTPException(
        status_code=404,
        detail=f"Symbol '{symbol_upper}' not found in current portfolio.",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Liveness probe — always returns ok."""
    return {"status": "ok"}


@app.get("/api/portfolio")
async def get_portfolio():
    """
    Return the current portfolio holdings.

    Uses Zerodha Kite Connect when ZERODHA_ACCESS_TOKEN is set,
    otherwise returns dummy data (see zerodha/client.py).

    Response shape (list):
        symbol, quantity, average_price, last_price, pnl, pnl_percentage
    """
    try:
        holdings = await get_holdings()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch holdings: {exc}")
    return holdings


@app.delete("/api/analysis/cache")
async def clear_analysis_cache():
    """Clear the in-memory AI analysis cache (forces re-analysis on next request)."""
    count = len(_ai_cache)
    _ai_cache.clear()
    return {"cleared": count}


@app.get("/api/analysis/ai/{symbol}")
async def get_analysis_ai(symbol: str):
    """
    Run TradingAgents + Google Gemini analysis for a single stock.

    This is the slow path (30–90 seconds). It is only called on explicit
    user request from the "Run AI Analysis" button — never by the dashboard.

    Results are cached for 1 hour in analyzer._ai_cache.

    Requires GOOGLE_API_KEY in .env.
    Timeout: 120 seconds.
    """
    symbol = symbol.upper().strip()
    # Always evict the cache entry so each button press triggers a fresh run
    _ai_cache.pop(symbol, None)
    try:
        holdings = await get_holdings()
        holding  = next((h for h in holdings if h["symbol"].upper() == symbol), {})
        pnl_pct  = holding.get("pnl_percentage", 0.0)
        result = await asyncio.wait_for(analyze_stock_ai(symbol, pnl_pct), timeout=600.0)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Analysis for {symbol} timed out after 600 seconds. Try again.",
        )
    return {"symbol": symbol, **result}


@app.get("/api/analysis/{symbol}")
async def get_analysis(symbol: str):
    """
    Return a rule-based Buy/Sell/Hold recommendation for a single stock.

    The recommendation is derived purely from the holding's unrealised P&L
    percentage — no external AI API is called.

    Path param:
        symbol: e.g. RELIANCE, TCS

    Response shape:
        symbol, recommendation, reasoning, trend, confidence,
        pnl_percentage (echo of the input used for the decision)
    """
    try:
        holding = await _get_holding_for_symbol(symbol)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch holding data: {exc}")

    pnl_pct = holding.get("pnl_percentage", 0.0)
    analysis = _rule_based_analysis(holding["symbol"], pnl_pct)

    return {
        "symbol":         holding["symbol"],
        "pnl_percentage": pnl_pct,
        **analysis,
    }


@app.get("/api/dashboard")
async def get_dashboard():
    """
    Return holdings merged with rule-based analysis for every stock.

    Fetches all holdings in one call, then fans out analysis concurrently
    via asyncio.gather so the response time doesn't grow linearly with
    portfolio size.

    Response shape (list):
        symbol, quantity, avg_price, current_price,
        pnl, pnl_pct, recommendation, reasoning, trend, confidence
    """
    try:
        holdings = await get_holdings()
    except Exception:
        # get_holdings() should never raise (it catches internally),
        # but if something unexpected slips through, serve dummy data.
        from zerodha.client import _dummy_holdings
        holdings = _dummy_holdings()

    async def _merge(holding: dict) -> dict:
        symbol  = holding["symbol"]
        pnl_pct = holding.get("pnl_percentage", 0.0)
        analysis = _rule_based_analysis(symbol, pnl_pct)
        return {
            "symbol":        symbol,
            "quantity":      holding.get("quantity", 0),
            "avg_price":     holding.get("average_price", 0.0),
            "current_price": holding.get("last_price", 0.0),
            "pnl":           holding.get("pnl", 0.0),
            "pnl_pct":       pnl_pct,
            **analysis,  # recommendation, reasoning, trend, confidence
        }

    dashboard = await asyncio.gather(*[_merge(h) for h in holdings])
    return list(dashboard)


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.get("/api/auth/login")
async def auth_login():
    """
    Return the Zerodha login URL so the frontend can open it in a new tab.

    The URL follows Kite Connect v3 format:
        https://kite.zerodha.com/connect/login?api_key=<key>&v=3

    Requires ZERODHA_API_KEY to be set in .env.
    """
    api_key = os.getenv("ZERODHA_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="ZERODHA_API_KEY is not configured. Add it to your .env file.",
        )
    # Construct URL directly per the specified format (v=3)
    login_url = f"https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"
    return {"login_url": login_url}


@app.get("/api/auth/callback", response_class=HTMLResponse)
async def auth_callback(
    request_token: str = Query(None),
    action: str = Query(None),
    status: str = Query(None),
):
    """
    Zerodha redirects the browser here after login with:
        ?action=login&type=login&status=success&request_token=XXXX

    Exchanges the token, saves it to .env, and returns an HTML page the
    user sees in the browser tab — no manual copy-paste required.
    """
    if not request_token or not request_token.strip():
        return HTMLResponse(_html_page(
            success=False,
            message="No request_token received. Please try logging in again.",
        ))

    try:
        access_token = await asyncio.to_thread(exchange_token, request_token.strip())
    except ValueError as exc:
        return HTMLResponse(_html_page(success=False, message=str(exc)))
    except Exception as exc:
        return HTMLResponse(_html_page(success=False, message=f"Token exchange failed: {exc}"))

    # Update live process env so get_holdings() picks up the token immediately
    os.environ["ZERODHA_ACCESS_TOKEN"] = access_token

    return HTMLResponse(_html_page(success=True))


@app.get("/api/auth/status")
async def auth_status():
    """
    Return whether a Zerodha access token is configured.
    Re-reads .env so a token saved by the callback is reflected instantly.
    """
    load_dotenv(override=True)
    token = os.getenv("ZERODHA_ACCESS_TOKEN", "").strip()
    connected = bool(token)
    return {"connected": connected, "source": "zerodha" if connected else "dummy"}


@app.delete("/api/auth/logout")
async def auth_logout():
    """
    Clear the Zerodha access token from .env and the live process env.
    Sets ZERODHA_ACCESS_TOKEN to an empty value rather than deleting the line,
    so the key remains in .env as a placeholder.
    """
    from zerodha.auth import _write_env_key
    _write_env_key("ZERODHA_ACCESS_TOKEN", "")
    os.environ["ZERODHA_ACCESS_TOKEN"] = ""
    return {"status": "logged out"}


# ---------------------------------------------------------------------------
# HTML page helper (used by /api/auth/callback)
# ---------------------------------------------------------------------------

def _html_page(success: bool, message: str = "") -> str:
    if success:
        icon    = "✅"
        heading = "Zerodha Connected!"
        body    = "Your account has been linked. Close this tab and return to your dashboard."
        color   = "#34d399"   # emerald
    else:
        icon    = "❌"
        heading = "Connection Failed"
        body    = message or "Something went wrong. Please try again."
        color   = "#f87171"   # red

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Zerodha — {"Connected" if success else "Error"}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: system-ui, 'Segoe UI', sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 14px;
      padding: 2.5rem 2rem;
      max-width: 420px;
      width: 90%;
      text-align: center;
    }}
    .icon  {{ font-size: 3rem; margin-bottom: 1rem; }}
    h1     {{ font-size: 1.25rem; font-weight: 700; color: {color}; margin-bottom: .5rem; }}
    p      {{ color: #94a3b8; font-size: .9rem; line-height: 1.6; margin-bottom: 1.75rem; }}
    button {{
      background: #0f172a;
      color: #94a3b8;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: .55rem 1.6rem;
      font-size: .875rem;
      cursor: pointer;
      transition: background .15s;
    }}
    button:hover {{ background: #1e293b; color: #e2e8f0; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">{icon}</div>
    <h1>{heading}</h1>
    <p>{body}</p>
    <button onclick="window.close()">Close this tab</button>
  </div>
</body>
</html>"""
