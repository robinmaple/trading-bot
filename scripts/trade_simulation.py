import asyncio
from core.storage.db import TradingDB
from core.logger import logger
from core.brokerages.ibkr.auth import IBKRAuth
from core.brokerages.ibkr.client import IBKRClient

async def main():

    # Initialize with your account
    db = TradingDB()  # Your configured database
    account_id = "U20131583"  # Your IBKR account
    
    # 1. Test authentication
    auth = IBKRAuth(db, account_id)
    if not auth.authenticate():
        logger.error("❌ Authentication failed")
        return
    
    logger.info("✅ Authentication successful")
    logger.info(f"Session cookie: {auth.session.cookies.get('JSESSIONID')}")
    
    # 2. Test market data
    client = IBKRClient(auth)
    # Test CONID lookup
    conid = await client._get_conid('BIDU')
    logger.info(f"BIDU CONID: {conid}")

    # Test price fetching
    try:
        price = await client.get_price('BIDU')
        logger.info(f"BIDU Price: {price}")
    except Exception as e:
        logger.error(f"Price check failed: {str(e)}")

    # Test order submission
    order = {
        "symbol": "BIDU",
        "quantity": 10,
        "order_type": "market"
    }
    try:
        result = await client.submit_order(order)
        logger.info(f"Order Result: {result}")
    except Exception as e:
        logger.error(f"Order failed: {str(e)}")
        
if __name__ == "__main__":
    asyncio.run(main())