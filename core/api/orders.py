import requests
from typing import Dict, List, Optional, Union
from core.logger import logger
import random

from config.env import (
    RISK_OF_CAPITAL,
    PROFIT_TO_LOSS_RATIO,
    AVAILABLE_QUANTITY_RATIO,
    DRY_RUN
)

class OrderService:
    def __init__(self, auth_client):
        self.auth = auth_client
        self.default_account = None  # Will be set by AccountManager

    def _make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Centralized request handler"""
        url = f"{self.auth.api_server}{endpoint}"
        headers = {'Authorization': f'Bearer {self.auth.get_valid_token()}'}
        
        try:
            response = requests.request(
                method,
                url,
                json=data,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_detail = getattr(e.response, 'json', lambda: {})().get('message', str(e))
            logger.error(f"API request failed: {error_detail}")
            raise

    def place_limit_order(self, 
                        account_id: str,
                        symbol_id: str,
                        limit_price: float,
                        quantity: int,
                        action: str) -> dict:
        """Place limit order with Questrade"""
        data = {
            "symbolId": symbol_id,
            "quantity": quantity,
            "limitPrice": limit_price,
            "orderType": "Limit",
            "timeInForce": "Day",
            "action": action.capitalize()
        }
        return self._make_request(
            'POST',
            f"v1/accounts/{account_id}/orders",
            data
        )

    def place_market_order(self,
                         account_id: str,
                         symbol_id: str,
                         quantity: int,
                         action: str) -> dict:
        """Place market order with Questrade"""
        data = {
            "symbolId": symbol_id,
            "quantity": quantity,
            "orderType": "Market",
            "timeInForce": "Day",
            "action": action.capitalize(),
            "primaryRoute": "AUTO",
            "secondaryRoute": "AUTO"
        }
        return self._make_request(
            'POST',
            f"v1/accounts/{account_id}/orders",
            data
        )

def place_stop_limit_order(self,
                         account_id: str,
                         symbol_id: str,
                         stop_price: float,
                         limit_price: float,
                         quantity: int,
                         action: str) -> dict:
    """Place stop-limit order with Questrade"""
    data = {
        "symbolId": symbol_id,
        "quantity": quantity,
        "stopPrice": stop_price,
        "limitPrice": limit_price,
        "orderType": "StopLimit",
        "timeInForce": "Day",
        "action": action.capitalize()
    }
    return self._make_request(
        'POST',
        f"v1/accounts/{account_id}/orders",
        data
    )

def place_stop_market_order(self,
                          account_id: str,
                          symbol_id: str,
                          stop_price: float,
                          quantity: int,
                          action: str) -> dict:
    """Place stop-market order with Questrade"""
    data = {
        "symbolId": symbol_id,
        "quantity": quantity,
        "stopPrice": stop_price,
        "orderType": "Stop",
        "timeInForce": "Day",
        "action": action.capitalize(),
        "primaryRoute": "AUTO",
        "secondaryRoute": "AUTO"
    }
    return self._make_request(
        'POST',
        f"v1/accounts/{account_id}/orders",
        data
    )

    def get_positions(self, account_id: str = None) -> List[Dict]:
        """Get all current positions"""
        account_id = account_id or self.default_account
        response = self._make_request(
            'GET',
            f"v1/accounts/{account_id}/positions"
        )
        return response.get('positions', [])

    def close_all_positions(self, account_id: str = None) -> None:
        """Close all open positions with market orders"""
        account_id = account_id or self.default_account
        positions = self.get_positions(account_id)
        
        for position in positions:
            try:
                self.place_market_order(
                    account_id=account_id,
                    symbol_id=position['symbolId'],
                    quantity=abs(int(float(position['currentPosition']))),
                    action='Sell' if position['side'] == 'Long' else 'Buy'
                )
                logger.info(f"Closed position: {position['symbol']}")
            except Exception as e:
                logger.error(f"Failed to close {position['symbol']}: {str(e)}")

from typing import Optional, Callable
from api.orders.enums import OrderStatus
from api.orders.order_service import OrderService
from api.pricing.price_service import PriceService
from utils.custom_logger import logger


class BracketOrder:
    def __init__(self, price_service: PriceService, order_service: OrderService):
        self.price_service = price_service
        self.order_service = order_service
        self.entry_order_id = None
        self.stop_loss_order_id = None
        self.profit_target_order_id = None

    def place_with_config(self,
                          symbol: str,
                          symbol_id: str,
                          account_id: str,
                          buying_power: float,
                          direction: str,
                          entry_type: str,
                          entry_details: dict,
                          stop_price: float,
                          quantity: Optional[int] = None,
                          status_callback: Optional[Callable] = None) -> Optional[dict]:
        """
        Generic method to place a bracket order using entry_type config
        - entry_type: 'limit' or 'stop-limit'
        - entry_details:
            For 'limit': {'entry_price': float}
            For 'stop-limit': {'trigger_price': float, 'limit_offset': float}
        """
        if entry_type == "limit":
            return self._place_limit_bracket_order(
                symbol, symbol_id, entry_details["entry_price"], stop_price,
                account_id, buying_power, direction, quantity, status_callback
            )
        elif entry_type == "stop-limit":
            return self.place_with_breakout_entry(
                symbol, symbol_id, entry_details["trigger_price"], stop_price,
                account_id, buying_power, direction, quantity,
                entry_details.get("limit_offset", 0.002), status_callback
            )
        else:
            raise ValueError(f"Unsupported entry_type: {entry_type}")

    def _place_limit_bracket_order(self,
                                   symbol: str,
                                   symbol_id: str,
                                   entry_price: float,
                                   stop_price: float,
                                   account_id: str,
                                   buying_power: float,
                                   direction: str = "Buy",
                                   quantity: Optional[int] = None,
                                   status_callback: Optional[Callable] = None) -> Optional[dict]:
        """
        Internal method to place a bracket order using a limit entry.
        """
        logger.info(f"Placing limit order for {symbol} at {entry_price} with stop at {stop_price}")
        if not quantity:
            quantity = self.price_service.calculate_quantity(entry_price, buying_power)
        if quantity == 0:
            logger.warn(f"Calculated quantity is 0 for {symbol} at {entry_price}")
            return None

        self.entry_order_id = self.order_service.place_limit_order(
            account_id, symbol_id, direction, quantity, entry_price, status_callback)

        if not self.entry_order_id:
            logger.error("Entry order placement failed.")
            return None

        # Place stop-loss (always a stop-market)
        self.stop_loss_order_id = self.order_service.place_stop_market_order(
            account_id, symbol_id, "Sell" if direction == "Buy" else "Buy",
            quantity, stop_price, parent_id=self.entry_order_id)

        return {
            "entry_order_id": self.entry_order_id,
            "stop_loss_order_id": self.stop_loss_order_id,
            "quantity": quantity
        }

    def place_with_breakout_entry(self,
                                   symbol: str,
                                   symbol_id: str,
                                   trigger_price: float,
                                   stop_price: float,
                                   account_id: str,
                                   buying_power: float,
                                   direction: str = "Buy",
                                   quantity: Optional[int] = None,
                                   limit_offset: float = 0.002,
                                   status_callback: Optional[Callable] = None) -> Optional[dict]:
        """
        Place a breakout-style bracket order:
        - Stop-limit entry (trigger + limit offset)
        - Stop-loss as stop-market
        """
        limit_price = trigger_price * (1 + limit_offset) if direction == "Buy" else trigger_price * (1 - limit_offset)

        logger.info(f"Placing stop-limit breakout order for {symbol}. Trigger: {trigger_price}, Limit: {limit_price}, Stop-loss: {stop_price}")
        if not quantity:
            quantity = self.price_service.calculate_quantity(trigger_price, buying_power)
        if quantity == 0:
            logger.warn(f"Calculated quantity is 0 for {symbol} at trigger price {trigger_price}")
            return None

        self.entry_order_id = self.order_service.place_stop_limit_order(
            account_id, symbol_id, direction, quantity,
            trigger_price=trigger_price, limit_price=limit_price, status_callback=status_callback)

        if not self.entry_order_id:
            logger.error("Entry stop-limit order placement failed.")
            return None

        self.stop_loss_order_id = self.order_service.place_stop_market_order(
            account_id, symbol_id, "Sell" if direction == "Buy" else "Buy",
            quantity, stop_price, parent_id=self.entry_order_id)

        return {
            "entry_order_id": self.entry_order_id,
            "stop_loss_order_id": self.stop_loss_order_id,
            "quantity": quantity
        }

class MockPriceService:
    def get_price(self, symbol: str) -> float:
        """Generate mock price data"""
        import random
        return round(169 + random.uniform(-1, 1), 2)

    def simulate_exit(self,
                    bracket_order: BracketOrder,
                    symbol: str,
                    order_data: Dict) -> None:
        """Simulate exit scenario"""
        direction = order_data.get("side", "Buy")
        entry = order_data["entry"]
        stop = order_data["stop"]
        risk = abs(entry - stop)
        
        profit_target = (entry + risk * PROFIT_TO_LOSS_RATIO if direction == "Buy"
                        else entry - risk * PROFIT_TO_LOSS_RATIO)
        
        logger.info(f"[SIMULATION] Watching {symbol}: Entry={entry}, SL={stop}, TP={profit_target}")
        
        simulated_exit_price = random.choice([stop, profit_target])
        logger.info(f"[SIMULATION] Exit triggered for {symbol} at {simulated_exit_price}")