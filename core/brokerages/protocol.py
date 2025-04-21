from typing import Protocol, runtime_checkable
from dataclasses import dataclass

@runtime_checkable
class PriceProtocol(Protocol):
    """Interface for price providers (Questrade, IBKR, etc.)."""
    def get_price(self, symbol: str) -> float:
        """Returns the current market price for a symbol."""
        ...

@runtime_checkable
class OrderProtocol(Protocol):
    """Interface for order execution."""
    def submit_order(self, order: 'OrderRequest') -> 'FillReport':
        """Submits an order and returns a fill report."""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """Cancels an order by ID. Returns success status."""
        ...

# Shared data models (minimal, extend as needed)
@dataclass
class OrderRequest:
    symbol: str
    quantity: float
    order_type: str  # "limit", "market", etc.

@dataclass
class FillReport:
    order_id: str
    filled_at: float  # Price
    status: str  # "filled", "rejected", etc.