from core.auth import QuestradeAuth
from core.api.orders import OrderService, BracketOrder, MockPriceService
from core.trading_plan import TradingPlanManager
from config.env import DRY_RUN
from core.logger import logger

def trade_simulation():
    logger.info(f"Starting daily_trade | DryRun={DRY_RUN}")

    # Setup services
    auth_client = QuestradeAuth()
    order_service = OrderService(auth_client)
    price_service = MockPriceService()
    bracket_order = BracketOrder(order_service, price_service)

    # Simulated buying power
    simulated_buying_power = 10000  # You can vary this for testing

    # Load and process the trading plan
    manager = TradingPlanManager()

    logger.info("Loaded trading plan:")
    for order in manager.orders:
        logger.info(order)

    # Try to trigger one active order
    symbol, order_data = manager.get_first_triggerable_order(simulated_buying_power)
    if symbol and order_data:
        logger.info(f"Triggering order for {symbol}")
        bracket_order.place(
            symbol=symbol,
            symbol_id=order_data['symbol_id'],
            entry_price=order_data['entry'],
            stop_price=order_data['stop'],  # Changed from 'stop_loss'
            account_id='dry_run_account',
            buying_power=simulated_buying_power,
            direction=order_data.get('side', 'Buy'),
            quantity=order_data.get('quantity')  # Optional
        )
        manager.mark_expired(symbol)  # Changed from mark_order_as_expired

        logger.info("Updated Trading Plan Status After Position Entry:")
        for o in manager.orders:
            logger.info(o)

        # Simulate exit logic
        price_service.simulate_exit(bracket_order, symbol, order_data, logger)

        logger.info("Updated Trading Plan After Exit:")
        for o in manager.orders:
            logger.info(o)
    else:
        logger.info("No orders met the available quantity ratio.")

if __name__ == "__main__":
    trade_simulation()