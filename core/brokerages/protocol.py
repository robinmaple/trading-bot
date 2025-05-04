from typing import Protocol, runtime_checkable
from abc import abstractmethod
from dataclasses import dataclass
from core.models import OrderStatus
from core.orders.bracket import BracketOrder
from typing import Optional, Dict, Union
from decimal import Decimal

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


@dataclass
class OrderRequest:
    """Request to place an order with a brokerage"""
    symbol: str
    quantity: float
    order_type: str  # "market", "limit", "stop", "stop_limit"
    limit_price: Optional[Union[float, Decimal]] = None
    stop_price: Optional[Union[float, Decimal]] = None
    
    def __post_init__(self):
        # Validate order type and price requirements
        if self.order_type.lower() not in ["market", "limit", "stop", "stop_limit"]:
            raise ValueError(f"Invalid order type: {self.order_type}")
            
        if "limit" in self.order_type.lower() and self.limit_price is None:
            raise ValueError("Limit price required for limit orders")
            
        if "stop" in self.order_type.lower() and self.stop_price is None:
            raise ValueError("Stop price required for stop orders")

@dataclass 
class FillReport:
    """Result of an order execution attempt"""
    order_id: str
    status: str  # "submitted", "filled", "rejected", "cancelled"
    filled_at: float = 0.0  # Timestamp of fill
    filled_price: Optional[float] = None  # Average fill price
    filled_quantity: Optional[float] = None  # Filled amount
    message: Optional[str] = None  # Rejection reason if applicable