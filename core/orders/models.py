from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class OrderRequest:
    """Request to execute an order (inputs)."""
    symbol: str
    quantity: float  # Positive for buy, negative for sell
    order_type: Literal["market", "limit", "stop", "stop_limit"]
    price: Optional[float] = None  # Required for limit/stop orders
    stop_price: Optional[float] = None  # Required for stop orders

@dataclass
class FillReport:
    """Result of an executed order (outputs)."""
    order_id: str
    filled_at: float  # Average fill price
    status: Literal["filled", "partial", "rejected", "canceled"]