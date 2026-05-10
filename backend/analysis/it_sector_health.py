"""
it_sector_health.py — IT sector macro indicators for thesis validation.

Fetches NIFTY IT vs NIFTY50 relative performance, macro signals (USD/INR, India VIX,
US 10Y yield, XLK/IGV ETF trends), and a per-stock sector heatmap. Combines into a
single thesis-validation score (0-100) where higher = thesis more validated.

All data via yfinance. Cached with a 15-minute TTL to respect rate limits.
"""
import asyncio
import time
from datetime import date

import yfinance as yf
import pandas as pd

# ---------------------------------------------------------------------------
# Cache layer — 15-min TTL for sector health data
# ---------------------------------------------------------------------------
_cache: dict[str, dict] = {}
_TTL = 900  # 15 minutes


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < _TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data) -> None:
    _cache[key] = {"data": data, "ts": time.time()}


# ---------------------------------------------------------------------------
# Blocking helpers (call via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _fetch_pct_change(yf_symbol: str, periods: list[int]) -> dict[str, float]:
    """
    Fetch daily closing prices and compute percentage changes for given period windows.
    periods is in trading days (approx).
    Returns {f"pct_{p}d": float} for each period, or 0.0 on failure.
    """
    try:
        max_days = max(periods) + 10
        hist = yf.Ticker(yf_symbol).history(period=f"{max_days}d")
        if hist is None or hist.empty:
            return {f"pct_{p}d": 0.0 for p in periods}
        closes = hist["Close"].dropna()
        result = {}
        for p in periods:
            if len(closes) > p:
                pct = (closes.iloc[-1] - closes.iloc[-(p + 1)]) / closes.iloc[-(p + 1)] * 100
                result[f"pct_{p}d"] = round(float(pct), 2)
            else:
                result[f"pct_{p}d"] = 0.0
        return result
    except Exception as e:
        print(f"[it_sector_health] pct_change failed for {yf_symbol}: {e}")
        return {f"pct_{p}d": 0.0 for p in periods}


def _fetch_current_value(yf_symbol: str) -> float:
    """Fetch the most recent closing price for a symbol."""
    try:
        hist = yf.Ticker(yf_symbol).history(period="5d")
        if hist is None or hist.empty:
            return 0.0
        return round(float(hist["Close"].dropna().iloc[-1]), 4)
    except Exception as e:
        print(f"[it_sector_health] current_value failed for {yf_symbol}: {e}")
        return 0.0


def _fetch_rsi(closes: pd.Series, period: int = 14) -> float:
    """Compute RSI for a price series."""
    if len(closes) < period + 1:
        return 50.0
    delta = closes.diff().dropna()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.rolling(window=period).mean().iloc[-1]
    avg_loss = losses.rolling(window=period).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(float(100 - 100 / (1 + rs)), 2)


def _fetch_trend(yf_symbol: str, period_days: int = 20) -> str:
    """
    Classify trend as 'bull', 'bear', or 'neutral' based on 20-day momentum.
    bull  = price > 20-DMA AND 20-DMA slope positive
    bear  = price < 20-DMA AND 20-DMA slope negative
    """
    try:
        hist = yf.Ticker(yf_symbol).history(period=f"{period_days + 10}d")
        if hist is None or hist.empty:
            return "neutral"
        closes = hist["Close"].dropna()
        if len(closes) < period_days:
            return "neutral"
        ma = closes.rolling(period_days).mean().dropna()
        if len(ma) < 2:
            return "neutral"
        price = float(closes.iloc[-1])
        current_ma = float(ma.iloc[-1])
        prev_ma = float(ma.iloc[-2])
        if price > current_ma and current_ma > prev_ma:
            return "bull"
        elif price < current_ma and current_ma < prev_ma:
            return "bear"
        return "neutral"
    except Exception as e:
        print(f"[it_sector_health] trend failed for {yf_symbol}: {e}")
        return "neutral"


def _fetch_stock_indicators(yf_symbol: str, symbol: str, name: str, country: str) -> dict | None:
    """
    Fetch price + compute RSI, 1d/5d/20d change, check above 50-DMA.
    """
    try:
        hist = yf.Ticker(yf_symbol).history(period="90d")
        if hist is None or hist.empty:
            return None
        closes = hist["Close"].dropna()
        if len(closes) < 5:
            return None

        price = float(closes.iloc[-1])
        change_1d = round((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100, 2) if len(closes) >= 2 else 0.0
        change_5d = round((closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100, 2) if len(closes) >= 6 else 0.0
        change_20d = round((closes.iloc[-1] - closes.iloc[-21]) / closes.iloc[-21] * 100, 2) if len(closes) >= 21 else 0.0
        rsi = _fetch_rsi(closes)

        above_50dma = False
        if len(closes) >= 50:
            dma_50 = float(closes.rolling(50).mean().iloc[-1])
            above_50dma = price > dma_50

        return {
            "symbol": symbol,
            "name": name,
            "country": country,
            "price": round(price, 2),
            "change_pct_1d": change_1d,
            "change_pct_5d": change_5d,
            "change_pct_20d": change_20d,
            "rsi": rsi,
            "above_50dma": above_50dma,
        }
    except Exception as e:
        print(f"[it_sector_health] stock indicators failed for {yf_symbol}: {e}")
        return None


# ---------------------------------------------------------------------------
# Public async functions
# ---------------------------------------------------------------------------

async def get_nifty_it_vs_nifty50() -> dict:
    """
    Returns relative strength data:
    {
        "nifty_it_pct_5d", "nifty_it_pct_20d", "nifty_it_pct_90d",
        "nifty50_pct_5d", "nifty50_pct_20d", "nifty50_pct_90d",
        "relative_strength": nifty_it / nifty50 over 20d,
        "regime": "underperforming" | "outperforming" | "neutral",
    }
    """
    cache_key = "nifty_it_vs_nifty50"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    nifty_it_data, nifty50_data = await asyncio.gather(
        asyncio.to_thread(_fetch_pct_change, "^CNXIT", [5, 20, 90]),
        asyncio.to_thread(_fetch_pct_change, "^NSEI", [5, 20, 90]),
    )

    nifty_it_20 = nifty_it_data.get("pct_20d", 0.0)
    nifty50_20 = nifty50_data.get("pct_20d", 0.0)

    # Relative strength = outperformance over NIFTY50
    rs = round(nifty_it_20 - nifty50_20, 2)

    if rs < -2.0:
        regime = "underperforming"
    elif rs > 2.0:
        regime = "outperforming"
    else:
        regime = "neutral"

    result = {
        "nifty_it_pct_5d": nifty_it_data.get("pct_5d", 0.0),
        "nifty_it_pct_20d": nifty_it_20,
        "nifty_it_pct_90d": nifty_it_data.get("pct_90d", 0.0),
        "nifty50_pct_5d": nifty50_data.get("pct_5d", 0.0),
        "nifty50_pct_20d": nifty50_20,
        "nifty50_pct_90d": nifty50_data.get("pct_90d", 0.0),
        "relative_strength": rs,
        "regime": regime,
    }

    _cache_set(cache_key, result)
    return result


async def get_macro_indicators() -> dict:
    """
    Returns macro context for IT-bear thesis:
    {
        "usd_inr": current rate + 20d change,
        "india_vix": current value,
        "us_10y_yield": value,
        "xlk_trend": 20-day momentum (bull/bear/neutral),
        "igv_trend": same for software ETF,
    }
    """
    cache_key = "macro_indicators"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    usd_inr_val, india_vix_val, us10y_val, usd_inr_chg, xlk_trend, igv_trend = await asyncio.gather(
        asyncio.to_thread(_fetch_current_value, "USDINR=X"),
        asyncio.to_thread(_fetch_current_value, "^INDIAVIX"),
        asyncio.to_thread(_fetch_current_value, "^TNX"),
        asyncio.to_thread(_fetch_pct_change, "USDINR=X", [20]),
        asyncio.to_thread(_fetch_trend, "XLK", 20),
        asyncio.to_thread(_fetch_trend, "IGV", 20),
    )

    result = {
        "usd_inr": {
            "value": usd_inr_val,
            "change_20d_pct": usd_inr_chg.get("pct_20d", 0.0),
            "note": "Higher INR depreciation = positive for IT revenue in INR terms (counter-thesis)",
        },
        "india_vix": india_vix_val,
        "us_10y_yield": us10y_val,
        "xlk_trend": xlk_trend,
        "igv_trend": igv_trend,
    }

    _cache_set(cache_key, result)
    return result


async def get_sector_heatmap() -> list[dict]:
    """
    For each stock in IT universe, return:
    {"symbol", "name", "price", "change_pct_1d", "change_pct_5d",
     "change_pct_20d", "rsi", "above_50dma": bool}
    Sorted by 20d weakest first (best short candidates at top).
    """
    cache_key = "sector_heatmap"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    from data.it_universe import get_all
    stocks = get_all()

    tasks = [
        asyncio.to_thread(
            _fetch_stock_indicators,
            s.get("yf", s["symbol"]),
            s["symbol"],
            s.get("name", s["symbol"]),
            s.get("country", ""),
        )
        for s in stocks
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    heatmap = []
    for r in results:
        if isinstance(r, Exception) or r is None:
            continue
        heatmap.append(r)

    # Sort by 20d change ascending (weakest performers first — best short candidates)
    heatmap.sort(key=lambda x: x.get("change_pct_20d", 0))

    _cache_set(cache_key, heatmap)
    return heatmap


async def get_sector_health_summary() -> dict:
    """
    Aggregate: {"thesis_score": 0-100, "regime", "key_signals": [...]}
    Higher score = thesis more validated.

    Scoring breakdown:
    - NIFTY IT underperforming NIFTY50 over 20d:  0-30 pts
    - NIFTY IT below 50-DMA:                      0-15 pts
    - India VIX elevated (>15):                   0-10 pts
    - US sector (XLK/IGV) in downtrend:           0-15 pts
    - Majority of stocks below 50-DMA:            0-15 pts
    - Majority of stocks have RSI < 50:           0-15 pts
    Total max: 100
    """
    cache_key = "sector_health_summary"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    rs_data, macro, heatmap = await asyncio.gather(
        get_nifty_it_vs_nifty50(),
        get_macro_indicators(),
        get_sector_heatmap(),
    )

    key_signals = []
    score = 0

    # 1. Relative underperformance (0-30 pts)
    rs = rs_data.get("relative_strength", 0.0)
    nifty_it_pct_20d = rs_data.get("nifty_it_pct_20d", 0.0)
    if rs < -5.0:
        score += 30
        key_signals.append(f"NIFTY IT severely underperforming NIFTY50 by {abs(rs):.1f}% (20d)")
    elif rs < -2.0:
        score += 20
        key_signals.append(f"NIFTY IT underperforming NIFTY50 by {abs(rs):.1f}% (20d)")
    elif rs < 0:
        score += 10
        key_signals.append(f"NIFTY IT mildly underperforming NIFTY50 by {abs(rs):.1f}% (20d)")

    # 2. NIFTY IT absolute performance (below 50-DMA proxy = 20d negative)
    if nifty_it_pct_20d < -5.0:
        score += 15
        key_signals.append(f"NIFTY IT down {abs(nifty_it_pct_20d):.1f}% over 20d — likely below 50-DMA")
    elif nifty_it_pct_20d < -2.0:
        score += 10
        key_signals.append(f"NIFTY IT down {abs(nifty_it_pct_20d):.1f}% over 20d")
    elif nifty_it_pct_20d < 0:
        score += 5

    # 3. India VIX (0-10 pts)
    vix = macro.get("india_vix", 0)
    if vix > 20:
        score += 10
        key_signals.append(f"India VIX elevated at {vix:.1f} — fear supports bear thesis")
    elif vix > 15:
        score += 5
        key_signals.append(f"India VIX above 15 at {vix:.1f}")

    # 4. US IT sector trend (0-15 pts)
    xlk = macro.get("xlk_trend", "neutral")
    igv = macro.get("igv_trend", "neutral")
    us_bear_count = sum(1 for t in [xlk, igv] if t == "bear")
    if us_bear_count == 2:
        score += 15
        key_signals.append("Both XLK + IGV in downtrend — US IT sector weak")
    elif us_bear_count == 1:
        score += 8
        key_signals.append(f"US IT sector mixed: XLK={xlk}, IGV={igv}")

    # 5. Stocks below 50-DMA (0-15 pts)
    total_stocks = len(heatmap)
    if total_stocks > 0:
        below_dma = sum(1 for s in heatmap if not s.get("above_50dma", True))
        below_pct = below_dma / total_stocks
        if below_pct >= 0.75:
            score += 15
            key_signals.append(f"{below_pct:.0%} of IT stocks below 50-DMA")
        elif below_pct >= 0.50:
            score += 10
            key_signals.append(f"{below_pct:.0%} of IT stocks below 50-DMA")
        elif below_pct >= 0.25:
            score += 5

        # 6. Stocks with RSI < 50 (0-15 pts)
        weak_rsi = sum(1 for s in heatmap if s.get("rsi", 50) < 50)
        weak_pct = weak_rsi / total_stocks
        if weak_pct >= 0.75:
            score += 15
            key_signals.append(f"{weak_pct:.0%} of IT stocks have RSI < 50")
        elif weak_pct >= 0.50:
            score += 10
            key_signals.append(f"{weak_pct:.0%} of IT stocks have RSI < 50")
        elif weak_pct >= 0.25:
            score += 5

    score = min(score, 100)

    if score >= 60:
        regime = "strongly_bearish"
    elif score >= 40:
        regime = "moderately_bearish"
    elif score >= 25:
        regime = "mildly_bearish"
    else:
        regime = "neutral_or_bullish"

    result = {
        "thesis_score": score,
        "regime": regime,
        "key_signals": key_signals,
        "relative_strength_20d": rs,
        "nifty_it_regime": rs_data.get("regime", "neutral"),
        "india_vix": vix,
        "xlk_trend": xlk,
        "igv_trend": igv,
    }

    _cache_set(cache_key, result)
    return result
