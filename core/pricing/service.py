from typing import List, Dict, Optional
from dataclasses import dataclass
from ..brokerages.protocol import PriceProtocol
import time
import asyncio  # For async support (optional)

@dataclass
class PriceTick:
    """Represents a price update from a provider."""
    symbol: str
    price: float
    provider: str  # e.g., "questrade", "mock"
    timestamp: float  # Unix epoch

class MultiProviderPriceService:
    def __init__(self, providers: List[PriceProtocol]):
        """
        Args:
            providers: List of brokers/data sources implementing PriceProtocol.
        """
        self.providers = {provider.__class__.__name__.lower(): provider 
                          for provider in providers}
        self._latest_prices: Dict[str, PriceTick] = {}

    def get_best_price(self, symbol: str) -> Optional[PriceTick]:
        """Returns the highest bid price across all providers."""
        prices = []
        for provider_name, provider in self.providers.items():
            try:
                price = provider.get_price(symbol)
                prices.append(PriceTick(symbol, price, provider_name, time.time()))
            except Exception as e:
                print(f"Price fetch failed from {provider_name}: {e}")
        
        if not prices:
            return None
        best_price = max(prices, key=lambda x: x.price)
        self._latest_prices[symbol] = best_price
        return best_price

    async def stream_prices(self, symbol: str, interval: float = 1.0):
        """Async generator for continuous price updates (e.g., for live trading)."""
        while True:
            price_tick = self.get_best_price(symbol)
            if price_tick:
                yield price_tick
            await asyncio.sleep(interval)