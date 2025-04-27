from core.storage.db import TradingDB  # Import TradingDB class
from typing import Any, Optional
from core.logger import logger

class Config:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_config()
        return cls._instance
    
    def _init_config(self):
        """Initialize with default DB path"""
        self.db_path = 'data/trading.db'
        self.db = TradingDB(self.db_path)  # Initialize TradingDB
    
    def _cast_value(self, value: str, value_type: str) -> Any:
        """Convert string value to proper type"""
        try:
            if value_type == 'bool':
                return value.upper() == 'TRUE'
            elif value_type == 'float':
                return float(value)
            elif value_type == 'int':
                return int(value)
            return value
        except (ValueError, AttributeError):
            return value

    def get_brokerage_config(self, name: str = 'QUESTRADE') -> dict:
        """Get all config for a specific brokerage"""
        try:
            with self.db._get_conn() as conn:  # Use TradingDB's _get_conn
                # Get brokerage
                brokerage = conn.execute(
                    "SELECT * FROM brokerages WHERE name = ?",
                    (name,)
                ).fetchone()
                
                if not brokerage:
                    return {}
                
                # Get primary account
                account = conn.execute(
                    "SELECT * FROM accounts WHERE brokerage_id = ? LIMIT 1",
                    (brokerage['id'],)
                ).fetchone()
                
                return {
                    'name': brokerage['name'],
                    'token_url': brokerage['token_url'],
                    'api_endpoint': brokerage['api_endpoint'],
                    'account_id': account['account_id'] if account else None,
                    'account_name': account['name'] if account else None,
                    'refresh_token': brokerage['refresh_token']
                }
        except Exception as e:
            logger.error(f"Failed to get brokerage config: {e}")
            return {}
        
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Enhanced with warning for missing keys"""
        try:
            with self.db._get_conn() as conn:  # Use TradingDB's _get_conn
                row = conn.execute(
                    "SELECT value, value_type FROM config WHERE key = ?",
                    (key,)
                ).fetchone()
                
                if row:
                    return self._cast_value(row['value'], row['value_type'])
                
                # Only warn if no default provided
                if default is None:
                    logger.warning(f"Config key not found: {key}")
                return default
        except Exception as e:
            logger.error(f"Config lookup failed for {key}: {e}")
            return default
