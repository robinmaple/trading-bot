from core.auth import QuestradeAuth
from core.api.orders import OrderService, BracketOrder, MockPriceService
from config.env import DRY_RUN
from core.logger import logger

def main():
    # Auth & Service Setup
    auth = QuestradeAuth()  # Loads token from file
    accounts = auth.get_accounts()
    account_id = accounts['accounts'][0]['number']  # Assumes first account is used

    # Buying power simulation
    buying_power = 10000  # Simulated; replace with real from API if needed

    # Example symbol and symbol ID (replace with real one if needed)
    symbol = "AAPL"
    symbol_id = 8049  # Example Questrade symbolId for Apple Inc.

    # Create services
    order_service = OrderService(auth)
    price_service = MockPriceService()
    bracket = BracketOrder(order_service, price_service)

    logger.info("=== TESTING BUY BRACKET ORDER ===")
    bracket.place(
        symbol=symbol,
        symbol_id=symbol_id,
        entry_price=170.00,
        stop_price=168.50,
        account_id=account_id,
        buying_power=buying_power,
        direction="Buy"
    )

    logger.info("=== TESTING SELL BRACKET ORDER ===")
    bracket.place(
        symbol=symbol,
        symbol_id=symbol_id,
        entry_price=170.00,
        stop_price=171.50,
        account_id=account_id,
        buying_power=buying_power,
        direction="Sell"
    )

if __name__ == "__main__":
    logger.info(f"DRY_RUN = {DRY_RUN}")
    main()
