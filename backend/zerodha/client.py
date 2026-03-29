"""
client.py — Zerodha holdings fetcher

Priority order:
    1. jugaad-trader Console API  (login_using_enc_token)
       - Returns real holdings → use them
       - Returns empty list    → account has no holdings, use dummy data
       - Any error             → fall through to dummy data
    2. Dummy data               (development / demo fallback)

Public API:
    from zerodha.client import get_holdings
    holdings = await get_holdings()

Each holding dict has:
    symbol, quantity, average_price, last_price, pnl, pnl_percentage
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Fixed dummy data — stable values for development / demo
# ---------------------------------------------------------------------------

_DUMMY_HOLDINGS: list[dict] = [
    {"symbol": "RELIANCE", "quantity": 15, "average_price": 2650.0, "last_price": 2810.0, "pnl":  2400.0, "pnl_percentage":  6.03},
    {"symbol": "TCS",      "quantity": 10, "average_price": 3200.0, "last_price": 3490.0, "pnl":  2900.0, "pnl_percentage":  9.06},
    {"symbol": "INFY",     "quantity": 20, "average_price": 1750.0, "last_price": 1820.0, "pnl":  1400.0, "pnl_percentage":  4.0 },
    {"symbol": "HDFCBANK", "quantity":  8, "average_price": 1680.0, "last_price": 1590.0, "pnl":  -720.0, "pnl_percentage": -5.36},
    {"symbol": "WIPRO",    "quantity": 25, "average_price":  480.0, "last_price":  445.0, "pnl":  -875.0, "pnl_percentage": -7.29},
]


def _dummy_holdings() -> list[dict]:
    return [h.copy() for h in _DUMMY_HOLDINGS]


# ---------------------------------------------------------------------------
# Source — jugaad-trader Console API
# ---------------------------------------------------------------------------

def _get_holdings_via_console() -> list[dict] | None:
    """
    Fetch real holdings via jugaad-trader.

    Supports both jugaad-trader v0.20+ (login()) and older versions
    (login_using_enc_token()).

    Returns:
        list[dict]  — real holdings (may be empty if account has none)
        None        — credentials not configured, skip silently
    Raises:
        Exception   — credentials set but login/fetch failed
    """
    from jugaad_trader import Zerodha
    import pyotp

    user_id     = os.getenv("ZERODHA_USER_ID",     "").strip()
    password    = os.getenv("ZERODHA_PASSWORD",    "").strip()
    totp_secret = os.getenv("ZERODHA_TOTP_SECRET", "").strip()

    if not all([user_id, password, totp_secret]):
        print("[client] Console API: credentials not set, skipping")
        return None

    print(f"[client] Console API: logging in as {user_id}…")

    # Generate current TOTP code from secret
    totp = pyotp.TOTP(totp_secret)
    totp_code = totp.now()

    # jugaad-trader v0.20+ uses login() method
    kite = Zerodha(user_id=user_id, password=password, twofa=totp_code)

    if hasattr(kite, 'login'):
        kite.login()
    elif hasattr(kite, 'login_using_enc_token'):
        kite.login_using_enc_token()
    else:
        # Try step-by-step login
        kite.login_step1()
        kite.login_step2(totp_code)

    raw      = kite.holdings()
    holdings = []

    for stock in raw:
        symbol     = stock.get("tradingsymbol", "")
        qty        = stock.get("quantity", 0)
        avg_price  = stock.get("average_price", 0.0)
        last_price = stock.get("last_price", avg_price)
        pnl        = (last_price - avg_price) * qty
        pnl_pct    = ((last_price - avg_price) / avg_price * 100) if avg_price > 0 else 0.0

        holdings.append({
            "symbol":         symbol,
            "quantity":       qty,
            "average_price":  avg_price,
            "last_price":     last_price,
            "pnl":            round(pnl, 2),
            "pnl_percentage": round(pnl_pct, 2),
        })

    print(f"[client] Console API: got {len(holdings)} holdings")
    return holdings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_holdings() -> list[dict]:
    """
    Return portfolio holdings.

    Never raises — always returns a usable list.
    Re-reads .env on every call so credentials saved at runtime are visible.
    """
    load_dotenv(override=True)

    # ── Console API ───────────────────────────────────────────────────────────
    try:
        holdings = await asyncio.to_thread(_get_holdings_via_console)

        if holdings is None:
            # Credentials not configured — skip to dummy
            pass
        elif len(holdings) == 0:
            print("[client] Account empty, using demo data")
            return _dummy_holdings()
        else:
            return holdings

    except Exception as exc:
        print(f"[client] Console API failed: {exc}")

    # ── Dummy data ────────────────────────────────────────────────────────────
    print("[client] Falling back to dummy data")
    return _dummy_holdings()
