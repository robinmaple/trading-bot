# core/price_services/finnhub_service.py
import os
import httpx
from typing import Optional
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
                response.raise_for_status()
                data = response.json()
                price = data.get("c")  # "c" is the current price
                return float(price) if price is not None else None
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            print(f"Finnhub error: {e}")
            return None
