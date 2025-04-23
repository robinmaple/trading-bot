# core/execution/bracket_order.py
from typing import Optional, Dict, Callable
from datetime import datetime
import uuid
import json
from core.logger import logger
from core.models import OrderStatus, OrderType, OrderDirection
from core.brokerages.protocol import BrokerageProtocol
from config.broker_config import load_broker_config

class BracketOrder:
    def __init__(
        self,
        brokerage: BrokerageProtocol,
        symbol: str,
        quantity: float,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        plan_id: str,
        entry_type: OrderType = OrderType.LIMIT,
        breakout_trigger_price: Optional[float] = None
    ):
        self.brokerage = brokerage
        self.symbol = symbol
        self.quantity = quantity
        self.entry_price = entry_price
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price
        self.plan_id = plan_id
        self.entry_type = entry_type
        self.breakout_trigger_price = breakout_trigger_price
        self.order_group_id = str(uuid.uuid4())
        # load broker config from config/broker_config.yaml
        self.broker_name = getattr(brokerage, "name", "unknown").lower()
        self.broker_config = load_broker_config(self.broker_name)
        self.supports_native = self.broker_config.get("supports_native_bracket", False)
        # Status Tracking
        self.lifecycle_status = OrderStatus.PENDING  # NEW: Tracks order progress
        self.order_type_status = None               # EXISTING: Your classification system
        self.entry_order_id: Optional[str] = None
        self.stop_loss_order_id: Optional[str] = None
        self.take_profit_order_id: Optional[str] = None
        self.entry_filled = False

    async def execute(self) -> Dict:
        """Main execution flow with config-aware bracket logic"""
        self.lifecycle_status = OrderStatus.PLACED

        if self.supports_native:
            result = await self._execute_native_bracket()
        elif self.entry_type == OrderType.LIMIT:
            result = await self._execute_limit_entry()
        elif self.entry_type == OrderType.STOP_LIMIT:
            result = await self._execute_stop_limit_entry()
        else:
            raise ValueError(f"Unsupported entry type: {self.entry_type}")

        self._log_order("placed")
        return result

    async def _execute_limit_entry(self) -> Dict:
        """Limit order entry workflow"""
        try:
            # Place entry order
            entry_result = await self.brokerage.place_limit_order(
                account_id=self._get_account_id(),
                symbol=self.symbol,
                limit_price=self.entry_price,
                quantity=self.quantity,
                action=OrderDirection.BUY.value
            )
            self.entry_order_id = entry_result.get("order_id")
            self.order_type_status = OrderStatus.ENTRY  # Your existing system

            # Place stop-loss
            sl_result = await self.brokerage.place_stop_order(
                account_id=self._get_account_id(),
                symbol=self.symbol,
                stop_price=self.stop_loss_price,
                quantity=self.quantity,
                action=OrderDirection.SELL.value
            )
            self.stop_loss_order_id = sl_result.get("order_id")

            return self._prepare_response()

        except Exception as e:
            self.lifecycle_status = OrderStatus.FAILED
            logger.error(f"Limit entry failed: {str(e)}")
            raise

    async def _execute_stop_limit_entry(self) -> Dict:
        """Stop-limit entry workflow"""
        if not self.breakout_trigger_price:
            raise ValueError("breakout_trigger_price required for stop-limit")

        try:
            # Place stop-limit entry
            entry_result = await self._place_stop_limit_entry()
            self.entry_order_id = entry_result.get("order_id")
            self.order_type_status = OrderStatus.ENTRY  # Your existing system

            # Place stop-loss
            sl_result = await self.brokerage.place_stop_order(
                account_id=self._get_account_id(),
                symbol=self.symbol,
                stop_price=self.stop_loss_price,
                quantity=self.quantity,
                action=OrderDirection.SELL.value
            )
            self.stop_loss_order_id = sl_result.get("order_id")

            return self._prepare_response()

        except Exception as e:
            self.lifecycle_status = OrderStatus.FAILED
            logger.error(f"Stop-limit entry failed: {str(e)}")
            raise

    async def on_entry_filled(self):
        """Handle entry fill event (places take-profit)"""
        if not self.entry_filled:
            self.entry_filled = True
            self.lifecycle_status = OrderStatus.FILLED
            self._log_order("filled")

            # Place take-profit
            tp_result = await self.brokerage.place_limit_order(
                account_id=self._get_account_id(),
                symbol=self.symbol,
                limit_price=self.take_profit_price,
                quantity=self.quantity,
                action=OrderDirection.SELL.value
            )
            self.take_profit_order_id = tp_result.get("order_id")
            self.order_type_status = OrderStatus.PROFIT_TARGET  # Your system
            self._log_order("tp_placed")

    def _prepare_response(self) -> Dict:
        """Standardized success response"""
        return {
            "status": self.lifecycle_status.value,
            "order_type": self.order_type_status.value,
            "entry_order_id": self.entry_order_id,
            "stop_loss_order_id": self.stop_loss_order_id,
            "order_group_id": self.order_group_id
        }

    def _log_order(self, event: str):
        """Unified logging with both status systems"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": self.symbol,
            "event": event,
            "lifecycle_status": self.lifecycle_status.value,
            "order_type_status": self.order_type_status.value if self.order_type_status else None,
            "order_group_id": self.order_group_id,
            "plan_id": self.plan_id,
            "entry_price": self.entry_price,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price
        }
        logger.info(json.dumps(log_entry, default=str))

    def _get_account_id(self) -> str:
        """Get account ID from your configuration"""
        # Implement based on your account management
        return "default_account"  # Replace with actual logic

    async def _place_stop_limit_entry(self) -> Dict:
        """Broker-specific stop-limit implementation"""
        # Implement based on your brokerage's requirements
        raise NotImplementedError("Stop-limit entry requires broker-specific implementation")
    
    async def _execute_native_bracket(self) -> Dict:
        """Native bracket order flow if supported by broker"""
        try:
            result = await self.brokerage.place_bracket_order(
                account_id=self._get_account_id(),
                symbol=self.symbol,
                quantity=self.quantity,
                entry_price=self.entry_price,
                stop_loss_price=self.stop_loss_price,
                take_profit_price=self.take_profit_price,
                entry_type=self.entry_type.value,  # 'limit' or 'stop_limit'
                group_id=self.order_group_id
            )
            self.entry_order_id = result.get("entry_order_id")
            self.stop_loss_order_id = result.get("stop_loss_order_id")
            self.take_profit_order_id = result.get("take_profit_order_id")
            self.lifecycle_status = OrderStatus.PLACED
            self.order_type_status = OrderStatus.ENTRY

            return self._prepare_response()
        except Exception as e:
            self.lifecycle_status = OrderStatus.FAILED
            logger.error(f"Native bracket order failed: {str(e)}")
            raise
