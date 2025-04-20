from abc import ABC, abstractmethod
from typing import Dict, Optional

class BrokerageAdapter(ABC):
    """Base class for all brokerage adapters. Each broker implements its own."""
    
    @abstractmethod
    async def submit_bracket_order(
        self,
        symbol: str,
        action: str,       # "BUY" or "SELL"
        quantity: float,
        take_profit: float,
        stop_loss: float,
    ) -> Dict:
        """Submit a bracket order (OCO) to the broker."""
        pass

    @abstractmethod
    async def get_account_balance(self, account_id: str) -> float:
        """Fetch available balance for the account."""
        pass