"""
main.py — FastAPI entry point for Stock Portfolio Assistant

Endpoints
---------
GET  /health                            → liveness check
GET  /api/portfolio                     → raw holdings from Zerodha (or dummy data)
GET  /api/dashboard                     → holdings + rule-based analysis merged per stock
GET  /api/screen/{symbol}               → fast technical screening (RSI, MACD, EMA — no LLM)
GET  /api/analysis/{symbol}             → rule-based Buy/Sell/Hold for a single stock
GET  /api/analysis/ai/{symbol}          → multi-agent AI analysis (slow, 600s timeout)
GET  /api/analyze/{symbol}              → full analysis for any stock (screening + AI)
GET  /api/search/stocks?q=              → autocomplete symbol search
DEL  /api/analysis/cache                → clear AI cache
GET  /api/auth/login                    → returns Zerodha login URL
GET  /api/auth/callback?request_token=  → exchanges token, saves to .env
GET  /api/auth/status                   → check if Zerodha connected
DEL  /api/auth/logout                   → clears Zerodha token
POST /api/strategies                    → create strategy from natural language
GET  /api/strategies                    → list all strategies
GET  /api/strategies/{id}               → strategy detail with rules
PUT  /api/strategies/{id}               → update strategy
DEL  /api/strategies/{id}               → delete strategy
POST /api/strategies/{id}/watchlist     → add symbols to watchlist
POST /api/strategies/{id}/run           → execute strategy against watchlist
GET  /api/alerts                        → list alerts
PUT  /api/alerts/{id}/read              → mark alert as read
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

    # Save to analysis history DB
    try:
        from db.database import save_analysis
        import json
        # Also capture screening data for historical context
        screening_json = None
        try:
            from analysis.screener import screen_stock
            sr = await asyncio.to_thread(screen_stock, symbol)
            screening_json = json.dumps(sr.to_dict())
        except Exception:
            pass
        await save_analysis(symbol, result, screening_json)
    except Exception as exc:
        print(f"[main] Failed to save analysis history: {exc}")

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
# Phase 1: Technical screening (fast, no LLM)
# ---------------------------------------------------------------------------

@app.get("/api/screen/{symbol}")
async def screen_stock_endpoint(symbol: str):
    """
    Run technical screening on a single stock.
    Returns signals (RSI, MACD, EMA crossovers, etc.), indicators, and overall direction.
    Fast (1-3 seconds) — no LLM calls, pure pandas_ta computation.
    """
    from analysis.screener import screen_stock

    symbol = symbol.upper().strip()
    try:
        result = await asyncio.to_thread(screen_stock, symbol)
        return result.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Screening failed for {symbol}: {exc}")


# ---------------------------------------------------------------------------
# Phase 2: External stock analysis (any NSE stock)
# ---------------------------------------------------------------------------

@app.get("/api/search/stocks")
async def search_stocks(q: str = Query(..., min_length=1)):
    """
    Search NSE stock symbols. Returns matching symbols + company names
    for autocomplete. Uses a local symbol list from NSE.
    """
    from data.nse_symbols import search_symbols

    try:
        results = await asyncio.to_thread(search_symbols, q)
        return results
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Symbol search failed: {exc}")


@app.get("/api/analyze/{symbol}")
async def analyze_external_stock(symbol: str):
    """
    Full analysis of any NSE stock (not necessarily in portfolio).
    Combines technical screening + AI analysis.
    Returns: screening signals + AI recommendation + price summary.
    """
    from analysis.screener import screen_stock

    symbol = symbol.upper().strip()

    # Run screening (fast)
    try:
        screening = await asyncio.to_thread(screen_stock, symbol)
        screening_data = screening.to_dict()
    except Exception as exc:
        screening_data = {"error": str(exc)}

    # Run AI analysis (slow)
    try:
        ai_result = await asyncio.wait_for(analyze_stock_ai(symbol, 0.0), timeout=600.0)
    except asyncio.TimeoutError:
        ai_result = {
            "recommendation": "Hold",
            "reasoning": f"AI analysis timed out for {symbol}",
            "trend": "Neutral",
            "confidence": 0.3,
            "source": "timeout",
        }
    except Exception as exc:
        ai_result = {
            "recommendation": "Hold",
            "reasoning": f"AI analysis failed: {exc}",
            "trend": "Neutral",
            "confidence": 0.3,
            "source": "error",
        }

    return {
        "symbol": symbol,
        "screening": screening_data,
        "ai_analysis": ai_result,
    }


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
# Phase 3: Strategy builder + alerts
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    from db.database import init_db
    await init_db()


@app.post("/api/strategies")
async def create_strategy_endpoint(body: dict):
    """Parse natural language input into rules and store as a strategy."""
    from analysis.rule_parser import parse_strategy
    from db.database import create_strategy, add_rules, add_to_watchlist

    user_input = body.get("input", "").strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="'input' field is required")

    # Parse with LLM
    parsed = await parse_strategy(user_input)

    # Create strategy
    strategy_id = await create_strategy(
        name=parsed["name"],
        description=parsed["description"],
        raw_input=user_input,
    )

    # Add rules
    if parsed["rules"]:
        await add_rules(strategy_id, parsed["rules"])

    # Add watchlist symbols (from request + LLM suggestions)
    symbols = body.get("symbols", []) + parsed.get("suggested_symbols", [])
    if symbols:
        await add_to_watchlist(strategy_id, symbols)

    return {"id": strategy_id, **parsed}


@app.get("/api/strategies")
async def list_strategies():
    """List all strategies with rule counts and active status."""
    from db.database import get_strategies
    return await get_strategies()


@app.get("/api/strategies/{strategy_id}")
async def get_strategy_endpoint(strategy_id: int):
    """Get strategy details with rules and watchlist."""
    from db.database import get_strategy
    result = await get_strategy(strategy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return result


@app.put("/api/strategies/{strategy_id}")
async def update_strategy_endpoint(strategy_id: int, body: dict):
    """Update strategy name, active status, etc."""
    from db.database import update_strategy
    found = await update_strategy(strategy_id, **body)
    if not found:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"status": "updated"}


@app.delete("/api/strategies/{strategy_id}")
async def delete_strategy_endpoint(strategy_id: int):
    """Delete a strategy and its rules."""
    from db.database import delete_strategy
    found = await delete_strategy(strategy_id)
    if not found:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"status": "deleted"}


@app.post("/api/strategies/{strategy_id}/watchlist")
async def add_to_watchlist_endpoint(strategy_id: int, body: dict):
    """Add symbols to a strategy's watchlist."""
    from db.database import add_to_watchlist
    symbols = body.get("symbols", [])
    if not symbols:
        raise HTTPException(status_code=400, detail="'symbols' list is required")
    await add_to_watchlist(strategy_id, symbols)
    return {"status": "added", "count": len(symbols)}


@app.post("/api/strategies/{strategy_id}/run")
async def run_strategy_endpoint(strategy_id: int):
    """Execute strategy against watchlist. Returns triggered alerts."""
    from db.database import run_strategy
    alerts = await run_strategy(strategy_id)
    return alerts


@app.get("/api/alerts")
async def get_alerts_endpoint(
    strategy_id: int = Query(None),
    unread: bool = Query(True),
):
    """Get alerts, optionally filtered."""
    from db.database import get_alerts
    return await get_alerts(strategy_id=strategy_id, unread_only=unread)


@app.put("/api/alerts/{alert_id}/read")
async def mark_alert_read_endpoint(alert_id: int):
    """Mark an alert as read."""
    from db.database import mark_alert_read
    found = await mark_alert_read(alert_id)
    if not found:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "read"}


# ---------------------------------------------------------------------------
# Analysis History
# ---------------------------------------------------------------------------

@app.get("/api/history")
async def get_history(symbol: str = Query(None), limit: int = Query(50)):
    """Get analysis history. Optionally filter by symbol."""
    from db.database import get_analysis_history
    return await get_analysis_history(symbol=symbol, limit=limit)


@app.get("/api/history/{symbol}/latest")
async def get_latest_analysis_endpoint(symbol: str):
    """Get the most recent saved analysis for a stock."""
    from db.database import get_latest_analysis
    result = await get_latest_analysis(symbol.upper())
    if not result:
        raise HTTPException(status_code=404, detail="No analysis history found")
    return result


# ---------------------------------------------------------------------------
# NSE Option Chain
# ---------------------------------------------------------------------------

@app.get("/api/options/symbols")
async def get_option_symbols():
    """List symbols with active NSE options."""
    from data.options import get_option_symbols
    return get_option_symbols()


@app.get("/api/options/{symbol}")
async def get_option_chain_endpoint(symbol: str):
    """Fetch full NSE option chain for a stock or index."""
    from data.options import get_option_chain
    symbol = symbol.upper().strip()
    try:
        result = await asyncio.to_thread(get_option_chain, symbol)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Option chain failed for {symbol}: {exc}")


# ---------------------------------------------------------------------------
# MCX Commodities
# ---------------------------------------------------------------------------

@app.get("/api/mcx")
async def get_mcx_prices():
    """Fetch current prices for major MCX commodities."""
    from data.mcx import get_commodity_prices
    try:
        return await asyncio.to_thread(get_commodity_prices)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MCX fetch failed: {exc}")


# ---------------------------------------------------------------------------
# Predefined F&O Strategies
# ---------------------------------------------------------------------------

@app.get("/api/predefined-strategies")
async def get_predefined_strategies():
    """List all 13 predefined F&O trading strategies."""
    from data.predefined_strategies import get_all_strategies
    return get_all_strategies()


@app.get("/api/predefined-strategies/categories")
async def get_strategy_categories():
    """Get strategy category metadata."""
    from data.predefined_strategies import get_categories
    return get_categories()


@app.get("/api/predefined-strategies/{strategy_id}")
async def get_predefined_strategy(strategy_id: str):
    """Get a single predefined strategy by ID."""
    from data.predefined_strategies import get_strategy
    result = get_strategy(strategy_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")
    return result


@app.get("/api/predefined-strategies/{strategy_id}/check/{symbol}")
async def check_predefined_strategy(strategy_id: str, symbol: str = "NIFTY"):
    """Check if a strategy's entry conditions are met for a given symbol."""
    from data.predefined_strategies import check_strategy_conditions

    symbol = symbol.upper().strip()

    # Get option chain data
    option_data = {}
    try:
        from data.options import get_option_chain
        option_data = await asyncio.to_thread(get_option_chain, symbol)
    except Exception:
        option_data = {"spot_price": 0, "pcr": 0, "strikes": [], "market_closed": True}

    # Get technical indicators
    indicators = {}
    try:
        from analysis.screener import screen_stock
        result = await asyncio.to_thread(screen_stock, symbol)
        indicators = result.indicators
    except Exception:
        pass

    return check_strategy_conditions(strategy_id, option_data, indicators)


@app.get("/api/mcx/list")
async def get_mcx_list():
    """List all available MCX commodities."""
    from data.mcx import get_commodity_list
    return get_commodity_list()


@app.get("/api/mcx/{symbol}")
async def get_mcx_history(symbol: str, days: int = Query(90)):
    """Fetch OHLCV history for a single MCX commodity."""
    from data.mcx import get_commodity_history
    try:
        result = await asyncio.to_thread(get_commodity_history, symbol.upper(), days)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MCX history failed: {exc}")


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
