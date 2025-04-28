# core/brokerages/auth/base.py
from abc import ABC, abstractmethod
from typing import Optional
import requests, time
from core.storage.db import TradingDB

class BaseBrokerageAuth(ABC):
    def __init__(self, db: Optional[TradingDB] = None, **kwargs):
        self.db = db
        self._config = kwargs
        self.access_token: Optional[str] = None
        self.expiry_time: float = 0
        
    @classmethod
    def from_db(cls, db: TradingDB, brokerage_name: str):
        """Factory method to create from database"""
        config = cls._load_db_config(db, brokerage_name)
        return cls(db=db, **config)
        
    @staticmethod
    @abstractmethod
    def _load_db_config(db: TradingDB, brokerage_name: str) -> dict:
        """Load config from DB - must be implemented by each brokerage"""
        pass
        
    @abstractmethod
    def _refresh_tokens(self) -> None:
        """Token refresh logic - must be implemented by each brokerage"""
        pass

    def get_valid_token(self) -> str:
        """Shared token validation logic"""
        if time.time() > self.expiry_time - 300:  # 5 minutes buffer
            self._refresh_tokens()
        return self.access_token

    def create_session(self) -> requests.Session:
        """Shared session creation"""
        session = requests.Session()
        session.headers.update({
            'Authorization': f'Bearer {self.get_valid_token()}'
        })
        return session