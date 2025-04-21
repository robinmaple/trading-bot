import os
from typing import List, Tuple
from dotenv import load_dotenv
load_dotenv()

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
DRY_RUN = os.getenv("DRY_RUN", "TRUE").lower() == "true"
ACCOUNT_ID = os.getenv("ACCOUNT_ID", "27348656")

# Risk Management
RISK_OF_CAPITAL = float(os.getenv("RISK_OF_CAPITAL", "0.005"))  # 0.5% of capital
PROFIT_TO_LOSS_RATIO = float(os.getenv("PROFIT_TO_LOSS_RATIO", "2.0"))
AVAILABLE_QUANTITY_RATIO = float(os.getenv("AVAILABLE_QUANTITY_RATIO", "0.5"))
DAILY_LOSS_LIMIT_PERCENT = float(os.getenv("DAILY_LOSS_LIMIT_PERCENT", "2.0"))

# Session Management
CLOSE_POSITIONS_BEFORE_CLOSE = os.getenv("CLOSE_POSITIONS_BEFORE_CLOSE", "Yes").lower() == "yes"
CLOSE_TRADES_BUFFER_MINUTES = int(os.getenv("CLOSE_TRADES_BUFFER_MINUTES", "5"))
TRADING_HOURS = _parse_trading_hours(os.getenv("TRADING_HOURS", "9:30-23:59"))

# API URLs and Keys for Price Services
ALPHA_VANTAGE_API_URL = os.getenv("ALPHA_VANTAGE_API_URL", "https://www.alphavantage.co/query")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

FINNHUB_API_URL = os.getenv("FINNHUB_API_URL", "https://finnhub.io/api/v1")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

LOG_DIR = os.getenv("LOG_DIR", "logs\executed_orders")
LOG_FILE = os.getenv("LOG_FILE", "trading_log.txt")

# Risk Management Parameters
DAILY_LOSS_LIMIT_PERCENT = float(os.getenv("DAILY_LOSS_LIMIT_PERCENT", "2.0"))
WEEKLY_LOSS_LIMIT_PERCENT = float(os.getenv("WEEKLY_LOSS_LIMIT_PERCENT", "5.0"))
MONTHLY_LOSS_LIMIT_PERCENT = float(os.getenv("MONTHLY_LOSS_LIMIT_PERCENT", "10.0"))

# Validation
assert 0 < RISK_OF_CAPITAL <= 1, "RISK_OF_CAPITAL must be between 0 and 1"
assert PROFIT_TO_LOSS_RATIO >= 1, "PROFIT_TO_LOSS_RATIO must be >= 1"
assert 0 < AVAILABLE_QUANTITY_RATIO <= 1, "AVAILABLE_QUANTITY_RATIO must be between 0 and 1"
assert DAILY_LOSS_LIMIT_PERCENT > 0, "DAILY_LOSS_LIMIT_PERCENT must be positive"
