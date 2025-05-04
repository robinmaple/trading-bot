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
    symbol = "AAPL"
    price = await client.get_price(symbol)
    logger.info(f"📊 {symbol} price: {price}")
    
    # 3. Test dry-run order submission
    if True:  # Set DRY_RUN=False in config to test real orders
        order = {
            "symbol": symbol,
            "quantity": 1,
            "order_type": "limit",
            "limit_price": round(price * 0.95, 2)  # 5% below market
        }
        try:
            report = await client.submit_order(order)
            logger.info(f"🟢 Dry-run order submitted: {report}")
        except Exception as e:
            logger.error(f"🔴 Order failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())