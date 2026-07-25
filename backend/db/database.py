"""
database.py — SQLite connection + CRUD operations for strategies, rules, and alerts.

Uses aiosqlite for async access from FastAPI.
DB file: backend/data/portfolio.db (gitignored)
"""

import json
from pathlib import Path

import aiosqlite

_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "portfolio.db"
_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


async def init_db() -> None:
    """Create tables if they don't exist. Called on app startup."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        schema = _SCHEMA_PATH.read_text()
        await db.executescript(schema)
        await db.commit()

        # IT-Bear: safely add new columns to trading_config if they don't exist.
        # SQLite ALTER TABLE only supports ADD COLUMN and has no IF NOT EXISTS.
        # We query existing columns first to avoid errors on repeated startups.
        it_bear_columns = {
            "auto_layer_core": "INTEGER DEFAULT 0",
            "auto_layer_tactical": "INTEGER DEFAULT 0",
            "auto_layer_us": "INTEGER DEFAULT 0",
            "auto_layer_hedge": "INTEGER DEFAULT 0",
            "it_bear_enabled": "INTEGER DEFAULT 1",
        }
        existing_cols_rows = await db.execute_fetchall(
            "PRAGMA table_info(trading_config)"
        )
        existing_cols = {row[1] for row in existing_cols_rows}

        for col_name, col_def in it_bear_columns.items():
            if col_name not in existing_cols:
                try:
                    await db.execute(
                        f"ALTER TABLE trading_config ADD COLUMN {col_name} {col_def}"
                    )
                    await db.commit()
                    print(f"[database] Added column trading_config.{col_name}")
                except Exception as e:
                    print(f"[database] Could not add column {col_name}: {e}")

    print(f"[database] Initialized at {_DB_PATH}")


def _get_db():
    """Get a database connection context manager. Use as: async with _get_db() as db:"""
    return aiosqlite.connect(str(_DB_PATH))


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

async def create_strategy(name: str, description: str, raw_input: str) -> int:
    """Insert strategy, return its id."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "INSERT INTO strategies (name, description, raw_input) VALUES (?, ?, ?)",
            (name, description, raw_input),
        )
        await db.commit()
        return cursor.lastrowid


async def get_strategies() -> list[dict]:
    """List all strategies with rule and watchlist counts."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("""
            SELECT s.*,
                   (SELECT COUNT(*) FROM rules WHERE strategy_id = s.id) AS rule_count,
                   (SELECT COUNT(*) FROM watchlist WHERE strategy_id = s.id) AS watchlist_count
            FROM strategies s
            ORDER BY s.created_at DESC
        """)
        return [dict(r) for r in rows]


async def get_strategy(strategy_id: int) -> dict | None:
    """Get strategy with its rules and watchlist."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute_fetchall(
            "SELECT * FROM strategies WHERE id = ?", (strategy_id,)
        )
        if not row:
            return None

        strategy = dict(row[0])

        rules = await db.execute_fetchall(
            "SELECT * FROM rules WHERE strategy_id = ? ORDER BY id", (strategy_id,)
        )
        strategy["rules"] = [dict(r) for r in rules]

        watchlist = await db.execute_fetchall(
            "SELECT * FROM watchlist WHERE strategy_id = ? ORDER BY symbol", (strategy_id,)
        )
        strategy["watchlist"] = [dict(w) for w in watchlist]

        return strategy


async def update_strategy(strategy_id: int, **kwargs) -> bool:
    """Update strategy fields. Returns True if found."""
    allowed = {"name", "description", "is_active"}
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not fields:
        return True

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [strategy_id]

    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"UPDATE strategies SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_strategy(strategy_id: int) -> bool:
    """Delete a strategy and cascade to rules, watchlist."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
        await db.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

async def add_rules(strategy_id: int, rules: list[dict]) -> None:
    """Bulk insert parsed rules for a strategy."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        for rule in rules:
            await db.execute(
                """INSERT INTO rules (strategy_id, indicator, operator, value, value_text, timeframe)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    strategy_id,
                    rule.get("indicator", ""),
                    rule.get("operator", ""),
                    rule.get("value"),
                    rule.get("value_text"),
                    rule.get("timeframe", "daily"),
                ),
            )
        await db.commit()


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

async def add_to_watchlist(strategy_id: int, symbols: list[str]) -> None:
    """Add symbols to a strategy's watchlist (ignores duplicates)."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        for sym in symbols:
            await db.execute(
                "INSERT OR IGNORE INTO watchlist (strategy_id, symbol) VALUES (?, ?)",
                (strategy_id, sym.upper().strip()),
            )
        await db.commit()


# ---------------------------------------------------------------------------
# Strategy execution
# ---------------------------------------------------------------------------

async def run_strategy(strategy_id: int) -> list[dict]:
    """
    Execute a strategy against its watchlist.
    For each symbol, run screening and check if rules are met.
    Returns list of triggered alerts.
    """
    from analysis.screener import screen_stock

    strategy = await get_strategy(strategy_id)
    if not strategy:
        return []

    rules = strategy.get("rules", [])
    watchlist = strategy.get("watchlist", [])
    triggered = []

    for item in watchlist:
        symbol = item["symbol"]
        try:
            result = screen_stock(symbol)
            indicators = result.indicators

            matched_rules = []
            for rule in rules:
                if _check_rule(rule, indicators):
                    matched_rules.append(rule)

            if matched_rules:
                signal_data = json.dumps({
                    "triggered_rules": matched_rules,
                    "indicators": {k: v for k, v in indicators.items()
                                   if k in ("rsi", "macd", "macd_hist", "ema_50", "adx",
                                            "current_price", "volume_ratio")},
                    "overall_direction": result.overall_direction,
                    "overall_score": result.overall_score,
                })

                alert_id = await _create_alert(
                    strategy_id=strategy_id,
                    symbol=symbol,
                    rule_id=matched_rules[0].get("id"),
                    signal_data=signal_data,
                )
                triggered.append({
                    "alert_id": alert_id,
                    "symbol": symbol,
                    "matched_rules": len(matched_rules),
                    "signal_data": signal_data,
                })

        except Exception as exc:
            print(f"[database] Error screening {symbol}: {exc}")

    return triggered


def _check_rule(rule: dict, indicators: dict) -> bool:
    """Check if a single rule is met against current indicator values."""
    indicator = rule.get("indicator", "").upper()
    operator = rule.get("operator", "")
    threshold = rule.get("value")
    value_text = rule.get("value_text", "")

    # Map rule indicators to screener indicator keys
    indicator_map = {
        "RSI": "rsi",
        "MACD": "macd",
        "MACD_HIST": "macd_hist",
        "MACD_HISTOGRAM": "macd_hist",
        "ADX": "adx",
        "EMA_10": "ema_10",
        "EMA_20": "ema_20",
        "EMA_50": "ema_50",
        "EMA_200": "ema_200",
        "PRICE": "current_price",
        "VOLUME": "volume_ratio",
        "VOLUME_RATIO": "volume_ratio",
        "STOCH_RSI": "stoch_rsi_k",
        "BB_UPPER": "bb_upper",
        "BB_LOWER": "bb_lower",
    }

    key = indicator_map.get(indicator)
    if not key or key not in indicators:
        return False

    current = indicators[key]
    if current is None or threshold is None:
        return False

    try:
        current = float(current)
        threshold = float(threshold)
    except (ValueError, TypeError):
        return False

    if operator == "gt":
        return current > threshold
    elif operator == "lt":
        return current < threshold
    elif operator == "gte":
        return current >= threshold
    elif operator == "lte":
        return current <= threshold
    elif operator == "crosses_above":
        # Simplified: just check if currently above
        return current > threshold
    elif operator == "crosses_below":
        return current < threshold

    return False


async def _create_alert(strategy_id: int, symbol: str, rule_id: int | None,
                        signal_data: str) -> int:
    """Create an alert record."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """INSERT INTO alerts (strategy_id, symbol, rule_id, signal_data)
               VALUES (?, ?, ?, ?)""",
            (strategy_id, symbol, rule_id, signal_data),
        )
        await db.commit()
        return cursor.lastrowid


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

async def get_alerts(strategy_id: int | None = None, unread_only: bool = True) -> list[dict]:
    """Get alerts, optionally filtered by strategy and read status."""
    conditions = []
    params = []

    if strategy_id is not None:
        conditions.append("a.strategy_id = ?")
        params.append(strategy_id)
    if unread_only:
        conditions.append("a.is_read = 0")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(f"""
            SELECT a.*, s.name AS strategy_name
            FROM alerts a
            LEFT JOIN strategies s ON a.strategy_id = s.id
            {where}
            ORDER BY a.triggered_at DESC
            LIMIT 100
        """, params)
        return [dict(r) for r in rows]


async def mark_alert_read(alert_id: int) -> bool:
    """Mark an alert as read."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Analysis History
# ---------------------------------------------------------------------------

async def save_analysis(symbol: str, result: dict, screening_data: str = None) -> int:
    """Save an AI analysis result to history. Returns the record id."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """INSERT INTO analysis_history
               (symbol, recommendation, reasoning, trend, confidence, source, screening_data)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                symbol.upper(),
                result.get("recommendation", "Hold"),
                result.get("reasoning", ""),
                result.get("trend", "Neutral"),
                result.get("confidence", 0),
                result.get("source", ""),
                screening_data,
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def get_analysis_history(symbol: str = None, limit: int = 50) -> list[dict]:
    """Get analysis history, optionally filtered by symbol."""
    if symbol:
        query = """SELECT * FROM analysis_history
                   WHERE symbol = ? ORDER BY created_at DESC LIMIT ?"""
        params = (symbol.upper(), limit)
    else:
        query = """SELECT * FROM analysis_history
                   ORDER BY created_at DESC LIMIT ?"""
        params = (limit,)

    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(query, params)
        return [dict(r) for r in rows]


async def get_latest_analysis(symbol: str) -> dict | None:
    """Get the most recent analysis for a symbol."""
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """SELECT * FROM analysis_history
               WHERE symbol = ? ORDER BY created_at DESC LIMIT 1""",
            (symbol.upper(),),
        )
        return dict(rows[0]) if rows else None
