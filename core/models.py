# core/models.py

from enum import Enum

class OrderStatus(str, Enum):
    ENTRY = "entry"
    STOP_LOSS = "stop_loss"
    PROFIT_TARGET = "profit_target"
    CLOSED = "closed"
