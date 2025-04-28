from core.storage.db import TradingDB

# Run once to update existing config keys
def migrate_config_keys():
    mapping = {
        'DRY_RUN': 'dry_run',
        'RISK_OF_CAPITAL': 'risk_of_capital',
        'AVAILABLE_QUANTITY_RATIO': 'available_quantity_ratio',
        'CLOSE_TRADES_BUFFER_MINUTES': 'close_trades_buffer_minutes',
        'DAILY_LOSS_LIMIT_PERCENT': 'daily_loss_limit_percent',
        'WEEKLY_LOSS_LIMIT_PERCENT': 'weekly_loss_limit_percent',
        'MONTHLY_LOSS_LIMIT_PERCENT': 'monthly_loss_limit_percent',
        'PROFIT_TO_LOSS_RATIO': 'profit_to_loss_ratio'
    }
    
    db = TradingDB()
    with db._get_conn() as conn:
        for old_key, new_key in mapping.items():
            conn.execute("""
                UPDATE config SET key = ? WHERE key = ?
            """, (new_key, old_key))
        conn.commit()  # <-- THIS IS MISSING!

if __name__ == "__main__":
    migrate_config_keys()
