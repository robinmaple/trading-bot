from typing import List, Dict, Optional
from dataclasses import dataclass
from ..brokerages.protocol import PriceProtocol
import time
import asyncio
from core.logger import logger

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

    async def get_best_price(self, symbol: str) -> Optional[PriceTick]:
        """Returns the highest bid price across all providers."""
        tasks = [provider.get_price(symbol) for provider in self.providers.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        prices = [
            PriceTick(symbol, price, name, time.time())
            for (name, provider), price in zip(self.providers.items(), results)
            if not isinstance(price, Exception)
        ]
                
        if not prices:
            return None
        
        best_price = max(prices, key=lambda x: x.price)
        self._latest_prices[symbol] = best_price.price
        return best_price

    async def stream_prices(self, symbol: str, interval: float = 1.0):
        """Async generator for continuous price updates (e.g., for live trading)."""
        while True:
            price_tick = await self.get_best_price(symbol)
            if price_tick:
                yield price_tick
            await asyncio.sleep(interval)

    async def get_price(self, symbol: str) -> float:
        """Returns the current price with better error handling."""
        try:
            price_tick = await self.get_best_price(symbol)
            if not price_tick:
                logger.warning(f"No providers returned price for {symbol}")
                return None  # Instead of raising an error
                
            return price_tick.price
        except Exception as e:
            logger.error(f"Price fetch failed for {symbol}: {str(e)}")
            return None