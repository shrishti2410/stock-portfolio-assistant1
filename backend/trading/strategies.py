"""
strategies.py — Strategy evaluators for the 3 core NIFTY/BANKNIFTY strategies.

Each evaluator:
1. Checks entry conditions against live market data
2. If conditions met, returns a TradeProposal with specific strikes and legs
3. If not, returns None (no signal)
"""
import json
from abc import ABC, abstractmethod
from datetime import datetime

from trading.intelligence import (
    get_atm_strike, get_atm_data, calculate_expected_move,
    calculate_greeks, days_to_expiry, classify_vix, calculate_max_pain,
    get_oi_levels, RISK_FREE_RATE,
)


def _round_strike(price: float, step: int = 50) -> int:
    """Round price to nearest strike step."""
    return round(price / step) * step


def _find_strike_data(strikes: list[dict], target_strike: int, option_type: str) -> dict:
    """Find specific strike's CE or PE data from option chain."""
    for s in strikes:
        if s.get("strikePrice") == target_strike:
            return s.get(option_type, {})
    return {}


class StrategyEvaluator(ABC):
    """Base class for strategy evaluators."""

    @property
    @abstractmethod
    def strategy_id(self) -> str: ...

    @property
    @abstractmethod
    def strategy_name(self) -> str: ...

    @abstractmethod
    async def evaluate(self, snapshot: dict, option_data: dict,
                       indicators: dict = None) -> dict | None:
        """
        Evaluate strategy conditions against live data.

        Args:
            snapshot: Market intelligence snapshot (from get_market_snapshot)
            option_data: Raw option chain data
            indicators: Technical indicators from screener (optional)

        Returns:
            Trade proposal dict if signal found, None otherwise.
        """

    def _build_proposal(self, symbol: str, direction: str, legs: list,
                        snapshot: dict, confidence: float, reasoning: str,
                        max_profit: float, max_loss: float, margin: float) -> dict:
        """Build a standardized trade proposal dict. All numeric values are Python floats (not numpy)."""
        # Cast all numeric values to Python types to avoid numpy/JSON serialization issues
        clean_legs = []
        for leg in legs:
            clean_legs.append({
                "action": str(leg.get("action", "")),
                "type": str(leg.get("type", "")),
                "strike": int(leg.get("strike", 0)),
                "qty": int(leg.get("qty", 0)),
                "ltp": float(leg.get("ltp", 0)),
                "iv": float(leg.get("iv", 0)),
            })

        clean_greeks = {}
        for k, v in (snapshot.get("greeks") or {}).items():
            if isinstance(v, dict):
                clean_greeks[k] = {kk: float(vv) for kk, vv in v.items()}
            else:
                clean_greeks[k] = float(v)

        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "symbol": symbol,
            "direction": direction,
            "legs": clean_legs,
            "greeks": clean_greeks,
            "intelligence": {
                "vix": float(snapshot.get("vix", 0)),
                "vix_regime": str(snapshot.get("vix_regime", "unknown")),
                "pcr": float(snapshot.get("pcr", 0)),
                "iv_percentile": float(snapshot.get("iv_percentile", -1)),
                "expected_move": float(snapshot.get("expected_move", 0)),
                "max_pain": int(snapshot.get("max_pain", 0)),
                "oi_support": int(snapshot.get("oi_levels", {}).get("support", 0)),
                "oi_resistance": int(snapshot.get("oi_levels", {}).get("resistance", 0)),
                "nearest_expiry": str(snapshot.get("nearest_expiry", "")),
                "days_to_expiry": float(snapshot.get("days_to_expiry", 0)),
            },
            "max_profit": float(round(max_profit, 2)),
            "max_loss": float(round(-abs(max_loss), 2)),
            "margin_needed": float(round(margin, 2)),
            "confidence": float(round(confidence, 2)),
            "reasoning": reasoning,
            "created_at": datetime.now().isoformat(),
        }


class IronCondorEvaluator(StrategyEvaluator):
    """
    Iron Condor: Sell OTM CE + OTM PE, buy further OTM wings.
    Best for: Range-bound market, low VIX.
    """

    @property
    def strategy_id(self): return "iron_condor"

    @property
    def strategy_name(self): return "Iron Condor"

    async def evaluate(self, snapshot, option_data, indicators=None):
        spot = snapshot.get("spot", 0)
        vix = snapshot.get("vix", 0)
        pcr = snapshot.get("pcr", 0)
        expected_move = snapshot.get("expected_move", 0)
        dte = snapshot.get("days_to_expiry", 0)
        strikes = option_data.get("strikes", [])

        if spot <= 0 or not strikes:
            return None

        # Entry conditions (ALL must be met)
        conditions = []

        # 1. VIX < 16 (low to normal)
        vix_ok = 0 < vix < 16 if vix > 0 else True  # Pass if VIX unavailable
        conditions.append(("VIX < 16", vix_ok, f"VIX = {vix}"))

        # 2. PCR between 0.8 and 1.2
        pcr_ok = 0.8 <= pcr <= 1.2 if pcr > 0 else False
        conditions.append(("PCR 0.8-1.2", pcr_ok, f"PCR = {pcr}"))

        # 3. Days to expiry 2-5
        dte_ok = 2 <= dte <= 5
        conditions.append(("DTE 2-5", dte_ok, f"DTE = {dte}"))

        # Check if enough conditions met
        met_count = sum(1 for _, ok, _ in conditions if ok)
        if met_count < 2:  # Need at least 2 of 3
            return None

        # Strike selection
        short_offset = max(int(expected_move * 1.1), 150) if expected_move > 0 else 200
        wing_offset = 200  # 200 pts further for protection

        short_ce_strike = _round_strike(spot + short_offset)
        long_ce_strike = _round_strike(short_ce_strike + wing_offset)
        short_pe_strike = _round_strike(spot - short_offset)
        long_pe_strike = _round_strike(short_pe_strike - wing_offset)

        # Get LTPs
        short_ce = _find_strike_data(strikes, short_ce_strike, "CE")
        long_ce = _find_strike_data(strikes, long_ce_strike, "CE")
        short_pe = _find_strike_data(strikes, short_pe_strike, "PE")
        long_pe = _find_strike_data(strikes, long_pe_strike, "PE")

        premium_collected = (short_ce.get("ltp", 0) + short_pe.get("ltp", 0) -
                             long_ce.get("ltp", 0) - long_pe.get("ltp", 0))

        if premium_collected <= 0:
            return None

        # Determine lot size based on symbol
        symbol = snapshot.get("symbol", "NIFTY")
        lot_size = 75 if "NIFTY" in symbol and "BANK" not in symbol else 35

        max_profit = premium_collected * lot_size
        max_loss = (wing_offset - premium_collected) * lot_size
        margin = max_loss * 1.5  # Approximate margin

        confidence = min(met_count / 3, 0.9)

        legs = [
            {"action": "sell", "type": "CE", "strike": short_ce_strike,
             "qty": lot_size, "ltp": short_ce.get("ltp", 0), "iv": short_ce.get("iv", 0)},
            {"action": "buy", "type": "CE", "strike": long_ce_strike,
             "qty": lot_size, "ltp": long_ce.get("ltp", 0), "iv": long_ce.get("iv", 0)},
            {"action": "sell", "type": "PE", "strike": short_pe_strike,
             "qty": lot_size, "ltp": short_pe.get("ltp", 0), "iv": short_pe.get("iv", 0)},
            {"action": "buy", "type": "PE", "strike": long_pe_strike,
             "qty": lot_size, "ltp": long_pe.get("ltp", 0), "iv": long_pe.get("iv", 0)},
        ]

        cond_text = " | ".join(
            f"{c[0]}: {'OK' if c[1] else 'FAIL'} ({c[2]})" for c in conditions
        )
        reasoning = (
            f"Iron Condor on {symbol} @ {spot}. "
            f"Short strikes: {short_pe_strike} PE / {short_ce_strike} CE (+-{short_offset} from spot). "
            f"Wings: {long_pe_strike} PE / {long_ce_strike} CE. "
            f"Net premium: Rs.{premium_collected:.1f}/unit (Rs.{max_profit:,.0f}/lot). "
            f"Expected move: +-{expected_move:.0f}. Conditions: {cond_text}"
        )

        return self._build_proposal(symbol, "neutral", legs, snapshot,
                                    confidence, reasoning, max_profit, max_loss, margin)


class StraddleAdjustEvaluator(StrategyEvaluator):
    """
    Short Straddle with Adjustment: Sell ATM CE + PE, adjust losing side if breached.
    Best for: Range-bound, elevated VIX (premium selling).
    """

    @property
    def strategy_id(self): return "straddle_adjust"

    @property
    def strategy_name(self): return "Straddle Sell + Adjust"

    async def evaluate(self, snapshot, option_data, indicators=None):
        spot = snapshot.get("spot", 0)
        vix = snapshot.get("vix", 0)
        pcr = snapshot.get("pcr", 0)
        iv_pct = snapshot.get("iv_percentile", -1)
        expected_move = snapshot.get("expected_move", 0)
        dte = snapshot.get("days_to_expiry", 0)
        strikes = option_data.get("strikes", [])
        atm = snapshot.get("atm", {})

        if spot <= 0 or not strikes:
            return None

        conditions = []

        # 1. VIX > 14 (elevated premium)
        vix_ok = vix > 14 if vix > 0 else False
        conditions.append(("VIX > 14", vix_ok, f"VIX = {vix}"))

        # 2. IV Percentile > 50% (if available)
        iv_ok = iv_pct > 50 if iv_pct >= 0 else True
        conditions.append(("IV Pct > 50%", iv_ok, f"IV% = {iv_pct}"))

        # 3. DTE 3-6 (not too close to expiry for straddle)
        dte_ok = 3 <= dte <= 6
        conditions.append(("DTE 3-6", dte_ok, f"DTE = {dte}"))

        met_count = sum(1 for _, ok, _ in conditions if ok)
        if met_count < 2:
            return None

        # ATM strike
        atm_strike = get_atm_strike(spot)
        atm_ce = _find_strike_data(strikes, atm_strike, "CE")
        atm_pe = _find_strike_data(strikes, atm_strike, "PE")

        ce_ltp = atm_ce.get("ltp", 0)
        pe_ltp = atm_pe.get("ltp", 0)
        premium = ce_ltp + pe_ltp

        if premium <= 0:
            return None

        symbol = snapshot.get("symbol", "NIFTY")
        lot_size = 75 if "NIFTY" in symbol and "BANK" not in symbol else 35

        max_profit = premium * 0.4 * lot_size  # Target 40% of premium
        max_loss = premium * lot_size  # Max loss = premium collected (with SL)
        margin = 200000  # Approximate straddle margin

        confidence = min(met_count / 3, 0.85)

        legs = [
            {"action": "sell", "type": "CE", "strike": atm_strike,
             "qty": lot_size, "ltp": ce_ltp, "iv": atm_ce.get("iv", 0)},
            {"action": "sell", "type": "PE", "strike": atm_strike,
             "qty": lot_size, "ltp": pe_ltp, "iv": atm_pe.get("iv", 0)},
        ]

        cond_text = " | ".join(
            f"{c[0]}: {'OK' if c[1] else 'FAIL'} ({c[2]})" for c in conditions
        )
        reasoning = (
            f"Short Straddle on {symbol} @ {spot}. Sell {atm_strike} CE (Rs.{ce_ltp}) + PE (Rs.{pe_ltp}). "
            f"Total premium: Rs.{premium:.1f}/unit (Rs.{premium * lot_size:,.0f}/lot). "
            f"Target: 40% (Rs.{max_profit:,.0f}). "
            f"Adjustment: Shift losing side if spot moves >{expected_move * 0.6:.0f} pts. "
            f"Max 2 adjustments. Conditions: {cond_text}"
        )

        return self._build_proposal(symbol, "neutral", legs, snapshot,
                                    confidence, reasoning, max_profit, max_loss, margin)


class DirectionalSpreadEvaluator(StrategyEvaluator):
    """
    Bull Call / Bear Put Spread based on strong technical signals.
    Best for: Clear directional bias confirmed by screener.
    """

    @property
    def strategy_id(self): return "directional_spread"

    @property
    def strategy_name(self): return "Directional Spread"

    async def evaluate(self, snapshot, option_data, indicators=None):
        spot = snapshot.get("spot", 0)
        pcr = snapshot.get("pcr", 0)
        strikes = option_data.get("strikes", [])

        if spot <= 0 or not strikes or not indicators:
            return None

        # Check technical signals
        rsi = indicators.get("rsi", 50)
        overall_score = indicators.get("overall_score", 0)
        ema_20 = indicators.get("ema_20", spot)
        ema_50 = indicators.get("ema_50", spot)
        price = indicators.get("current_price", spot)

        conditions = []

        # Determine direction
        bullish_signals = 0
        bearish_signals = 0

        # 1. Screener score
        if overall_score > 0.4:
            bullish_signals += 1
            conditions.append(("Score > 0.4", True, f"Score = {overall_score:.2f}"))
        elif overall_score < -0.4:
            bearish_signals += 1
            conditions.append(("Score < -0.4", True, f"Score = {overall_score:.2f}"))
        else:
            conditions.append(("Strong score", False, f"Score = {overall_score:.2f}"))

        # 2. RSI
        if rsi and rsi > 60:
            bullish_signals += 1
            conditions.append(("RSI > 60", True, f"RSI = {rsi:.1f}"))
        elif rsi and rsi < 40:
            bearish_signals += 1
            conditions.append(("RSI < 40", True, f"RSI = {rsi:.1f}"))
        else:
            conditions.append(("RSI extreme", False, f"RSI = {rsi:.1f}" if rsi else "N/A"))

        # 3. EMA alignment
        if price and ema_20 and ema_50:
            if price > ema_20 > ema_50:
                bullish_signals += 1
                conditions.append(("EMA aligned bull", True, "P > EMA20 > EMA50"))
            elif price < ema_20 < ema_50:
                bearish_signals += 1
                conditions.append(("EMA aligned bear", True, "P < EMA20 < EMA50"))
            else:
                conditions.append(("EMA alignment", False, "No clear alignment"))

        # 4. PCR extreme (contrarian)
        if pcr > 1.2:
            bullish_signals += 1
            conditions.append(("PCR > 1.2 (contrarian bull)", True, f"PCR = {pcr}"))
        elif pcr < 0.8 and pcr > 0:
            bearish_signals += 1
            conditions.append(("PCR < 0.8 (contrarian bear)", True, f"PCR = {pcr}"))
        else:
            conditions.append(("PCR extreme", False, f"PCR = {pcr}"))

        # Need at least 3 signals in same direction
        if bullish_signals >= 3:
            direction = "bullish"
        elif bearish_signals >= 3:
            direction = "bearish"
        else:
            return None  # No clear signal

        # Build spread
        symbol = snapshot.get("symbol", "NIFTY")
        lot_size = 75 if "NIFTY" in symbol and "BANK" not in symbol else 35
        spread_width = 200

        if direction == "bullish":
            buy_strike = get_atm_strike(spot)
            sell_strike = _round_strike(buy_strike + spread_width)
            buy_data = _find_strike_data(strikes, buy_strike, "CE")
            sell_data = _find_strike_data(strikes, sell_strike, "CE")

            debit = buy_data.get("ltp", 0) - sell_data.get("ltp", 0)
            if debit <= 0:
                return None

            legs = [
                {"action": "buy", "type": "CE", "strike": buy_strike,
                 "qty": lot_size, "ltp": buy_data.get("ltp", 0), "iv": buy_data.get("iv", 0)},
                {"action": "sell", "type": "CE", "strike": sell_strike,
                 "qty": lot_size, "ltp": sell_data.get("ltp", 0), "iv": sell_data.get("iv", 0)},
            ]

            max_profit = (spread_width - debit) * lot_size
            max_loss = debit * lot_size

        else:  # bearish
            buy_strike = get_atm_strike(spot)
            sell_strike = _round_strike(buy_strike - spread_width)
            buy_data = _find_strike_data(strikes, buy_strike, "PE")
            sell_data = _find_strike_data(strikes, sell_strike, "PE")

            debit = buy_data.get("ltp", 0) - sell_data.get("ltp", 0)
            if debit <= 0:
                return None

            legs = [
                {"action": "buy", "type": "PE", "strike": buy_strike,
                 "qty": lot_size, "ltp": buy_data.get("ltp", 0), "iv": buy_data.get("iv", 0)},
                {"action": "sell", "type": "PE", "strike": sell_strike,
                 "qty": lot_size, "ltp": sell_data.get("ltp", 0), "iv": sell_data.get("iv", 0)},
            ]

            max_profit = (spread_width - debit) * lot_size
            max_loss = debit * lot_size

        margin = max_loss * 1.2
        confidence = max(bullish_signals, bearish_signals) / 4

        cond_text = " | ".join(
            f"{c[0]}: {'OK' if c[1] else 'FAIL'} ({c[2]})" for c in conditions
        )
        spread_type = "Bull Call" if direction == "bullish" else "Bear Put"
        reasoning = (
            f"{spread_type} Spread on {symbol} @ {spot}. "
            f"Direction: {direction.upper()} ({max(bullish_signals, bearish_signals)}/4 signals). "
            f"Debit: Rs.{debit:.1f}/unit (Rs.{max_loss:,.0f}/lot). "
            f"Max profit: Rs.{max_profit:,.0f}/lot. "
            f"Conditions: {cond_text}"
        )

        return self._build_proposal(symbol, direction, legs, snapshot,
                                    confidence, reasoning, max_profit, max_loss, margin)


# All evaluators
ALL_EVALUATORS = [
    IronCondorEvaluator(),
    StraddleAdjustEvaluator(),
    DirectionalSpreadEvaluator(),
]


def get_evaluator(strategy_id: str) -> StrategyEvaluator | None:
    """Get evaluator by strategy ID."""
    for e in ALL_EVALUATORS:
        if e.strategy_id == strategy_id:
            return e
    return None
