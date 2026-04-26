"""
intelligence.py — Options analytics: Greeks, IV Percentile, Expected Move, Max Pain, VIX.
Uses scipy for Black-Scholes calculations.
"""
import math
from datetime import datetime, date

import numpy as np
from scipy.stats import norm


# Risk-free rate (India 10Y govt bond yield, approximate)
RISK_FREE_RATE = 0.07


def calculate_greeks(spot: float, strike: float, T: float, r: float, sigma: float,
                     option_type: str = "CE") -> dict:
    """
    Black-Scholes Greeks calculation.

    Args:
        spot: Current underlying price
        strike: Option strike price
        T: Time to expiry in years (e.g., 5/365 for 5 days)
        r: Risk-free rate (annualized)
        sigma: Implied volatility (annualized, as decimal e.g. 0.15 for 15%)
        option_type: "CE" for call, "PE" for put

    Returns:
        dict with delta, gamma, theta, vega
    """
    if T <= 0 or sigma <= 0 or spot <= 0 or strike <= 0:
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0}

    sqrt_T = math.sqrt(T)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    # Delta
    if option_type == "CE":
        delta = norm.cdf(d1)
    else:
        delta = norm.cdf(d1) - 1

    # Gamma (same for calls and puts)
    gamma = norm.pdf(d1) / (spot * sigma * sqrt_T)

    # Theta (per day)
    theta_common = -(spot * norm.pdf(d1) * sigma) / (2 * sqrt_T)
    if option_type == "CE":
        theta = (theta_common - r * strike * math.exp(-r * T) * norm.cdf(d2)) / 365
    else:
        theta = (theta_common + r * strike * math.exp(-r * T) * norm.cdf(-d2)) / 365

    # Vega (per 1% change in IV)
    vega = spot * sqrt_T * norm.pdf(d1) / 100

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 2),
        "vega": round(vega, 2),
    }


def days_to_expiry(expiry_date_str: str) -> float:
    """Calculate days to expiry from date string (e.g., '27-Mar-2025')."""
    try:
        for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%B-%Y"):
            try:
                exp = datetime.strptime(expiry_date_str, fmt).date()
                dte = (exp - date.today()).days
                return max(dte, 0.01)  # Avoid zero
            except ValueError:
                continue
        return 5  # Default 5 days
    except Exception:
        return 5


def calculate_expected_move(atm_call_ltp: float, atm_put_ltp: float) -> float:
    """
    Expected 1-sigma move = 0.85 x ATM Straddle Price.
    Used for Iron Condor strike selection — sell short strikes outside this range.
    """
    return round(0.85 * (atm_call_ltp + atm_put_ltp), 2)


def calculate_max_pain(strikes: list[dict]) -> int:
    """
    Max Pain = strike where total loss for option holders is minimized.

    For each potential expiry price:
    - Calculate total intrinsic value of all calls (loss for call holders)
    - Calculate total intrinsic value of all puts (loss for put holders)
    - Max Pain is the price that minimizes the sum
    """
    if not strikes:
        return 0

    # Get unique strike prices
    strike_prices = sorted(set(s.get("strikePrice", 0) for s in strikes if s.get("strikePrice", 0) > 0))
    if not strike_prices:
        return 0

    # Build OI map
    call_oi = {}
    put_oi = {}
    for s in strikes:
        sp = s.get("strikePrice", 0)
        if sp <= 0:
            continue
        ce = s.get("CE", {})
        pe = s.get("PE", {})
        call_oi[sp] = ce.get("oi", 0)
        put_oi[sp] = pe.get("oi", 0)

    min_loss = float("inf")
    max_pain_strike = strike_prices[len(strike_prices) // 2]

    for test_price in strike_prices:
        total_loss = 0
        for sp in strike_prices:
            # Call holder loss: max(0, test_price - strike) * OI
            if test_price > sp:
                total_loss += (test_price - sp) * call_oi.get(sp, 0)
            # Put holder loss: max(0, strike - test_price) * OI
            if test_price < sp:
                total_loss += (sp - test_price) * put_oi.get(sp, 0)

        if total_loss < min_loss:
            min_loss = total_loss
            max_pain_strike = test_price

    return max_pain_strike


def get_oi_levels(strikes: list[dict], spot: float) -> dict:
    """
    Find OI-based support and resistance levels.
    Resistance = strike with highest CE OI above spot
    Support = strike with highest PE OI below spot
    """
    max_ce_oi = 0
    max_pe_oi = 0
    resistance = 0
    support = 0

    for s in strikes:
        sp = s.get("strikePrice", 0)
        if sp <= 0:
            continue

        ce_oi = s.get("CE", {}).get("oi", 0)
        pe_oi = s.get("PE", {}).get("oi", 0)

        if sp >= spot and ce_oi > max_ce_oi:
            max_ce_oi = ce_oi
            resistance = sp

        if sp <= spot and pe_oi > max_pe_oi:
            max_pe_oi = pe_oi
            support = sp

    return {
        "resistance": resistance,
        "resistance_oi": max_ce_oi,
        "support": support,
        "support_oi": max_pe_oi,
    }


def classify_vix(vix: float) -> str:
    """Classify VIX regime for strategy selection."""
    if vix < 12:
        return "low"
    elif vix < 16:
        return "normal"
    elif vix < 22:
        return "elevated"
    else:
        return "high"


def get_atm_strike(spot: float, step: int = 50) -> int:
    """Round spot to nearest strike step."""
    return round(spot / step) * step


def get_atm_data(strikes: list[dict], spot: float) -> dict:
    """Get ATM call and put LTP + IV from option chain."""
    atm = get_atm_strike(spot)
    atm_ce = {"ltp": 0, "iv": 0, "oi": 0}
    atm_pe = {"ltp": 0, "iv": 0, "oi": 0}

    for s in strikes:
        if s.get("strikePrice") == atm:
            ce = s.get("CE", {})
            pe = s.get("PE", {})
            atm_ce = {"ltp": ce.get("ltp", 0), "iv": ce.get("iv", 0), "oi": ce.get("oi", 0)}
            atm_pe = {"ltp": pe.get("ltp", 0), "iv": pe.get("iv", 0), "oi": pe.get("oi", 0)}
            break

    return {"strike": atm, "CE": atm_ce, "PE": atm_pe}


async def get_vix() -> float:
    """Fetch India VIX. Returns 0 if unavailable."""
    try:
        import yfinance as yf
        import asyncio
        vix_data = await asyncio.to_thread(
            lambda: yf.Ticker("^INDIAVIX").history(period="1d")
        )
        if not vix_data.empty:
            return round(float(vix_data["Close"].iloc[-1]), 2)
    except Exception as e:
        print(f"[intelligence] VIX fetch failed: {e}")
    return 0


async def get_iv_percentile_from_db(symbol: str) -> float:
    """
    IV Percentile = % of days in past year with IV below current level.
    Requires iv_history table to have data.
    """
    from db.database import _get_db

    async with _get_db() as db:
        db.row_factory = __import__("aiosqlite").Row
        rows = await db.execute_fetchall(
            "SELECT atm_iv FROM iv_history WHERE symbol = ? ORDER BY date DESC LIMIT 252",
            (symbol.upper(),)
        )

    if len(rows) < 10:
        return -1  # Not enough data

    historical_ivs = [r["atm_iv"] for r in rows]
    current_iv = historical_ivs[0]
    below_count = sum(1 for iv in historical_ivs if iv < current_iv)

    return round(below_count / len(historical_ivs) * 100, 1)


async def save_iv_snapshot(symbol: str, atm_iv: float, vix: float) -> None:
    """Save today's IV to history for percentile calculation."""
    from db.database import _get_db
    today = date.today().isoformat()

    async with _get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO iv_history (symbol, date, atm_iv, vix) VALUES (?, ?, ?, ?)",
            (symbol.upper(), today, atm_iv, vix),
        )
        await db.commit()


async def get_market_snapshot(symbol: str, option_data: dict) -> dict:
    """
    Aggregate all intelligence into one snapshot.

    Returns dict with:
    - spot, vix, vix_regime, pcr
    - atm_data (strike, CE/PE LTP and IV)
    - expected_move
    - max_pain
    - oi_levels (support, resistance)
    - iv_percentile
    - greeks for ATM call and put
    """
    spot = option_data.get("spot_price", 0)
    strikes = option_data.get("strikes", [])
    pcr = option_data.get("pcr", 0)

    vix = await get_vix()
    atm = get_atm_data(strikes, spot)
    expected_move = calculate_expected_move(atm["CE"]["ltp"], atm["PE"]["ltp"])
    max_pain = calculate_max_pain(strikes)
    oi_levels = get_oi_levels(strikes, spot)
    iv_pct = await get_iv_percentile_from_db(symbol)

    # Get nearest expiry
    expiry_dates = option_data.get("expiry_dates", [])
    nearest_expiry = expiry_dates[0] if expiry_dates else ""
    dte = days_to_expiry(nearest_expiry)
    T = dte / 365

    # ATM Greeks
    atm_iv_ce = atm["CE"]["iv"] / 100 if atm["CE"]["iv"] > 0 else 0.15
    atm_iv_pe = atm["PE"]["iv"] / 100 if atm["PE"]["iv"] > 0 else 0.15

    ce_greeks = calculate_greeks(spot, atm["strike"], T, RISK_FREE_RATE, atm_iv_ce, "CE")
    pe_greeks = calculate_greeks(spot, atm["strike"], T, RISK_FREE_RATE, atm_iv_pe, "PE")

    # Save IV for percentile tracking
    avg_atm_iv = (atm["CE"]["iv"] + atm["PE"]["iv"]) / 2
    if avg_atm_iv > 0:
        await save_iv_snapshot(symbol, avg_atm_iv, vix)

    return {
        "symbol": symbol,
        "spot": spot,
        "vix": vix,
        "vix_regime": classify_vix(vix),
        "pcr": pcr,
        "atm": atm,
        "expected_move": expected_move,
        "max_pain": max_pain,
        "oi_levels": oi_levels,
        "iv_percentile": iv_pct,
        "nearest_expiry": nearest_expiry,
        "days_to_expiry": dte,
        "greeks": {
            "atm_ce": ce_greeks,
            "atm_pe": pe_greeks,
            "net_delta": round(ce_greeks["delta"] + pe_greeks["delta"], 4),
            "net_theta": round(ce_greeks["theta"] + pe_greeks["theta"], 2),
        },
        "timestamp": datetime.now().isoformat(),
    }
