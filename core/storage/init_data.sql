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
DELETE FROM encryption_keys;

-- Add encryption key (in production, this would be set separately)
INSERT OR REPLACE INTO encryption_keys (key_name, key_value) VALUES
('brokerage_creds', 'aWkysbmUGMuc05y72nISgJIyIg37ATE-H9YFnBiMm9Q=');


-- Insert Configuration
SELECT 'Inserting configuration' AS message;
INSERT OR REPLACE INTO config (key, value, value_type, description) VALUES
('dry_run', 'TRUE', 'bool', 'Test mode without real trades'),
('daily_loss_limit_percent', '2', 'float', 'Max daily loss before pausing (2%)'),
('weekly_loss_limit_percent', '5', 'float', 'Max weekly loss before pausing (5%)'),
('monthly_loss_limit_percent', '10', 'float', 'Max monthly loss before pausing (10%)'),
('close_trades_buffer_minutes', '5', 'int', 'Minutes before market close to exit trades');

-- Insert Brokerages
SELECT 'Inserting brokerages' AS message;
-- Updated brokerage inserts (with placeholder encrypted values)
INSERT OR REPLACE INTO brokerages 
(name, token_url, api_endpoint, auth_type, username, password, client_id, client_secret, refresh_token) 
VALUES
('IBKR', 
 'https://localhost:5000/v1/portal',  -- CPGW auth endpoint
 'https://localhost:5000/v1/api',               -- CPGW base URL
 'username_password',                          -- Placeholder (IBKR uses session auth)
 'enc:robinmaple',           -- Encrypted IBKR username
 'enc:Mjx80360!@#$',           -- Encrypted IBKR password
 NULL,                                         -- client_id unused
 NULL,                                         -- client_secret unused
 NULL                                          -- refresh_token unused
),

('QUESTRADE', 
 'https://login.questrade.com/oauth2/token', 
 'https://api.questrade.com',
 'authorization_code',
 NULL,                                         -- username unused
 NULL,                                         -- password unused
 NULL,                                         -- client_id unused
 NULL,                                         -- client_secret unused
 'enc:B-mtz8jXuyscfPX0HNkNn0rZRg_xK5mC0'      -- Encrypted refresh token
);


-- Insert Accounts
SELECT 'Inserting accounts' AS message;
INSERT OR REPLACE INTO accounts (account_id, brokerage_id, name) VALUES
('27348656', 
 (SELECT id FROM brokerages WHERE name = 'QUESTRADE'), 
 'MARGIN');

INSERT OR REPLACE INTO accounts (account_id, brokerage_id, name) VALUES
('U20131583', 
 (SELECT id FROM brokerages WHERE name = 'IBKR'), 
 'MARGIN');

COMMIT;
SELECT 'Data initialization completed successfully' AS message;