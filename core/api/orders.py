import requests
from typing import Dict, List, Optional, Union
from core.logger import logger
import uuid
from core.pricing.service import MultiProviderPriceService
from typing import Optional, Callable
import json
import os
from datetime import datetime
from typing import Dict, Any
from core.models import (OrderLifecycle, OrderType, OrderMethod, OrderStatus)
from core.symbols.symbol_resolver import SymbolResolver

from config.env import (
    RISK_OF_CAPITAL,
    PROFIT_TO_LOSS_RATIO,
    AVAILABLE_QUANTITY_RATIO,
    DRY_RUN,
    LOG_DIR,
    LOG_FILE
)

class OrderService:
    def __init__(self, auth_client):
        self.auth = auth_client
        self.default_account = None
        self.symbol_resolver = SymbolResolver() 
        os.makedirs(LOG_DIR, exist_ok=True)

    def _mock_order_response(self, data: dict) -> dict:
        """Generate fake order ID response in dry-run mode."""
        order_id = str(uuid.uuid4())
        logger.info(f"[DRY_RUN] Simulated order: {data}")
        return {"id": order_id, "status": "Simulated"}

    def _make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Centralized request handler with dry-run logic"""
        if DRY_RUN:
            return self._mock_order_response(data)

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

    def place_limit_order(self, account_id, symbol_id, limit_price, quantity, action):
        data = {
            "symbolId": symbol_id,
            "quantity": quantity,
            "limitPrice": limit_price,
            "orderType": "Limit",
            "timeInForce": "Day",
            "action": action.capitalize()
        }
        return self._make_request('POST', f"v1/accounts/{account_id}/orders", data)

    def place_market_order(self, account_id, symbol_id, quantity, action):
        data = {
            "symbolId": symbol_id,
            "quantity": quantity,
            "orderType": "Market",
            "timeInForce": "Day",
            "action": action.capitalize(),
            "primaryRoute": "AUTO",
            "secondaryRoute": "AUTO"
        }
        return self._make_request('POST', f"v1/accounts/{account_id}/orders", data)

    def place_stop_limit_order(self, account_id, symbol_id, stop_price, limit_price, quantity, action):
        data = {
            "symbolId": symbol_id,
            "quantity": quantity,
            "stopPrice": stop_price,
            "limitPrice": limit_price,
            "orderType": "StopLimit",
            "timeInForce": "Day",
            "action": action.capitalize()
        }
        return self._make_request('POST', f"v1/accounts/{account_id}/orders", data)

    def place_stop_market_order(self, account_id, symbol_id, stop_price, quantity, action):
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
        return self._make_request('POST', f"v1/accounts/{account_id}/orders", data)

    def log_executed_order(self, symbol:str, order_data: dict):
        resolved = self.symbol_resolver.resolve(symbol) or {}
        
        log_entry = {
            "symbol": symbol,
            "symbol_id": resolved.get("symbol_id"),
            "exchange": resolved.get("exchange"),
            "asset_type": resolved.get("asset_type"),
            "price_service_symbol": resolved.get("price_service_symbol"),
            "broker_symbol_id": resolved.get("broker_symbol_id"),
            "order_type": order_data.get("type"),
            "side": order_data.get("side"),
            "quantity": order_data.get("quantity"),
            "price": order_data.get("price"),
            "timestamp": order_data.get("timestamp"),
            "status": order_data.get("status"),
            "filled_qty": order_data.get("filled_qty", 0),
            "fill_price": order_data.get("fill_price", None),
        }

        # Append to file or save as JSON — your existing logic
        logger.info(f"[ORDER LOG] {json.dumps(log_entry, indent=2)}")

        try:
            with open(LOG_FILE, "a") as f:
                f.write(json.dumps(order_data) + "\n")
        except Exception as e:
            logger.error(f"Failed to log executed order: {e}")

    def update_executed_order(self, update_data: dict):
        """
        Updates an existing log entry matching the order_group_id.
        """
        try:
            updated = False
            lines = []
            with open(LOG_FILE, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get("order_group_id") == update_data.get("order_group_id"):
                        entry.update(update_data)
                        updated = True
                    lines.append(entry)

            if updated:
                with open(LOG_FILE, "w") as f:
                    for entry in lines:
                        f.write(json.dumps(entry) + "\n")
            else:
                logger.warning(f"No matching entry found for update: {update_data.get('order_group_id')}")

        except Exception as e:
            logger.error(f"Failed to update executed order: {e}")

class BracketOrder:
    def __init__(
            self,
            symbol: str,
            quantity: int,
            entry_price: float,
            stop_loss_price: float,
            take_profit_price: float,
            order_service: OrderService,
            plan_id: str,
            entry_type: str = "limit",
            breakout_trigger_price: Optional[float] = None,
            price_service: Optional[MultiProviderPriceService] = None
        ):
            self.symbol = symbol
            self.quantity = quantity
            self.entry_price = entry_price
            self.stop_loss_price = stop_loss_price
            self.take_profit_price = take_profit_price
            self.entry_type: OrderMethod = OrderMethod(entry_type)
            self.breakout_trigger_price = breakout_trigger_price
            self.plan_id = plan_id
            self.order_service = order_service
            self.order_group_id = str(uuid.uuid4())

            self.status = OrderStatus.PENDING
            self.entry_order_id = None
            self.stop_loss_order_id = None
            self.take_profit_order_id = None

            self.price_service = price_service
            self.entry_filled = False

    def log_entry_order(self):
        self.order_service.log_executed_order({
            "plan_id": self.plan_id,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "status": OrderLifecycle.PLACED.value,
            "order_type": OrderType.ENTRY.value,
            "executed_at": datetime.utcnow().isoformat(),
            "is_paper": self.order_service.dry_run,
            "order_group_id": self.order_group_id
        })

    def log_exit_order(self, pnl: float, exit_price: float):
        self.order_service.update_executed_order({
            "order_group_id": self.order_group_id,
            "exit_price": exit_price,
            "pnl": pnl,
            "status": OrderLifecycle.CLOSED.value,
            "closed_at": datetime.utcnow().isoformat()
        })

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

        logger.info(f"Placing limit bracket order for {self.symbol} at {self.entry_price}")
        self.status = OrderStatus.PLACED
        self.entry_order_id = "ENTRY_ORDER_ID_MOCK"
        self.log_entry_order()

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
        if self.breakout_trigger_price is None:
            raise ValueError("Breakout trigger price is required for stop-limit entries.")

        logger.info(f"Monitoring {self.symbol} for breakout entry at {self.breakout_trigger_price}")
        self.status = OrderStatus.PLACED
        self.entry_order_id = "ENTRY_ORDER_ID_MOCK"
        self.log_entry_order()

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
    
    def on_entry_filled(self, account_id: str, symbol_id: str, direction: str):
        """
        Call this when entry is filled to place SL and TP orders.
        """
        logger.info(f"[BRACKET] Entry filled for {self.symbol}. Placing SL/TP orders.")
        self.entry_filled = True

        # Place Stop-Loss
        self.stop_loss_order_id = self.order_service.place_stop_market_order(
            account_id=account_id,
            symbol_id=symbol_id,
            stop_price=self.stop_loss_price,
            quantity=self.quantity,
            action="Sell" if direction == "Buy" else "Buy"
        )

        # Place Take-Profit
        self.take_profit_order_id = self.order_service.place_limit_order(
            account_id=account_id,
            symbol_id=symbol_id,
            limit_price=self.take_profit_price,
            quantity=self.quantity,
            action="Sell" if direction == "Buy" else "Buy"
        )

        logger.info(f"[BRACKET] SL/TP placed: SL={self.stop_loss_price}, TP={self.take_profit_price}")
