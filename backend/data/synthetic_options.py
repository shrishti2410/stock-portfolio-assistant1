"""
synthetic_options.py — Generate synthetic option chain data for paper trading.

Used when:
  - NSE market is closed (weekends/holidays)
  - Paper trading mode is active

Pulls last NIFTY/BANKNIFTY spot price + VIX from yfinance, then generates
realistic option chain using Black-Scholes pricing.

This lets users TEST paper trading 24/7 without waiting for market open.
"""
import math
from datetime import date, datetime, timedelta

import yfinance as yf
from scipy.stats import norm


YF_SYMBOLS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "FINNIFTY": "^CNXFIN",
    "NIFTYIT": "^CNXIT",
    "NIFTY IT": "^CNXIT",
}

STRIKE_STEPS = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "FINNIFTY": 50,
    "NIFTYIT": 100,
    "NIFTY IT": 100,
}


def _resolve_yf_ticker(symbol: str) -> str:
    """Map a trading symbol to its yfinance ticker.

    1. Index symbols → fixed map above
    2. Indian stocks → check IT universe (returns yf field) → fall back to {SYMBOL}.NS
    3. US stocks → use as-is
    """
    sym = symbol.upper().strip()
    if sym in YF_SYMBOLS:
        return YF_SYMBOLS[sym]
    try:
        from data.it_universe import get_by_symbol
        stock = get_by_symbol(sym)
        if stock and stock.get("yf"):
            return stock["yf"]
    except Exception:
        pass
    # Heuristic fallback
    if "." in sym:
        return sym
    return f"{sym}.NS"


def _resolve_strike_step(symbol: str, spot: float) -> int:
    """Pick a reasonable strike step for the symbol/price."""
    sym = symbol.upper().strip()
    if sym in STRIKE_STEPS:
        return STRIKE_STEPS[sym]
    # Heuristic based on price level (rounding to look realistic)
    if spot >= 10000:
        return 100
    if spot >= 2000:
        return 50
    if spot >= 500:
        return 10
    if spot >= 100:
        return 5
    if spot >= 20:
        return 1
    return 1


def _bs_price(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
    """Black-Scholes option price."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(0, S - K) if option_type == "CE" else max(0, K - S)

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "CE":
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    return max(round(price, 2), 0.05)


def _next_thursday(from_date: date) -> date:
    """Find the next Thursday (NIFTY weekly expiry day)."""
    days_ahead = 3 - from_date.weekday()  # Thursday is 3
    if days_ahead <= 0:
        days_ahead += 7
    return from_date + timedelta(days=days_ahead)


def _get_spot_and_vix(symbol: str) -> tuple[float, float]:
    """Fetch last close from yfinance. Returns (spot, vix)."""
    yf_sym = _resolve_yf_ticker(symbol)

    spot_ticker = yf.Ticker(yf_sym)
    hist = spot_ticker.history(period="5d")
    spot = float(hist["Close"].iloc[-1]) if not hist.empty else 23500.0

    vix_ticker = yf.Ticker("^INDIAVIX")
    vix_hist = vix_ticker.history(period="5d")
    vix = float(vix_hist["Close"].iloc[-1]) if not vix_hist.empty else 15.0

    return spot, vix


def generate_synthetic_chain(symbol: str) -> dict:
    """
    Generate a realistic option chain using yfinance spot + Black-Scholes.

    Returns same structure as data.options.get_option_chain() for compatibility.
    """
    symbol = symbol.upper().strip()
    spot, vix = _get_spot_and_vix(symbol)
    sigma = vix / 100  # VIX is annualized %, convert to decimal
    step = _resolve_strike_step(symbol, spot)

    # Round spot to nearest strike
    atm = round(spot / step) * step

    # Generate strikes: ATM ± 20 strikes (40 strikes total)
    strikes_range = list(range(atm - 20 * step, atm + 21 * step, step))

    # Generate 4 weekly expiries
    today = date.today()
    expiry_dates = []
    next_exp = _next_thursday(today)
    for i in range(4):
        expiry_dates.append(next_exp.strftime("%d-%b-%Y"))
        next_exp += timedelta(days=7)

    # Use nearest expiry for the data
    nearest_expiry_date = _next_thursday(today)
    days_to_exp = max((nearest_expiry_date - today).days, 1)
    T = days_to_exp / 365
    r = 0.07  # Risk-free rate

    # Generate strike data
    strikes = []
    total_ce_oi = 0
    total_pe_oi = 0

    for K in strikes_range:
        # Calculate prices
        ce_price = _bs_price(spot, K, T, r, sigma, "CE")
        pe_price = _bs_price(spot, K, T, r, sigma, "PE")

        # Generate realistic OI distribution (highest near ATM)
        moneyness_ce = abs(K - atm) / atm
        moneyness_pe = abs(K - atm) / atm

        # OI is highest at ATM, decays exponentially
        ce_oi = int(50000 * math.exp(-moneyness_ce * 30))
        pe_oi = int(50000 * math.exp(-moneyness_pe * 30))

        # Add some "wall" effect — higher OI at round-number resistance/support
        if K > atm:  # Resistance side (Call OI dominant)
            if K - atm == 2 * step:
                ce_oi = int(ce_oi * 2.5)
        elif K < atm:  # Support side (Put OI dominant)
            if atm - K == 2 * step:
                pe_oi = int(pe_oi * 2.5)

        # IV varies — higher for OTM strikes (smile)
        ce_iv = vix * (1 + abs(K - atm) / atm * 0.3)
        pe_iv = vix * (1 + abs(K - atm) / atm * 0.3)

        # Volume = ~10% of OI for ATM, less for OTM
        ce_volume = int(ce_oi * 0.15 * (1 - moneyness_ce * 5)) if moneyness_ce < 0.2 else 0
        pe_volume = int(pe_oi * 0.15 * (1 - moneyness_pe * 5)) if moneyness_pe < 0.2 else 0
        ce_volume = max(0, ce_volume)
        pe_volume = max(0, pe_volume)

        total_ce_oi += ce_oi
        total_pe_oi += pe_oi

        strikes.append({
            "strikePrice": K,
            "expiryDate": expiry_dates[0],
            "CE": {
                "oi": ce_oi,
                "changeInOI": int(ce_oi * 0.05),  # Simulate 5% change
                "volume": ce_volume,
                "iv": round(ce_iv, 2),
                "ltp": ce_price,
                "change": 0,
                "bidPrice": round(ce_price * 0.99, 2),
                "askPrice": round(ce_price * 1.01, 2),
            },
            "PE": {
                "oi": pe_oi,
                "changeInOI": int(pe_oi * 0.05),
                "volume": pe_volume,
                "iv": round(pe_iv, 2),
                "ltp": pe_price,
                "change": 0,
                "bidPrice": round(pe_price * 0.99, 2),
                "askPrice": round(pe_price * 1.01, 2),
            },
        })

    pcr = round(total_pe_oi / total_ce_oi, 3) if total_ce_oi > 0 else 1.0

    return {
        "symbol": symbol,
        "spot_price": round(spot, 2),
        "expiry_dates": expiry_dates,
        "total_ce_oi": total_ce_oi,
        "total_pe_oi": total_pe_oi,
        "pcr": pcr,
        "strikes": strikes,
        "strike_count": len(strikes),
        "synthetic": True,
        "synthetic_note": f"Generated from last close ({spot:.2f}) + VIX ({vix:.2f}). For paper trading only.",
        "vix": round(vix, 2),
    }


def get_chain_with_fallback(symbol: str, paper_mode: bool = True) -> dict:
    """
    Try live NSE chain first. If empty (market closed) and paper mode is on,
    fall back to synthetic chain generated from yfinance.
    """
    from data.options import get_option_chain

    live = get_option_chain(symbol)

    if live.get("market_closed") or live.get("strike_count", 0) == 0:
        if paper_mode:
            print(f"[options] Market closed — using synthetic chain for {symbol} (paper mode)")
            return generate_synthetic_chain(symbol)

    return live
