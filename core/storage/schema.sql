-- core/storage/schema.sql
-- Fixed schema with proper syntax

-- Global Configuration
CREATE TABLE IF NOT EXISTS config (
    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    value_type TEXT CHECK(value_type IN ('bool', 'float', 'int', 'str')) DEFAULT 'str',
    description TEXT
);

-- Brokerages
CREATE TABLE IF NOT EXISTS brokerages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    token_url TEXT,
    refresh_token TEXT,
    last_token_update TIMESTAMP,
    api_endpoint TEXT,
    token_expiry TIMESTAMP,
    last_refresh TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Accounts
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    brokerage_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    bp_override REAL,
    FOREIGN KEY (brokerage_id) REFERENCES brokerages(id),
    UNIQUE(brokerage_id, name)
);

-- Trading Plans
CREATE TABLE IF NOT EXISTS plans (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Planned Trades
CREATE TABLE IF NOT EXISTS planned_trades (
    planned_trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    account_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    entry_price REAL,
    stop_loss_price REAL,
    expiry_date DATE,
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
);

-- Executed Trades
CREATE TABLE IF NOT EXISTS executed_trades (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    planned_trade_id INTEGER NOT NULL,
    actual_entry_price REAL NOT NULL,
    actual_quantity INTEGER NOT NULL,
    fees REAL DEFAULT 0,
    status TEXT CHECK(status IN ('filled', 'partial', 'canceled')) NOT NULL,
    execution_time TIMESTAMP NOT NULL,
    close_time TIMESTAMP,
    close_reason TEXT CHECK(close_reason IN ('SL', 'TP', 'EOD', 'MANUAL')),
    pnl REAL,
    FOREIGN KEY (planned_trade_id) REFERENCES planned_trades(planned_trade_id)
);

-- Positions
CREATE TABLE IF NOT EXISTS positions (
    account_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    planned_trade_id INTEGER,
    PRIMARY KEY (account_id, symbol),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id),
    FOREIGN KEY (planned_trade_id) REFERENCES planned_trades(planned_trade_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_planned_account ON planned_trades(account_id);
CREATE INDEX IF NOT EXISTS idx_planned_expiry ON planned_trades(expiry_date);
CREATE INDEX IF NOT EXISTS idx_positions_account ON positions(account_id);