"""
mcx_reversal.py — "MCX Pre-US Reversal" engine implementation.

Fade a strong 09:00->18:10 IST one-sided commodity move during the
18:10-18:55 US-liquidity window; hard exit 19:00. Runs on COMEX/NYMEX
proxy symbols (GC=F, CL=F, ...) mapped to MCX commodities via
config["symbol_map_proxy"]. qty=1 unit, so P&L is in PRICE POINTS of the
proxy (the engine treats 1 point = 1 INR — see run assumptions).
"""

from datetime import time as dtime

import pandas as pd


def _t(hhmm, default: dtime | None = None) -> dtime | None:
    """'18:10' -> datetime.time(18, 10). Falls back to default on garbage."""
    try:
        h, m = str(hhmm).strip().split(":")
        return dtime(int(h), int(m))
    except (AttributeError, TypeError, ValueError):
        return default


class McxReversal:
    slug = "mcx_pre_us_reversal"

    def run_day(self, day_df: pd.DataFrame, symbol: str, config: dict, ctx: dict) -> list[dict]:
        """One IST calendar day of 5m bars -> at most one trade dict."""
        if day_df is None or day_df.empty:
            return []
        config = config or {}

        day = day_df.sort_index()
        day_date = day.index[0].date()
        if day_date.isoformat() in (config.get("avoid_event_days") or []):
            return []

        # Symbol -> commodity threshold (skip unmapped symbols).
        commodity = (config.get("symbol_map_proxy") or {}).get(symbol) or symbol
        spec = (config.get("commodities") or {}).get(commodity)
        if not isinstance(spec, dict):
            return []
        thr = float(spec.get("threshold_pct") or 0)
        if thr <= 0:
            return []

        t_start = _t(config.get("session_start"), dtime(9, 0))
        t_trend = _t(config.get("trend_measure_until"), dtime(18, 10))
        t_last_entry = dtime(18, 55)
        t_hard = _t(config.get("hard_exit"), dtime(19, 0))

        # --- Day trend: 09:00 -> 18:10 move (nearest available bars). ---
        session = day.between_time(t_start, t_trend)
        if len(session) < 20:
            return []
        close_start = float(session["close"].iloc[0])
        close_trend = float(session["close"].iloc[-1])
        if not close_start or pd.isna(close_start):
            return []
        trend_pct = (close_trend / close_start - 1.0) * 100.0
        if abs(trend_pct) < thr:
            return []
        direction = "short" if trend_pct > 0 else "long"  # fade the move

        # --- Indicator frame: session start through end of IST day. ---
        watch = day.between_time(t_start, dtime(23, 59))
        if len(watch) < 20:
            return []

        # Cumulative session VWAP (typical price, volume weighted). If volume
        # is absent/zero, fall back to the expanding mean of close.
        tp = (watch["high"] + watch["low"] + watch["close"]) / 3.0
        vol = watch["volume"].fillna(0).astype(float)
        cum_vol = vol.cumsum()
        vwap = (tp * vol).cumsum() / cum_vol.mask(cum_vol <= 0)
        vwap = vwap.fillna(watch["close"].expanding().mean())

        # ATR14 on 5m bars (rolling mean of true range).
        prev_close = watch["close"].shift(1)
        true_range = pd.concat(
            [
                watch["high"] - watch["low"],
                (watch["high"] - prev_close).abs(),
                (watch["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = true_range.rolling(14).mean()

        min_stretch = float(config.get("vwap_stretch_min_atr", 0.4) or 0)
        windows = config.get("entry_windows") or [
            ["18:10", "18:25"], ["18:25", "18:40"], ["18:40", "18:55"],
        ]
        enabled = config.get("enabled_windows")
        if enabled is None:
            enabled = list(range(len(windows)))
        conf_cfg = config.get("confirmation") or {}
        need_opposite = bool(conf_cfg.get("opposite_candle", True))
        need_break = bool(conf_cfg.get("break_prev_extreme", True))

        # --- Scan 18:10-18:55 for stretch + confirmation bar. ---
        times = [ts.time() for ts in watch.index]
        entry_idx = None
        entry_window = None
        entry_stretch = None
        for i in range(1, len(watch)):
            bt = times[i]
            if bt < t_trend or bt > t_last_entry:
                continue

            atr_i = atr.iloc[i]
            vwap_i = vwap.iloc[i]
            if pd.isna(atr_i) or atr_i <= 0 or pd.isna(vwap_i):
                continue
            bar = watch.iloc[i]
            stretch_atr = abs(float(bar["close"]) - float(vwap_i)) / float(atr_i)
            if stretch_atr < min_stretch:
                continue  # keep checking subsequent bars until 18:55

            window_idx = None
            for j, win in enumerate(windows):
                if j not in enabled:
                    continue
                ws, we = _t(win[0]), _t(win[1])
                if ws and we and ws <= bt <= we:
                    window_idx = j
                    break
            if window_idx is None:
                continue

            prev = watch.iloc[i - 1]
            if direction == "short":
                opposite = float(bar["close"]) < float(bar["open"])   # red candle
                breaks_prev = float(bar["low"]) < float(prev["low"])
            else:
                opposite = float(bar["close"]) > float(bar["open"])   # green candle
                breaks_prev = float(bar["high"]) > float(prev["high"])
            if need_opposite and not opposite:
                continue
            if need_break and not breaks_prev:
                continue

            entry_idx, entry_window, entry_stretch = i, window_idx, stretch_atr
            break  # max 1 trade per commodity per day

        if entry_idx is None:
            return []

        entry_ts = watch.index[entry_idx]
        entry_price = float(watch["close"].iloc[entry_idx])
        target_pct = float(config.get("target_pct", 0.25) or 0)
        stop_pct = float(config.get("stop_pct", 0.2) or 0)
        if direction == "short":
            target_price = entry_price * (1 - target_pct / 100.0)
            stop_price = entry_price * (1 + stop_pct / 100.0)
        else:
            target_price = entry_price * (1 + target_pct / 100.0)
            stop_price = entry_price * (1 - stop_pct / 100.0)

        # --- Walk forward: stop checked first when both hit in one bar. ---
        after = watch.iloc[entry_idx + 1:]
        if after.empty:
            return []

        exit_ts = exit_price = exit_reason = None
        for ts, bar in after.iterrows():
            if ts.time() >= t_hard:
                exit_ts, exit_price, exit_reason = ts, float(bar["close"]), "time"
                break
            hi, lo = float(bar["high"]), float(bar["low"])
            if direction == "short":
                if hi >= stop_price:
                    exit_ts, exit_price, exit_reason = ts, stop_price, "stop"
                    break
                if lo <= target_price:
                    exit_ts, exit_price, exit_reason = ts, target_price, "target"
                    break
            else:
                if lo <= stop_price:
                    exit_ts, exit_price, exit_reason = ts, stop_price, "stop"
                    break
                if hi >= target_price:
                    exit_ts, exit_price, exit_reason = ts, target_price, "target"
                    break
        if exit_ts is None:  # data ended before the 19:00 bar
            exit_ts = after.index[-1]
            exit_price = float(after["close"].iloc[-1])
            exit_reason = "time"

        qty = 1.0  # 1 unit of the proxy -> pnl measured in price points
        if direction == "short":
            pnl = (entry_price - exit_price) * qty
        else:
            pnl = (exit_price - entry_price) * qty
        pnl_pct = (pnl / (entry_price * qty) * 100.0) if entry_price else 0.0

        return [{
            "symbol": symbol,
            "direction": direction,
            "entry_ts": entry_ts.isoformat(),
            "entry_price": round(entry_price, 4),
            "exit_ts": exit_ts.isoformat(),
            "exit_price": round(exit_price, 4),
            "qty": qty,
            "pnl": round(pnl, 4),
            "pnl_pct": round(pnl_pct, 4),
            "exit_reason": exit_reason,
            "meta": {
                "day_trend_pct": round(trend_pct, 3),
                "vwap_dist_atr": round(float(entry_stretch), 3),
                "window": entry_window,
            },
        }]
