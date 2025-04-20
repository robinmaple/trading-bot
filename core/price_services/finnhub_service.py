# core/price_services/finnhub_service.py
import os
import httpx
from typing import Optional
from core.logger import logger, redact_sensitive
from .price_service import PriceService

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
FINNHUB_API_URL = os.getenv("FINNHUB_API_URL", "https://finnhub.io/api/v1")


class FinnhubPriceService(PriceService):
    async def get_price(self, symbol: str) -> Optional[float]:
        endpoint = f"{FINNHUB_API_URL}/quote"
        params = {
            "symbol": symbol,
            "token": FINNHUB_API_KEY
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, params=params, timeout=10.0)
                logger.info(redact_sensitive(f"[Finnhub] HTTP {response.status_code} for symbol: {symbol}"))

                if response.status_code != 200:
                    logger.warning(f"[Finnhub] HTTP error {response.status_code} for {symbol}: {response.text}")
                    return None

                data = response.json()

                if not isinstance(data, dict) or "c" not in data:
                    logger.warning(f"[Finnhub] Unexpected response format for {symbol}: {data}")
                    return None

                price = data.get("c")
                if price is None:
                    logger.warning(f"[Finnhub] 'c' (current price) missing for {symbol}: {data}")
                    return None

                logger.info(f"[Finnhub] Retrieved price for {symbol}: {price}")
                return float(price)

        except httpx.RequestError as e:
            logger.error(f"[Finnhub] Request error for {symbol}: {e}")
            return None
        except Exception as e:
            logger.exception(f"[Finnhub] Unexpected error for {symbol}")
            return None
