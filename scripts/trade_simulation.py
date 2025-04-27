import asyncio
from core.brokerages.questrade.auth import QuestradeAuth
from core.brokerages.questrade.client import QuestradeClient
from core.pricing.service import MultiProviderPriceService
from core.trading.manager import TradingManager
from config import settings
from core.config import Config
config = Config()
from core.storage.db import TradingDB

async def main():
    # 1. Initialize authentication
    db = TradingDB()
    auth = QuestradeAuth(db)
    
    # 2. Set up brokerage clients
    questrade_client = QuestradeClient(auth)
    price_service = MultiProviderPriceService([questrade_client])
    
    # 3. Initialize TradingManager with protocol-compliant clients
    trading_manager = TradingManager(
        order_client=questrade_client,  # Must implement OrderProtocol
        price_client=price_service     # Must implement PriceProtocol
    )
    
    # 4. Run the trading loop
    await trading_manager.run()

if __name__ == "__main__":
    asyncio.run(main())