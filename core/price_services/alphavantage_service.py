# core/price_services/alpha_vantage_service.py
import os
import httpx
from typing import Optional
from core.logger import logger, redact_sensitive
from .price_service import PriceService

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
ALPHA_VANTAGE_API_URL = os.getenv("ALPHA_VANTAGE_API_URL", "https://www.alphavantage.co/query")


class AlphaVantagePriceService(PriceService):
    async def get_price(self, symbol: str) -> Optional[float]:
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": ALPHA_VANTAGE_API_KEY
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(ALPHA_VANTAGE_API_URL, params=params, timeout=10)

                logger.info(redact_sensitive(f"[AlphaVantage] HTTP {response.status_code} for symbol: {symbol}"))
                
                if response.status_code != 200:
                    logger.warning(f"[AlphaVantage] HTTP error {response.status_code}: {response.text}")
                    return None

                data = response.json()

                if "Note" in data:
                    logger.warning(f"[AlphaVantage] Rate limit notice for {symbol}: {data['Note']}")
                    return None

                if "Error Message" in data:
                    logger.warning(f"[AlphaVantage] API error for {symbol}: {data['Error Message']}")
                    return None

                if "Global Quote" not in data or not data["Global Quote"]:
                    logger.warning(f"[AlphaVantage] Missing or empty 'Global Quote' for {symbol}. Raw: {data}")
                    return None

                price_str = data["Global Quote"].get("05. price")
                if not price_str:
                    logger.warning(f"[AlphaVantage] '05. price' not found in quote for {symbol}: {data['Global Quote']}")
                    return None

                price = float(price_str)
                logger.info(f"[AlphaVantage] Retrieved price for {symbol}: {price}")
                return price

        except httpx.RequestError as e:
            logger.error(f"[AlphaVantage] Request error for {symbol}: {e}")
            return None
        except Exception as e:
            logger.exception(f"[AlphaVantage] Unexpected error for {symbol}")
            return None
