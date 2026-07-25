"""
seeds.py — Seed the unified strategy registry (strategy_defs table).

Sources merged into one registry:
    1. 13 predefined F&O strategies   (data.predefined_strategies.STRATEGIES)
    2. 5  IT-Bear strategies          (hardcoded below)
    3. Legacy NL-builder strategies   (db tables: strategies + rules)
    4. 2  backtestable Phase-D seeds  (MCX pre-US reversal, index premium expansion)

seed_all() is idempotent: a slug that already exists is skipped, never overwritten.
"""

import aiosqlite

from db.database import _get_db
from marketplace.registry import _insert_row, _slug_exists


def _cond(indicator: str, operator: str, value, note: str = "") -> dict:
    """Build one condition element {indicator, operator, value, note}."""
    return {"indicator": indicator, "operator": operator, "value": value, "note": note}


def _direction_from_best_for(text: str) -> str:
    t = (text or "").lower()
    if "bull" in t:
        return "bullish"
    if "bear" in t:
        return "bearish"
    return "neutral"


# ---------------------------------------------------------------------------
# 1) Predefined F&O strategies (13)
# ---------------------------------------------------------------------------

def _predefined_seeds() -> list[dict]:
    from data.predefined_strategies import STRATEGIES

    seeds = []
    for s in STRATEGIES:
        seeds.append({
            "slug": s["id"],
            "name": s["name"],
            "source": "predefined",
            "category": "options",
            "market": "IN",
            "direction": _direction_from_best_for(s.get("best_for", "")),
            "description": s.get("description", ""),
            "entry_conditions": [
                _cond(r.get("indicator", ""), "raw", r.get("condition", ""),
                      r.get("description", ""))
                for r in s.get("entry_rules", [])
            ],
            "exit_conditions": [
                _cond(r.get("type", ""), "raw", r.get("value", ""))
                for r in s.get("exit_rules", [])
            ],
            "legs": s.get("legs", []),
            "config": {
                "win_rate": s.get("win_rate"),
                "capital": s.get("capital"),
                "max_profit": s.get("max_profit"),
                "max_loss": s.get("max_loss"),
                "best_for": s.get("best_for"),
            },
            "risk": s.get("risk"),
            "tags": [],
            "is_editable": 0,
        })
    return seeds


# ---------------------------------------------------------------------------
# 2) IT-Bear strategies (5)
# ---------------------------------------------------------------------------

def _it_bear_seeds() -> list[dict]:
    common = {
        "source": "it_bear",
        "market": "IN",
        "direction": "bearish",
        "category": "options",
        "is_editable": 0,
        "tags": [],
    }
    return [
        {
            **common,
            "slug": "it_long_put_breakdown",
            "name": "Long Put (Technical Breakdown)",
            "description": (
                "Buy puts on IT names breaking down technically: price below "
                "50DMA, weak RSI, negative sector relative strength and 5-day return."
            ),
            "risk": "medium",
            "entry_conditions": [
                _cond("price", "lt", "50dma"),
                _cond("rsi", "lt", 45),
                _cond("sector_rs_5d", "lt", -2),
                _cond("return_5d", "lt", -3, "3 of 4 required"),
            ],
            "exit_conditions": [
                _cond("profit_target", "raw", "50% premium gain"),
                _cond("stop", "raw", "-50% premium"),
                _cond("time", "raw", "reassess at 30 days"),
            ],
            "legs": [],
            "config": {},
        },
        {
            **common,
            "slug": "it_pre_earnings_put",
            "name": "Pre-Earnings Long Put",
            "description": (
                "Buy puts 1-3 weeks before earnings on IT names that missed or "
                "cut guidance last quarter, while IV percentile is still reasonable."
            ),
            "risk": "medium",
            "entry_conditions": [
                _cond("earnings_days", "between", [7, 21]),
                _cond("last_quarter", "raw", "missed estimates or guidance cut"),
                _cond("rsi", "lt", 50),
                _cond("iv_percentile", "lt", 70),
            ],
            "exit_conditions": [
                _cond("profit", "raw", "50% gain"),
                _cond("stop", "raw", "-50%"),
                _cond("time", "raw", "exit 1 day before earnings"),
            ],
            "legs": [],
            "config": {},
        },
        {
            **common,
            "slug": "it_bear_put_spread",
            "name": "Bear Put Spread",
            "description": (
                "Debit put spread on weak IT names: buy ATM put, sell 5% OTM put "
                "to reduce cost."
            ),
            "risk": "medium",
            "entry_conditions": [
                _cond("sector_rs", "lt", 0),
                _cond("price", "lt", "20dma"),
                _cond("rsi", "lt", 50),
            ],
            "exit_conditions": [],
            "legs": [
                {"action": "buy", "type": "PE", "strike": "ATM",
                 "label": "Buy ATM PE"},
                {"action": "sell", "type": "PE", "strike": "5% OTM",
                 "label": "Sell 5% OTM PE"},
            ],
            "config": {},
        },
        {
            **common,
            "slug": "it_bear_call_spread",
            "name": "Bear Call Spread (Credit)",
            "description": (
                "Credit call spread when IV is elevated: sell ATM call, buy 5% OTM "
                "call. Profits if the stock stays flat or falls."
            ),
            "risk": "medium",
            "entry_conditions": [
                _cond("iv_percentile", "gt", 50),
                _cond("earnings_week", "eq", False),
                _cond("sector_rs", "lt", 0),
            ],
            "exit_conditions": [
                _cond("profit", "raw", "50% of credit"),
                _cond("stop", "raw", "2x credit"),
            ],
            "legs": [
                {"action": "sell", "type": "CE", "strike": "ATM",
                 "label": "Sell ATM CE"},
                {"action": "buy", "type": "CE", "strike": "5% OTM",
                 "label": "Buy 5% OTM CE"},
            ],
            "config": {},
        },
        {
            **common,
            "slug": "it_nifty_futures_short",
            "name": "Short NIFTY IT Futures",
            "description": (
                "Short NIFTY IT index futures when the sector trades below both "
                "the 50DMA and 200DMA with a strong bearish thesis score."
            ),
            "risk": "high",
            "entry_conditions": [
                _cond("price", "lt", "50dma"),
                _cond("price", "lt", "200dma"),
                _cond("sector_rs_20d", "lt", -5),
                _cond("thesis_score", "gt", 70),
            ],
            "exit_conditions": [],
            "legs": [],
            "config": {},
        },
    ]


# ---------------------------------------------------------------------------
# 3) Legacy NL-builder strategies (db: strategies + rules)
# ---------------------------------------------------------------------------

async def _legacy_custom_seeds(db) -> list[dict]:
    seeds = []
    strategy_rows = await db.execute_fetchall(
        "SELECT * FROM strategies ORDER BY id"
    )
    for s in strategy_rows:
        s = dict(s)
        rule_rows = await db.execute_fetchall(
            "SELECT * FROM rules WHERE strategy_id = ? ORDER BY id", (s["id"],)
        )
        entry = [
            _cond(
                r["indicator"],
                r["operator"],
                r["value"] if r["value"] is not None else r["value_text"],
            )
            for r in (dict(r) for r in rule_rows)
        ]
        seeds.append({
            "slug": f"custom-{s['id']}",
            "name": s["name"],
            "source": "custom",
            "category": "screening",
            "market": "IN",
            "direction": None,
            "description": s.get("raw_input") or s.get("description") or "",
            "entry_conditions": entry,
            "exit_conditions": [],
            "legs": [],
            "config": {},
            "risk": None,
            "tags": [],
            "is_editable": 1,
        })
    return seeds


# ---------------------------------------------------------------------------
# 4) Backtestable Phase-D seeds (2) — engine-ready
# ---------------------------------------------------------------------------

def _phase_d_seeds() -> list[dict]:
    mcx = {
        "slug": "mcx_pre_us_reversal",
        "name": "MCX Pre-US Reversal",
        "source": "predefined",
        "category": "commodity",
        "market": "IN",
        "direction": "any",
        "risk": "medium",
        "tags": ["backtestable", "doc"],
        "is_editable": 1,
        "description": (
            "Fade a strong 9:00-18:10 IST one-sided commodity move during the "
            "18:10-18:55 US-liquidity window. Target 0.20-0.35%, stop 0.15-0.25%, "
            "hard exit 19:00. One trade per commodity per day, no averaging, "
            "skip major US event days."
        ),
        "entry_conditions": [
            _cond("day_trend_pct", "gte",
                  "per-commodity threshold (Gold 0.35 / Silver 0.50 / Crude 0.60 / NG 0.80)",
                  "absolute 9:00→18:10 move"),
            _cond("vwap_stretch", "gte", "0.4 ATR", "price stretched from VWAP"),
            _cond("time", "time_window", "18:10-18:55 IST", "entry windows"),
            _cond("confirmation", "raw",
                  "opposite candle + break of prev bar extreme",
                  "reversal confirmation"),
            _cond("event_day", "eq", False, "skip CPI/Fed/NFP/inventory days"),
        ],
        "exit_conditions": [
            _cond("target", "gte", "0.25%", "premium of entry"),
            _cond("stop", "lte", "-0.20%"),
            _cond("time", "raw", "19:00 IST hard exit"),
        ],
        "legs": [],
        "config": {
            "commodities": {
                "GOLD": {"threshold_pct": 0.35},
                "SILVER": {"threshold_pct": 0.5},
                "CRUDE": {"threshold_pct": 0.6},
                "NATURALGAS": {"threshold_pct": 0.8},
            },
            "symbol_map_proxy": {
                "GC=F": "GOLD",
                "SI=F": "SILVER",
                "CL=F": "CRUDE",
                "NG=F": "NATURALGAS",
            },
            "session_start": "09:00",
            "trend_measure_until": "18:10",
            "entry_windows": [
                ["18:10", "18:25"],
                ["18:25", "18:40"],
                ["18:40", "18:55"],
            ],
            "enabled_windows": [0, 1, 2],
            "vwap_stretch_min_atr": 0.4,
            "confirmation": {
                "opposite_candle": True,
                "break_prev_extreme": True,
            },
            "target_pct": 0.25,
            "stop_pct": 0.2,
            "hard_exit": "19:00",
            "max_trades_per_commodity_per_day": 1,
            "averaging": False,
            "avoid_event_days": [],
            "partial_booking": {
                "enabled": False,
                "book_at_pct": 0.2,
                "book_fraction": 0.5,
            },
            "costs": {
                # Proxy backtests run in price POINTS with qty=1, so a flat INR
                # fee would dwarf the ~10-point moves. Keep costs bps-only until
                # real MCX data + contract multipliers land (then restore ~₹40).
                "per_trade_inr": 0,
                "slippage_bps": 2,
            },
        },
    }

    index_premium = {
        "slug": "index_premium_expansion",
        "name": "Index Options Last-15-Min Premium Expansion",
        "source": "predefined",
        "category": "options",
        "market": "IN",
        "direction": "any",
        "risk": "high",
        "tags": ["backtestable", "doc"],
        "is_editable": 1,
        "description": (
            "Buy ATM index option at 15:05-15:15 when the day is clearly "
            "directional, VWAP supports the bias, VIX is not falling sharply, "
            "and 2-5 days remain to expiry. Exit +8% / -5% on premium or hard "
            "exit 15:27. Fills modeled at synthetic ask/bid (Black-Scholes + "
            "India VIX + modeled spread)."
        ),
        "entry_conditions": [
            _cond("day_return_pct", "raw",
                  ">= +0.35% call bias / <= -0.35% put bias, avoid -0.25..+0.25",
                  "measured at 15:00"),
            _cond("vwap", "raw", "price above VWAP for calls, below for puts"),
            _cond("vix", "raw", "flat or rising (avoid if falling > 3%)",
                  "daily India VIX"),
            _cond("days_to_expiry", "between", [2, 5], "skip expiry & expiry-1"),
            _cond("time", "time_window", "15:05-15:15 IST",
                  "no fresh entry after 15:20"),
        ],
        "exit_conditions": [
            _cond("target", "gte", "+8% premium"),
            _cond("stop", "lte", "-5% premium"),
            _cond("time", "raw", "15:27 hard exit, never carry overnight"),
        ],
        "legs": [],
        "config": {
            "indices": ["NIFTY"],
            "proxy_symbols": {
                "NIFTY": "^NSEI",
                "BANKNIFTY": "^NSEBANK",
            },
            "expiry_weekday": {
                "NIFTY": 1,
                "BANKNIFTY": 3,
            },
            "min_days_to_expiry": 2,
            "max_days_to_expiry": 5,
            "decision_time": "15:00",
            "day_return_call_min_pct": 0.35,
            "day_return_put_min_pct": -0.35,
            "avoid_band_pct": [-0.25, 0.25],
            "require_vwap_support": True,
            "vix_filter": {
                "mode": "daily_flat_or_rising",
                "avoid_if_falling_pct": -3,
            },
            "entry_window": ["15:05", "15:15"],
            "no_entry_after": "15:20",
            "hard_exit": "15:27",
            "target_premium_pct": 8,
            "stop_premium_pct": 5,
            "basket": "conservative",
            "strike_step": {
                "NIFTY": 50,
                "BANKNIFTY": 100,
            },
            "lot_size": {
                "NIFTY": 75,
                "BANKNIFTY": 35,
            },
            "pricing": {
                "risk_free_rate": 0.065,
                "iv_source": "india_vix_daily",
                "skew_bump_pct": 0,
                "spread_pct_each_side": 0.75,
                "min_spread_rs": 0.3,
            },
            "costs": {
                "per_trade_inr": 50,
                "slippage_bps": 0,
            },
        },
    }

    return [mcx, index_premium]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def seed_all() -> dict:
    """Seed strategy_defs from all sources. Idempotent (skips existing slugs).

    Returns {"seeded": n, "skipped": n}.
    """
    seeds = _predefined_seeds() + _it_bear_seeds() + _phase_d_seeds()

    seeded = 0
    skipped = 0
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        seeds += await _legacy_custom_seeds(db)

        for seed in seeds:
            if await _slug_exists(db, seed["slug"]):
                skipped += 1
                continue
            await _insert_row(db, seed)
            seeded += 1

        await db.commit()

    return {"seeded": seeded, "skipped": skipped}
