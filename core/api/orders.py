import requests
import time
from core.logger import logger
from config.env import DRY_RUN, RISK_OF_CAPITAL, PROFIT_TO_LOSS_RATIO

class OrderService:
    def __init__(self, auth_client):
        self.auth = auth_client

    def place_limit_order(self, account_id, symbol_id, limit_price, quantity, action):
        try:
            url = f"{self.auth.api_server}v1/accounts/{account_id}/orders"
            headers = {'Authorization': f'Bearer {self.auth.get_valid_token()}'}
            data = {
                "symbolId": symbol_id,
                "quantity": quantity,
                "limitPrice": limit_price,
                "orderType": "Limit",
                "timeInForce": "Day",
                "action": action
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            # Get detailed error message
            if response.status_code != 200:
                error_detail = response.json().get('message', 'No error details')
                logger.error(f"Order failed ({response.status_code}): {error_detail}")
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Order placement crashed: {str(e)}")
            raise

class BracketOrder:
    def __init__(self, order_service, price_service):
        self.order_service = order_service
        self.price_service = price_service  # New: to monitor prices

    def place(self, symbol, entry_price, stop_loss_price, account_id, quantity=None):
        risk_per_share = entry_price - stop_loss_price
        if quantity is None:
            quantity = int(RISK_OF_CAPITAL / risk_per_share)
            if quantity < 1:
                raise ValueError("Quantity < 1. Adjust risk.")

        take_profit_price = entry_price + (entry_price - stop_loss_price) * PROFIT_TO_LOSS_RATIO
        logger.info(f"[Bracket Order] {symbol}: Entry={entry_price}, SL={stop_loss_price}, TP={take_profit_price}, Qty={quantity}, DryRun={DRY_RUN}")

        if DRY_RUN:
            logger.info(f"DRY RUN: Simulating entry order for {symbol} at {entry_price}")
            position_entered = self.simulate_entry_fill(symbol, entry_price)
            if position_entered:
                logger.info(f"DRY RUN: Entered position. Watching for exit...")
                self.simulate_exit_logic(symbol, stop_loss_price, take_profit_price)
            return

        # Actual order placement: Entry first
        entry_response = self.order_service.place_limit_order(
            symbol=symbol,
            price=entry_price,
            quantity=quantity,
            account_id=account_id,
            action="Buy"
        )
        # Later enhancement: poll until filled, then send stop-loss and take-profit orders
        return entry_response

    def simulate_entry_fill(self, symbol, entry_price):
        # For dry run, just assume immediate fill (real version polls quote API)
        market_price = self.price_service.get_price(symbol)
        return market_price <= entry_price

    def simulate_exit_logic(self, symbol, stop_loss_price, take_profit_price):
        while True:
            price = self.price_service.get_price(symbol)
            logger.info(f"Watching {symbol} | Current: {price} | TP: {take_profit_price} | SL: {stop_loss_price}")

            if price >= take_profit_price:
                logger.info(f"DRY RUN: TAKE PROFIT triggered at {price}")
                break
            elif price <= stop_loss_price:
                logger.info(f"DRY RUN: STOP LOSS triggered at {price}")
                break

class MockPriceService:
    def get_price(self, symbol):
        import random
        # Simulate price movement around 169~171
        return round(169 + random.uniform(-1, 1), 2)
