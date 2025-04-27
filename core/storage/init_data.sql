-- core/storage/init_data.sql
BEGIN TRANSACTION;

-- Global Config
INSERT OR REPLACE INTO config (key, value, value_type, description) VALUES
('DRY_RUN', 'TRUE', 'bool', 'Execute trades in test mode'),
('RISK_OF_CAPITAL', '0.5', 'float', '% of capital to risk per trade'),
('PROFIT_TO_LOSS_RATIO', '2', 'float', 'Reward/risk ratio'),
('AVAILABLE_QUANTITY_RATIO', '0.5', 'float', '% of calculated position size to trade'),
('DAILY_LOSS_LIMIT_PERCENT', '2', 'float', 'Cease trading if daily loss reaches this %'),
('WEEKLY_LOSS_LIMIT_PERCENT', '5', 'float', 'Cease trading if weekly loss reaches this %'),
('MONTHLY_LOSS_LIMIT_PERCENT', '10', 'float', 'Cease trading if monthly loss reaches this %'),
('CLOSE_TRADES_BUFFER_MINUTES', '5', 'int', 'Minutes before close to start position closing');

-- Questrade Brokerage
INSERT OR REPLACE INTO brokerages (name, token_url, api_endpoint, refresh_token) VALUES
('QUESTRADE', 'https://login.questrade.com/oauth2/token', 'https://api.questrade.com', 'B-mtz8jXuyscfPX0HNkNn0rZRg_xK5mC0');

-- Questrade Margin Account
INSERT OR REPLACE INTO accounts (account_id, brokerage_id, name) VALUES
('27348656', 
 (SELECT id FROM brokerages WHERE name = 'QUESTRADE'), 
 'MARGIN');

-- Add sample trading plan

-- Insert the main plan
INSERT INTO plans (upload_time) VALUES (datetime('now'));

-- Get the last inserted plan_id
-- Note: In SQLite, last_insert_rowid() gets the last autoincrement ID
INSERT INTO planned_trades (
    plan_id,
    account_id,
    symbol,
    entry_price,
    stop_loss_price,
    expiry_date
) VALUES 
    -- AAPL trade (using last_insert_rowid() for plan_id)
    (
        last_insert_rowid(),
        '27348656',  -- Replace with actual account ID
        'AAPL',
        205.0,
        199.99,
        date('now', '+7 days')  -- Expires 7 days from now
    ),
    -- TSLA trade (same plan_id since they're part of the same plan)
    (
        last_insert_rowid(),
        '27348656',  -- Replace with actual account ID
        'TSLA',
        255.0,
        249.59,
        date('now', '+7 days')  -- Expires 7 days from now
    );

-- Commit the transaction

COMMIT;