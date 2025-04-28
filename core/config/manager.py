# core/config/manager.py
from typing import Any
from core.storage.db import TradingDB
from core.logger import logger
from .constants import CONFIG_SPECS

class ConfigManager:
    def __init__(self, db: TradingDB):
        self.db = db
        self._specs = CONFIG_SPECS
        self._cache = {}

    def get(self, key: str) -> Any:
        """Get validated config value"""
        if key not in self._specs:
            logger.error(f"Attempted to access unknown config key: {key}")
            raise KeyError(f"Unknown config key: {key}")
            
        if key in self._cache:
            return self._cache[key]
            
        # Get raw value from database
        with self.db._get_conn() as conn:
            result = conn.execute(
                "SELECT value FROM config WHERE key = ?", 
                (key,)
            ).fetchone()
            
        raw_value = result[0] if result else None
        self._cache[key] = self._specs[key].validate(raw_value)
        return self._cache[key]

    def get_all(self) -> dict:
        """Get all validated config values"""
        return {key: self.get(key) for key in self._specs.keys()}

    def initialize_defaults(self):
        """Ensure all config specs exist in database"""
        with self.db._get_conn() as conn:
            existing_keys = {row[0] for row in conn.execute("SELECT key FROM config")}
            
            missing = []
            for key, spec in self._specs.items():
                if key not in existing_keys:
                    missing.append((key, str(spec.default), spec.description))
            
            if missing:
                conn.executemany(
                    """INSERT INTO config 
                    (key, value, value_type, description) 
                    VALUES (?, ?, ?, ?)""",
                    [
                        (
                            key, 
                            value, 
                            spec.type.__name__, 
                            spec.description
                        )
                        for key, value, spec in [
                            (k, v, self._specs[k]) 
                            for k, v, _ in missing
                        ]
                    ]
                )
                logger.info(f"Initialized {len(missing)} config defaults")

# Singleton instance
config = ConfigManager(TradingDB())
config.initialize_defaults()