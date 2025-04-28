-- core/storage/init_data.sql
BEGIN TRANSACTION;

-- Global Config
INSERT OR REPLACE INTO config (key, value, value_type, description) VALUES
('dry_run', 'TRUE', 'bool', 'Test mode without real trades'),
('risk_of_capital', '0.01', 'float', 'Max % of capital to risk per trade (0.01 = 1%)'),
('profit_to_loss_ratio', '2', 'float', 'Minimum profit target as multiple of risk'),
('available_quantity_ratio', '0.8', 'float', 'Max % of calculated position size to take'),
('daily_loss_limit_percent', '2', 'float', 'Max daily loss before pausing (2%)'),
('weekly_loss_limit_percent', '5', 'float', 'Max weekly loss before pausing (5%)'),
('monthly_loss_limit_percent', '10', 'float', 'Max monthly loss before pausing (10%)'),
('close_trades_buffer_minutes', '5', 'int', 'Minutes before market close to exit trades');

-- Questrade Brokerage
INSERT OR REPLACE INTO brokerages (name, token_url, api_endpoint, refresh_token) VALUES
('QUESTRADE', 'https://login.questrade.com/oauth2/token', 'https://api.questrade.com', 'B-mtz8jXuyscfPX0HNkNn0rZRg_xK5mC0');

-- Questrade Margin Account
INSERT OR REPLACE INTO accounts (account_id, brokerage_id, name) VALUES
('27348656', 
 (SELECT id FROM brokerages WHERE name = 'QUESTRADE'), 
 'MARGIN');

-- Add sample trading plan

-- Insert the main plan with account_id
INSERT INTO plans (account_id, upload_time) 
VALUES ('27348656', datetime('now'));  -- Account ID at plan level

-- Get the last inserted plan_id
-- Insert trades without account_id (inherited from plan)
INSERT INTO planned_trades (
    plan_id,
    symbol,
    entry_price,
    stop_loss_price,
    expiry_date
) VALUES 
    -- AAPL trade (using last_insert_rowid() for plan_id)
    (
        last_insert_rowid(),
        'AAPL',
        205.0,
        199.99,
        date('now', '+7 days')  -- Expires 7 days from now
    ),
    -- TSLA trade (same plan_id since they're part of the same plan)
    (
        last_insert_rowid(),
        'TSLA',
        255.0,
        249.59,
        date('now', '+7 days')  -- Expires 7 days from now
    );

-- Commit the transaction

COMMIT;