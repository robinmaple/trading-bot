import json
import os
from datetime import datetime
import asyncio
import math
from dataclasses import dataclass
from typing import Dict
from core.logger import logger
from core.orders.bracket import BracketOrder
from core.brokerages.protocol import OrderProtocol, PriceProtocol
from core.trading.plan import TradingPlan
from config.env import DRY_RUN


from config.env import (
    DRY_RUN,
    ACCOUNT_ID,
    CLOSE_TRADES_BUFFER_MINUTES,
    RISK_OF_CAPITAL,
    AVAILABLE_QUANTITY_RATIO
)

@dataclass
class TradingConfig:
    dry_run: bool = DRY_RUN
    account_id: str = ACCOUNT_ID
    close_buffer_minutes: int = CLOSE_TRADES_BUFFER_MINUTES
    risk_of_capital: float = RISK_OF_CAPITAL
    available_quantity_ratio: float = AVAILABLE_QUANTITY_RATIO
    persist_dry_run: bool = False  # Add this new field

class TradingManager:
    def __init__(
        self,
        order_client: OrderProtocol,
        price_client: PriceProtocol,
        plan_path: str = 'config/trading_plan.json'
    ):
        self.order_client = order_client
        self.price_client = price_client
        self.config = TradingConfig()
        self.plan = TradingPlan.load_from_file(plan_path)
        self.active_orders: Dict[str, BracketOrder] = {}
        self._capital_lock = asyncio.Lock()
        self.remaining_bp = 0.0

        self._capital_lock = asyncio.Lock()
        self.remaining_bp = 0.0
        self.committed_capital = 0.0  # Track total committed

    async def run(self):
        """Main trading loop with execution tracking"""
        logger.info("Starting trading manager with execution tracking")
        
        while True:
            if not await self._should_trade():
                await asyncio.sleep(60)
                continue
            
            # Verify existing orders first
            await self.verify_active_orders()
            
            # Process new plans
            await self._process_plans()
            await asyncio.sleep(5)  # Reduced from 60 to catch executions faster    
        
    async def _process_plans(self):
        """Check and execute all active plans with capital awareness"""
        active_plans = self.plan.get_active_plans()
        if not active_plans:
            return

        async with self._capital_lock:
            # Refresh buying power snapshot
            self.remaining_bp = await self.order_client.get_buying_power(
                account_id=self.config.account_id
            ) - self.committed_capital

            for symbol, plan in active_plans.items():
                try:
                    current_price = await self.price_client.get_price(
                        self._normalize_symbol(symbol)
                    )
                    if not current_price:
                        continue

                    if not self._should_trigger(plan, current_price):
                        continue

                    bracket = BracketOrder.from_plan(plan, current_price)
                    bracket.quantity = self._calculate_safe_quantity(bracket)

                    if bracket.quantity <= 0:
                        logger.info(f"Skipped {symbol}: insufficient remaining capital")
                        continue

                    # Track capital commitment
                    order_value = bracket.entry_price * bracket.quantity
                    self.remaining_bp -= order_value
                    self.committed_capital += order_value

                    await self._execute_plan(plan, bracket)

                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")

    def _calculate_safe_quantity(self, bracket: BracketOrder) -> int:
        """Thread-safe quantity calculation with remaining BP"""
        if self.remaining_bp <= 0:
            return 0

        quantity = self.adjust_quantity_for_capital(
            buying_power=self.remaining_bp,  # Use remaining capital
            entry_price=bracket.entry_price,
            stop_loss_price=bracket.stop_loss_price,
            risk_of_capital=self.config.risk_of_capital,
            available_quantity_ratio=self.config.available_quantity_ratio
        )

        # Ensure we don't exceed remaining BP
        max_possible = int(self.remaining_bp / bracket.entry_price)
        return min(quantity, max_possible)

    async def _execute_plan(self, plan: dict, bracket: BracketOrder):
        symbol = plan['symbol']        
        try:
            if self.config.dry_run:
                self._handle_dry_run_execution(plan, bracket)
                return

            result = await self.order_client.submit_bracket_order(
                bracket,
                account_id=self.config.account_id
            )
            
            if result.success:
                # Mark executed and persist immediately
                self.plan.mark_executed(plan['symbol'], bracket.entry_price)
                self.plan.save_to_file('config/trading_plan.json')  # Immediate persistence
                
                self.active_orders[plan['symbol']] = bracket
                self.log_executed_order(plan, bracket, dry_run=False)
                logger.info(f"Order executed: {result}")

        except Exception as e:
            logger.error(f"Order failed for {plan['symbol']}: {e}")
            # Revert execution status if needed
            if symbol in self.plan.executed_plans:
                self.plan.reset_execution_status(symbol)

    def _handle_dry_run_execution(self, plan: dict, bracket: BracketOrder):
        """Dry-run execution with full tracking"""
        self.plan.mark_executed(plan['symbol'], bracket.entry_price)
        self.active_orders[plan['symbol']] = bracket
        self.log_executed_order(plan, bracket, dry_run=True)
        
        logger.info(
            f"[DRY RUN] Executed: {plan['symbol']} Qty: {bracket.quantity} "
            f"@ {bracket.entry_price} | TP: {bracket.take_profit_price} "
            f"| SL: {bracket.stop_loss_price}"
        )
        # Persist even in dry-run for testing
        if self.config.persist_dry_run:  
            self.plan.save_to_file('config/trading_plan.json')
            
    async def _handle_live_order(self, plan: dict, bracket: BracketOrder):
        """Preserve all existing live execution logic"""
        result = await self.order_client.submit_bracket_order(
            bracket,
            account_id=self.config.account_id
        )
        
        if result.success:
            self.plan.mark_executed(plan['symbol'])
            self.active_orders[plan['symbol']] = bracket
            self.log_executed_order(plan, bracket, dry_run=False)
            logger.info(f"Order executed: {result}")
        else:
            raise Exception(f"Order submission failed: {result}")
        
    async def verify_active_orders(self):
        """Check broker for order fulfillment and update execution status"""
        for symbol in list(self.active_orders.keys()):
            try:
                status = await self.order_client.get_order_status(symbol)
                if status in ['filled', 'completed'] and symbol not in self.plan.executed_plans:
                    filled_price = await self.order_client.get_execution_price(symbol)
                    self.plan.mark_executed(symbol, filled_price)
                    self.plan.save_to_file('config/trading_plan.json')
                    self.active_orders.pop(symbol)
            except Exception as e:
                logger.error(f"Failed to verify order {symbol}: {e}")

    async def _should_trade(self) -> bool:
        """Check market conditions"""
        return True  # Placeholder for real logic

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol format for the price client"""
        if '/' in symbol:  # Forex pair
            return symbol.replace('/', '')
        return symbol
    
    def _should_trigger(self, plan: dict, price: float) -> bool:
        """Check plan-specific conditions"""
        return True  # Placeholder for real logic
    
    def adjust_quantity_for_capital(
        self,
        buying_power: float,
        entry_price: float,
        stop_loss_price: float,
        risk_of_capital: float,
        available_quantity_ratio: float
    ) -> int:
        """
        Adjust quantity based on risk and available buying power.
        """
        if entry_price <= stop_loss_price:
            return 0  # Invalid setup

        # Calculate risk-based quantity
        risk_per_share = entry_price - stop_loss_price
        max_risk_amount = buying_power * risk_of_capital
        ideal_quantity = int(max_risk_amount / risk_per_share)

        if ideal_quantity <= 0:
            return 0

        # Determine max quantity by buying power
        max_affordable_quantity = int(buying_power / entry_price)

        quantity = min(ideal_quantity, max_affordable_quantity)

        if quantity < math.ceil(ideal_quantity * available_quantity_ratio):
            return 0

        return quantity
    
    def log_executed_order(self, plan: dict, bracket: BracketOrder, dry_run: bool):
        """Log all executions (both dry-run and real)"""
        try:
            log_dir = "logs/executions"
            os.makedirs(log_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = "dry_" if dry_run else "live_"
            filename = f"{log_dir}/{prefix}{plan['symbol']}_{timestamp}.json"

            data = {
                "symbol": plan["symbol"],
                "dry_run": dry_run,
                "timestamp": timestamp,
                "entry_price": bracket.entry_price,
                "stop_loss": bracket.stop_loss_price,
                "take_profit": bracket.take_profit_price,
                "quantity": bracket.quantity,
                "plan": plan,
                "type": bracket.entry_type,
                "side": bracket.side
            }

            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Execution logged to {filename}")
        except Exception as e:
            logger.error(f"Failed to log order: {e}")