"""
strategies_it_bear.py — Short-biased strategy evaluators for IT services.

All inherit from StrategyEvaluator (from trading.strategies).
Each evaluator outputs proposals in the same format as existing strategies.

Capital allocation (Rs.8L initial):
  Layer: core      40% = Rs.3.2L  — NIFTY IT futures short, long puts on weak IT
  Layer: tactical  30% = Rs.2.4L  — pre-earnings puts, bear spreads
  Layer: us        20% = Rs.1.6L  — US IT signals (ACN, CTSH, etc.)
  Layer: hedge     10% = Rs.0.8L  — NIFTY 50 hedge to protect against market rally
"""
import asyncio
import math
from datetime import datetime, date, timedelta

from trading.strategies import StrategyEvaluator
from trading.intelligence import (
    get_atm_strike, calculate_greeks, RISK_FREE_RATE,
)


# ---------------------------------------------------------------------------
# Strike step for IT stocks (Rs. 50 step for most Indian IT stocks)
# ---------------------------------------------------------------------------
_DEFAULT_STEP = 50
_IT_STRIKE_STEPS = {
    "TCS": 100, "INFY": 50, "HCLTECH": 50, "WIPRO": 50, "TECHM": 50,
    "LTIM": 50, "PERSISTENT": 100, "MPHASIS": 100, "COFORGE": 100, "LTTS": 100,
    "TATAELXSI": 100, "OFSS": 100, "NIFTYIT": 100,
}


def _round_it_strike(price: float, symbol: str) -> int:
    step = _IT_STRIKE_STEPS.get(symbol.upper(), _DEFAULT_STEP)
    return round(price / step) * step


def _find_it_strike(strikes: list[dict], target: int, opt_type: str) -> dict:
    """Find option data at target strike from synthetic chain."""
    for s in strikes:
        if s.get("strikePrice") == target:
            return s.get(opt_type, {})
    return {}


def _get_lot_size(symbol: str) -> int:
    """Return lot size for IT stocks."""
    from data.it_universe import get_by_symbol
    stock = get_by_symbol(symbol)
    if stock:
        return stock.get("lot_size", 100)
    return 100


def _get_layer_capital(layer: str) -> float:
    """Return allocated capital for each layer (out of Rs.8L initial)."""
    layers = {"core": 320000.0, "tactical": 240000.0, "us": 160000.0, "hedge": 80000.0}
    return layers.get(layer, 240000.0)


async def _get_it_indicators(symbol: str) -> dict:
    """
    Fetch technical indicators for an IT stock.
    Returns dict with: price, rsi, ema_20, ema_50, above_50dma,
    change_5d_pct, nifty_it_rs_5d.
    """
    indicators = {}
    try:
        import yfinance as yf
        from data.it_universe import get_by_symbol

        stock = get_by_symbol(symbol)
        yf_sym = stock.get("yf", symbol + ".NS") if stock else symbol + ".NS"

        hist = await asyncio.to_thread(
            lambda: yf.Ticker(yf_sym).history(period="90d")
        )

        if hist is None or hist.empty:
            return {}

        closes = hist["Close"].dropna()
        if len(closes) < 5:
            return {}

        price = float(closes.iloc[-1])
        indicators["price"] = price
        indicators["current_price"] = price

        # EMA 20
        if len(closes) >= 20:
            ema_20 = float(closes.ewm(span=20, adjust=False).mean().iloc[-1])
            indicators["ema_20"] = ema_20

        # EMA 50
        if len(closes) >= 50:
            ema_50 = float(closes.ewm(span=50, adjust=False).mean().iloc[-1])
            indicators["ema_50"] = ema_50
            indicators["above_50dma"] = price > ema_50
        else:
            indicators["above_50dma"] = True  # Assume not weak if not enough data

        # 5-day change
        if len(closes) >= 6:
            change_5d = (closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100
            indicators["change_5d_pct"] = round(float(change_5d), 2)

        # RSI
        if len(closes) >= 15:
            delta = closes.diff().dropna()
            gain = delta.clip(lower=0).rolling(14).mean().iloc[-1]
            loss = (-delta.clip(upper=0)).rolling(14).mean().iloc[-1]
            if loss and loss != 0:
                rs = gain / loss
                rsi = 100 - 100 / (1 + rs)
            else:
                rsi = 100.0 if gain > 0 else 50.0
            indicators["rsi"] = round(float(rsi), 2)
        else:
            indicators["rsi"] = 50.0

    except Exception as e:
        print(f"[strategies_it_bear] Indicator fetch failed for {symbol}: {e}")

    return indicators


async def _get_nifty_it_rs_5d() -> float:
    """Return NIFTY IT 5-day relative strength vs NIFTY50 (percentage difference)."""
    try:
        from analysis.it_sector_health import get_nifty_it_vs_nifty50
        rs_data = await get_nifty_it_vs_nifty50()
        # RS = (nifty_it_5d - nifty50_5d)
        return rs_data.get("nifty_it_pct_5d", 0.0) - rs_data.get("nifty50_pct_5d", 0.0)
    except Exception:
        return 0.0


async def _get_thesis_score() -> int:
    """Get current IT-bear thesis validation score (0-100)."""
    try:
        from analysis.it_sector_health import get_sector_health_summary
        summary = await get_sector_health_summary()
        return summary.get("thesis_score", 0)
    except Exception:
        return 0


def _nearest_expiry_str(weeks_out: int = 4) -> str:
    """Return expiry date string roughly N weeks out (nearest Thursday)."""
    today = date.today()
    # Find next Thursday
    days_to_thursday = (3 - today.weekday()) % 7
    if days_to_thursday == 0:
        days_to_thursday = 7
    next_thursday = today + timedelta(days=days_to_thursday)
    # Add extra weeks
    expiry = next_thursday + timedelta(weeks=max(0, weeks_out - 1))
    return expiry.strftime("%d-%b-%Y")


def _build_it_snapshot(symbol: str, spot: float, indicators: dict) -> dict:
    """Build a minimal snapshot dict compatible with _build_proposal."""
    return {
        "symbol": symbol,
        "spot": spot,
        "vix": indicators.get("vix", 0),
        "vix_regime": "unknown",
        "pcr": 0,
        "atm": {},
        "expected_move": 0,
        "max_pain": 0,
        "oi_levels": {"support": 0, "resistance": 0},
        "iv_percentile": indicators.get("iv_percentile", -1),
        "nearest_expiry": _nearest_expiry_str(4),
        "days_to_expiry": 28,
        "greeks": {},
    }


# ---------------------------------------------------------------------------
# Strategy evaluators
# ---------------------------------------------------------------------------

class LongPutBreakdownEvaluator(StrategyEvaluator):
    """
    Buy ATM put when technical breakdown confirmed.

    Conditions (3+ of 4 required):
    1. Price < 50-DMA
    2. RSI < 45 (weak momentum)
    3. NIFTY IT relative strength deteriorating (5-day RS < -2%)
    4. Stock down > 3% in last 5 days

    Structure: Buy 1-month ATM put.
    Risk: premium paid. Reward: unlimited (capped at 100% of strike - premium).
    Layer: core
    """

    @property
    def strategy_id(self) -> str:
        return "it_long_put_breakdown"

    @property
    def strategy_name(self) -> str:
        return "Long Put (Technical Breakdown)"

    async def evaluate(self, snapshot: dict, option_data: dict,
                       indicators: dict = None) -> dict | None:
        symbol = snapshot.get("symbol", "")
        if not symbol:
            return None

        # Fetch or use provided indicators
        if not indicators or "rsi" not in indicators:
            indicators = await _get_it_indicators(symbol)
        if not indicators:
            return None

        spot = float(indicators.get("price", snapshot.get("spot", 0)))
        if spot <= 0:
            return None

        rsi = float(indicators.get("rsi", 50))
        above_50dma = indicators.get("above_50dma", True)
        change_5d = float(indicators.get("change_5d_pct", 0))
        nifty_it_rs = await _get_nifty_it_rs_5d()

        conditions = []
        met = 0

        # 1. Price < 50-DMA
        c1 = not above_50dma
        conditions.append(("Price below 50-DMA", c1, f"above_50dma={above_50dma}"))
        if c1:
            met += 1

        # 2. RSI < 45
        c2 = rsi < 45
        conditions.append(("RSI < 45", c2, f"RSI={rsi:.1f}"))
        if c2:
            met += 1

        # 3. NIFTY IT RS < -2%
        c3 = nifty_it_rs < -2.0
        conditions.append(("NIFTY IT RS < -2%", c3, f"RS={nifty_it_rs:.2f}%"))
        if c3:
            met += 1

        # 4. Stock down > 3% in 5 days
        c4 = change_5d < -3.0
        conditions.append(("Stock down >3% in 5d", c4, f"5d chg={change_5d:.2f}%"))
        if c4:
            met += 1

        if met < 3:
            return None

        # Build proposal
        atm_strike = _round_it_strike(spot, symbol)
        lot_size = _get_lot_size(symbol)

        # Get put premium from synthetic chain or estimate
        put_ltp = 0.0
        put_iv = 18.0
        strikes = option_data.get("strikes", [])
        if strikes:
            pe_data = _find_it_strike(strikes, atm_strike, "PE")
            put_ltp = float(pe_data.get("ltp", 0))
            put_iv = float(pe_data.get("iv", 18.0))

        if put_ltp <= 0:
            # Black-Scholes estimate: ATM put with 28 DTE, 18% IV
            T = 28 / 365
            sigma = put_iv / 100
            try:
                d1 = (math.log(spot / atm_strike) + (RISK_FREE_RATE + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
                d2 = d1 - sigma * math.sqrt(T)
                from scipy.stats import norm
                put_ltp = atm_strike * math.exp(-RISK_FREE_RATE * T) * norm.cdf(-d2) - spot * norm.cdf(-d1)
                put_ltp = max(round(put_ltp, 2), 1.0)
            except Exception:
                put_ltp = spot * 0.03  # Fallback: 3% of spot

        max_loss = put_ltp * lot_size
        max_profit = (atm_strike - put_ltp) * lot_size  # If stock goes to zero (unrealistic max)
        margin = max_loss  # Debit trade — margin = premium paid
        confidence = round(met / 4 * 0.85, 2)

        legs = [
            {
                "action": "buy",
                "type": "PE",
                "strike": atm_strike,
                "qty": lot_size,
                "ltp": float(put_ltp),
                "iv": float(put_iv),
            }
        ]

        cond_text = " | ".join(f"{c[0]}: {'OK' if c[1] else 'FAIL'} ({c[2]})" for c in conditions)
        reasoning = (
            f"Long Put on {symbol} @ Rs.{spot:.0f}. "
            f"ATM Put {atm_strike} PE @ Rs.{put_ltp:.1f} (28 DTE). "
            f"Conditions met: {met}/4. {cond_text}. "
            f"Max risk: Rs.{max_loss:,.0f}. "
            f"Thesis: IT sector breakdown trade."
        )

        proposal = self._build_proposal(
            symbol, "bearish", legs,
            _build_it_snapshot(symbol, spot, indicators),
            confidence, reasoning, max_profit, max_loss, margin,
        )
        proposal["intelligence"]["layer"] = "core"
        proposal["intelligence"]["strategy_theme"] = "it_bear_thesis"
        return proposal


class PreEarningsLongPutEvaluator(StrategyEvaluator):
    """
    Buy puts 2-3 weeks before earnings on weak setups.

    Conditions (ALL required):
    1. Earnings within 7-21 days
    2. Last quarter missed estimates OR guidance cut (from earnings history)
    3. RSI < 50 OR price below 50-DMA
    4. IV percentile < 70 (don't buy expensive premium)

    Structure: Buy ATM put 1 month out (covers earnings).
    Exit: 50% profit OR -50% loss OR 1 day before earnings (if no spike).
    Layer: tactical
    """

    @property
    def strategy_id(self) -> str:
        return "it_pre_earnings_put"

    @property
    def strategy_name(self) -> str:
        return "Pre-Earnings Long Put"

    async def evaluate(self, snapshot: dict, option_data: dict,
                       indicators: dict = None) -> dict | None:
        symbol = snapshot.get("symbol", "")
        if not symbol:
            return None

        if not indicators or "rsi" not in indicators:
            indicators = await _get_it_indicators(symbol)
        if not indicators:
            return None

        spot = float(indicators.get("price", snapshot.get("spot", 0)))
        if spot <= 0:
            return None

        # Condition 1: earnings in 7-21 days
        from data.earnings_calendar import is_pre_earnings_window
        in_window, days_to_earnings = await is_pre_earnings_window(symbol, days_before=21)
        if not in_window or days_to_earnings < 7:
            return None  # Need at least 7 days out for meaningful pre-earnings trade

        # Condition 2: last quarter weakness — check from earnings history
        quarter_weak = False
        earnings_note = "Recent quarter data unavailable"
        try:
            from data.earnings_calendar import get_quarterly_history
            history = await get_quarterly_history(symbol, num_quarters=2)
            if len(history) >= 1:
                latest = history[0]
                yoy = latest.get("revenue_yoy_pct")
                if yoy is not None and yoy < -2.0:
                    quarter_weak = True
                    earnings_note = f"Revenue YoY: {yoy:.1f}% (declined)"
                elif yoy is not None and yoy < 5.0:
                    quarter_weak = True  # Below 5% YoY growth counts as weak for IT
                    earnings_note = f"Revenue YoY: {yoy:.1f}% (below IT sector average)"
                else:
                    earnings_note = f"Revenue YoY: {yoy:.1f}%" if yoy else "Unknown"
        except Exception:
            # If we can't get data, be conservative — don't trigger
            return None

        if not quarter_weak:
            return None

        # Condition 3: RSI < 50 OR below 50-DMA
        rsi = float(indicators.get("rsi", 50))
        above_50dma = indicators.get("above_50dma", True)
        c3 = rsi < 50 or not above_50dma
        if not c3:
            return None

        # Condition 4: IV percentile < 70
        iv_pct = float(snapshot.get("iv_percentile", -1))
        if iv_pct >= 70:
            return None  # Premium too expensive — skip

        # Build proposal
        atm_strike = _round_it_strike(spot, symbol)
        lot_size = _get_lot_size(symbol)

        # Get put from option chain or estimate
        put_ltp = 0.0
        put_iv = 20.0
        strikes = option_data.get("strikes", [])
        if strikes:
            pe_data = _find_it_strike(strikes, atm_strike, "PE")
            put_ltp = float(pe_data.get("ltp", 0))
            put_iv = float(pe_data.get("iv", 20.0))

        if put_ltp <= 0:
            # Estimate: ATM put 35 DTE (covers earnings), 20% IV
            T = 35 / 365
            sigma = 0.20
            try:
                d1 = (math.log(spot / atm_strike) + (RISK_FREE_RATE + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
                d2 = d1 - sigma * math.sqrt(T)
                from scipy.stats import norm
                put_ltp = atm_strike * math.exp(-RISK_FREE_RATE * T) * norm.cdf(-d2) - spot * norm.cdf(-d1)
                put_ltp = max(round(put_ltp, 2), 1.0)
            except Exception:
                put_ltp = spot * 0.035

        max_loss = put_ltp * lot_size
        max_profit = put_ltp * lot_size * 0.5  # Target: 50% of premium (2x the investment)
        margin = max_loss
        confidence = round(0.65 if (rsi < 45 and not above_50dma) else 0.55, 2)

        legs = [
            {
                "action": "buy",
                "type": "PE",
                "strike": atm_strike,
                "qty": lot_size,
                "ltp": float(put_ltp),
                "iv": float(put_iv),
            }
        ]

        reasoning = (
            f"Pre-Earnings Long Put on {symbol} @ Rs.{spot:.0f}. "
            f"Earnings in {days_to_earnings} days. {earnings_note}. "
            f"RSI: {rsi:.1f}, above 50-DMA: {above_50dma}. "
            f"ATM Put {atm_strike} PE @ Rs.{put_ltp:.1f}. "
            f"Exit: +50% profit OR -50% loss OR 1 day before earnings. "
            f"Max risk: Rs.{max_loss:,.0f}."
        )

        proposal = self._build_proposal(
            symbol, "bearish", legs,
            _build_it_snapshot(symbol, spot, indicators),
            confidence, reasoning, max_profit, max_loss, margin,
        )
        proposal["intelligence"]["layer"] = "tactical"
        proposal["intelligence"]["days_to_earnings"] = days_to_earnings
        proposal["intelligence"]["strategy_theme"] = "it_bear_thesis"
        return proposal


class BearPutSpreadEvaluator(StrategyEvaluator):
    """
    Buy ATM put + Sell OTM put (debit spread).
    Cheaper than naked put. Defined risk + defined reward.

    Conditions (3+ required):
    1. Sector RS negative (NIFTY IT vs NIFTY50, 5d)
    2. Price below 20-DMA
    3. RSI < 50

    Structure: Buy ATM put, sell put 5% OTM (lower).
    Width chosen based on volatility.
    Layer: core
    """

    @property
    def strategy_id(self) -> str:
        return "it_bear_put_spread"

    @property
    def strategy_name(self) -> str:
        return "Bear Put Spread"

    async def evaluate(self, snapshot: dict, option_data: dict,
                       indicators: dict = None) -> dict | None:
        symbol = snapshot.get("symbol", "")
        if not symbol:
            return None

        if not indicators or "rsi" not in indicators:
            indicators = await _get_it_indicators(symbol)
        if not indicators:
            return None

        spot = float(indicators.get("price", snapshot.get("spot", 0)))
        if spot <= 0:
            return None

        rsi = float(indicators.get("rsi", 50))
        ema_20 = float(indicators.get("ema_20", spot))
        nifty_it_rs = await _get_nifty_it_rs_5d()

        conditions = []
        met = 0

        # 1. Sector RS negative
        c1 = nifty_it_rs < 0
        conditions.append(("Sector RS negative", c1, f"NIFTY IT RS={nifty_it_rs:.2f}%"))
        if c1:
            met += 1

        # 2. Price below 20-DMA
        c2 = spot < ema_20
        conditions.append(("Price < 20-DMA", c2, f"spot={spot:.0f} vs EMA20={ema_20:.0f}"))
        if c2:
            met += 1

        # 3. RSI < 50
        c3 = rsi < 50
        conditions.append(("RSI < 50", c3, f"RSI={rsi:.1f}"))
        if c3:
            met += 1

        if met < 3:
            return None

        # Strike selection
        atm_strike = _round_it_strike(spot, symbol)
        # Sell put 5% OTM below spot
        otm_strike = _round_it_strike(spot * 0.95, symbol)
        spread_width = atm_strike - otm_strike

        lot_size = _get_lot_size(symbol)
        strikes = option_data.get("strikes", [])

        # Get ATM put
        atm_put_ltp = 0.0
        atm_put_iv = 18.0
        if strikes:
            pe_data = _find_it_strike(strikes, atm_strike, "PE")
            atm_put_ltp = float(pe_data.get("ltp", 0))
            atm_put_iv = float(pe_data.get("iv", 18.0))

        # Get OTM put
        otm_put_ltp = 0.0
        otm_put_iv = 20.0
        if strikes:
            pe_data_otm = _find_it_strike(strikes, otm_strike, "PE")
            otm_put_ltp = float(pe_data_otm.get("ltp", 0))
            otm_put_iv = float(pe_data_otm.get("iv", 20.0))

        # Estimate if not available
        if atm_put_ltp <= 0:
            T = 28 / 365
            sigma = 0.18
            try:
                d1 = (math.log(spot / atm_strike) + (RISK_FREE_RATE + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
                d2 = d1 - sigma * math.sqrt(T)
                from scipy.stats import norm
                atm_put_ltp = max(atm_strike * math.exp(-RISK_FREE_RATE * T) * norm.cdf(-d2) - spot * norm.cdf(-d1), 1.0)
            except Exception:
                atm_put_ltp = spot * 0.025

        if otm_put_ltp <= 0:
            T = 28 / 365
            sigma = 0.20
            try:
                d1 = (math.log(spot / otm_strike) + (RISK_FREE_RATE + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
                d2 = d1 - sigma * math.sqrt(T)
                from scipy.stats import norm
                otm_put_ltp = max(otm_strike * math.exp(-RISK_FREE_RATE * T) * norm.cdf(-d2) - spot * norm.cdf(-d1), 0.5)
            except Exception:
                otm_put_ltp = spot * 0.01

        net_debit = round(atm_put_ltp - otm_put_ltp, 2)
        if net_debit <= 0:
            return None

        max_profit = (spread_width - net_debit) * lot_size
        max_loss = net_debit * lot_size
        margin = max_loss
        confidence = round(met / 3 * 0.80, 2)

        legs = [
            {
                "action": "buy",
                "type": "PE",
                "strike": atm_strike,
                "qty": lot_size,
                "ltp": round(float(atm_put_ltp), 2),
                "iv": float(atm_put_iv),
            },
            {
                "action": "sell",
                "type": "PE",
                "strike": otm_strike,
                "qty": lot_size,
                "ltp": round(float(otm_put_ltp), 2),
                "iv": float(otm_put_iv),
            },
        ]

        cond_text = " | ".join(f"{c[0]}: {'OK' if c[1] else 'FAIL'} ({c[2]})" for c in conditions)
        reasoning = (
            f"Bear Put Spread on {symbol} @ Rs.{spot:.0f}. "
            f"Buy {atm_strike} PE @ Rs.{atm_put_ltp:.1f}, "
            f"Sell {otm_strike} PE @ Rs.{otm_put_ltp:.1f}. "
            f"Net debit: Rs.{net_debit:.1f}/unit (Rs.{max_loss:,.0f}/lot). "
            f"Max profit: Rs.{max_profit:,.0f} if stock falls {((1 - otm_strike/spot)*100):.1f}%. "
            f"Conditions: {cond_text}"
        )

        proposal = self._build_proposal(
            symbol, "bearish", legs,
            _build_it_snapshot(symbol, spot, indicators),
            confidence, reasoning, max_profit, max_loss, margin,
        )
        proposal["intelligence"]["layer"] = "core"
        proposal["intelligence"]["spread_width"] = spread_width
        proposal["intelligence"]["strategy_theme"] = "it_bear_thesis"
        return proposal


class BearCallSpreadEvaluator(StrategyEvaluator):
    """
    Sell ATM call + Buy OTM call (credit spread).
    Profit if stock stays below short strike. High probability of profit.

    Conditions (ALL required):
    1. IV percentile > 50 (premium worth selling)
    2. Stock NOT in earnings week (avoid event risk)
    3. Sector RS negative (chart-based resistance proxy)
    4. Sector RS negative (NIFTY IT underperforming)

    Structure: Sell ATM call, buy 5% OTM call.
    Target: 50% of credit. Stop: 2x credit received.
    Layer: tactical
    """

    @property
    def strategy_id(self) -> str:
        return "it_bear_call_spread"

    @property
    def strategy_name(self) -> str:
        return "Bear Call Spread (Credit)"

    async def evaluate(self, snapshot: dict, option_data: dict,
                       indicators: dict = None) -> dict | None:
        symbol = snapshot.get("symbol", "")
        if not symbol:
            return None

        if not indicators or "rsi" not in indicators:
            indicators = await _get_it_indicators(symbol)
        if not indicators:
            return None

        spot = float(indicators.get("price", snapshot.get("spot", 0)))
        if spot <= 0:
            return None

        # Condition 1: IV percentile > 50
        iv_pct = float(snapshot.get("iv_percentile", 50))
        # If iv_pct unavailable (-1), use default of 50 — allow the trade
        if iv_pct != -1 and iv_pct < 50:
            return None

        # Condition 2: Not in earnings week (7 days)
        from data.earnings_calendar import is_pre_earnings_window
        _, days_to_earnings = await is_pre_earnings_window(symbol, days_before=7)
        if 0 < days_to_earnings <= 7:
            return None  # Too close to earnings — event risk

        # Condition 3 + 4: Sector RS negative
        nifty_it_rs = await _get_nifty_it_rs_5d()
        if nifty_it_rs >= 0:
            return None  # Sector not weak enough

        rsi = float(indicators.get("rsi", 50))
        above_50dma = indicators.get("above_50dma", True)

        # Additional check: stock should not be in a strong uptrend
        if rsi > 60 and above_50dma:
            return None  # Stock is in uptrend — too risky for short call

        # Strike selection
        atm_strike = _round_it_strike(spot, symbol)
        otm_strike = _round_it_strike(spot * 1.05, symbol)  # 5% OTM buy wing
        spread_width = otm_strike - atm_strike

        lot_size = _get_lot_size(symbol)
        strikes = option_data.get("strikes", [])

        # Get ATM call premium
        atm_call_ltp = 0.0
        atm_call_iv = 18.0
        if strikes:
            ce_data = _find_it_strike(strikes, atm_strike, "CE")
            atm_call_ltp = float(ce_data.get("ltp", 0))
            atm_call_iv = float(ce_data.get("iv", 18.0))

        # Get OTM call premium
        otm_call_ltp = 0.0
        otm_call_iv = 16.0
        if strikes:
            ce_data_otm = _find_it_strike(strikes, otm_strike, "CE")
            otm_call_ltp = float(ce_data_otm.get("ltp", 0))
            otm_call_iv = float(ce_data_otm.get("iv", 16.0))

        # Estimate if not available
        if atm_call_ltp <= 0:
            T = 28 / 365
            sigma = atm_call_iv / 100 if atm_call_iv > 0 else 0.18
            try:
                d1 = (math.log(spot / atm_strike) + (RISK_FREE_RATE + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
                d2 = d1 - sigma * math.sqrt(T)
                from scipy.stats import norm
                atm_call_ltp = max(spot * norm.cdf(d1) - atm_strike * math.exp(-RISK_FREE_RATE * T) * norm.cdf(d2), 1.0)
            except Exception:
                atm_call_ltp = spot * 0.025

        if otm_call_ltp <= 0:
            T = 28 / 365
            sigma = otm_call_iv / 100 if otm_call_iv > 0 else 0.16
            try:
                d1 = (math.log(spot / otm_strike) + (RISK_FREE_RATE + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
                d2 = d1 - sigma * math.sqrt(T)
                from scipy.stats import norm
                otm_call_ltp = max(spot * norm.cdf(d1) - otm_strike * math.exp(-RISK_FREE_RATE * T) * norm.cdf(d2), 0.5)
            except Exception:
                otm_call_ltp = spot * 0.008

        net_credit = round(atm_call_ltp - otm_call_ltp, 2)
        if net_credit <= 0:
            return None

        max_profit = net_credit * lot_size  # Keep full credit
        max_loss = (spread_width - net_credit) * lot_size  # If stock rallies through both strikes
        margin = max_loss * 1.2  # Approximate SPAN margin
        confidence = round(0.65 if nifty_it_rs < -3.0 else 0.55, 2)

        legs = [
            {
                "action": "sell",
                "type": "CE",
                "strike": atm_strike,
                "qty": lot_size,
                "ltp": round(float(atm_call_ltp), 2),
                "iv": float(atm_call_iv),
            },
            {
                "action": "buy",
                "type": "CE",
                "strike": otm_strike,
                "qty": lot_size,
                "ltp": round(float(otm_call_ltp), 2),
                "iv": float(otm_call_iv),
            },
        ]

        reasoning = (
            f"Bear Call Spread on {symbol} @ Rs.{spot:.0f}. "
            f"Sell {atm_strike} CE @ Rs.{atm_call_ltp:.1f}, "
            f"Buy {otm_strike} CE @ Rs.{otm_call_ltp:.1f}. "
            f"Net credit: Rs.{net_credit:.1f}/unit (Rs.{max_profit:,.0f}/lot). "
            f"Target: 50% profit (Rs.{max_profit/2:,.0f}). "
            f"Stop: 2x credit (Rs.{max_profit*2:,.0f} loss). "
            f"NIFTY IT RS={nifty_it_rs:.2f}%, RSI={rsi:.1f}, days to earnings: {days_to_earnings}."
        )

        proposal = self._build_proposal(
            symbol, "bearish", legs,
            _build_it_snapshot(symbol, spot, indicators),
            confidence, reasoning, max_profit, max_loss, margin,
        )
        proposal["intelligence"]["layer"] = "tactical"
        proposal["intelligence"]["net_credit"] = float(net_credit)
        proposal["intelligence"]["strategy_theme"] = "it_bear_thesis"
        return proposal


class NiftyITFuturesShortEvaluator(StrategyEvaluator):
    """
    Short NIFTY IT futures — sector-level bet, highest conviction only.

    Conditions (ALL required):
    1. NIFTY IT below 50-DMA AND below 200-DMA (proxy: price down >10% in 90d and >5% in 20d)
    2. Sector RS very negative (< -5% vs NIFTY50 in 20d)
    3. Sector health score > 70 (thesis strongly validated)

    Structure: Short 1-2 lots NIFTY IT futures (lot size 25).
    Stop: above recent swing high (~5% above entry).
    Layer: core
    """

    @property
    def strategy_id(self) -> str:
        return "it_nifty_futures_short"

    @property
    def strategy_name(self) -> str:
        return "Short NIFTY IT Futures"

    async def evaluate(self, snapshot: dict, option_data: dict,
                       indicators: dict = None) -> dict | None:
        symbol = snapshot.get("symbol", "NIFTYIT")

        # This evaluator is sector-level — only runs on NIFTYIT/CNXIT
        if symbol not in ("NIFTYIT", "NIFTY IT", "^CNXIT"):
            # Allow running on the index specifically
            pass  # Will still fetch index data below

        # Always fetch fresh NIFTY IT indicators
        nifty_it_indicators = {}
        try:
            import yfinance as yf
            hist = await asyncio.to_thread(
                lambda: yf.Ticker("^CNXIT").history(period="250d")
            )
            if hist is not None and not hist.empty:
                closes = hist["Close"].dropna()
                price = float(closes.iloc[-1])
                nifty_it_indicators["price"] = price

                # Check 50-DMA
                if len(closes) >= 50:
                    dma_50 = float(closes.rolling(50).mean().iloc[-1])
                    nifty_it_indicators["below_50dma"] = price < dma_50
                    nifty_it_indicators["dma_50"] = dma_50
                else:
                    nifty_it_indicators["below_50dma"] = False

                # Check 200-DMA
                if len(closes) >= 200:
                    dma_200 = float(closes.rolling(200).mean().iloc[-1])
                    nifty_it_indicators["below_200dma"] = price < dma_200
                    nifty_it_indicators["dma_200"] = dma_200
                else:
                    nifty_it_indicators["below_200dma"] = False
        except Exception as e:
            print(f"[NiftyITFuturesShort] Failed to fetch NIFTY IT data: {e}")
            return None

        # Condition 1: Below both 50-DMA and 200-DMA
        c1 = nifty_it_indicators.get("below_50dma", False) and nifty_it_indicators.get("below_200dma", False)
        if not c1:
            return None

        # Condition 2: Sector RS very negative (< -5% vs NIFTY50 in 20d)
        try:
            from analysis.it_sector_health import get_nifty_it_vs_nifty50
            rs_data = await get_nifty_it_vs_nifty50()
            rs_20d = rs_data.get("relative_strength", 0.0)
        except Exception:
            rs_20d = 0.0

        if rs_20d >= -5.0:
            return None  # Not weak enough for futures short

        # Condition 3: Thesis score > 70
        thesis_score = await _get_thesis_score()
        if thesis_score < 70:
            return None  # Thesis not strongly enough validated

        # Build proposal
        spot = float(nifty_it_indicators.get("price", 30000))
        lot_size = 25  # NIFTY IT futures lot size
        num_lots = 1 if thesis_score < 80 else 2  # 2 lots at highest conviction

        # Futures contract: no premium, P&L = lot_size * price_move
        # Stop loss: 5% above current level (swing high)
        stop_loss_pct = 0.05
        stop_level = round(spot * (1 + stop_loss_pct), 0)
        max_loss = spot * stop_loss_pct * lot_size * num_lots

        # Target: 10% decline
        target_pct = 0.10
        target_level = round(spot * (1 - target_pct), 0)
        max_profit = spot * target_pct * lot_size * num_lots

        # Margin: NIFTY IT futures margin approx 12% of contract value
        margin = spot * lot_size * num_lots * 0.12
        confidence = round(min(thesis_score / 100 * 0.9, 0.85), 2)

        legs = [
            {
                "action": "sell",
                "type": "FUT",
                "strike": int(spot),  # Futures entry price used as strike
                "qty": lot_size * num_lots,
                "ltp": float(spot),
                "iv": 0.0,  # No IV for futures
            }
        ]

        reasoning = (
            f"Short NIFTY IT Futures @ {spot:.0f}. "
            f"{num_lots} lot(s) of {lot_size}. "
            f"Conditions: "
            f"Below 50-DMA ({nifty_it_indicators.get('dma_50', 0):.0f}) AND "
            f"200-DMA ({nifty_it_indicators.get('dma_200', 0):.0f}). "
            f"Sector RS (20d): {rs_20d:.2f}% vs NIFTY50. "
            f"Thesis score: {thesis_score}/100. "
            f"Stop: {stop_level:.0f} (+5%). Target: {target_level:.0f} (-10%). "
            f"Max risk: Rs.{max_loss:,.0f}. Max profit: Rs.{max_profit:,.0f}."
        )

        it_snapshot = _build_it_snapshot("NIFTYIT", spot, {})
        it_snapshot["vix_regime"] = rs_data.get("regime", "unknown")

        proposal = self._build_proposal(
            "NIFTYIT", "bearish", legs,
            it_snapshot,
            confidence, reasoning, max_profit, max_loss, margin,
        )
        proposal["intelligence"]["layer"] = "core"
        proposal["intelligence"]["thesis_score"] = thesis_score
        proposal["intelligence"]["sector_rs_20d"] = rs_20d
        proposal["intelligence"]["stop_level"] = float(stop_level)
        proposal["intelligence"]["target_level"] = float(target_level)
        proposal["intelligence"]["strategy_theme"] = "it_bear_thesis"
        return proposal


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_IT_BEAR_EVALUATORS = [
    LongPutBreakdownEvaluator(),
    PreEarningsLongPutEvaluator(),
    BearPutSpreadEvaluator(),
    BearCallSpreadEvaluator(),
    NiftyITFuturesShortEvaluator(),
]


def get_it_bear_evaluator(strategy_id: str) -> StrategyEvaluator | None:
    """Get IT-bear evaluator by strategy ID."""
    for e in ALL_IT_BEAR_EVALUATORS:
        if e.strategy_id == strategy_id:
            return e
    return None
