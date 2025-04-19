from core.logger import logger
from .mock_service import MockPriceService
from .alphavantage_service import AlphaVantagePriceService
from core.price_services.finnhub_service import FinnhubPriceService
from core.price_services.price_service import PriceService
# Add additional imports here as needed

class MultiProviderPriceService(PriceService):
    def __init__(self):
        self.providers = [
            AlphaVantagePriceService(),
            FinnhubPriceService(),
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    (),  # fallback
        ]

    def get_price(self, symbol: str) -> float:
        for provider in self.providers:
            try:
                return provider.get_price(symbol)
            except Exception as e:
                print(f"[MultiProvider] {provider.__class__.__name__} failed: {e}")
        raise RuntimeError(f"All price providers failed for {symbol}")
