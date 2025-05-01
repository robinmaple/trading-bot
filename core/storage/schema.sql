-- core/storage/schema.sql
-- Fixed schema with proper SQLite syntax

-- Global Configuration
CREATE TABLE IF NOT EXISTS config (
    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Updated brokerages table with flexible credential storage
CREATE TABLE IF NOT EXISTS brokerages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    token_url TEXT,
    api_endpoint TEXT,
    -- Authentication fields (all encrypted)
    client_id TEXT,        -- For IBKR, TD Ameritrade, etc.
    client_secret TEXT,    -- For IBKR, TD Ameritrade, etc.
    api_key TEXT,          -- For Alpaca, etc.
    refresh_token TEXT,    -- For Questrade, TD Ameritrade, etc.
    access_token TEXT,
    -- Metadata
    auth_type TEXT NOT NULL CHECK(auth_type IN ('client_credentials', 'authorization_code', 'api_key')),
    token_expiry TIMESTAMP,
    last_token_update TIMESTAMP,
    credentials_encrypted BOOLEAN DEFAULT 1,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Accounts
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    brokerage_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    bp_override REAL,
    risk_per_trade REAL DEFAULT 0.01,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (brokerage_id) REFERENCES brokerages(id) ON DELETE CASCADE,
    UNIQUE(brokerage_id, name)
);


-- Trading Plans
CREATE TABLE IF NOT EXISTS plans (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    name TEXT,
    description TEXT,
    upload_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expiry_time DATETIME,
    status TEXT CHECK(status IN ('pending', 'active', 'completed', 'canceled')) DEFAULT 'pending',
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
);

-- Planned Trades
CREATE TABLE IF NOT EXISTS planned_trades (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    entry_price REAL,
    stop_loss_price REAL,
    take_profit_price REAL,
    quantity INTEGER,
    expiry_date TEXT,
    status TEXT CHECK(status IN ('pending', 'ready', 'executed', 'canceled')) DEFAULT 'pending',
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id) ON DELETE CASCADE
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
    FOREIGN KEY (planned_trade_id) REFERENCES planned_trades(trade_id)
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
    FOREIGN KEY (planned_trade_id) REFERENCES planned_trades(trade_id)
);

-- New encryption key table
CREATE TABLE IF NOT EXISTS encryption_keys (
    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name TEXT NOT NULL UNIQUE,
    key_value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP
);

-- Historical Data Download
CREATE TABLE IF NOT EXISTS symbols (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    last_updated TIMESTAMP
);