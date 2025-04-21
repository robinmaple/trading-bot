from dataclasses import dataclass
from typing import Optional

@dataclass
class PriceTick:
    symbol: str
    price: float
    provider: str
    timestamp: float

@dataclass
class PriceAlert:
    symbol: str
    threshold: float
    direction: str  # "above" or "below"