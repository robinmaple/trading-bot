# core/models.py
from enum import Enum, auto

class OrderLifecycle(str, Enum):
    """Tracks order progress (new system)"""
    PENDING = "pending"
    PLACED = "placed"
    FILLED = "filled"
    CLOSED = "closed"
    FAILED = "failed"

class OrderType(str, Enum):
    """Classifies order purpose (your existing system)"""
    ENTRY = "entry"
    STOP_LOSS = "stop_loss"
    PROFIT_TARGET = "profit_target"

class OrderDirection(str, Enum):
    BUY = "Buy"
    SELL = "Sell"

class OrderMethod(str, Enum):
    LIMIT = "limit"
    STOP_LIMIT = "stop-limit"
    MARKET = "market"

class PeriodType(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class OrderStatus(str, Enum):
    OPEN = "open"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"