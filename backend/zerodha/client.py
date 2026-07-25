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

    # Per-user (multi-user auth) variant — see auth/service.py user_settings:
    from zerodha.client import get_holdings_for_user
    holdings = await get_holdings_for_user(user)   # user: dict | None

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

def _get_holdings_via_console(user_id: str, password: str, totp_secret: str) -> list[dict] | None:
    """
    Fetch real holdings via jugaad-trader, given explicit Console credentials.

    Supports both jugaad-trader v0.20+ (login()) and older versions
    (login_using_enc_token()).

    Args:
        user_id, password, totp_secret: Zerodha Console login credentials
            (NOT Kite Connect API key/secret — these are the actual
            user's Zerodha login + their TOTP app's shared secret).

    Returns:
        list[dict]  — real holdings (may be empty if account has none)
        None        — credentials incomplete, skip silently
    Raises:
        Exception   — credentials provided but login/fetch failed
    """
    from jugaad_trader import Zerodha
    import pyotp

    user_id     = (user_id or "").strip()
    password    = (password or "").strip()
    totp_secret = (totp_secret or "").strip()

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
# Credential resolution — env (legacy/global) vs per-user (auth/service.py)
# ---------------------------------------------------------------------------

def _env_creds() -> tuple[str, str, str] | None:
    """Read Zerodha Console credentials from the environment (.env). None if incomplete."""
    load_dotenv(override=True)
    user_id     = os.getenv("ZERODHA_USER_ID",     "").strip()
    password    = os.getenv("ZERODHA_PASSWORD",    "").strip()
    totp_secret = os.getenv("ZERODHA_TOTP_SECRET", "").strip()
    if user_id and password and totp_secret:
        return user_id, password, totp_secret
    return None


def _get_holdings_via_console_env() -> list[dict] | None:
    """Backward-compatible env-reading wrapper around _get_holdings_via_console()."""
    creds = _env_creds()
    if creds is None:
        print("[client] Console API: credentials not set, skipping")
        return None
    return _get_holdings_via_console(*creds)


async def _resolve_creds_for_user(user: dict | None) -> tuple[str, str, str] | None:
    """
    Resolve (user_id, password, totp_secret) Console credentials for `user`.

      - user is None            -> legacy/global path: env credentials.
      - user has own settings   -> use their zerodha_user_id/password/totp_secret
                                    (see auth/service.py user_settings, encrypted at rest).
      - user has none, is_admin -> fall back to legacy env credentials.
      - otherwise               -> None (caller should use dummy data).

    Never raises.
    """
    if user is None:
        return _env_creds()

    from auth import service as auth_service

    try:
        zerodha_user_id = await auth_service.get_user_setting(user["id"], "zerodha_user_id")
        zerodha_password = await auth_service.get_user_setting(user["id"], "zerodha_password")
        zerodha_totp_secret = await auth_service.get_user_setting(user["id"], "zerodha_totp_secret")
    except Exception as exc:
        print(f"[client] Failed to read per-user Zerodha settings: {exc}")
        zerodha_user_id = zerodha_password = zerodha_totp_secret = None

    if zerodha_user_id and zerodha_password and zerodha_totp_secret:
        return zerodha_user_id, zerodha_password, zerodha_totp_secret

    if user.get("is_admin"):
        return _env_creds()

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_holdings() -> list[dict]:
    """
    Return portfolio holdings (legacy/global — env credentials or dummy data).

    Never raises — always returns a usable list.
    Re-reads .env on every call so credentials saved at runtime are visible.
    Kept working as-is for the trading engine + other legacy callers that
    don't have a per-request user (see get_holdings_for_user() for the
    multi-user-aware equivalent).
    """
    load_dotenv(override=True)

    # ── Console API ───────────────────────────────────────────────────────────
    try:
        holdings = await asyncio.to_thread(_get_holdings_via_console_env)

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


async def get_holdings_for_user(user: dict | None) -> list[dict]:
    """
    Return portfolio holdings for a specific authenticated user.

      - Complete per-user Zerodha creds (Settings UI) -> real holdings.
      - Incomplete per-user creds + user is admin      -> legacy env creds.
      - Incomplete per-user creds + non-admin           -> dummy data.
      - user is None                                    -> legacy env-or-dummy
        (same behaviour as get_holdings()).
      - Any failure at any step                         -> dummy data.

    Never raises.
    """
    try:
        creds = await _resolve_creds_for_user(user)
        if creds is None:
            print("[client] get_holdings_for_user: no usable credentials, using dummy data")
            return _dummy_holdings()

        holdings = await asyncio.to_thread(_get_holdings_via_console, *creds)

        if not holdings:
            print("[client] get_holdings_for_user: account empty/no data, using dummy data")
            return _dummy_holdings()
        return holdings

    except Exception as exc:
        print(f"[client] get_holdings_for_user failed: {exc}")
        return _dummy_holdings()
