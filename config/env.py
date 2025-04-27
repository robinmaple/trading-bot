import os
from typing import List, Tuple
from dotenv import load_dotenv
from core.config import Config
config = Config()
# load_dotenv()

def _parse_trading_hours(hours_str: str) -> List[Tuple[str, str]]:
    """Parse TRADING_HOURS into list of (start, end) tuples."""
    if not isinstance(hours_str, str):
        raise ValueError("Input must be a string")
    
    ranges = []
    for range_str in hours_str.split(','):
        range_str = range_str.strip()
        if not range_str:
            continue  # Skip empty entries
        try:
            start, end = range_str.split('-')
            ranges.append((start.strip(), end.strip()))
        except ValueError:
            raise ValueError(f"Invalid time range format: '{range_str}'. Expected 'HH:MM-HH:MM'")
    return ranges

# Core Trading Parameters
DRY_RUN = config.get("DRY_RUN")
questrade = config.get_brokerage_config('QUESTRADE')
ACCOUNT_ID = questrade.get("account_id")

# Risk Management
RISK_OF_CAPITAL = config.get("RISK_OF_CAPITAL")
PROFIT_TO_LOSS_RATIO = config.get("PROFIT_TO_LOSS_RATIO")
AVAILABLE_QUANTITY_RATIO = config.get("AVAILABLE_QUANTITY_RATIO")
DAILY_LOSS_LIMIT_PERCENT = config.get("DAILY_LOSS_LIMIT_PERCENT")
WEEKLY_LOSS_LIMIT_PERCENT = config.get("WEEKLY_LOSS_LIMIT_PERCENT")
MONTHLY_LOSS_LIMIT_PERCENT = config.get("MONTHLY_LOSS_LIMIT_PERCENT")

# Session Management
CLOSE_TRADES_BUFFER_MINUTES = config.get("CLOSE_TRADES_BUFFER_MINUTES")
TRADING_HOURS = _parse_trading_hours(os.getenv("TRADING_HOURS", "9:30-23:59"))

# Validation
assert 0 < RISK_OF_CAPITAL <= 1, "RISK_OF_CAPITAL must be between 0 and 1"
assert PROFIT_TO_LOSS_RATIO >= 1, "PROFIT_TO_LOSS_RATIO must be >= 1"
assert 0 < AVAILABLE_QUANTITY_RATIO <= 1, "AVAILABLE_QUANTITY_RATIO must be between 0 and 1"
assert DAILY_LOSS_LIMIT_PERCENT > 0, "DAILY_LOSS_LIMIT_PERCENT must be positive"
