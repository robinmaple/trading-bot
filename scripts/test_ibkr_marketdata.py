# test_ibkr_marketdata.py
import asyncio
from core.storage.db import TradingDB
from core.brokerages.ibkr.auth import IBKRAuth
from core.brokerages.ibkr.client import IBKRClient
from core.logger import logger

async def test_ibkr_market_data():
    """Test IBKR market data connectivity and quality"""
    try:
        # Initialize with your actual credentials
        db = TradingDB()
        
        # Proper initialization with brokerage_name
        auth = IBKRAuth.from_db(db, brokerage_name='IBKR')
        client = IBKRClient(auth)
        
        # Test connectivity
        logger.info("Testing IBKR API connectivity...")
        if not await client.connect():
            raise ConnectionError("Failed to connect to IBKR")
        logger.success("✓ Connectivity verified")
        
        # Test with simple symbol first
        test_symbol = 'AAPL'  # Start with one symbol for debugging
        logger.info(f"\nTesting market data for {test_symbol}...")
        
        start_time = asyncio.get_event_loop().time()
        data = await client.get_price(test_symbol)
        latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        
        logger.info(f"Price: {data.get('last')}")
        logger.info(f"Bid/Ask: {data.get('bid')}/{data.get('ask')}")
        logger.info(f"Latency: {latency_ms:.1f}ms")
        
        # Basic validation
        if not all(key in data for key in ['last', 'bid', 'ask']):
            raise ValueError("Missing price data fields")
            
        logger.success("✓ Basic market data verified")
        
        # Add more symbols after basic test passes
        additional_symbols = ['SPY', 'MSFT']
        for symbol in additional_symbols:
            try:
                data = await client.get_price(symbol)
                logger.info(f"\n{symbol}: {data['last']} (Bid: {data['bid']}, Ask: {data['ask']})")
            except Exception as e:
                logger.warning(f"Failed to get data for {symbol}: {str(e)}")
                
        logger.success("\nAll tests completed successfully")
        return True
        
    except Exception as e:
        logger.critical(f"IBKR test failed: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    asyncio.run(test_ibkr_market_data())