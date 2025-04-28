# test_ibkr.py
import asyncio
from core.storage.db import TradingDB
from core.brokerages.ibkr.client import IBKRClient
from core.logger import logger

async def main():
    try:
        # Initialize database connection
        db = TradingDB()
        
        # Initialize IBKR client
        ibkr_client = IBKRClient(db)
        
        # Test connection
        logger.info(f"Primary account ID: {ibkr_client.account_id}")
        
        # Test price fetching
        aapl_price = await ibkr_client.get_price("AAPL")
        logger.info(f"AAPL price: {aapl_price}")
        
        # Test account balance
        buying_power = await ibkr_client.get_buying_power(ibkr_client.account_id)
        logger.info(f"Buying power: ${buying_power:,.2f}")
        
        # Test bracket order (dry run first)
        bracket_order = {
            "symbol": "AAPL",
            "entry_price": aapl_price,
            "stop_loss_price": aapl_price * 0.99,  # 1% stop
            "take_profit_price": aapl_price * 1.02,  # 2% target
            "quantity": 10
        }
        order_result = await ibkr_client.submit_bracket_order(**bracket_order)
        logger.info(f"Bracket order result: {order_result}")
        
    except Exception as e:
        logger.error(f"Error in IBKR test: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())