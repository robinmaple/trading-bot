# core/price_services/composite_price_service.py
import asyncio
import time
from typing import Optional

from core.price_services.price_service import PriceService
from core.price_services.alphavantage_service import AlphaVantagePriceService
from core.price_services.finnhub_service import FinnhubPriceService

class CompositePriceService(PriceService):
    def __init__(self, alpha_service: AlphaVantagePriceService, finnhub_service: FinnhubPriceService):
        self.alpha = alpha_service
        self.finnhub = finnhub_service

        # API Rate limits (requests per minute)
        self.alpha_limit = 5
        self.finnhub_limit = 60

        self.alpha_calls = []
        self.finnhub_calls = []

    def _can_call(self, timestamps, limit) -> bool:
        now = time.time()
        # Remove timestamps older than 60 seconds
        timestamps[:] = [t for t in timestamps if now - t < 60]
        return len(timestamps) < limit

    def _register_call(self, timestamps):
        timestamps.append(time.time())

    async def get_price(self, symbol: str) -> Optional[float]:
        tasks = []

        # Queue Alpha call if allowed
        if self._can_call(self.alpha_calls, self.alpha_limit):
            tasks.append(self._get_price_with_tracking(self.alpha, self.alpha_calls, symbol))

        # Queue Finnhub call if allowed
        if self._can_call(self.finnhub_calls, self.finnhub_limit):
            tasks.append(self._get_price_with_tracking(self.finnhub, self.finnhub_calls, symbol))

        if not tasks:
            return None

        results = await asyncio.gather(*tasks, return_exceptions=True)

        prices = [r for r in results if isinstance(r, (int, float)) and r > 0]

        if not prices:
            return None
        elif len(prices) == 1:
            return prices[0]
        else:
            # Handle conflicting prices
            p1, p2 = prices
            if abs(p1 - p2) / max(p1, p2) < 0.001:  # Less than 0.1% difference
                return (p1 + p2) / 2
            return prices[0]  # Return first available

    async def _get_price_with_tracking(self, service: PriceService, tracker, symbol: str):
        self._register_call(tracker)
        return await service.get_price(symbol)
