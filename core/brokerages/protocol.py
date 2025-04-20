from typing import Protocol, runtime_checkable

@runtime_checkable
class BrokerageProtocol(Protocol):
    """Defines the minimum interface for bracket order support."""
    
    def place_limit_order(
        self,
        account_id: str,
        symbol: str,
        limit_price: float,
        quantity: float,
        action: str  # "BUY" or "SELL"
    ) -> dict:
        ...
    
    def place_stop_order(
        self,
        account_id: str,
        symbol: str,
        stop_price: float,
        quantity: float,
        action: str
    ) -> dict:
        ...