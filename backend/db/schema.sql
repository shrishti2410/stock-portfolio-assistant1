CREATE TABLE IF NOT EXISTS strategies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    raw_input   TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    indicator   TEXT NOT NULL,
    operator    TEXT NOT NULL,
    value       REAL,
    value_text  TEXT,
    timeframe   TEXT DEFAULT 'daily',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    symbol      TEXT NOT NULL,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(strategy_id, symbol)
);

CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id  INTEGER NOT NULL REFERENCES strategies(id),
    symbol       TEXT NOT NULL,
    rule_id      INTEGER REFERENCES rules(id),
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    signal_data  TEXT,
    is_read      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS analysis_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    recommendation  TEXT NOT NULL,
    reasoning       TEXT,
    trend           TEXT,
    confidence      REAL,
    source          TEXT,
    screening_data  TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analysis_symbol ON analysis_history(symbol);
CREATE INDEX IF NOT EXISTS idx_analysis_created ON analysis_history(created_at DESC);
