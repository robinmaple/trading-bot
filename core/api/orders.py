import requests
from core.logger import logger
from config.env import DRY_RUN, RISK_OF_CAPITAL, PROFIT_TO_LOSS_RATIO, AVAILABLE_QUANTITY_RATIO

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
        self.price_service = price_service

    def place(self, symbol, symbol_id, entry_price, stop_price, account_id, buying_power, direction="Buy", quantity=None):
        if direction not in ["Buy", "Sell"]:
            raise ValueError("direction must be 'Buy' or 'Sell'")

        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share == 0:
            raise ValueError("Risk per share is zero!")

        max_risk_capital = RISK_OF_CAPITAL * buying_power
        computed_qty = int(max_risk_capital / risk_per_share)

        # Apply threshold logic
        min_required_qty = int(AVAILABLE_QUANTITY_RATIO * buying_power / entry_price)

        if quantity is None:
            quantity = computed_qty

        if quantity < 1 or quantity < min_required_qty:
            logger.warn(f"Quantity too low for {symbol}: {quantity} < {min_required_qty}")
            return None

        take_profit_price = (
            entry_price + risk_per_share * PROFIT_TO_LOSS_RATIO
            if direction == "Buy"
            else entry_price - risk_per_share * PROFIT_TO_LOSS_RATIO
        )

        logger.info(f"[Bracket Order] {symbol}: {direction} Entry={entry_price}, SL={stop_price}, TP={take_profit_price}, Qty={quantity}, DryRun={DRY_RUN}")

        if DRY_RUN:
            logger.info(f"DRY RUN: Simulating {direction} order for {symbol} at {entry_price}")
            position_entered = self.simulate_entry_fill(symbol, entry_price, direction)
            if position_entered:
                logger.info("DRY RUN: Position filled. Watching for exit trigger...")
                self.simulate_exit_logic(symbol, stop_price, take_profit_price, direction)
            return

        return self.order_service.place_limit_order(
            account_id=account_id,
            symbol_id=symbol_id,
            limit_price=entry_price,
            quantity=quantity,
            action=direction
        )

    def simulate_entry_fill(self, symbol, entry_price, direction):
        market_price = self.price_service.get_price(symbol)
        return market_price <= entry_price if direction == "Buy" else market_price >= entry_price

    def simulate_exit_logic(self, symbol, stop_loss_price, take_profit_price, direction):
        while True:
            price = self.price_service.get_price(symbol)
            logger.info(f"Watching {symbol} | Current: {price} | TP: {take_profit_price} | SL: {stop_loss_price}")
            if direction == "Buy":
                if price >= take_profit_price:
                    logger.info(f"DRY RUN: TAKE PROFIT hit at {price}")
                    break
                elif price <= stop_loss_price:
                    logger.info(f"DRY RUN: STOP LOSS hit at {price}")
                    break
            else:  # Sell
                if price <= take_profit_price:
                    logger.info(f"DRY RUN: TAKE PROFIT hit at {price}")
                    break
                elif price >= stop_loss_price:
                    logger.info(f"DRY RUN: STOP LOSS hit at {price}")
                    break

class MockPriceService:
    def get_price(self, symbol):
        import random
        return round(169 + random.uniform(-1, 1), 2)
