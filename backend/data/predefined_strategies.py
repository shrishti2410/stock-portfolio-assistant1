"""
predefined_strategies.py — 13 pre-defined F&O trading strategies for NIFTY/BANKNIFTY

Each strategy has entry/exit rules, risk categorization, and can be checked
against live option chain + indicator data.

Public API:
    get_all_strategies() -> list[dict]
    get_strategy(id) -> dict
    check_strategy(id, symbol) -> dict   (evaluate against live data)
"""

STRATEGIES = [
    {
        "id": "iron_condor",
        "name": "Iron Condor",
        "category": "conservative",
        "risk": "low",
        "reward": "low-medium",
        "win_rate": "65-70%",
        "capital": "₹1-1.5L",
        "best_for": "Sideways / Range-bound markets",
        "description": "Sell OTM Call + OTM Put, buy further OTM hedges on both sides. Profits from time decay when market stays in a range.",
        "legs": [
            {"action": "sell", "type": "CE", "strike_offset": 300, "label": "Sell OTM Call"},
            {"action": "buy", "type": "CE", "strike_offset": 500, "label": "Buy Far OTM Call (hedge)"},
            {"action": "sell", "type": "PE", "strike_offset": -300, "label": "Sell OTM Put"},
            {"action": "buy", "type": "PE", "strike_offset": -500, "label": "Buy Far OTM Put (hedge)"},
        ],
        "entry_rules": [
            {"indicator": "VIX", "condition": "< 15", "description": "India VIX below 15 (low volatility)"},
            {"indicator": "PCR", "condition": "0.9 - 1.1", "description": "Put-Call Ratio neutral"},
            {"indicator": "TIME", "condition": "After 9:30 AM", "description": "Wait for initial volatility to settle"},
        ],
        "exit_rules": [
            {"type": "profit", "value": "65% of premium collected"},
            {"type": "stop_loss", "value": "Underlying breaches short strike"},
            {"type": "time", "value": "Close by 2:30 PM on expiry day"},
        ],
        "max_profit": "Net premium collected (₹3,000-6,000/lot)",
        "max_loss": "Spread width minus premium (₹7,000-10,000/lot)",
    },
    {
        "id": "bull_call_spread",
        "name": "Bull Call Spread",
        "category": "moderate",
        "risk": "medium",
        "reward": "medium",
        "win_rate": "50-55%",
        "capital": "₹6,500-10,000",
        "best_for": "Moderately bullish / Trending up",
        "description": "Buy ATM Call + Sell OTM Call. Limited risk bullish bet that profits when market moves up within the spread range.",
        "legs": [
            {"action": "buy", "type": "CE", "strike_offset": 0, "label": "Buy ATM Call"},
            {"action": "sell", "type": "CE", "strike_offset": 200, "label": "Sell OTM Call"},
        ],
        "entry_rules": [
            {"indicator": "EMA", "condition": "Price > 20 EMA (15-min)", "description": "Price above 20 EMA on 15-min chart"},
            {"indicator": "RSI", "condition": "> 55 (5-min)", "description": "RSI above 55 on 5-min chart"},
            {"indicator": "VWAP", "condition": "Price > VWAP", "description": "Price above VWAP — bullish bias"},
        ],
        "exit_rules": [
            {"type": "profit", "value": "70% of max spread width"},
            {"type": "stop_loss", "value": "50% of net premium paid"},
            {"type": "time", "value": "Exit by 2:00 PM if target not hit"},
        ],
        "max_profit": "(Spread width - debit) × lot size ≈ ₹6,500/lot",
        "max_loss": "Net premium paid ≈ ₹6,500/lot",
    },
    {
        "id": "bear_put_spread",
        "name": "Bear Put Spread",
        "category": "moderate",
        "risk": "medium",
        "reward": "medium",
        "win_rate": "50-55%",
        "capital": "₹6,500-10,000",
        "best_for": "Moderately bearish / Trending down",
        "description": "Buy ATM Put + Sell OTM Put. Limited risk bearish bet that profits when market falls within the spread range.",
        "legs": [
            {"action": "buy", "type": "PE", "strike_offset": 0, "label": "Buy ATM Put"},
            {"action": "sell", "type": "PE", "strike_offset": -200, "label": "Sell OTM Put"},
        ],
        "entry_rules": [
            {"indicator": "EMA", "condition": "Price < 20 EMA (15-min)", "description": "Price below 20 EMA — bearish"},
            {"indicator": "RSI", "condition": "< 45 (5-min)", "description": "RSI below 45 — weak momentum"},
            {"indicator": "VWAP", "condition": "Price < VWAP", "description": "Price below VWAP — bearish bias"},
        ],
        "exit_rules": [
            {"type": "profit", "value": "70% of max spread width"},
            {"type": "stop_loss", "value": "50% of net premium paid"},
            {"type": "time", "value": "Exit by 2:00 PM"},
        ],
        "max_profit": "(Spread width - debit) × lot size ≈ ₹6,500/lot",
        "max_loss": "Net premium paid ≈ ₹6,500/lot",
    },
    {
        "id": "short_straddle_expiry",
        "name": "Short Straddle (Expiry Day)",
        "category": "conservative-selling",
        "risk": "high",
        "reward": "medium",
        "win_rate": "60-65%",
        "capital": "₹1.5-2.5L (margin)",
        "best_for": "Expiry day sideways movement",
        "description": "Sell ATM Call + ATM Put on expiry day. Profits from rapid theta decay. Requires high margin but has high win rate on range-bound expiry days.",
        "legs": [
            {"action": "sell", "type": "CE", "strike_offset": 0, "label": "Sell ATM Call"},
            {"action": "sell", "type": "PE", "strike_offset": 0, "label": "Sell ATM Put"},
        ],
        "entry_rules": [
            {"indicator": "DAY", "condition": "Expiry day only", "description": "NIFTY Tue / BANKNIFTY Wed"},
            {"indicator": "TIME", "condition": "9:30 AM", "description": "After initial volatility settles"},
            {"indicator": "VIX", "condition": "> 13", "description": "VIX elevated for higher premiums"},
            {"indicator": "EVENT", "condition": "No major events", "description": "No RBI policy, no budget today"},
        ],
        "exit_rules": [
            {"type": "profit", "value": "65% of premium collected"},
            {"type": "stop_loss", "value": "40% additional loss on total premium"},
            {"type": "time", "value": "Mandatory close by 3:15 PM"},
        ],
        "max_profit": "Total premium ≈ ₹15,000-25,000/lot",
        "max_loss": "Unlimited (use stop loss!)",
    },
    {
        "id": "long_straddle_event",
        "name": "Long Straddle (Event-Based)",
        "category": "aggressive",
        "risk": "high",
        "reward": "high",
        "win_rate": "40-45%",
        "capital": "₹20,000-25,000",
        "best_for": "Before major events (RBI, Budget, Fed)",
        "description": "Buy ATM Call + ATM Put before a major event. Profits from large moves in either direction. Must exit quickly after event to avoid IV crush.",
        "legs": [
            {"action": "buy", "type": "CE", "strike_offset": 0, "label": "Buy ATM Call"},
            {"action": "buy", "type": "PE", "strike_offset": 0, "label": "Buy ATM Put"},
        ],
        "entry_rules": [
            {"indicator": "VIX", "condition": "> 15 and rising", "description": "VIX above 15 and trending up"},
            {"indicator": "EVENT", "condition": "1 day before event", "description": "Enter day before RBI/Budget/Fed"},
            {"indicator": "TIME", "condition": "2-3 PM day before", "description": "Enter late afternoon before event"},
        ],
        "exit_rules": [
            {"type": "profit", "value": "Premium doubles (100% return)"},
            {"type": "stop_loss", "value": "30% of total premium"},
            {"type": "time", "value": "Exit within 30 min of post-event open"},
        ],
        "max_profit": "Unlimited if large move occurs",
        "max_loss": "Total premium paid ≈ ₹22,750/lot",
    },
    {
        "id": "long_strangle",
        "name": "Long Strangle",
        "category": "aggressive",
        "risk": "medium-high",
        "reward": "high",
        "win_rate": "35-40%",
        "capital": "₹15,000-18,000",
        "best_for": "Pre-breakout / Volatile markets",
        "description": "Buy OTM Call + OTM Put. Cheaper than straddle. Profits from large moves. Needs bigger move to break even.",
        "legs": [
            {"action": "buy", "type": "CE", "strike_offset": 200, "label": "Buy OTM Call"},
            {"action": "buy", "type": "PE", "strike_offset": -200, "label": "Buy OTM Put"},
        ],
        "entry_rules": [
            {"indicator": "VIX", "condition": "Crossing above 14", "description": "VIX rising from low levels"},
            {"indicator": "BB", "condition": "Bollinger squeeze", "description": "Bands narrowing — breakout expected"},
            {"indicator": "OI", "condition": "Equal buildup both sides", "description": "Neutral OI buildup"},
        ],
        "exit_rules": [
            {"type": "profit", "value": "Exit winning leg when it doubles"},
            {"type": "stop_loss", "value": "30% of total combined premium"},
            {"type": "time", "value": "Exit by 1 PM if no move"},
        ],
        "max_profit": "Unlimited on winning side",
        "max_loss": "Total premium paid ≈ ₹15,600/lot",
    },
    {
        "id": "bull_put_credit_spread",
        "name": "Bull Put Credit Spread",
        "category": "conservative",
        "risk": "low",
        "reward": "low",
        "win_rate": "70-75%",
        "capital": "₹15,000-25,000",
        "best_for": "Sideways to mildly bullish",
        "description": "Sell OTM Put + Buy further OTM Put. Collect premium upfront. Highest win rate strategy. Profits from time decay and stable/rising markets.",
        "legs": [
            {"action": "sell", "type": "PE", "strike_offset": -200, "label": "Sell OTM Put"},
            {"action": "buy", "type": "PE", "strike_offset": -400, "label": "Buy Far OTM Put (hedge)"},
        ],
        "entry_rules": [
            {"indicator": "VWAP", "condition": "Price > VWAP (15-min)", "description": "Price above VWAP — bullish"},
            {"indicator": "RSI", "condition": "> 50 (15-min)", "description": "RSI above neutral"},
            {"indicator": "OI", "condition": "Put OI building at short strike", "description": "Support confirmed by Put OI"},
            {"indicator": "VIX", "condition": "< 15", "description": "Low volatility environment"},
        ],
        "exit_rules": [
            {"type": "profit", "value": "50% of credit received"},
            {"type": "stop_loss", "value": "Spread value doubles from entry"},
            {"type": "time", "value": "Hold till expiry if conditions ok"},
        ],
        "max_profit": "Net credit ≈ ₹2,600/lot",
        "max_loss": "Spread width - credit ≈ ₹10,400/lot",
    },
    {
        "id": "call_ratio_backspread",
        "name": "Call Ratio Backspread (1:2)",
        "category": "aggressive",
        "risk": "medium-high",
        "reward": "very-high",
        "win_rate": "35-40%",
        "capital": "₹30,000-50,000",
        "best_for": "Strong bullish breakout expected",
        "description": "Sell 1 ATM Call + Buy 2 OTM Calls. Small credit or debit. Unlimited profit on sharp up-moves. Risk is limited to the zone between strikes.",
        "legs": [
            {"action": "sell", "type": "CE", "strike_offset": 0, "label": "Sell 1× ATM Call"},
            {"action": "buy", "type": "CE", "strike_offset": 300, "qty": 2, "label": "Buy 2× OTM Call"},
        ],
        "entry_rules": [
            {"indicator": "BREAKOUT", "condition": "Price above resistance (daily)", "description": "Clear breakout above daily resistance"},
            {"indicator": "VIX", "condition": "14-22", "description": "Moderate volatility"},
            {"indicator": "VOLUME", "condition": "Above average", "description": "Volume spike confirming breakout"},
        ],
        "exit_rules": [
            {"type": "profit", "value": "Trail stop at 20% below peak premium"},
            {"type": "stop_loss", "value": "Close if price stalls near long strike"},
            {"type": "time", "value": "Exit by 1 PM on non-event days"},
        ],
        "max_profit": "Unlimited above breakeven",
        "max_loss": "(Strike diff - credit) × lot ≈ ₹14,300/lot",
    },
    {
        "id": "vwap_ema_scalping",
        "name": "VWAP + EMA Scalping",
        "category": "scalping",
        "risk": "medium",
        "reward": "low-per-trade",
        "win_rate": "55-60%",
        "capital": "₹15,000-25,000",
        "best_for": "Trending intraday markets",
        "description": "Quick in-and-out trades using 9/21 EMA crossover, VWAP, and RSI on 5-min chart. Buy ATM options for quick ₹10-20 scalps. Max 3-4 trades/day.",
        "legs": [
            {"action": "buy", "type": "CE", "strike_offset": 0, "label": "Buy ATM CE (bullish signal)"},
            {"action": "buy", "type": "PE", "strike_offset": 0, "label": "OR Buy ATM PE (bearish signal)"},
        ],
        "entry_rules": [
            {"indicator": "EMA", "condition": "9 EMA crosses 21 EMA (5-min)", "description": "Short-term EMA crossover"},
            {"indicator": "VWAP", "condition": "Price on correct side of VWAP", "description": "Above VWAP for CE, below for PE"},
            {"indicator": "RSI", "condition": "> 55 for CE, < 45 for PE", "description": "RSI confirming direction"},
            {"indicator": "TIME", "condition": "9:30 AM - 1:00 PM only", "description": "Avoid afternoon theta decay"},
        ],
        "exit_rules": [
            {"type": "profit", "value": "₹10-20 on option premium (₹650-1,300/lot)"},
            {"type": "stop_loss", "value": "₹10-15 loss on premium (₹650-975/lot)"},
            {"type": "signal", "value": "Exit if EMA crosses back"},
        ],
        "max_profit": "₹650-1,300 per trade",
        "max_loss": "₹650-975 per trade",
    },
    {
        "id": "oi_support_resistance",
        "name": "OI-Based Support/Resistance",
        "category": "data-driven",
        "risk": "medium",
        "reward": "medium-high",
        "win_rate": "55-60%",
        "capital": "₹15,000-25,000",
        "best_for": "Any market — adapts based on OI data",
        "description": "Use option chain OI to find support (highest PUT OI) and resistance (highest CALL OI). Trade bounces off these levels or breakouts through them.",
        "legs": [
            {"action": "buy", "type": "CE", "strike_offset": 0, "label": "Buy CE at support bounce"},
            {"action": "buy", "type": "PE", "strike_offset": 0, "label": "OR Buy PE at resistance rejection"},
        ],
        "entry_rules": [
            {"indicator": "OI", "condition": "Highest PUT OI = support", "description": "Identify max PUT OI strike"},
            {"indicator": "OI", "condition": "Highest CALL OI = resistance", "description": "Identify max CALL OI strike"},
            {"indicator": "PRICE", "condition": "Near support for CE, near resistance for PE", "description": "Price within 50 pts of OI wall"},
            {"indicator": "OI_CHANGE", "condition": "OI increasing at level", "description": "Confirms support/resistance strength"},
        ],
        "exit_rules": [
            {"type": "profit", "value": "Opposite OI wall (support→resistance or vice versa)"},
            {"type": "stop_loss", "value": "25 points beyond the OI level"},
            {"type": "signal", "value": "Exit if OI at your level starts declining"},
        ],
        "max_profit": "Distance between OI walls × delta",
        "max_loss": "Defined by stop loss ≈ ₹1,625/lot (25 pts)",
    },
    {
        "id": "pcr_contrarian",
        "name": "PCR Contrarian",
        "category": "data-driven",
        "risk": "medium",
        "reward": "medium-high",
        "win_rate": "55-60%",
        "capital": "₹15,000-20,000",
        "best_for": "Extreme sentiment reversals",
        "description": "Trade against the crowd. When PCR > 1.3 (extreme bearish), buy CE. When PCR < 0.7 (extreme bullish), buy PE. Catches reversals at sentiment extremes.",
        "legs": [
            {"action": "buy", "type": "CE", "strike_offset": 0, "label": "Buy CE when PCR > 1.3 (contrarian bullish)"},
            {"action": "buy", "type": "PE", "strike_offset": 0, "label": "OR Buy PE when PCR < 0.7 (contrarian bearish)"},
        ],
        "entry_rules": [
            {"indicator": "PCR", "condition": "> 1.3 for CE, < 0.7 for PE", "description": "Extreme PCR reading"},
            {"indicator": "RSI", "condition": "< 35 for CE (oversold), > 65 for PE (overbought)", "description": "RSI confirming extreme"},
            {"indicator": "OI", "condition": "Price near highest OI wall", "description": "Near strong support/resistance"},
        ],
        "exit_rules": [
            {"type": "profit", "value": "60% gain or PCR reverts to 1.0"},
            {"type": "stop_loss", "value": "30% of premium paid"},
            {"type": "time", "value": "Exit in 2-3 hours if no reversal"},
        ],
        "max_profit": "2-3× premium if strong reversal",
        "max_loss": "Premium with 30% SL ≈ ₹4,500-6,000/lot",
    },
    {
        "id": "max_pain_gravity",
        "name": "Max Pain Gravity",
        "category": "expiry-focused",
        "risk": "medium",
        "reward": "medium",
        "win_rate": "55-65%",
        "capital": "₹10,000-15,000",
        "best_for": "1-2 days before expiry",
        "description": "Price tends to gravitate toward Max Pain (strike where most options expire worthless) near expiry. Trade in the direction of convergence.",
        "legs": [
            {"action": "buy", "type": "PE", "strike_offset": 0, "label": "Buy PE if spot > Max Pain + 150"},
            {"action": "buy", "type": "CE", "strike_offset": 0, "label": "OR Buy CE if spot < Max Pain - 150"},
        ],
        "entry_rules": [
            {"indicator": "MAX_PAIN", "condition": "Spot diverges 150+ pts from Max Pain", "description": "Significant gap from Max Pain"},
            {"indicator": "EXPIRY", "condition": "1-2 days before expiry", "description": "Gravity effect strongest near expiry"},
            {"indicator": "OI", "condition": "OI concentration confirms Max Pain", "description": "Multiple strikes' OI supports the level"},
        ],
        "exit_rules": [
            {"type": "profit", "value": "Spot reaches within 50 pts of Max Pain"},
            {"type": "stop_loss", "value": "100 pts move away from Max Pain"},
            {"type": "time", "value": "Close before 2 PM on expiry day"},
        ],
        "max_profit": "Premium gain from convergence (50-100%)",
        "max_loss": "Defined by stop loss",
    },
    {
        "id": "butterfly_spread",
        "name": "Butterfly Spread",
        "category": "conservative",
        "risk": "low",
        "reward": "medium",
        "win_rate": "30-40%",
        "capital": "₹3,000-8,000",
        "best_for": "Tight range near expiry",
        "description": "Buy 1 ITM + Sell 2 ATM + Buy 1 OTM (all calls or puts). Very low cost, high reward-to-risk ratio. Best when expecting price to stay near center strike at expiry.",
        "legs": [
            {"action": "buy", "type": "CE", "strike_offset": -200, "label": "Buy 1× ITM Call"},
            {"action": "sell", "type": "CE", "strike_offset": 0, "qty": 2, "label": "Sell 2× ATM Call"},
            {"action": "buy", "type": "CE", "strike_offset": 200, "label": "Buy 1× OTM Call"},
        ],
        "entry_rules": [
            {"indicator": "BB", "condition": "Bandwidth < 1% (daily)", "description": "Bollinger Bands squeezing — tight range"},
            {"indicator": "VIX", "condition": "< 14", "description": "Low volatility"},
            {"indicator": "EXPIRY", "condition": "1-2 days to expiry", "description": "Theta maximizes the spread value"},
        ],
        "exit_rules": [
            {"type": "profit", "value": "50% of max theoretical profit"},
            {"type": "stop_loss", "value": "80% of net debit paid"},
            {"type": "time", "value": "Close by 2 PM on expiry day"},
        ],
        "max_profit": "5-10× the net debit (if price at center at expiry)",
        "max_loss": "Net debit paid ≈ ₹3,000-8,000/lot",
    },
]

# Category metadata for frontend display
CATEGORIES = {
    "conservative": {
        "label": "Conservative",
        "color": "emerald",
        "icon": "🛡️",
        "description": "High win rate, lower returns. Capital preservation focus.",
    },
    "conservative-selling": {
        "label": "Conservative (Selling)",
        "color": "emerald",
        "icon": "🏦",
        "description": "Premium selling strategies. High margin needed, high win rate.",
    },
    "moderate": {
        "label": "Moderate",
        "color": "amber",
        "icon": "⚖️",
        "description": "Balanced risk-reward. Good for directional views.",
    },
    "aggressive": {
        "label": "Aggressive",
        "color": "red",
        "icon": "🔥",
        "description": "High risk, high reward. For strong directional or event bets.",
    },
    "scalping": {
        "label": "Scalping",
        "color": "blue",
        "icon": "⚡",
        "description": "Quick in-and-out. Multiple small trades for cumulative profit.",
    },
    "data-driven": {
        "label": "Data-Driven",
        "color": "purple",
        "icon": "📊",
        "description": "Based on OI, PCR, and option chain data analysis.",
    },
    "expiry-focused": {
        "label": "Expiry-Focused",
        "color": "cyan",
        "icon": "📅",
        "description": "Strategies optimized for near-expiry time decay and gamma.",
    },
}


def get_all_strategies() -> list[dict]:
    """Return all predefined strategies with category metadata."""
    result = []
    for s in STRATEGIES:
        cat = CATEGORIES.get(s["category"], {})
        result.append({
            **s,
            "category_label": cat.get("label", s["category"]),
            "category_color": cat.get("color", "slate"),
            "category_icon": cat.get("icon", ""),
        })
    return result


def get_strategy(strategy_id: str) -> dict | None:
    """Get a single strategy by ID."""
    for s in STRATEGIES:
        if s["id"] == strategy_id:
            cat = CATEGORIES.get(s["category"], {})
            return {
                **s,
                "category_label": cat.get("label", s["category"]),
                "category_color": cat.get("color", "slate"),
                "category_icon": cat.get("icon", ""),
            }
    return None


def get_categories() -> dict:
    """Return all category metadata."""
    return CATEGORIES


def check_strategy_conditions(strategy_id: str, option_data: dict, indicators: dict) -> dict:
    """
    Check if a strategy's entry conditions are met based on live data.

    Args:
        strategy_id: ID of the predefined strategy
        option_data: Option chain data (from /api/options/)
        indicators: Technical indicators (from screener)

    Returns:
        dict with met/unmet conditions and overall signal
    """
    strategy = get_strategy(strategy_id)
    if not strategy:
        return {"error": f"Strategy {strategy_id} not found"}

    spot = option_data.get("spot_price", 0)
    pcr = option_data.get("pcr", 0)
    strikes = option_data.get("strikes", [])

    results = []
    met_count = 0

    for rule in strategy.get("entry_rules", []):
        indicator = rule["indicator"]
        condition = rule["condition"]
        met = False
        current_value = None

        if indicator == "RSI":
            val = indicators.get("rsi")
            current_value = val
            if val is not None:
                if ">" in condition:
                    threshold = float(condition.split(">")[1].strip().split()[0])
                    met = val > threshold
                elif "<" in condition:
                    threshold = float(condition.split("<")[1].strip().split()[0])
                    met = val < threshold

        elif indicator == "PCR":
            current_value = pcr
            if "-" in condition:
                parts = condition.split("-")
                low, high = float(parts[0].strip()), float(parts[1].strip())
                met = low <= pcr <= high
            elif ">" in condition:
                threshold = float(condition.split(">")[1].strip().split()[0])
                met = pcr > threshold
            elif "<" in condition:
                threshold = float(condition.split("<")[1].strip().split()[0])
                met = pcr < threshold

        elif indicator == "VIX":
            # VIX not always available — mark as unknown
            current_value = "N/A (check manually)"
            met = None

        elif indicator == "EMA":
            ema_20 = indicators.get("ema_20")
            price = indicators.get("current_price")
            current_value = f"Price={price}, EMA20={ema_20}"
            if price and ema_20:
                if ">" in condition:
                    met = price > ema_20
                elif "<" in condition:
                    met = price < ema_20

        elif indicator == "VWAP":
            # VWAP from indicators if available
            current_value = "Check chart"
            met = None

        elif indicator == "OI":
            if strikes:
                # Find highest CE and PE OI
                max_ce_oi = max((s.get("CE", {}).get("oi", 0) for s in strikes), default=0)
                max_pe_oi = max((s.get("PE", {}).get("oi", 0) for s in strikes), default=0)
                current_value = f"Max CE OI: {max_ce_oi:,}, Max PE OI: {max_pe_oi:,}"
                met = True  # OI data is available
            else:
                current_value = "No OI data (market closed?)"
                met = None

        else:
            current_value = "Check manually"
            met = None

        if met is True:
            met_count += 1

        results.append({
            "indicator": indicator,
            "condition": condition,
            "description": rule["description"],
            "current_value": str(current_value) if current_value else "N/A",
            "met": met,
        })

    total_rules = len(results)
    checkable_rules = len([r for r in results if r["met"] is not None])
    met_pct = (met_count / checkable_rules * 100) if checkable_rules > 0 else 0

    if met_pct >= 75:
        signal = "strong_entry"
        signal_label = "Strong Entry Signal"
    elif met_pct >= 50:
        signal = "moderate_entry"
        signal_label = "Moderate — Some Conditions Met"
    else:
        signal = "weak"
        signal_label = "Weak — Most Conditions Not Met"

    # Calculate suggested strikes
    suggested_legs = []
    if spot > 0:
        for leg in strategy.get("legs", []):
            strike = _round_strike(spot + leg.get("strike_offset", 0))
            suggested_legs.append({
                **leg,
                "suggested_strike": strike,
            })

    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy["name"],
        "spot_price": spot,
        "pcr": pcr,
        "signal": signal,
        "signal_label": signal_label,
        "met_count": met_count,
        "total_rules": total_rules,
        "met_percentage": round(met_pct, 1),
        "conditions": results,
        "suggested_legs": suggested_legs,
    }


def _round_strike(price: float, step: int = 50) -> int:
    """Round price to nearest strike step (50 for NIFTY)."""
    return round(price / step) * step
