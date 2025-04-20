# core/price_services/composite_price_service.py
import asyncio
import time
from typing import Optional

from core.price_services.price_service import PriceService
from core.price_services.alphavantage_service import AlphaVantagePriceService
from core.price_services.finnhub_service import FinnhubPriceService
from core.price_services.questrade_service import QuestradePriceService

class CompositePriceService(PriceService):
    def __init__(
        self,
        alpha_service: AlphaVantagePriceService,
        finnhub_service: FinnhubPriceService,
        questrade_service: QuestradePriceService,
    ):
        self.alpha = alpha_service
        self.finnhub = finnhub_service
        self.questrade = questrade_service

        # API Rate limits (adjust based on your Questrade tier)
        self.alpha_daily_limit = 25
        self.finnhub_minute_limit = 60
        self.questrade_minute_limit = 60  # Check Questrade docs for exact limits

        self.alpha_calls = []
        self.finnhub_calls = []
        self.questrade_calls = []

    async def get_price(self, symbol: str) -> Optional[float]:
        tasks = []

        if self._can_call(self.alpha_calls, self.alpha_daily_limit):
            tasks.append(self._get_price_with_tracking(self.alpha, self.alpha_calls, symbol))

        if self._can_call(self.finnhub_calls, self.finnhub_minute_limit):
            tasks.append(self._get_price_with_tracking(self.finnhub, self.finnhub_calls, symbol))

        if self._can_call(self.questrade_calls, self.questrade_minute_limit):
            tasks.append(self._get_price_with_tracking(self.questrade, self.questrade_calls, symbol))

        if not tasks:
            return None

        results = await asyncio.gather(*tasks, return_exceptions=True)
        prices = [r for r in results if isinstance(r, (int, float)) and r > 0]

        if not prices:
            return None
        elif len(prices) == 1:
            return prices[0]
        else:
            # Take median price to reduce outlier impact
            return sorted(prices)[len(prices) // 2]
        
    async def _get_price_with_tracking(self, service: PriceService, tracker, symbol: str):
        self._register_call(tracker)
        return await service.get_price(symbol)

    def _can_call(self, timestamps, limit) -> bool:
        now = time.time()
        # Remove timestamps older than 60 seconds
        timestamps[:] = [t for t in timestamps if now - t < 60]
        return len(timestamps) < limit

    def _register_call(self, timestamps):
        timestamps.append(time.time())

