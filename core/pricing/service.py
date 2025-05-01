# Updated core/pricing/service.py
from typing import List, Dict, Optional, AsyncGenerator
from dataclasses import dataclass
from ..brokerages.protocol import PriceProtocol
import time
import asyncio
from core.logger import logger

@dataclass
@dataclass
class PriceTick:
    symbol: str
    price: float
    provider: str  # Required field (no default)
    timestamp: float = time.time()  # Default must come after required
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[float] = None
    
class MultiProviderPriceService:
    def __init__(self, providers: List[PriceProtocol]):
        """
        Args:
            providers: List of brokers/data sources implementing PriceProtocol.
        """
        self.providers = {
            self._normalize_provider_name(provider): provider 
            for provider in providers
        }
        self._latest_prices: Dict[str, PriceTick] = {}
        
    def _normalize_provider_name(self, provider: PriceProtocol) -> str:
        """Standardize provider names (e.g., 'IBKRClient' -> 'ibkr')"""
        name = provider.__class__.__name__.lower()
        return name.replace('client', '').replace('adapter', '').strip()

    async def get_price_with_depth(self, symbol: str) -> Optional[PriceTick]:
        """
        Enhanced version that returns price with market depth where available.
        IBKR provides bid/ask by default, others may not.
        """
        tasks = {
            name: provider.get_price(symbol) 
            for name, provider in self.providers.items()
        }
        
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        price_ticks = []
        
        for (name, result) in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.debug(f"Price fetch failed from {name}: {str(result)}")
                continue
                
            # Normalize different provider responses
            if name == 'ibkr':
                # IBKR returns dict with price, bid, ask
                price_ticks.append(PriceTick(
                    symbol=symbol,
                    price=result['last'],
                    bid=result.get('bid'),
                    ask=result.get('ask'),
                    provider=name,
                    timestamp=time.time()
                ))
            elif name == 'questrade':
                # Questrade returns simple float price
                price_ticks.append(PriceTick(
                    symbol=symbol,
                    price=result,
                    provider=name,
                    timestamp=time.time()
                ))
            else:
                # Default handling for other providers
                price_ticks.append(PriceTick(
                    symbol=symbol,
                    price=result,
                    provider=name,
                    timestamp=time.time()
                ))
        
        if not price_ticks:
            return None
            
        # Select best price (could be based on bid/ask spread)
        best_tick = self._select_best_price(price_ticks)
        self._latest_prices[symbol] = best_tick
        return best_tick

    def _select_best_price(self, ticks: List[PriceTick]) -> PriceTick:
        """Selects best price based on provider priority and market depth"""
        # 1. Prefer providers that give full depth info
        ticks_with_depth = [t for t in ticks if t.bid is not None and t.ask is not None]
        if ticks_with_depth:
            # Calculate mid price for comparison
            for tick in ticks_with_depth:
                if tick.bid and tick.ask:
                    tick.mid_price = (tick.bid + tick.ask) / 2
            return min(ticks_with_depth, key=lambda x: x.ask - x.bid)  # Tightest spread
        
        # 2. Fallback to simple price comparison
        return max(ticks, key=lambda x: x.price)

    async def get_best_price(self, symbol: str) -> Optional[PriceTick]:
        """Backward-compatible alias"""
        return await self.get_price_with_depth(symbol)

    async def stream_prices(self, symbol: str, interval: float = 1.0) -> AsyncGenerator[PriceTick, None]:
        """Enhanced streaming with market depth"""
        while True:
            price_tick = await self.get_price_with_depth(symbol)
            if price_tick:
                yield price_tick
            await asyncio.sleep(interval)

    async def get_price(self, symbol: str) -> Optional[float]:
        """Simple price-only accessor"""
        price_tick = await self.get_price_with_depth(symbol)
        return price_tick.price if price_tick else None