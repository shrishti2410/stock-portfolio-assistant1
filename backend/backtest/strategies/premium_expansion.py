"""
premium_expansion.py — "Index Options Last-15-Min Premium Expansion" engine impl.

Buy a synthetic ATM index option (CE on a clearly-up day / PE on a
clearly-down day, decided at 15:00 IST) inside the 15:05-15:15 entry window,
exit +target% / -stop% on premium or hard exit at 15:27.

Premiums are SYNTHETIC: Black-Scholes marks using the daily India VIX close
as sigma, with a modeled bid/ask spread (see backtest.options_pricer).
Entries fill at the synthetic ask, exits at the synthetic bid.
"""

from datetime import time as dtime

import pandas as pd

from backtest.options_pricer import bs_price, synthetic_quote

TRADING_MINUTES_PER_DAY = 375.0  # 09:15 -> 15:30 IST
_T_FLOOR = 1e-5  # years; keeps BS well-behaved on the last bar


def _t(hhmm, default: dtime | None = None) -> dtime | None:
    """'15:05' -> datetime.time(15, 5). Falls back to default on garbage."""
    try:
        h, m = str(hhmm).strip().split(":")
        return dtime(int(h), int(m))
    except (AttributeError, TypeError, ValueError):
        return default


class PremiumExpansion:
    slug = "index_premium_expansion"

    def run_day(self, day_df: pd.DataFrame, symbol: str, config: dict, ctx: dict) -> list[dict]:
        """One IST calendar day of 5m index bars -> at most one option trade."""
        if day_df is None or day_df.empty:
            return []
        config = config or {}
        ctx = ctx or {}

        # Proxy symbol -> index name (e.g. ^NSEI -> NIFTY); skip unmapped.
        proxy_map = config.get("proxy_symbols") or {}
        index_name = next((k for k, v in proxy_map.items() if v == symbol), None)
        if index_name is None:
            return []
        enabled_indices = config.get("indices")
        if enabled_indices and index_name not in enabled_indices:
            return []

        day = day_df.sort_index().between_time(dtime(9, 15), dtime(15, 30))
        if day.empty:
            return []
        # Need bars covering 09:15 -> ~15:27 (NSE last 5m bar is labeled 15:25).
        if day.index[0].time() > dtime(9, 20) or day.index[-1].time() < dtime(15, 20):
            return []

        day_date = day.index[0].date()

        # --- Days to expiry: next configured expiry weekday (0=Mon..6=Sun). ---
        expiry_wd = (config.get("expiry_weekday") or {}).get(index_name)
        if expiry_wd is None:
            return []
        dte = (int(expiry_wd) - day_date.weekday()) % 7  # today is expiry -> 0
        min_dte = int(config.get("min_days_to_expiry", 2))
        max_dte = int(config.get("max_days_to_expiry", 5))
        if not (min_dte <= dte <= max_dte):
            return []

        # --- Decision at 15:00: day return vs first bar open. ---
        t_decision = _t(config.get("decision_time"), dtime(15, 0))
        upto_decision = day.between_time(dtime(9, 15), t_decision)
        if upto_decision.empty:
            return []
        dec_ts = upto_decision.index[-1]
        if dec_ts.time() < dtime(14, 50):  # decision bar too far from 15:00
            return []
        dec_close = float(upto_decision["close"].iloc[-1])
        first_open = float(day["open"].iloc[0])
        if not first_open or pd.isna(first_open):
            return []
        day_ret_pct = (dec_close / first_open - 1.0) * 100.0

        band = config.get("avoid_band_pct") or [-0.25, 0.25]
        call_min = float(config.get("day_return_call_min_pct", 0.35))
        put_min = float(config.get("day_return_put_min_pct", -0.35))
        if len(band) == 2 and band[0] <= day_ret_pct <= band[1]:
            return []
        if day_ret_pct >= call_min:
            bias = "CE"
        elif day_ret_pct <= put_min:
            bias = "PE"
        else:
            return []

        # --- VWAP support (price above VWAP for CE, below for PE). ---
        if config.get("require_vwap_support", True):
            tp = (day["high"] + day["low"] + day["close"]) / 3.0
            vol = day["volume"].fillna(0).astype(float)
            cum_vol = vol.cumsum()
            vwap = (tp * vol).cumsum() / cum_vol.mask(cum_vol <= 0)
            # Index feeds (^NSEI) often carry zero volume -> expanding close mean.
            vwap = vwap.fillna(day["close"].expanding().mean())
            vwap_dec = float(vwap.loc[:dec_ts].iloc[-1])
            if bias == "CE" and not dec_close > vwap_dec:
                return []
            if bias == "PE" and not dec_close < vwap_dec:
                return []

        # --- VIX filter + sigma. ctx["vix"] = daily close Series indexed by date. ---
        vix_today = vix_prev = None
        vix_series = ctx.get("vix")
        if vix_series is not None and len(vix_series):
            try:
                for idx_date, value in vix_series.dropna().items():
                    if idx_date == day_date:
                        vix_today = float(value)
                    elif idx_date < day_date and (vix_prev is None or idx_date > vix_prev[0]):
                        vix_prev = (idx_date, float(value))
            except (TypeError, ValueError):
                vix_today = vix_prev = None
        vix_prev_val = vix_prev[1] if vix_prev else None

        vix_filter = config.get("vix_filter") or {}
        if (
            vix_filter.get("mode") == "daily_flat_or_rising"
            and vix_today is not None
            and vix_prev_val
        ):
            change_pct = (vix_today / vix_prev_val - 1.0) * 100.0
            if change_pct < float(vix_filter.get("avoid_if_falling_pct", -3)):
                return []

        pricing = config.get("pricing") or {}
        base_vix = vix_today if vix_today is not None else vix_prev_val
        sigma = (base_vix / 100.0) if base_vix else 0.15
        sigma *= 1.0 + float(pricing.get("skew_bump_pct", 0) or 0) / 100.0
        rate = float(pricing.get("risk_free_rate", 0.065))
        spread_pct = float(pricing.get("spread_pct_each_side", 0.75))
        min_spread = float(pricing.get("min_spread_rs", 0.3))

        # --- ATM strike from spot at decision time. ---
        step = float((config.get("strike_step") or {}).get(index_name) or 50)
        strike = round(dec_close / step) * step

        # --- Synthetic premium path from 15:00 to hard exit. ---
        t_hard = _t(config.get("hard_exit"), dtime(15, 27))
        path = day.between_time(t_decision, t_hard)
        if path.empty:
            return []
        path_times = [ts.time() for ts in path.index]

        def mark_at(i: int) -> float:
            bt = path_times[i]
            minutes_to_1530 = max((15 * 60 + 30) - (bt.hour * 60 + bt.minute), 0)
            T = max((dte + minutes_to_1530 / TRADING_MINUTES_PER_DAY) / 365.0, _T_FLOOR)
            return bs_price(float(path["close"].iloc[i]), strike, T, rate, sigma, bias)

        entry_window = config.get("entry_window") or ["15:05", "15:15"]
        t_ew_start = _t(entry_window[0], dtime(15, 5))
        t_ew_end = _t(entry_window[1], dtime(15, 15))
        t_no_entry = _t(config.get("no_entry_after"), dtime(15, 20))

        entry_i = None
        for i, bt in enumerate(path_times):
            if t_ew_start <= bt <= t_ew_end and bt <= t_no_entry:
                entry_i = i
                break
        if entry_i is None:
            return []

        entry_ts = path.index[entry_i]
        entry_mark = mark_at(entry_i)
        entry_bid, entry_ask = synthetic_quote(entry_mark, spread_pct, min_spread)
        entry_price = entry_ask  # buy at modeled ask
        target_pct = float(config.get("target_premium_pct", 8))
        stop_pct = float(config.get("stop_premium_pct", 5))
        target_level = entry_price * (1.0 + target_pct / 100.0)
        stop_level = entry_price * (1.0 - stop_pct / 100.0)

        # --- Track bids on later bars; stop checked before target. ---
        exit_ts = exit_price = exit_reason = None
        last_bid, last_ts = entry_bid, entry_ts
        for i in range(entry_i + 1, len(path)):
            bid, _ask = synthetic_quote(mark_at(i), spread_pct, min_spread)
            last_bid, last_ts = bid, path.index[i]
            if bid <= stop_level:
                exit_ts, exit_price, exit_reason = path.index[i], bid, "stop"
                break
            if bid >= target_level:
                exit_ts, exit_price, exit_reason = path.index[i], bid, "target"
                break
        if exit_ts is None:  # hard exit at the last bar before 15:27
            exit_ts, exit_price, exit_reason = last_ts, last_bid, "time"

        qty = float((config.get("lot_size") or {}).get(index_name) or 1)
        pnl = (exit_price - entry_price) * qty
        pnl_pct = ((exit_price / entry_price - 1.0) * 100.0) if entry_price else 0.0

        return [{
            "symbol": symbol,
            "direction": "long_ce" if bias == "CE" else "long_pe",
            "entry_ts": entry_ts.isoformat(),
            "entry_price": round(entry_price, 2),
            "exit_ts": exit_ts.isoformat(),
            "exit_price": round(exit_price, 2),
            "qty": qty,
            "pnl": round(pnl, 4),
            "pnl_pct": round(pnl_pct, 4),
            "exit_reason": exit_reason,
            "meta": {
                "strike": strike,
                "dte": dte,
                "bias": bias,
                "vix": round(base_vix, 2) if base_vix else None,
                "sigma": round(sigma, 4),
                "spread_pct": spread_pct,
                "spread_rs": round(entry_ask - entry_mark, 2),
                "day_ret_pct": round(day_ret_pct, 3),
                "entry_mark": round(entry_mark, 2),
            },
        }]
