-- core/storage/init_data.sql
BEGIN TRANSACTION;

-- Print start message
SELECT 'Starting data initialization' AS message;

-- Clear existing data (if needed)
SELECT 'Clearing existing data' AS message;
DELETE FROM positions;
DELETE FROM planned_trades;
DELETE FROM plans;
DELETE FROM accounts;
DELETE FROM brokerages;
DELETE FROM config;

-- Insert Configuration
SELECT 'Inserting configuration' AS message;
INSERT OR REPLACE INTO config (key, value, value_type, description) VALUES
('dry_run', 'TRUE', 'bool', 'Test mode without real trades'),
('risk_of_capital', '0.01', 'float', 'Max % of capital to risk per trade (0.01 = 1%)'),
('profit_to_loss_ratio', '2', 'float', 'Minimum profit target as multiple of risk'),
('available_quantity_ratio', '0.8', 'float', 'Max % of calculated position size to take'),
('daily_loss_limit_percent', '2', 'float', 'Max daily loss before pausing (2%)'),
('weekly_loss_limit_percent', '5', 'float', 'Max weekly loss before pausing (5%)'),
('monthly_loss_limit_percent', '10', 'float', 'Max monthly loss before pausing (10%)'),
('close_trades_buffer_minutes', '5', 'int', 'Minutes before market close to exit trades');

-- Insert Brokerages
SELECT 'Inserting brokerages' AS message;
INSERT OR REPLACE INTO brokerages (name, token_url, api_endpoint, refresh_token) VALUES
('QUESTRADE', 'https://login.questrade.com/oauth2/token', 'https://api.questrade.com', 'B-mtz8jXuyscfPX0HNkNn0rZRg_xK5mC0'),
('IBKR', 'https://api.ibkr.com/v1/api/oauth/token', 'https://api.ibkr.com/v1/api', '');

-- Insert Accounts
SELECT 'Inserting accounts' AS message;
INSERT OR REPLACE INTO accounts (account_id, brokerage_id, name) VALUES
('27348656', 
 (SELECT id FROM brokerages WHERE name = 'QUESTRADE'), 
 'MARGIN');

-- Insert Plan
SELECT 'Inserting trading plan' AS message;
INSERT INTO plans (account_id, upload_time) 
VALUES ('27348656', datetime('now'));

-- Insert Planned Trades
SELECT 'Inserting planned trades' AS message;
INSERT INTO planned_trades (
    plan_id,
    symbol,
    entry_price,
    stop_loss_price,
    expiry_date
)
SELECT 
    last_insert_rowid(),
    'AAPL',
    205.0,
    199.99,
    date('now', '+7 days')
UNION ALL
SELECT 
    last_insert_rowid(),
    'TSLA',
    255.0,
    249.59,
    date('now', '+7 days');

-- Verify data was inserted
SELECT 'Verifying data' AS message;
SELECT 'Config rows:' AS label, COUNT(*) AS count FROM config
UNION ALL
SELECT 'Brokerages:', COUNT(*) FROM brokerages
UNION ALL
SELECT 'Accounts:', COUNT(*) FROM accounts
UNION ALL
SELECT 'Plans:', COUNT(*) FROM plans
UNION ALL
SELECT 'Planned Trades:', COUNT(*) FROM planned_trades;

COMMIT;
SELECT 'Data initialization completed successfully' AS message;