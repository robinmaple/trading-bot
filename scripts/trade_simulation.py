import asyncio
from core.storage.db import TradingDB
from core.brokerages.questrade.client import QuestradeClient
from core.logger import logger

async def main():
    try:
        # Initialize database connection
        db = TradingDB()  # Make sure this is properly configured
        
        # Initialize client
        questrade_client = QuestradeClient(db)
        
        # Test connection
        logger.info(f"Primary account ID: {questrade_client.account_id}")
        
        # Rest of your simulation code...
        price = await questrade_client.get_price("AAPL")
        logger.info(f"AAPL price: {price}")
        
    except Exception as e:
        logger.error(f"Error in trade simulation: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())