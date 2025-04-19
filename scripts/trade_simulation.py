from core.auth import QuestradeAuth
from core.trading_manager import TradingManager
from config.env import DRY_RUN
from core.logger import logger

def trade_simulation():
    logger.info(f"Starting trading session | DryRun={DRY_RUN}")
    
    # Initialize trading manager with auth
    auth = QuestradeAuth()
    manager = TradingManager(auth)
    
    try:
        # Run the main trading loop
        manager.run()
    except KeyboardInterrupt:
        logger.info("Gracefully shutting down...")
    except Exception as e:
        logger.error(f"Fatal error in trading session: {str(e)}")
        raise

if __name__ == "__main__":
    trade_simulation()