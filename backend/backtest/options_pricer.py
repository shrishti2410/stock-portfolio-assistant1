"""
options_pricer.py — synthetic option pricing for backtests (pure sync, no I/O).

THE MODEL (read this before trusting premium-strategy backtests):

  * Mark price = Black-Scholes-Merton European option price where
      - spot  : the underlying proxy bar close (e.g. ^NSEI 5m close)
      - sigma : India VIX **daily** close / 100 — a flat IV with no skew,
                no smile and no intraday term structure
      - T     : (days_to_expiry + intraday_minutes_remaining/375) / 365
      - r     : flat risk-free rate from strategy config
    Real option chains carry skew, event premia and supply/demand effects
    that this model deliberately ignores. Marks are SYNTHETIC.

  * Quotes are MODELED, not real market quotes. synthetic_quote() applies a
    half-spread of max(mark * spread_pct_each_side/100, min_spread_rs) on
    each side of the mark. Buying at ask and selling at bid therefore embeds
    a round-trip spread cost of ~2x the half-spread.

  * All prices are floored at 0.05 (exchange tick floor for options).
"""

from math import exp, log, sqrt

from scipy.stats import norm

PRICE_FLOOR = 0.05


def bs_price(
    spot: float,
    strike: float,
    T: float,
    r: float,
    sigma: float,
    kind: str = "CE",
) -> float:
    """Black-Scholes price of a European CE (call) or PE (put).

    spot/strike in price units, T in years, r and sigma as decimals
    (e.g. r=0.065, sigma=0.14 for India VIX 14). Result floored at 0.05.
    Degenerate inputs (T<=0, sigma<=0, non-positive spot/strike) fall back
    to floored intrinsic value.
    """
    kind = (kind or "CE").upper()
    if spot is None or strike is None or spot <= 0 or strike <= 0:
        return PRICE_FLOOR

    spot = float(spot)
    strike = float(strike)
    T = float(T) if T is not None else 0.0
    sigma = float(sigma) if sigma is not None else 0.0
    r = float(r or 0.0)

    if T <= 0 or sigma <= 0:
        intrinsic = (spot - strike) if kind == "CE" else (strike - spot)
        return max(intrinsic, PRICE_FLOOR)

    sqrt_t = sqrt(T)
    d1 = (log(spot / strike) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    if kind == "CE":
        price = spot * norm.cdf(d1) - strike * exp(-r * T) * norm.cdf(d2)
    else:
        price = strike * exp(-r * T) * norm.cdf(-d2) - spot * norm.cdf(-d1)

    return max(float(price), PRICE_FLOOR)


def synthetic_quote(
    mark: float,
    spread_pct_each_side: float,
    min_spread_rs: float,
) -> tuple[float, float]:
    """Return (bid, ask) around a synthetic mark.

    Half-spread per side = max(mark * spread_pct_each_side/100, min_spread_rs).
    The spread is MODELED (see module docstring) — it approximates typical
    liquid index-option spreads, it is not sourced from real order books.
    Bid is floored at 0.05; both sides rounded to 2 decimals (5 paise-ish).
    """
    mark = max(float(mark or 0.0), PRICE_FLOOR)
    half = max(mark * float(spread_pct_each_side or 0.0) / 100.0, float(min_spread_rs or 0.0))
    bid = max(mark - half, PRICE_FLOOR)
    ask = mark + half
    return round(bid, 2), round(ask, 2)
