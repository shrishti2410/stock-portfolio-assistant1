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
GET  /api/zerodha/login                 → returns Zerodha login URL
GET  /api/zerodha/callback?request_token= → exchanges token, saves to .env
GET  /api/zerodha/status                → check if Zerodha connected
DEL  /api/zerodha/logout                → clears Zerodha token
POST /api/auth/login                    → multi-user login (sets session cookie)
POST /api/auth/logout                   → multi-user logout
GET  /api/auth/me                       → current authenticated user
                                           (see routers/auth_api.py, routers/broker_api.py
                                            for the full multi-user auth + per-user
                                            broker credential API)
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
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from zerodha.client import get_holdings, get_holdings_for_user
from zerodha.auth import get_login_url, exchange_token
from analysis.analyzer import analyze_stock_ai, _ai_cache
from auth.service import get_session_user
from auth.seed import ensure_admin

load_dotenv()

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Stock Portfolio Assistant", version="0.1.0")

# ── Feature routers (Phase B/C/D: marketplace, chat authoring, data, backtest, auth) ──
from routers.marketplace import router as marketplace_router
from routers.marketplace_chat import router as marketplace_chat_router
from routers.data_api import router as data_router
from routers.backtest_api import router as backtest_router
from routers.auth_api import router as auth_api_router
from routers.broker_api import router as broker_api_router

app.include_router(marketplace_router)
app.include_router(marketplace_chat_router)
app.include_router(data_router)
app.include_router(backtest_router)
app.include_router(auth_api_router)
app.include_router(broker_api_router)


# ---------------------------------------------------------------------------
# Auth middleware — protects all /api/* routes except a small allowlist.
# Any path NOT starting with /api/ (static SPA assets, index.html, etc.) is
# always let through untouched so the login page itself can load.
# ---------------------------------------------------------------------------

_AUTH_ALLOWLIST_EXACT = {"/health", "/api/auth/login"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # CORS preflight requests never carry cookies and must reach
    # CORSMiddleware untouched, regardless of auth state.
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if path in _AUTH_ALLOWLIST_EXACT or not path.startswith("/api/"):
        return await call_next(request)

    token = request.cookies.get("session")
    user = await get_session_user(token) if token else None
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    request.state.user = user
    return await call_next(request)


# NOTE: CORSMiddleware is registered AFTER auth_middleware above so it ends up
# as the OUTERMOST layer — Starlette wraps middleware in the reverse order
# they're added (the most-recently-added becomes outermost). This guarantees
# CORS headers are present even on 401 responses from auth_middleware, and
# that preflight requests are always handled correctly.
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
async def get_portfolio(request: Request):
    """
    Return the current portfolio holdings for the authenticated user.

    Uses that user's own Zerodha credentials when configured (Settings UI),
    falls back to legacy env credentials for admins, otherwise dummy data
    (see zerodha/client.py get_holdings_for_user()).

    Response shape (list):
        symbol, quantity, average_price, last_price, pnl, pnl_percentage
    """
    user = getattr(request.state, "user", None)
    try:
        holdings = await get_holdings_for_user(user)
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
async def get_dashboard(request: Request):
    """
    Return holdings merged with rule-based analysis for every stock, for the
    authenticated user (see get_holdings_for_user() in zerodha/client.py).

    Fetches all holdings in one call, then fans out analysis concurrently
    via asyncio.gather so the response time doesn't grow linearly with
    portfolio size.

    Response shape (list):
        symbol, quantity, avg_price, current_price,
        pnl, pnl_pct, recommendation, reasoning, trend, confidence
    """
    user = getattr(request.state, "user", None)
    try:
        holdings = await get_holdings_for_user(user)
    except Exception:
        # get_holdings_for_user() should never raise (it catches internally),
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

@app.get("/api/zerodha/login")
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


@app.get("/api/zerodha/callback", response_class=HTMLResponse)
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


@app.get("/api/zerodha/status")
async def auth_status():
    """
    Return whether a Zerodha access token is configured.
    Re-reads .env so a token saved by the callback is reflected instantly.
    """
    load_dotenv(override=True)
    token = os.getenv("ZERODHA_ACCESS_TOKEN", "").strip()
    connected = bool(token)
    return {"connected": connected, "source": "zerodha" if connected else "dummy"}


@app.delete("/api/zerodha/logout")
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

    # Multi-user auth: ensure a default admin exists (idempotent), and
    # migrate any legacy .env Zerodha credentials into their user_settings.
    try:
        await ensure_admin()
    except Exception as e:
        print(f"[startup] ensure_admin failed: {e}")

    # Sync market events to DB
    try:
        from trading.events import sync_events_to_db
        await sync_events_to_db()
    except Exception as e:
        print(f"[startup] Event sync: {e}")

    # IT-Bear morning refresh: if today's earnings cache is stale, fire a
    # background refresh so the user has fresh data when they open the UI.
    # First-of-the-day startup only — no-ops on subsequent restarts.
    async def _morning_refresh():
        try:
            from data.earnings_calendar import (
                is_cache_fresh_today, refresh_universe_earnings_cache,
            )
            if await is_cache_fresh_today():
                print("[startup] IT-Bear earnings cache fresh — skipping refresh.")
                return
            print("[startup] IT-Bear earnings cache stale → refreshing in background...")
            await refresh_universe_earnings_cache()
        except Exception as e:
            print(f"[startup] IT-Bear morning refresh failed: {e}")

    asyncio.create_task(_morning_refresh())

    # Seed the unified strategy marketplace (idempotent — skips existing slugs)
    try:
        from marketplace.seeds import seed_all
        result = await seed_all()
        print(f"[startup] Marketplace seed: {result}")
    except Exception as e:
        print(f"[startup] Marketplace seed failed: {e}")

    # Telegram long-poll listener — only starts if TELEGRAM_BOT_TOKEN is set
    async def _start_telegram():
        try:
            from notifications.telegram_listener import start_listener, _is_configured
            if _is_configured():
                result = await start_listener()
                print(f"[startup] Telegram listener: {result}")
            else:
                print("[startup] Telegram listener: not configured (TELEGRAM_BOT_TOKEN missing)")
        except Exception as e:
            print(f"[startup] Telegram listener failed to start: {e}")

    asyncio.create_task(_start_telegram())


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


# ---------------------------------------------------------------------------
# Trading Engine API
# ---------------------------------------------------------------------------

@app.get("/api/trading/status")
async def trading_status():
    """Get trading engine status."""
    from trading.engine import trading_engine
    return trading_engine.status


@app.post("/api/trading/start")
async def trading_start():
    """Start the trading engine. Auto-enables engine_enabled flag."""
    from trading.engine import trading_engine
    from db.database import _get_db

    # Auto-enable engine_enabled when user clicks Start
    async with _get_db() as db:
        await db.execute(
            "UPDATE trading_config SET engine_enabled = 1, updated_at = CURRENT_TIMESTAMP WHERE id = 1"
        )
        await db.commit()

    config = await trading_engine._load_config()

    # Validate at least one strategy is enabled
    import json
    enabled = json.loads(config.get("strategies_enabled", "[]"))
    if not enabled:
        raise HTTPException(
            status_code=400,
            detail="No strategies enabled. Go to Settings and enable at least one strategy."
        )

    return await trading_engine.start(config)


@app.post("/api/trading/stop")
async def trading_stop():
    """Stop the trading engine."""
    from trading.engine import trading_engine
    return await trading_engine.stop()


@app.post("/api/trading/scan-now")
async def trading_scan_now():
    """Trigger an immediate scan (auto-enables engine flag for this scan)."""
    from trading.engine import trading_engine
    from db.database import _get_db

    # Auto-enable engine_enabled for manual scan
    async with _get_db() as db:
        await db.execute(
            "UPDATE trading_config SET engine_enabled = 1 WHERE id = 1"
        )
        await db.commit()

    config = await trading_engine._load_config()

    # Validate at least one strategy is enabled
    import json
    enabled = json.loads(config.get("strategies_enabled", "[]"))
    if not enabled:
        raise HTTPException(
            status_code=400,
            detail="No strategies enabled. Go to Settings and enable at least one strategy."
        )

    result = await trading_engine.run_scan(config)
    # Update P&L after scan
    try:
        await trading_engine.update_paper_pnl()
    except Exception:
        pass
    return result


@app.get("/api/trading/config")
async def trading_get_config():
    """Get trading configuration."""
    from trading.engine import trading_engine
    config = await trading_engine._load_config()
    # Parse JSON fields for frontend
    import json
    config["strategies_enabled"] = json.loads(config.get("strategies_enabled", "[]"))
    return config


@app.put("/api/trading/config")
async def trading_update_config(body: dict):
    """Update trading configuration."""
    import json
    from db.database import _get_db

    # Ensure config row exists
    async with _get_db() as db:
        await db.execute("INSERT OR IGNORE INTO trading_config (id) VALUES (1)")
        await db.commit()

    allowed = {
        "max_capital", "max_loss_per_trade", "max_daily_loss", "max_positions",
        "risk_per_trade_pct", "paper_mode", "engine_enabled", "strategies_enabled",
        "scan_interval_min", "nifty_lot_size", "banknifty_lot_size",
    }
    updates = {}
    for k, v in body.items():
        if k in allowed:
            if k == "strategies_enabled" and isinstance(v, list):
                updates[k] = json.dumps(v)
            elif k == "paper_mode":
                updates[k] = 1 if v else 0
            elif k == "engine_enabled":
                updates[k] = 1 if v else 0
            else:
                updates[k] = v

    if not updates:
        return {"status": "no changes"}

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())

    async with _get_db() as db:
        await db.execute(
            f"UPDATE trading_config SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
            values,
        )
        await db.commit()

        # Return updated config
        import aiosqlite
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT * FROM trading_config WHERE id = 1")
        if rows:
            result = dict(rows[0])
            result["strategies_enabled"] = json.loads(result.get("strategies_enabled", "[]"))
            return result

    return {"status": "updated", "fields": list(updates.keys())}


_STRATEGY_NAMES = {
    "iron_condor": "Iron Condor",
    "straddle_adjust": "Straddle Sell + Adjust",
    "directional_spread": "Directional Spread",
}


def _transform_proposal(d: dict) -> dict:
    """Transform raw DB row to frontend-friendly format."""
    import json as _json
    out = dict(d)

    # Add strategy_name
    out["strategy_name"] = _STRATEGY_NAMES.get(d.get("strategy_id", ""), d.get("strategy_id", ""))

    # Convert confidence 0-1 -> 0-100
    conf = d.get("confidence", 0)
    if conf is not None:
        out["confidence_score"] = round(float(conf) * 100)

    # Parse JSON fields
    for field in ("legs", "greeks", "intelligence", "risk_checks"):
        val = d.get(field)
        if val and isinstance(val, str):
            try:
                out[field] = _json.loads(val)
            except Exception:
                pass

    # Transform legs to frontend format (action UPPERCASE, type -> option_type)
    if isinstance(out.get("legs"), list):
        out["legs"] = [
            {
                **leg,
                "action": str(leg.get("action", "")).upper(),
                "option_type": leg.get("type", leg.get("option_type", "")),
            }
            for leg in out["legs"]
        ]

    return out


def _transform_position(d: dict) -> dict:
    """Transform position DB row to frontend-friendly format."""
    import json as _json
    out = dict(d)
    out["strategy_name"] = _STRATEGY_NAMES.get(d.get("strategy_id", ""), d.get("strategy_id", ""))

    # Parse legs JSON
    legs_str = d.get("legs", "[]")
    legs_list = []
    if isinstance(legs_str, str):
        try:
            legs_list = _json.loads(legs_str)
        except Exception:
            legs_list = []
    elif isinstance(legs_str, list):
        legs_list = legs_str
    out["legs"] = legs_list

    # Aliases for frontend
    out["unrealized_pnl"] = d.get("current_pnl", 0)
    out["entry_premium"] = d.get("total_premium", 0)
    # Total quantity = sum of legs (or use first leg qty)
    out["quantity"] = legs_list[0].get("quantity", 0) if legs_list else 0

    return out


@app.get("/api/trading/proposals")
async def trading_get_proposals(status: str = Query(None)):
    """List trade proposals. Filter by status (pending, approved, rejected, expired, executed)."""
    from db.database import _get_db
    if status:
        query = "SELECT * FROM trade_proposals WHERE status = ? ORDER BY created_at DESC LIMIT 50"
        params = (status,)
    else:
        query = "SELECT * FROM trade_proposals ORDER BY created_at DESC LIMIT 50"
        params = ()

    async with _get_db() as db:
        import aiosqlite
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(query, params)
        return [_transform_proposal(dict(r)) for r in rows]


@app.post("/api/trading/proposals")
async def trading_create_proposal(body: dict):
    """
    Manually create a trade proposal (e.g., from the Strategy Builder).

    Body accepts the frontend-friendly shape:
      symbol, strategy_name, direction, mode, legs, max_profit, max_loss,
      margin_required (or margin_needed), confidence_score (0-100, or confidence 0-1),
      reasoning, source, layer
    Returns the proposal ID + status.

    If body.auto_execute is True (default), runs through risk checks +
    OrderManager immediately. Otherwise saves as 'pending' for manual approval.
    """
    import json as _json
    from trading.engine import trading_engine
    from db.database import _get_db

    # Normalize input
    symbol = str(body.get("symbol", "")).upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="'symbol' is required")

    # Frontend may send confidence as 0-100 OR 0-1. Normalize to 0-1.
    conf_raw = body.get("confidence_score", body.get("confidence", 50))
    confidence = float(conf_raw) / 100 if conf_raw > 1 else float(conf_raw)

    # Frontend may send margin_required OR margin_needed
    margin = float(body.get("margin_required", body.get("margin_needed", 0)) or 0)

    # Strategy id — best effort from name
    strategy_id = body.get("strategy_id") or _strategy_id_from_name(body.get("strategy_name", ""))

    # Legs: normalize action UPPERCASE, ensure option_type / type both present
    raw_legs = body.get("legs", []) or []
    legs = []
    for leg in raw_legs:
        action = str(leg.get("action", "")).upper()
        opt_type = leg.get("type") or leg.get("option_type") or ""
        legs.append({
            "action": action.lower(),  # canonical lower-case for engine
            "type": opt_type,
            "option_type": opt_type,
            "strike": int(leg.get("strike", 0)),
            "qty": int(leg.get("qty", leg.get("quantity", 0))),
            "ltp": float(leg.get("ltp", 0)),
            "iv": float(leg.get("iv", 0)),
        })

    # Save as pending proposal
    proposal_record = {
        "strategy_id": strategy_id,
        "symbol": symbol,
        "direction": str(body.get("direction", "bearish")).lower(),
        "legs_json": _json.dumps(legs),
        "greeks_json": _json.dumps(body.get("greeks", {})),
        "intelligence_json": _json.dumps({
            "layer": body.get("layer", "tactical"),
            "source": body.get("source", "manual"),
            "strategy_theme": "it_bear_thesis",
        }),
        "max_profit": float(body.get("max_profit", 0) or 0),
        "max_loss": float(body.get("max_loss", 0) or 0),
        "margin_needed": margin,
        "confidence": confidence,
        "reasoning": str(body.get("reasoning", "")),
    }

    async with _get_db() as db:
        cursor = await db.execute(
            """INSERT INTO trade_proposals
               (strategy_id, symbol, direction, legs, greeks, intelligence,
                max_profit, max_loss, margin_needed, confidence, reasoning,
                risk_checks, status, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', 'pending',
                       datetime('now', '+30 minutes'))""",
            (proposal_record["strategy_id"], proposal_record["symbol"],
             proposal_record["direction"], proposal_record["legs_json"],
             proposal_record["greeks_json"], proposal_record["intelligence_json"],
             proposal_record["max_profit"], proposal_record["max_loss"],
             proposal_record["margin_needed"], proposal_record["confidence"],
             proposal_record["reasoning"]),
        )
        await db.commit()
        proposal_id = cursor.lastrowid

    # Auto-execute by default (frontend "Execute as Paper Trade" expects execution).
    # For MANUAL proposals from the Strategy Builder, the user has explicitly chosen
    # the trade — so we auto-enable engine_enabled + add this strategy to
    # enabled_strategies before running risk checks (the engine_enabled and
    # strategy_enabled gates are meant for the auto-scanner, not user-initiated trades).
    auto_execute = bool(body.get("auto_execute", True))
    if auto_execute:
        async with _get_db() as db:
            import aiosqlite
            db.row_factory = aiosqlite.Row
            # Auto-enable engine flag
            await db.execute(
                "UPDATE trading_config SET engine_enabled = 1 WHERE id = 1"
            )
            # Add this strategy to enabled list if not already
            rows = await db.execute_fetchall("SELECT strategies_enabled FROM trading_config WHERE id = 1")
            if rows:
                enabled = _json.loads(rows[0]["strategies_enabled"] or "[]")
                if strategy_id not in enabled:
                    enabled.append(strategy_id)
                    await db.execute(
                        "UPDATE trading_config SET strategies_enabled = ? WHERE id = 1",
                        (_json.dumps(enabled),)
                    )
            await db.commit()

        result = await trading_engine.execute_approved(proposal_id)
        if "error" in result:
            return {
                "proposal_id": proposal_id,
                "status": "rejected",
                "error": result["error"],
                "message": f"Proposal saved but execution failed: {result['error']}",
            }
        return {
            "proposal_id": proposal_id,
            "position_id": result.get("position_id"),
            "status": "executed",
            "message": f"Paper trade executed. Position #{result.get('position_id')} created.",
        }

    return {
        "proposal_id": proposal_id,
        "status": "pending",
        "message": f"Proposal #{proposal_id} created. Approve from dashboard to execute.",
    }


def _strategy_id_from_name(name: str) -> str:
    """Best-effort map strategy name → canonical strategy_id."""
    n = (name or "").lower()
    if "iron condor" in n: return "iron_condor"
    if "straddle" in n and ("sell" in n or "short" in n or "adjust" in n): return "straddle_adjust"
    if "bear put" in n or "put spread" in n: return "it_bear_put_spread"
    if "bear call" in n or "call spread" in n: return "it_bear_call_spread"
    if "pre-earnings" in n or "pre earnings" in n: return "it_pre_earnings_put"
    if "long put" in n: return "it_long_put_breakdown"
    if "nifty it" in n and "future" in n: return "it_nifty_futures_short"
    if "directional" in n: return "directional_spread"
    return "manual_proposal"


@app.get("/api/trading/proposals/{proposal_id}")
async def trading_get_proposal(proposal_id: int):
    """Get full proposal detail."""
    from db.database import _get_db
    import aiosqlite
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM trade_proposals WHERE id = ?", (proposal_id,)
        )
    if not rows:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return _transform_proposal(dict(rows[0]))


@app.post("/api/trading/proposals/{proposal_id}/approve")
async def trading_approve_proposal(proposal_id: int):
    """Approve a trade proposal for execution."""
    from trading.engine import trading_engine
    result = await trading_engine.execute_approved(proposal_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/trading/proposals/{proposal_id}/reject")
async def trading_reject_proposal(proposal_id: int):
    """Reject a trade proposal."""
    from trading.engine import trading_engine
    await trading_engine._update_proposal_status(proposal_id, "rejected")
    return {"status": "rejected"}


@app.get("/api/trading/positions")
async def trading_get_positions(status: str = Query(None)):
    """List positions. Filter by status (open, closed, stopped_out, target_hit)."""
    from db.database import _get_db
    import aiosqlite
    if status:
        query = "SELECT * FROM positions WHERE status = ? ORDER BY entry_time DESC LIMIT 50"
        params = (status,)
    else:
        query = "SELECT * FROM positions ORDER BY entry_time DESC LIMIT 50"
        params = ()

    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(query, params)
        return [_transform_position(dict(r)) for r in rows]


@app.get("/api/trading/positions/{position_id}")
async def trading_get_position(position_id: int):
    """Get position detail with order log."""
    from db.database import _get_db
    import aiosqlite
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        pos_rows = await db.execute_fetchall(
            "SELECT * FROM positions WHERE id = ?", (position_id,)
        )
        if not pos_rows:
            raise HTTPException(status_code=404, detail="Position not found")

        order_rows = await db.execute_fetchall(
            "SELECT * FROM order_log WHERE position_id = ? ORDER BY placed_at", (position_id,)
        )

    result = _transform_position(dict(pos_rows[0]))
    result["orders"] = [dict(r) for r in order_rows]
    return result


@app.post("/api/trading/positions/{position_id}/close")
async def trading_close_position(position_id: int):
    """Force-close an open position."""
    from trading.engine import trading_engine
    result = await trading_engine.close_position(position_id, reason="manual_close")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/trading/pnl")
async def trading_pnl():
    """Get daily P&L history + summary."""
    from db.database import _get_db
    from datetime import date
    import aiosqlite
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM daily_pnl ORDER BY date DESC LIMIT 90"
        )
        history = [dict(r) for r in rows]

        # Today's P&L
        today_str = date.today().isoformat()
        today_row = next((h for h in history if h.get("date") == today_str), None)
        today_pnl = (today_row.get("realized", 0) + today_row.get("unrealized", 0)) if today_row else 0

        # Sum unrealized from open positions
        pos_rows = await db.execute_fetchall(
            "SELECT SUM(current_pnl) as total FROM positions WHERE status = 'open'"
        )
        unrealized_now = float(pos_rows[0]["total"] or 0) if pos_rows else 0

        # Total realized P&L all-time
        all_rows = await db.execute_fetchall("SELECT SUM(realized) as total FROM daily_pnl")
        total_realized = float(all_rows[0]["total"] or 0) if all_rows else 0

        return {
            "today_pnl": round(today_pnl + unrealized_now, 2),
            "total_pnl": round(total_realized + unrealized_now, 2),
            "unrealized_pnl": round(unrealized_now, 2),
            "history": history,
        }


@app.get("/api/trading/performance")
async def trading_performance():
    """Get per-strategy performance stats."""
    from db.database import _get_db
    import aiosqlite
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("""
            SELECT strategy_id,
                   COUNT(*) as total_trades,
                   SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN realized_pnl <= 0 THEN 1 ELSE 0 END) as losses,
                   SUM(realized_pnl) as total_pnl,
                   AVG(realized_pnl) as avg_pnl
            FROM positions
            WHERE status != 'open'
            GROUP BY strategy_id
        """)
        results = []
        for r in rows:
            d = dict(r)
            d["win_rate"] = round(d["wins"] / d["total_trades"] * 100, 1) if d["total_trades"] > 0 else 0
            results.append(d)
        return results


@app.get("/api/trading/intelligence/{symbol}")
async def trading_intelligence(symbol: str):
    """Get full market intelligence snapshot for a symbol."""
    from data.options import get_option_chain
    from trading.intelligence import get_market_snapshot

    symbol = symbol.upper().strip()
    option_data = await asyncio.to_thread(get_option_chain, symbol)
    snapshot = await get_market_snapshot(symbol, option_data)
    return snapshot


@app.get("/api/trading/events")
async def trading_events():
    """Get upcoming market events."""
    from trading.events import get_upcoming_events
    return get_upcoming_events(days_ahead=14)


@app.post("/api/trading/circuit-breaker/reset")
async def trading_reset_circuit_breaker():
    """Manually reset the daily loss circuit breaker."""
    from db.database import _get_db
    from datetime import date
    today = date.today().isoformat()
    async with _get_db() as db:
        await db.execute(
            "UPDATE daily_pnl SET realized = 0, unrealized = 0 WHERE date = ?",
            (today,),
        )
        await db.commit()
    return {"status": "circuit_breaker_reset", "date": today}


# ---------------------------------------------------------------------------
# IT-Bear Module API
# ---------------------------------------------------------------------------

@app.get("/api/it-bear/universe")
async def it_bear_universe():
    """
    List of IT stocks with current price + key metadata.
    Combines static universe data + current prices via yfinance.
    """
    from data.it_universe import get_all
    from analysis.it_sector_health import get_sector_heatmap

    stocks = get_all()
    # Enrich with live prices from sector heatmap (cached 15min)
    try:
        heatmap = await get_sector_heatmap()
        price_map = {s["symbol"]: s for s in heatmap}
    except Exception:
        price_map = {}

    result = []
    for s in stocks:
        sym = s["symbol"]
        live = price_map.get(sym, {})
        result.append({
            "symbol": sym,
            "name": s.get("name", sym),
            "country": s.get("country", ""),
            "tier": s.get("tier", ""),
            "segment": s.get("segment", ""),
            "lot_size": s.get("lot_size"),
            "fno": s.get("fno", False),
            "notes": s.get("notes", ""),
            "yf": s.get("yf", sym),
            "price": live.get("price"),
            "change_pct_1d": live.get("change_pct_1d"),
            "change_pct_5d": live.get("change_pct_5d"),
            "change_pct_20d": live.get("change_pct_20d"),
            "rsi": live.get("rsi"),
            "above_50dma": live.get("above_50dma"),
        })

    return result


@app.get("/api/it-bear/universe/{symbol}")
async def it_bear_stock_detail(symbol: str):
    """Single stock: full details + last 4 quarters + indicators."""
    from data.it_universe import get_by_symbol
    from data.earnings_calendar import get_next_earnings, get_quarterly_history
    from analysis.it_sector_health import _fetch_stock_indicators

    symbol = symbol.upper().strip()
    stock = get_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not in IT universe")

    yf_sym = stock.get("yf", symbol)

    # Fetch indicators, earnings info concurrently
    indicators_task = asyncio.to_thread(
        _fetch_stock_indicators, yf_sym, symbol,
        stock.get("name", symbol), stock.get("country", "")
    )
    earnings_task = get_next_earnings(symbol)
    history_task = get_quarterly_history(symbol, num_quarters=4)

    indicators, earnings, quarterly = await asyncio.gather(
        indicators_task, earnings_task, history_task, return_exceptions=True
    )

    return {
        **stock,
        "indicators": indicators if not isinstance(indicators, Exception) else {},
        "next_earnings": earnings if not isinstance(earnings, Exception) else None,
        "quarterly_history": quarterly if not isinstance(quarterly, Exception) else [],
    }


@app.get("/api/it-bear/earnings")
async def it_bear_earnings(days_ahead: int = Query(90, ge=1, le=365)):
    """Upcoming earnings calendar for IT universe (cached in DB, refreshed daily)."""
    from data.earnings_calendar import get_universe_earnings_calendar
    return await get_universe_earnings_calendar(days_ahead=days_ahead)


@app.get("/api/it-bear/earnings/refresh-status")
async def it_bear_earnings_refresh_status():
    """Tells the frontend whether today's earnings have been refreshed."""
    from data.earnings_calendar import get_last_refresh_date, is_cache_fresh_today
    last = await get_last_refresh_date()
    fresh = await is_cache_fresh_today()
    return {
        "last_refresh_date": last,
        "is_fresh_today": fresh,
        "today": __import__("datetime").date.today().isoformat(),
    }


@app.post("/api/it-bear/earnings/refresh")
async def it_bear_earnings_refresh(force: bool = Query(False)):
    """
    Refresh earnings + last 4 quarters for the entire IT universe.

    Called by:
    - The morning-startup script (~/Documents/My Software/start-stock-portfolio.command)
    - Manual "Refresh" button in the UI

    If already refreshed today, returns the cached summary unless force=true.
    Refresh takes ~20-30s (21 stocks × 2 yfinance calls, 8-way concurrency).
    """
    from data.earnings_calendar import (
        is_cache_fresh_today, refresh_universe_earnings_cache,
        get_last_refresh_date,
    )

    if not force and await is_cache_fresh_today():
        return {
            "status": "skipped",
            "reason": "Already refreshed today",
            "last_refresh_date": await get_last_refresh_date(),
        }

    summary = await refresh_universe_earnings_cache()
    return {"status": "refreshed", **summary}


@app.get("/api/it-bear/sector-health")
async def it_bear_sector_health():
    """NIFTY IT vs NIFTY 50, macro indicators, and sector heatmap."""
    from analysis.it_sector_health import (
        get_nifty_it_vs_nifty50, get_macro_indicators,
        get_sector_heatmap, get_sector_health_summary,
    )

    summary, rs_data, macro, heatmap = await asyncio.gather(
        get_sector_health_summary(),
        get_nifty_it_vs_nifty50(),
        get_macro_indicators(),
        get_sector_heatmap(),
        return_exceptions=True,
    )

    return {
        "summary": summary if not isinstance(summary, Exception) else {},
        "nifty_it_vs_nifty50": rs_data if not isinstance(rs_data, Exception) else {},
        "macro": macro if not isinstance(macro, Exception) else {},
        "heatmap": heatmap if not isinstance(heatmap, Exception) else [],
    }


@app.get("/api/it-bear/scanner")
async def it_bear_scanner():
    """
    Run all 5 IT-bear evaluators against all IT stocks.
    Returns ranked signals sorted by confidence descending.
    """
    from data.it_universe import get_india
    from data.synthetic_options import generate_synthetic_chain
    from trading.strategies_it_bear import ALL_IT_BEAR_EVALUATORS

    stocks = get_india()
    # Reuse the NIFTY IT chain as base for all stocks
    try:
        niftyit_chain = await asyncio.to_thread(generate_synthetic_chain, "NIFTYIT")
    except Exception:
        niftyit_chain = {"strikes": [], "spot_price": 0, "pcr": 0, "strike_count": 0}

    signals = []

    async def _scan_stock(stock: dict):
        sym = stock["symbol"]
        yf_sym = stock.get("yf", sym)

        # Try stock-specific chain, fallback to NIFTY IT chain
        try:
            from data.synthetic_options import get_chain_with_fallback
            chain = await asyncio.to_thread(get_chain_with_fallback, sym, True)
            if chain.get("strike_count", 0) == 0:
                chain = niftyit_chain
        except Exception:
            chain = niftyit_chain

        spot = chain.get("spot_price", 0)
        snapshot = {
            "symbol": sym,
            "spot": spot,
            "vix": chain.get("vix", 0),
            "vix_regime": "unknown",
            "pcr": chain.get("pcr", 0),
            "atm": {},
            "expected_move": 0,
            "max_pain": 0,
            "oi_levels": {"support": 0, "resistance": 0},
            "iv_percentile": -1,
            "nearest_expiry": "",
            "days_to_expiry": 28,
            "greeks": {},
        }

        stock_signals = []
        for evaluator in ALL_IT_BEAR_EVALUATORS:
            try:
                proposal = await evaluator.evaluate(snapshot, chain)
                if proposal:
                    proposal["stock_meta"] = {
                        "name": stock.get("name", sym),
                        "tier": stock.get("tier", ""),
                        "segment": stock.get("segment", ""),
                    }
                    stock_signals.append(proposal)
            except Exception as e:
                print(f"[scanner] {evaluator.strategy_id} on {sym}: {e}")

        return stock_signals

    tasks = [_scan_stock(s) for s in stocks]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in all_results:
        if isinstance(result, list):
            signals.extend(result)

    # Sort by confidence descending
    signals.sort(key=lambda x: x.get("confidence", 0), reverse=True)

    return {
        "signals": signals,
        "total": len(signals),
        "scanned_symbols": len(stocks),
        "evaluators_run": len(ALL_IT_BEAR_EVALUATORS),
    }


@app.get("/api/it-bear/strategy-suggest/{symbol}")
async def it_bear_suggest_strategy(
    symbol: str,
    conviction: str = Query("moderate"),
    horizon_days: int = Query(30, ge=5, le=365),
):
    """
    Suggest specific option structure for a name given conviction + horizon.
    Accepts conviction: weak|low | moderate | strong|high
    horizon_days: 5-365
    Returns a flat suggestion (matching frontend expectations) PLUS alternatives list.
    """
    from data.it_universe import get_by_symbol
    from data.synthetic_options import generate_synthetic_chain, get_chain_with_fallback
    from trading.intelligence import get_market_snapshot
    from trading.strategies_it_bear import (
        LongPutBreakdownEvaluator, BearPutSpreadEvaluator,
        BearCallSpreadEvaluator, PreEarningsLongPutEvaluator,
        NiftyITFuturesShortEvaluator,
    )

    # Normalize conviction (accept both frontend "weak/moderate/strong" and "low/moderate/high")
    conv_map = {"weak": "low", "strong": "high", "low": "low", "moderate": "moderate", "high": "high"}
    conviction_norm = conv_map.get(conviction.lower(), "moderate")

    symbol = symbol.upper().strip()
    stock = get_by_symbol(symbol)

    if not stock and symbol not in ("NIFTYIT", "NIFTY IT"):
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not in IT universe")

    # Get chain (real, fall back to synthetic NIFTY IT if needed)
    chain_symbol = symbol if symbol != "NIFTY IT" else "NIFTYIT"
    try:
        chain = await asyncio.to_thread(get_chain_with_fallback, chain_symbol, True)
        if chain.get("strike_count", 0) == 0:
            chain = await asyncio.to_thread(generate_synthetic_chain, "NIFTYIT")
    except Exception:
        chain = await asyncio.to_thread(generate_synthetic_chain, "NIFTYIT")

    # Build a REAL snapshot (with ATM data, expected move, OI levels) so evaluators work
    try:
        snapshot = await get_market_snapshot(chain_symbol, chain)
    except Exception as e:
        print(f"[suggest] snapshot error: {e}")
        snapshot = {
            "symbol": chain_symbol,
            "spot": chain.get("spot_price", 0),
            "vix": chain.get("vix", 0),
            "vix_regime": "unknown",
            "pcr": chain.get("pcr", 0),
            "atm": {"strike": 0, "CE": {"ltp": 0, "iv": 0}, "PE": {"ltp": 0, "iv": 0}},
            "expected_move": 0,
            "max_pain": 0,
            "oi_levels": {"support": 0, "resistance": 0, "support_oi": 0, "resistance_oi": 0},
            "iv_percentile": -1,
            "nearest_expiry": chain.get("expiry_dates", [""])[0] if chain.get("expiry_dates") else "",
            "days_to_expiry": horizon_days,
            "greeks": {},
        }

    # Build indicators for directional strategies (use index_indicators for indices, screener for stocks)
    indicators = {}
    try:
        if chain_symbol in ("NIFTY", "NIFTYIT", "BANKNIFTY"):
            from trading.index_indicators import get_index_indicators
            ind_sym = "NIFTYIT" if chain_symbol == "NIFTYIT" else chain_symbol
            indicators = await asyncio.to_thread(get_index_indicators, ind_sym)
        else:
            from analysis.screener import screen_stock
            screen_result = await asyncio.to_thread(screen_stock, symbol)
            indicators = screen_result.indicators or {}
            indicators["overall_score"] = screen_result.overall_score
    except Exception as e:
        print(f"[suggest] indicators error: {e}")

    # Strategy recommendation: conviction (normalized) + horizon → preferred evaluator
    horizon_bucket = "short" if horizon_days <= 14 else "medium" if horizon_days <= 60 else "long"

    strategy_map = {
        ("high", "short"): NiftyITFuturesShortEvaluator() if chain_symbol == "NIFTYIT" else LongPutBreakdownEvaluator(),
        ("high", "medium"): LongPutBreakdownEvaluator(),
        ("high", "long"): BearPutSpreadEvaluator(),
        ("moderate", "short"): BearCallSpreadEvaluator(),
        ("moderate", "medium"): BearPutSpreadEvaluator(),
        ("moderate", "long"): PreEarningsLongPutEvaluator(),
        ("low", "short"): BearCallSpreadEvaluator(),
        ("low", "medium"): BearCallSpreadEvaluator(),
        ("low", "long"): BearPutSpreadEvaluator(),
    }
    primary_evaluator = strategy_map.get((conviction_norm, horizon_bucket), BearPutSpreadEvaluator())

    # Run all evaluators, collect any that produce a proposal
    all_evals = [primary_evaluator, LongPutBreakdownEvaluator(), BearPutSpreadEvaluator(),
                 BearCallSpreadEvaluator(), PreEarningsLongPutEvaluator()]

    seen_ids = set()
    suggestions = []
    for ev in all_evals:
        if ev.strategy_id in seen_ids:
            continue
        seen_ids.add(ev.strategy_id)
        try:
            proposal = await ev.evaluate(snapshot, chain, indicators)
            if proposal:
                proposal["recommended_for"] = {
                    "conviction": conviction_norm,
                    "horizon_days": horizon_days,
                    "is_primary": ev.strategy_id == primary_evaluator.strategy_id,
                }
                suggestions.append(proposal)
        except Exception as e:
            print(f"[suggest] {ev.strategy_id} on {symbol}: {e}")

    # FALLBACK: if no evaluator produced anything (conditions too strict), force-build
    # a Bear Put Spread proposal so the user always sees a structure for their query
    if not suggestions:
        try:
            from datetime import datetime as _dt
            from trading.strategies import _round_strike, _find_strike_data
            spot = snapshot.get("spot", 0) or chain.get("spot_price", 0)
            strikes = chain.get("strikes", [])
            if spot > 0 and strikes:
                # Use 100-point wide spread, rounded to 50
                atm = _round_strike(spot, 50)
                otm = atm - 100
                buy_put = _find_strike_data(strikes, atm, "PE")
                sell_put = _find_strike_data(strikes, otm, "PE")
                buy_ltp = buy_put.get("ltp") or max(spot * 0.02, 5.0)
                sell_ltp = sell_put.get("ltp") or max(spot * 0.01, 2.5)
                debit = max(buy_ltp - sell_ltp, 1.0)
                lot_size = stock.get("lot_size", 100) if stock else 100
                spread_width = 100
                max_loss = debit * lot_size
                max_profit = max((spread_width - debit) * lot_size, lot_size)
                fallback = {
                    "strategy_id": "it_bear_put_spread",
                    "strategy_name": "Bear Put Spread",
                    "symbol": chain_symbol,
                    "direction": "bearish",
                    "legs": [
                        {"action": "BUY", "type": "PE", "strike": atm, "qty": lot_size,
                         "ltp": float(buy_ltp), "option_type": "PE"},
                        {"action": "SELL", "type": "PE", "strike": otm, "qty": lot_size,
                         "ltp": float(sell_ltp), "option_type": "PE"},
                    ],
                    "max_profit": float(round(max_profit, 2)),
                    "max_loss": float(round(-abs(max_loss), 2)),
                    "margin_needed": float(round(max_loss, 2)),
                    "confidence": 0.55,
                    "reasoning": (
                        f"Bear Put Spread on {chain_symbol} @ Rs.{spot:.0f}. "
                        f"BUY {atm} PE @ Rs.{buy_ltp:.1f}, SELL {otm} PE @ Rs.{sell_ltp:.1f}. "
                        f"Net debit Rs.{debit:.1f}/unit (Rs.{max_loss:,.0f}/lot). "
                        f"Conviction: {conviction_norm}, horizon: {horizon_days}d. "
                        f"Defined-risk structure for the IT bear thesis."
                    ),
                    "recommended_for": {
                        "conviction": conviction_norm,
                        "horizon_days": horizon_days,
                        "is_primary": True,
                    },
                    "intelligence": {"layer": "core", "spread_width": spread_width,
                                      "is_fallback": True, "nearest_expiry": snapshot.get("nearest_expiry", "")},
                    "created_at": _dt.now().isoformat(),
                }
                suggestions.append(fallback)
        except Exception as e:
            print(f"[suggest] fallback failed: {e}")

    # Primary is the first suggestion (or None)
    primary = suggestions[0] if suggestions else None

    # Build response: flat top-level fields the frontend expects + suggestions list
    response = {
        "symbol": symbol,
        "conviction": conviction_norm,
        "horizon_days": horizon_days,
        "primary_strategy": primary_evaluator.strategy_name,
        "suggestions": suggestions,
    }
    if primary:
        # Compute breakeven for bear put spread: BUY strike - debit
        breakeven = None
        try:
            legs = primary.get("legs", [])
            buy_leg = next((l for l in legs if str(l.get("action", "")).upper() == "BUY"), None)
            if buy_leg:
                buy_strike = buy_leg.get("strike", 0)
                buy_ltp = buy_leg.get("ltp", 0)
                breakeven = buy_strike - buy_ltp
        except Exception:
            pass

        response.update({
            "structure": primary.get("strategy_name", "Bear Put Spread"),
            "strategy_type": primary.get("strategy_id", ""),
            "confidence": round(float(primary.get("confidence", 0)) * 100, 0),
            "legs": primary.get("legs", []),
            "max_profit": primary.get("max_profit", 0),
            "max_loss": primary.get("max_loss", 0),
            "breakeven": breakeven,
            "capital_required": primary.get("margin_needed", 0),
            "reasoning": primary.get("reasoning", ""),
            "layer": primary.get("intelligence", {}).get("layer", "core"),
        })

    return response


# ---------------------------------------------------------------------------
# Notification Management API
# ---------------------------------------------------------------------------

@app.get("/api/notifications/config")
async def notification_config():
    """
    Get notification channel configuration status.
    Returns which channels are configured (without exposing credentials).
    """
    import os
    return {
        "email": {
            "configured": bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASS")),
            "recipient": os.getenv("NOTIFY_EMAIL") or os.getenv("SMTP_USER", ""),
            "smtp_host": os.getenv("SMTP_HOST", ""),
        },
        "telegram": {
            "configured": bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        },
        "websocket": {
            "configured": True,  # Always available
        },
    }


@app.put("/api/notifications/config")
async def update_notification_config(body: dict):
    """
    Update notification channel preferences.
    Accepts: notify_email, telegram_chat_id, smtp_host, smtp_port, smtp_user.
    Note: Credentials are NOT stored in DB — use .env file for security.
    For UI toggle only (enable/disable channels in trading_config).
    """
    from db.database import _get_db

    allowed = {"it_bear_enabled", "auto_layer_core", "auto_layer_tactical",
               "auto_layer_us", "auto_layer_hedge"}

    updates = {k: (1 if v else 0) for k, v in body.items() if k in allowed}

    if not updates:
        return {"status": "no_changes", "note": "Set SMTP/Telegram credentials in .env file"}

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())

    async with _get_db() as db:
        await db.execute(
            f"UPDATE trading_config SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
            values,
        )
        await db.commit()

    # Update engine's in-memory layer config
    from trading.engine import trading_engine
    for key, val in updates.items():
        if key.startswith("auto_layer_"):
            layer = key.replace("auto_layer_", "")
            trading_engine.auto_execute_layers[layer] = bool(val)

    return {"status": "updated", "fields": list(updates.keys())}


@app.post("/api/notifications/test/{channel}")
async def test_notification(channel: str):
    """
    Send a test message to a specific channel.
    channel: email | telegram | websocket | all
    """
    if channel not in ("email", "telegram", "websocket", "all"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid channel '{channel}'. Use: email, telegram, websocket, all"
        )

    from notifications.dispatcher import send_test_notification
    results = await send_test_notification(channel)
    return {
        "channel": channel,
        "results": results,
        "any_success": any(results.values()),
    }


# ---------------------------------------------------------------------------
# Telegram setup + listener control
# ---------------------------------------------------------------------------

@app.post("/api/notifications/telegram/setup")
async def telegram_setup(body: dict):
    """
    One-step Telegram setup. Body: { "bot_token": "1234:abc..." }

    Persists the token to .env, optionally captures a chat_id from any
    pending /start messages, then starts the long-polling listener.
    The user can then send /start to their bot — the listener will
    auto-save TELEGRAM_CHAT_ID and reply with a welcome message.
    """
    from zerodha.auth import _write_env_key
    from notifications.telegram_listener import start_listener, stop_listener
    import httpx

    token = (body.get("bot_token") or "").strip()
    if not token or ":" not in token:
        raise HTTPException(
            status_code=400,
            detail="bot_token is required (looks like '1234567890:AAabcde...')"
        )

    # Validate by calling getMe
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            data = resp.json()
            if not data.get("ok"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid bot token: {data.get('description', 'rejected by Telegram')}"
                )
            bot_info = data["result"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to validate token: {e}")

    # Save token
    _write_env_key("TELEGRAM_BOT_TOKEN", token)
    os.environ["TELEGRAM_BOT_TOKEN"] = token

    # Try to capture chat_id from existing /start updates (idempotent)
    chat_id_captured = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            updates_resp = await client.get(f"https://api.telegram.org/bot{token}/getUpdates")
            updates = updates_resp.json().get("result", [])
        for upd in updates:
            msg = upd.get("message", {})
            if msg.get("text", "").startswith("/start"):
                cid = msg.get("chat", {}).get("id")
                if cid:
                    chat_id_captured = cid
                    _write_env_key("TELEGRAM_CHAT_ID", str(cid))
                    os.environ["TELEGRAM_CHAT_ID"] = str(cid)
                    break
    except Exception as e:
        print(f"[telegram_setup] chat_id capture skipped: {e}")

    # Restart listener with new token
    await stop_listener()
    listener_result = await start_listener()

    return {
        "status": "configured",
        "bot": {
            "username": bot_info.get("username"),
            "name": bot_info.get("first_name"),
        },
        "chat_id_captured": chat_id_captured,
        "listener": listener_result,
        "next_step": (
            "Send /start to your bot in Telegram. The listener will auto-save your chat_id."
            if not chat_id_captured
            else "✅ All set — send /add TCS INFY AAPL to your bot."
        ),
    }


@app.get("/api/notifications/telegram/status")
async def telegram_status():
    """Show whether token + chat_id are set + listener state."""
    from notifications.telegram_listener import is_listening
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    return {
        "token_set": bool(token),
        "token_preview": (token[:10] + "..." + token[-4:]) if token else "",
        "chat_id_set": bool(chat_id),
        "chat_id": chat_id,
        "listener_running": is_listening(),
    }


@app.post("/api/notifications/telegram/listener/{action}")
async def telegram_listener_control(action: str):
    """action: start | stop | restart"""
    from notifications.telegram_listener import start_listener, stop_listener
    if action == "start":
        return await start_listener()
    if action == "stop":
        return await stop_listener()
    if action == "restart":
        await stop_listener()
        return await start_listener()
    raise HTTPException(status_code=400, detail="action must be: start | stop | restart")


@app.get("/api/telegram/watchlist")
async def telegram_watchlist():
    """Return all stocks added to the watchlist via Telegram."""
    from notifications.telegram_listener import _get_watchlist
    return await _get_watchlist()


# ---------------------------------------------------------------------------
# LLM Gateway — cost observability + budget control
# ---------------------------------------------------------------------------

@app.get("/api/llm/usage")
async def llm_usage():
    """Token/cost observability: spend today/month, limits, by-feature, recent calls."""
    from llm.gateway import usage_summary
    return await usage_summary()


@app.get("/api/llm/config")
async def llm_get_config():
    """Current LLM limits + provider/model config."""
    from llm.gateway import get_config
    return await get_config()


@app.put("/api/llm/config")
async def llm_update_config(body: dict):
    """Update LLM limits (daily/monthly USD caps, per-call tokens, rate, provider, model)."""
    from llm.gateway import update_config
    return await update_config(body)


@app.post("/api/llm/test")
async def llm_test(body: dict = None):
    """
    Fire a tiny test completion to verify the provider + key work.
    Counts against the budget (it's a real call) but capped to ~30 tokens.
    """
    from llm.gateway import complete, LLMError
    body = body or {}
    try:
        res = await complete(
            body.get("prompt", "Reply with exactly: LLM gateway OK"),
            feature="gateway_test",
            max_tokens=30,
            allow_cache=False,
        )
        return {"status": "ok", **res.to_dict()}
    except LLMError as e:
        raise HTTPException(status_code=400, detail={"status": e.status, "message": str(e)})


@app.get("/api/llm/providers")
async def llm_providers():
    """Which provider API keys are configured (for the Settings UI)."""
    return {
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY", "").strip()),
        "openai": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "groq": bool(os.getenv("GROQ_API_KEY", "").strip()),
        "gemini": bool(os.getenv("GOOGLE_API_KEY", "").strip()),
    }


@app.post("/api/llm/provider-key")
async def llm_set_provider_key(body: dict):
    """
    Save a provider API key to .env (so the user can paste their Claude/OpenAI key
    from the UI). body: { provider: 'anthropic'|'openai'|'groq'|'gemini', api_key: '...' }
    """
    from zerodha.auth import _write_env_key
    provider = (body.get("provider") or "").lower()
    api_key = (body.get("api_key") or "").strip()
    env_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "groq": "GROQ_API_KEY",
        "gemini": "GOOGLE_API_KEY",
    }
    if provider not in env_map:
        raise HTTPException(status_code=400, detail="provider must be anthropic|openai|groq|gemini")
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key is required")
    _write_env_key(env_map[provider], api_key)
    os.environ[env_map[provider]] = api_key
    return {"status": "saved", "provider": provider, "env_var": env_map[provider]}


# ---------------------------------------------------------------------------
# System health (ops/admin) — protected implicitly by auth_middleware since
# this path starts with /api/.
# ---------------------------------------------------------------------------

@app.get("/api/system/health")
async def system_health():
    """
    System resource snapshot for the admin dashboard: disk, memory, load
    average, DB file size, Python version, and server time.

    mem.* fields are None on platforms without /proc/meminfo (e.g. macOS).
    """
    import shutil
    import sys
    from datetime import datetime, timezone

    # Disk usage (root filesystem)
    disk_total, _disk_used_ignored, disk_free = shutil.disk_usage("/")
    disk_used = disk_total - disk_free
    disk = {
        "total_gb": round(disk_total / (1024 ** 3), 2),
        "used_gb": round(disk_used / (1024 ** 3), 2),
        "pct": round(disk_used / disk_total * 100, 1) if disk_total else None,
    }

    # Memory — Linux-only via /proc/meminfo; None fields elsewhere (e.g. macOS).
    mem = {"total_mb": None, "available_mb": None, "pct": None}
    try:
        meminfo: dict[str, int] = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    meminfo[parts[0].strip()] = int(parts[1].strip().split()[0])

        total_kb = meminfo.get("MemTotal")
        available_kb = meminfo.get("MemAvailable")
        if total_kb:
            mem["total_mb"] = round(total_kb / 1024, 1)
        if available_kb:
            mem["available_mb"] = round(available_kb / 1024, 1)
        if total_kb and available_kb:
            mem["pct"] = round((total_kb - available_kb) / total_kb * 100, 1)
    except Exception:
        pass  # /proc/meminfo not available on this platform

    # Load average
    try:
        load_avg = list(os.getloadavg())
    except (OSError, AttributeError):
        load_avg = None

    # DB file size
    db_path = Path(__file__).resolve().parent / "data" / "portfolio.db"
    try:
        db_size_mb = round(os.path.getsize(db_path) / (1024 ** 2), 2)
    except OSError:
        db_size_mb = None

    return {
        "disk": disk,
        "mem": mem,
        "load_avg": load_avg,
        "db_size_mb": db_size_mb,
        "python": sys.version.split()[0],
        "time": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# WebSocket for trading notifications
# ---------------------------------------------------------------------------

@app.websocket("/ws/trading")
async def trading_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time trading updates. Requires a valid session cookie."""
    from trading.engine import trading_engine

    token = websocket.cookies.get("session")
    user = await get_session_user(token) if token else None
    if not user:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    trading_engine.register_ws(websocket)

    try:
        # Send initial status
        await websocket.send_json({"type": "engine_status", **trading_engine.status})
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Client can send ping/pong or commands
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        trading_engine.unregister_ws(websocket)
    except Exception:
        trading_engine.unregister_ws(websocket)


# ---------------------------------------------------------------------------
# SPA static serving — serves the built frontend (frontend/dist), if present.
#
# Entirely a no-op in dev before `npm run build` has ever produced a dist/
# folder: none of the routes below get registered, so nothing about local
# dev (Vite on :5173 talking to this API on its own port) changes.
#
# Must stay at the very end of the file: the catch-all route matches any
# path, so anything registered after it would be unreachable.
# ---------------------------------------------------------------------------

_FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    _FRONTEND_ASSETS = _FRONTEND_DIST / "assets"
    if _FRONTEND_ASSETS.exists():
        app.mount("/assets", StaticFiles(directory=str(_FRONTEND_ASSETS)), name="assets")

    _FRONTEND_FAVICON = _FRONTEND_DIST / "favicon.svg"

    @app.get("/favicon.svg")
    async def _spa_favicon():
        if _FRONTEND_FAVICON.exists():
            return FileResponse(str(_FRONTEND_FAVICON))
        raise HTTPException(status_code=404, detail="favicon.svg not found")

    @app.get("/{full_path:path}")
    async def _spa_catch_all(full_path: str):
        """Serve index.html for any non-API, non-WS path (client-side routing)."""
        if full_path.startswith("api/") or full_path == "ws" or full_path.startswith("ws/"):
            raise HTTPException(status_code=404, detail="Not found")

        index_file = _FRONTEND_DIST / "index.html"
        if not index_file.exists():
            raise HTTPException(status_code=404, detail="Frontend build not found")
        return FileResponse(str(index_file))

    print(f"[main] Serving SPA static build from {_FRONTEND_DIST}")
else:
    print(f"[main] Frontend dist not found at {_FRONTEND_DIST} — SPA static serving disabled (dev mode).")
