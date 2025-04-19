import httpx
from typing import Optional
from core.price_services.price_service import PriceService

class FinnhubPriceService(PriceService):
    def __init__(self, api_key: str, api_url: str = "https://finnhub.io/api/v1"):
        self.api_key = api_key
        self.api_url = api_url

    async def get_price(self, symbol: str) -> Optional[float]:
        endpoint = f"{self.api_url}/quote"
        params = {"symbol": symbol, "token": self.api_key}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(endpoint, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                price = data.get("c")  # "c" is the current price
                return float(price) if price is not None else None
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
                print(f"Error fetching price from Finnhub: {e}")
                return None
