import json
import os
from pathlib import Path
from core.models import OrderMethod, OrderDirection
from config.env import (
    PROFIT_TO_LOSS_RATIO as DEFAULT_PROFIT_TO_LOSS_RATIO,
    RISK_OF_CAPITAL as DEFAULT_RISK_OF_CAPITAL,
    AVAILABLE_QUANTITY_RATIO as DEFAULT_AVAILABLE_QUANTITY_RATIO
)

class TradingPlanManager:
    def __init__(self, filepath=None):
        self.filepath = filepath or Path("config/trading_plan.json")
        self.orders = []
        self.load_trading_plan()

    def load_trading_plan(self):
        with open(self.filepath) as f:
            plan = json.load(f)
        self.orders = [self._prepare_order(order) for order in plan]

    def _prepare_order(self, raw):
        required = ["symbol", "side", "entry", "stop"]
        for field in required:
            if field not in raw:
                raise ValueError(f"Missing required field: {field} in trading plan entry: {raw}")

        side = raw["side"].capitalize()
        if side not in ["Buy", "Sell"]:
            raise ValueError(f"Side must be 'Buy' or 'Sell': {raw}")

        entry_type = raw.get("entry_type", "limit").lower()
        if entry_type not in [OrderMethod.LIMIT, OrderMethod.STOP_LIMIT]:
            raise ValueError(f"Invalid entry_type: {entry_type}")

        entry_stop_trigger = raw.get("entry_stop_trigger")

        return {
            "symbol": raw["symbol"],
            "side": side.value,
            "entry": float(raw["entry"]),
            "stop": float(raw["stop"]),
            "entry_type": entry_type.value,
            "entry_stop_trigger": float(entry_stop_trigger) if entry_stop_trigger else None,
            "profit_to_loss_ratio": float(raw.get("profit_to_loss_ratio", DEFAULT_PROFIT_TO_LOSS_RATIO)),
            "risk_of_capital": float(raw.get("risk_of_capital", DEFAULT_RISK_OF_CAPITAL)),
            "available_quantity_ratio": float(raw.get("available_quantity_ratio", DEFAULT_AVAILABLE_QUANTITY_RATIO)),
            "status": "active"
        }

    def get_active_orders(self):
        return [order for order in self.orders if order["status"] == "active"]

    def mark_in_position(self, symbol):
        for order in self.orders:
            if order["symbol"] == symbol:
                order["status"] = "in_position"
            elif order["status"] == "active":
                order["status"] = "inactive"

    def mark_expired(self, symbol):
        for order in self.orders:
            if order["symbol"] == symbol:
                order["status"] = "expired"

    def reactivate_eligible_orders(self):
        for order in self.orders:
            if order["status"] == "inactive":
                order["status"] = "active"

    def get_first_triggerable_order(self, buying_power):
        """Returns the first active order that meets the buying power requirements"""
        for order in self.orders:
            if order['status'] != 'active':
                continue
                
            entry_price = order['entry']
            risk_per_share = abs(entry_price - order['stop'])
            max_risk_capital = order['risk_of_capital'] * buying_power
            computed_qty = int(max_risk_capital / risk_per_share)
            
            min_required_qty = int(order['available_quantity_ratio'] * buying_power / entry_price)
            
            if computed_qty >= 1 and computed_qty >= min_required_qty:
                # Add symbol_id if needed (you might need to fetch this elsewhere)
                order_data = order.copy()
                order_data['symbol_id'] = None  # You'll need to populate this
                order_data['quantity'] = computed_qty
                return order['symbol'], order_data
                
        return None, None

    def __repr__(self):
        return f"TradingPlanManager(orders={self.orders})"
