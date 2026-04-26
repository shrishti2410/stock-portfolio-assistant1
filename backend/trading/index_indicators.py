"""
index_indicators.py — Compute technical indicators for NIFTY/BANKNIFTY indices.

Uses yfinance for index price history (works on weekends).
Computes RSI, EMA, overall_score for the directional spread strategy.
"""
import yfinance as yf
import pandas as pd


YF_INDEX_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "FINNIFTY": "^CNXFIN",
}


def _rsi(series: pd.Series, period: int = 14) -> float:
    """Compute RSI from a price series."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(val) if pd.notna(val) else 50.0


def _ema(series: pd.Series, period: int) -> float:
    """Compute EMA latest value."""
    val = series.ewm(span=period, adjust=False).mean().iloc[-1]
    return float(val) if pd.notna(val) else float(series.iloc[-1])


def get_index_indicators(symbol: str) -> dict:
    """
    Fetch technical indicators for an index using yfinance.

    Returns dict with: rsi, ema_20, ema_50, current_price, overall_score
    overall_score: -1 (very bearish) to +1 (very bullish)
    """
    yf_sym = YF_INDEX_MAP.get(symbol.upper())
    if not yf_sym:
        return {}

    ticker = yf.Ticker(yf_sym)
    hist = ticker.history(period="6mo")

    if hist.empty or len(hist) < 50:
        return {}

    close = hist["Close"]
    current_price = float(close.iloc[-1])

    rsi = _rsi(close, 14)
    ema_20 = _ema(close, 20)
    ema_50 = _ema(close, 50)
    ema_200 = _ema(close, 200) if len(close) >= 200 else ema_50

    # Compute overall_score: weighted combination of signals
    score = 0.0

    # RSI contribution
    if rsi > 70:
        score -= 0.3  # Overbought
    elif rsi > 55:
        score += 0.3  # Bullish momentum
    elif rsi < 30:
        score += 0.3  # Oversold (potential bounce)
    elif rsi < 45:
        score -= 0.3  # Bearish momentum

    # EMA alignment
    if current_price > ema_20 > ema_50:
        score += 0.4  # Bullish trend
    elif current_price < ema_20 < ema_50:
        score -= 0.4  # Bearish trend

    # Long-term trend
    if current_price > ema_200:
        score += 0.2
    else:
        score -= 0.2

    # Cap to [-1, +1]
    score = max(-1.0, min(1.0, score))

    return {
        "rsi": round(rsi, 2),
        "ema_20": round(ema_20, 2),
        "ema_50": round(ema_50, 2),
        "ema_200": round(ema_200, 2),
        "current_price": round(current_price, 2),
        "overall_score": round(score, 2),
    }
