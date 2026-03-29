"""
screener.py — Technical screening using jugaad-data + pandas_ta

Replaces yfinance for Indian stock price data. Computes the same technical
indicators PKScreener uses (RSI, MACD, EMA crossovers, Bollinger Bands,
volume analysis, ADX) as a callable library.

Public API:
    get_price_data(symbol, days=90) -> pd.DataFrame
    screen_stock(symbol) -> ScreeningResult
    get_fundamental_data(symbol) -> dict  (yfinance fallback)
"""

import time
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta

import pandas as pd

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    name: str           # e.g. "RSI_Oversold", "MACD_Bullish_Cross"
    direction: str      # "bullish" | "bearish" | "neutral"
    strength: float     # 0.0–1.0
    description: str    # human-readable

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScreeningResult:
    symbol: str
    signals: list[Signal] = field(default_factory=list)
    overall_direction: str = "neutral"    # "bullish" | "bearish" | "neutral"
    overall_score: float = 0.0            # -1.0 (max bearish) to +1.0 (max bullish)
    price_data_summary: dict = field(default_factory=dict)
    indicators: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "signals": [s.to_dict() for s in self.signals],
            "overall_direction": self.overall_direction,
            "overall_score": round(self.overall_score, 3),
            "price_data_summary": self.price_data_summary,
            "indicators": self.indicators,
        }


# ---------------------------------------------------------------------------
# Price data fetching — jugaad-data (primary), yfinance (fallback)
# ---------------------------------------------------------------------------

_price_cache: dict[str, dict] = {}  # {symbol: {"df": DataFrame, "ts": float}}
_PRICE_CACHE_TTL = 900  # 15 minutes


def get_price_data(symbol: str, days: int = 90) -> pd.DataFrame:
    """
    Fetch OHLCV data from NSE via jugaad-data.
    Falls back to yfinance if jugaad-data fails.

    Returns DataFrame with columns: Date, Open, High, Low, Close, Volume
    """
    cache_key = f"{symbol}_{days}"
    cached = _price_cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < _PRICE_CACHE_TTL:
        return cached["df"].copy()

    df = _fetch_jugaad(symbol, days)
    if df is None or df.empty:
        print(f"[screener] jugaad-data failed for {symbol}, trying yfinance…")
        df = _fetch_yfinance(symbol, days)

    if df is None or df.empty:
        raise ValueError(f"No price data available for {symbol}")

    _price_cache[cache_key] = {"df": df, "ts": time.time()}
    return df.copy()


def _fetch_jugaad(symbol: str, days: int) -> pd.DataFrame | None:
    """Fetch from NSE via jugaad-data."""
    try:
        from jugaad_data.nse import stock_df

        end = date.today()
        start = end - timedelta(days=days)
        raw = stock_df(symbol=symbol, from_date=start, to_date=end, series="EQ")

        if raw.empty:
            return None

        # jugaad-data returns duplicate column names (e.g. two "Close", two "Volume")
        # We need to pick the right ones by position/content
        cols = list(raw.columns)
        cols_lower = [str(c).lower() for c in cols]

        # Build a clean DataFrame by selecting specific columns
        result = pd.DataFrame()

        # Date — first date-like column
        for i, cl in enumerate(cols_lower):
            if "date" in cl:
                result["Date"] = raw.iloc[:, i]
                break

        # OHLC — pick first occurrence of each
        for target, keywords in [
            ("Open", ("open",)),
            ("High", ("high",)),
            ("Low", ("low",)),
        ]:
            for i, cl in enumerate(cols_lower):
                if cl in keywords:
                    result[target] = pd.to_numeric(raw.iloc[:, i], errors="coerce")
                    break

        # Close — use "CLOSE" (the official close), which is typically the first "close" col
        # jugaad-data has "CLOSE" and "ltp" both mapping to Close
        for i, cl in enumerate(cols_lower):
            if cl == "close":
                result["Close"] = pd.to_numeric(raw.iloc[:, i], errors="coerce")
                break

        # Volume — use the first large volume column (total traded qty, not delivery qty)
        # The first "volume" column in jugaad-data is total traded quantity
        for i, cl in enumerate(cols_lower):
            if cl in ("volume", "total traded quantity"):
                vol = pd.to_numeric(raw.iloc[:, i], errors="coerce")
                # Pick the one with larger values (total traded > delivery trades)
                if "Volume" not in result.columns or vol.mean() > result["Volume"].mean():
                    result["Volume"] = vol
                break

        if "Close" not in result.columns:
            print(f"[screener] jugaad-data: no Close column found in {cols}")
            return None

        # Sort by date ascending
        if "Date" in result.columns:
            result = result.sort_values("Date").reset_index(drop=True)

        return result

    except ImportError:
        print("[screener] jugaad-data not installed")
        return None
    except Exception as exc:
        print(f"[screener] jugaad-data error for {symbol}: {exc}")
        return None


def _fetch_yfinance(symbol: str, days: int) -> pd.DataFrame | None:
    """Fallback: fetch from Yahoo Finance."""
    try:
        import yfinance as yf

        nse_symbol = f"{symbol}.NS"
        period = "3mo" if days <= 90 else "6mo"
        ticker = yf.Ticker(nse_symbol)
        hist = ticker.history(period=period)

        if hist.empty:
            return None

        hist = hist.reset_index()
        hist = hist.rename(columns={"Date": "Date"})
        return hist.tail(days)

    except Exception as exc:
        print(f"[screener] yfinance error for {symbol}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Fundamental data (yfinance only — jugaad-data doesn't have fundamentals)
# ---------------------------------------------------------------------------

_fund_cache: dict[str, dict] = {}
_FUND_CACHE_TTL = 3600  # 1 hour


def get_fundamental_data(symbol: str) -> dict:
    """
    Fetch fundamental metrics from yfinance.
    Returns dict with pe_ratio, market_cap, 52w_high, 52w_low, sector, etc.
    """
    cached = _fund_cache.get(symbol)
    if cached and (time.time() - cached["ts"]) < _FUND_CACHE_TTL:
        return cached["data"]

    data = _fetch_fundamentals_yf(symbol)
    _fund_cache[symbol] = {"data": data, "ts": time.time()}
    return data


def _fetch_fundamentals_yf(symbol: str) -> dict:
    """Fetch fundamentals from yfinance."""
    try:
        import yfinance as yf
        info = yf.Ticker(f"{symbol}.NS").info

        mktcap = info.get("marketCap", "N/A")
        if isinstance(mktcap, (int, float)):
            mktcap_display = f"₹{mktcap / 1e7:.1f} Cr"
        else:
            mktcap_display = "N/A"

        return {
            "pe_ratio": info.get("trailingPE", "N/A"),
            "market_cap": mktcap,
            "market_cap_display": mktcap_display,
            "52w_high": info.get("fiftyTwoWeekHigh", "N/A"),
            "52w_low": info.get("fiftyTwoWeekLow", "N/A"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "current_price": info.get("currentPrice", "N/A"),
            "book_value": info.get("bookValue", "N/A"),
            "dividend_yield": info.get("dividendYield", "N/A"),
        }
    except Exception as exc:
        print(f"[screener] yfinance fundamentals error for {symbol}: {exc}")
        return {
            "pe_ratio": "N/A", "market_cap": "N/A", "market_cap_display": "N/A",
            "52w_high": "N/A", "52w_low": "N/A", "sector": "N/A",
            "industry": "N/A", "current_price": "N/A", "book_value": "N/A",
            "dividend_yield": "N/A",
        }


# ---------------------------------------------------------------------------
# Technical indicator computation (using pandas_ta)
# ---------------------------------------------------------------------------

def _compute_indicators(df: pd.DataFrame) -> dict:
    """
    Compute all technical indicators using pandas_ta.
    Returns dict of raw indicator values.
    """
    import pandas_ta as ta

    indicators = {}

    close = df["Close"].astype(float)
    high = df["High"].astype(float) if "High" in df.columns else close
    low = df["Low"].astype(float) if "Low" in df.columns else close
    volume = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series([0] * len(df))

    # RSI (14-period)
    rsi = ta.rsi(close, length=14)
    if rsi is not None and not rsi.empty:
        indicators["rsi"] = round(float(rsi.iloc[-1]), 2)
        indicators["rsi_prev"] = round(float(rsi.iloc[-2]), 2) if len(rsi) > 1 else indicators["rsi"]

    # MACD (12, 26, 9)
    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    if macd_df is not None and not macd_df.empty:
        macd_cols = macd_df.columns.tolist()
        indicators["macd"] = round(float(macd_df[macd_cols[0]].iloc[-1]), 2)
        indicators["macd_signal"] = round(float(macd_df[macd_cols[1]].iloc[-1]), 2)
        indicators["macd_hist"] = round(float(macd_df[macd_cols[2]].iloc[-1]), 2)
        if len(macd_df) > 1:
            indicators["macd_hist_prev"] = round(float(macd_df[macd_cols[2]].iloc[-2]), 2)

    # EMA (10, 20, 50, 200)
    for period in [10, 20, 50, 200]:
        ema = ta.ema(close, length=period)
        if ema is not None and not ema.empty and not pd.isna(ema.iloc[-1]):
            indicators[f"ema_{period}"] = round(float(ema.iloc[-1]), 2)

    # Bollinger Bands (20, 2)
    bbands = ta.bbands(close, length=20, std=2)
    if bbands is not None and not bbands.empty:
        bb_cols = bbands.columns.tolist()
        indicators["bb_lower"] = round(float(bbands[bb_cols[0]].iloc[-1]), 2)
        indicators["bb_mid"] = round(float(bbands[bb_cols[1]].iloc[-1]), 2)
        indicators["bb_upper"] = round(float(bbands[bb_cols[2]].iloc[-1]), 2)

    # ADX (14)
    adx_df = ta.adx(high, low, close, length=14)
    if adx_df is not None and not adx_df.empty:
        adx_cols = adx_df.columns.tolist()
        indicators["adx"] = round(float(adx_df[adx_cols[0]].iloc[-1]), 2)

    # Stochastic RSI
    stoch_rsi = ta.stochrsi(close, length=14)
    if stoch_rsi is not None and not stoch_rsi.empty:
        stoch_cols = stoch_rsi.columns.tolist()
        indicators["stoch_rsi_k"] = round(float(stoch_rsi[stoch_cols[0]].iloc[-1]), 2)
        indicators["stoch_rsi_d"] = round(float(stoch_rsi[stoch_cols[1]].iloc[-1]), 2)

    # Volume analysis
    if float(volume.sum()) > 0:
        vol_sma20 = ta.sma(volume, length=20)
        if vol_sma20 is not None and not vol_sma20.empty and not pd.isna(vol_sma20.iloc[-1]):
            current_vol = float(volume.iloc[-1])
            avg_vol = float(vol_sma20.iloc[-1])
            indicators["volume_current"] = int(current_vol)
            indicators["volume_avg_20d"] = int(avg_vol)
            indicators["volume_ratio"] = round(current_vol / avg_vol, 2) if avg_vol > 0 else 1.0

    # Current price info
    indicators["current_price"] = round(float(close.iloc[-1]), 2)
    if len(close) > 1:
        prev_close = float(close.iloc[-2])
        indicators["prev_close"] = round(prev_close, 2)
        change_pct = ((close.iloc[-1] - prev_close) / prev_close * 100) if prev_close > 0 else 0
        indicators["change_pct"] = round(float(change_pct), 2)

    return indicators


# ---------------------------------------------------------------------------
# Signal generation from indicators
# ---------------------------------------------------------------------------

def _generate_signals(indicators: dict) -> list[Signal]:
    """Interpret indicator values into actionable signals."""
    signals = []

    # --- RSI ---
    rsi = indicators.get("rsi")
    if rsi is not None:
        if rsi < 30:
            signals.append(Signal("RSI_Oversold", "bullish", 0.8,
                                  f"RSI at {rsi} — oversold territory, potential bounce"))
        elif rsi > 70:
            signals.append(Signal("RSI_Overbought", "bearish", 0.8,
                                  f"RSI at {rsi} — overbought territory, potential pullback"))
        elif rsi < 45:
            signals.append(Signal("RSI_Weak", "bearish", 0.4,
                                  f"RSI at {rsi} — below neutral, weak momentum"))
        elif rsi > 55:
            signals.append(Signal("RSI_Strong", "bullish", 0.4,
                                  f"RSI at {rsi} — above neutral, positive momentum"))
        else:
            signals.append(Signal("RSI_Neutral", "neutral", 0.2,
                                  f"RSI at {rsi} — neutral zone"))

    # --- MACD ---
    macd_hist = indicators.get("macd_hist")
    macd_hist_prev = indicators.get("macd_hist_prev")
    if macd_hist is not None:
        if macd_hist > 0 and (macd_hist_prev is not None and macd_hist_prev <= 0):
            signals.append(Signal("MACD_Bullish_Cross", "bullish", 0.9,
                                  "MACD histogram crossed above zero — bullish crossover"))
        elif macd_hist < 0 and (macd_hist_prev is not None and macd_hist_prev >= 0):
            signals.append(Signal("MACD_Bearish_Cross", "bearish", 0.9,
                                  "MACD histogram crossed below zero — bearish crossover"))
        elif macd_hist > 0:
            signals.append(Signal("MACD_Bullish", "bullish", 0.5,
                                  f"MACD histogram positive ({macd_hist}) — bullish momentum"))
        else:
            signals.append(Signal("MACD_Bearish", "bearish", 0.5,
                                  f"MACD histogram negative ({macd_hist}) — bearish momentum"))

    # --- EMA Crossovers ---
    ema_10 = indicators.get("ema_10")
    ema_20 = indicators.get("ema_20")
    ema_50 = indicators.get("ema_50")
    ema_200 = indicators.get("ema_200")
    price = indicators.get("current_price")

    if ema_10 and ema_20:
        if ema_10 > ema_20:
            signals.append(Signal("EMA_Short_Bullish", "bullish", 0.6,
                                  f"EMA 10 ({ema_10}) above EMA 20 ({ema_20}) — short-term uptrend"))
        else:
            signals.append(Signal("EMA_Short_Bearish", "bearish", 0.6,
                                  f"EMA 10 ({ema_10}) below EMA 20 ({ema_20}) — short-term downtrend"))

    if ema_50 and ema_200:
        if ema_50 > ema_200:
            signals.append(Signal("Golden_Cross", "bullish", 0.8,
                                  f"EMA 50 ({ema_50}) above EMA 200 ({ema_200}) — golden cross (bullish)"))
        else:
            signals.append(Signal("Death_Cross", "bearish", 0.8,
                                  f"EMA 50 ({ema_50}) below EMA 200 ({ema_200}) — death cross (bearish)"))

    # Price relative to EMAs
    if price and ema_50:
        if price > ema_50:
            signals.append(Signal("Price_Above_EMA50", "bullish", 0.5,
                                  f"Price ({price}) above EMA 50 ({ema_50})"))
        else:
            signals.append(Signal("Price_Below_EMA50", "bearish", 0.5,
                                  f"Price ({price}) below EMA 50 ({ema_50})"))

    # --- Bollinger Bands ---
    bb_lower = indicators.get("bb_lower")
    bb_upper = indicators.get("bb_upper")
    if price and bb_lower and bb_upper:
        if price <= bb_lower:
            signals.append(Signal("BB_Oversold", "bullish", 0.7,
                                  f"Price at lower Bollinger Band ({bb_lower}) — potential bounce"))
        elif price >= bb_upper:
            signals.append(Signal("BB_Overbought", "bearish", 0.7,
                                  f"Price at upper Bollinger Band ({bb_upper}) — potential pullback"))

    # --- ADX (trend strength) ---
    adx = indicators.get("adx")
    if adx is not None:
        if adx > 25:
            signals.append(Signal("ADX_Strong_Trend", "neutral", 0.6,
                                  f"ADX at {adx} — strong trend in place"))
        else:
            signals.append(Signal("ADX_Weak_Trend", "neutral", 0.3,
                                  f"ADX at {adx} — weak/no clear trend"))

    # --- Volume ---
    vol_ratio = indicators.get("volume_ratio")
    if vol_ratio is not None:
        if vol_ratio > 2.0:
            signals.append(Signal("Volume_Spike", "neutral", 0.7,
                                  f"Volume {vol_ratio:.1f}x above 20-day average — unusual activity"))
        elif vol_ratio > 1.5:
            signals.append(Signal("Volume_High", "neutral", 0.4,
                                  f"Volume {vol_ratio:.1f}x above average — above-normal interest"))
        elif vol_ratio < 0.5:
            signals.append(Signal("Volume_Low", "neutral", 0.3,
                                  f"Volume {vol_ratio:.1f}x of average — low participation"))

    # --- Stochastic RSI ---
    stoch_k = indicators.get("stoch_rsi_k")
    stoch_d = indicators.get("stoch_rsi_d")
    if stoch_k is not None:
        if stoch_k < 20:
            signals.append(Signal("StochRSI_Oversold", "bullish", 0.6,
                                  f"Stochastic RSI at {stoch_k} — oversold"))
        elif stoch_k > 80:
            signals.append(Signal("StochRSI_Overbought", "bearish", 0.6,
                                  f"Stochastic RSI at {stoch_k} — overbought"))

    return signals


def _compute_overall_score(signals: list[Signal]) -> tuple[float, str]:
    """
    Compute weighted average score from signals.
    Returns (score, direction) where score is -1.0 to +1.0.
    """
    if not signals:
        return 0.0, "neutral"

    total_weight = 0.0
    weighted_sum = 0.0

    for signal in signals:
        weight = signal.strength
        if signal.direction == "bullish":
            weighted_sum += weight
        elif signal.direction == "bearish":
            weighted_sum -= weight
        # neutral signals don't affect the score
        total_weight += weight

    if total_weight == 0:
        return 0.0, "neutral"

    score = weighted_sum / total_weight  # normalized to -1..+1

    if score > 0.15:
        direction = "bullish"
    elif score < -0.15:
        direction = "bearish"
    else:
        direction = "neutral"

    return round(score, 3), direction


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def screen_stock(symbol: str) -> ScreeningResult:
    """
    Run full technical screening on a single NSE stock.

    Fetches 90 days of price data, computes RSI, MACD, EMA crossovers,
    Bollinger Bands, ADX, volume analysis, and Stochastic RSI.

    Returns ScreeningResult with signals, overall direction, and raw indicators.
    """
    symbol = symbol.upper().strip()
    print(f"[screener] Screening {symbol}…")

    df = get_price_data(symbol, days=90)
    indicators = _compute_indicators(df)
    signals = _generate_signals(indicators)
    score, direction = _compute_overall_score(signals)

    # Price summary
    close = df["Close"].astype(float)
    price_summary = {
        "current_price": indicators.get("current_price", 0),
        "change_pct": indicators.get("change_pct", 0),
        "high_90d": round(float(close.max()), 2),
        "low_90d": round(float(close.min()), 2),
        "data_points": len(df),
    }

    result = ScreeningResult(
        symbol=symbol,
        signals=signals,
        overall_direction=direction,
        overall_score=score,
        price_data_summary=price_summary,
        indicators=indicators,
    )

    print(f"[screener] {symbol}: {direction} (score={score:.3f}, {len(signals)} signals)")
    return result


def get_price_summary_for_prompt(symbol: str) -> str:
    """
    Return a compact text summary of price data + indicators for LLM prompts.
    Used by analyzer.py to enrich the AI agent prompts.
    """
    try:
        result = screen_stock(symbol)
        lines = [f"Technical Screening for {symbol}:"]
        lines.append(f"Overall: {result.overall_direction.upper()} (score: {result.overall_score:+.2f})")
        lines.append("")

        # Key indicators
        ind = result.indicators
        if "rsi" in ind:
            lines.append(f"RSI(14): {ind['rsi']}")
        if "macd" in ind:
            lines.append(f"MACD: {ind['macd']}, Signal: {ind.get('macd_signal', 'N/A')}, Hist: {ind.get('macd_hist', 'N/A')}")
        for period in [10, 20, 50, 200]:
            key = f"ema_{period}"
            if key in ind:
                lines.append(f"EMA {period}: {ind[key]}")
        if "adx" in ind:
            lines.append(f"ADX: {ind['adx']}")
        if "volume_ratio" in ind:
            lines.append(f"Volume Ratio (vs 20d avg): {ind['volume_ratio']:.1f}x")
        lines.append("")

        # Top signals
        lines.append("Signals:")
        for sig in result.signals:
            arrow = "+" if sig.direction == "bullish" else ("-" if sig.direction == "bearish" else "~")
            lines.append(f"  [{arrow}] {sig.description}")

        return "\n".join(lines)

    except Exception as exc:
        return f"Technical screening unavailable for {symbol}: {exc}"
