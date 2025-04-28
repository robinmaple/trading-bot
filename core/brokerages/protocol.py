from typing import Protocol, runtime_checkable
from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict
from core.models import OrderStatus
from core.orders.bracket import BracketOrder


@runtime_checkable
class PriceProtocol(Protocol):
    """Interface for price providers (Questrade, IBKR, etc.)."""

    async def get_price(self, symbol: str) -> float:
        """Returns the current market price for a symbol."""
        ...


@runtime_checkable
class OrderProtocol(Protocol):
    """Interface for order execution."""

    async def submit_order(self, order: 'OrderRequest') -> 'FillReport':
        """Submits an order and returns a fill report."""
        ...

    async def cancel_order(self, order_id: str) -> bool:
        """Cancels an order by ID. Returns success status."""
        ...

    async def get_buying_power(self, account_id: str) -> float:
        """Return available buying power for trading"""
        ...

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Check current status of an order"""
        ...
        
    async def get_execution_price(self, order_id: str) -> Optional[float]:
        """Get average filled price for order"""
        ...
    
    async def submit_bracket_order(self, bracket: BracketOrder, account_id: str) -> bool:
        """Submit bracket order (entry + SL + TP)"""
        ...

@runtime_checkable
class BrokerageProtocol(Protocol):
    """Base protocol all brokerages must implement"""

    async def connect(self) -> bool:
        """Establish connection to brokerage."""
        ...

    @abstractmethod
    async def submit_bracket_order(self, bracket: BracketOrder) -> Dict:
        """Submit a bracket order (entry + take profit + stop loss).
        
        Should first attempt native implementation if available,
        then fall back to generic implementation if needed.
        """
        pass

    @property
    def supports_native_bracket(self) -> bool:
        """Whether this brokerage supports native bracket orders."""
        return False  # Default to False, brokerages can override


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
