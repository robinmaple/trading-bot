# core/price_services/alpha_vantage_service.py
import os
import httpx
from typing import Optional
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
                response.raise_for_status()
                data = response.json()
                return float(data["Global Quote"]["05. price"])
        except Exception as e:
            print(f"AlphaVantage error: {e}")
            return None
