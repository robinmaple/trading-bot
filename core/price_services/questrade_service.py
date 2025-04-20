import httpx
from typing import Optional
from core.logger import logger
from .price_service import PriceService

class QuestradePriceService(PriceService):
    def __init__(self, api_client):
        self.api_client = api_client  # Reuse your existing Questrade API client

    async def get_price(self, symbol: str) -> Optional[float]:
        try:
            # Questrade uses slightly different symbol formats (e.g., "USD/CAD" vs. "CADUSD.FX")
            questrade_symbol = self._convert_to_questrade_format(symbol)
            
            # Use Questrade's market data endpoint
            response = await self.api_client.get(
                f"v1/markets/quotes/{questrade_symbol}",
                timeout=10.0
            )
            
            if response.status_code != 200:
                logger.warning(f"[Questrade] Failed to fetch price for {symbol}: {response.text}")
                return None

            data = response.json()
            if not data.get("quotes"):
                logger.warning(f"[Questrade] No quotes returned for {symbol}")
                return None

            last_price = data["quotes"][0].get("lastTradePrice")
            if last_price is None:
                logger.warning(f"[Questrade] Missing lastTradePrice for {symbol}")
                return None

            logger.info(f"[Questrade] Retrieved price for {symbol}: {last_price}")
            return float(last_price)

        except httpx.RequestError as e:
            logger.error(f"[Questrade] Request error for {symbol}: {e}")
            return None
        except Exception as e:
            logger.exception(f"[Questrade] Unexpected error for {symbol}")
            return None

    def _convert_to_questrade_format(self, symbol: str) -> str:
        """Converts standard symbols (e.g., 'USD/CAD') to Questrade format ('CADUSD.FX')."""
        if "/" in symbol:
            base, quote = symbol.split("/")
            return f"{quote}{base}.FX"  # Questrade FX format
        return symbol  # Assume stock symbols are the same