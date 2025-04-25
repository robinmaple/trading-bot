import json
import os
from datetime import datetime
import time
import asyncio
import math
from pathlib import Path
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
        """Process plans with strict buying power enforcement"""
        async with self._capital_lock:
            # Get fresh buying power snapshot
            total_bp = await self.order_client.get_buying_power(self.config.account_id)
            used_bp = sum(
                order.entry_price * order.quantity 
                for order in self.active_orders.values()
            )
            self.remaining_bp = total_bp - used_bp

            for symbol, plan in self.plan.get_active_plans().items():
                try:
                    # Price check and quantity calculation
                    current_price = await self.price_client.get_price(symbol)
                    bracket = BracketOrder.from_plan(plan, current_price)
                    bracket.quantity = self._calculate_safe_quantity(bracket)
                    
                    # Hard stop if no BP remaining
                    if self.remaining_bp <= 0:
                        logger.warning(f"Insufficient BP for {symbol}, remaining: {self.remaining_bp}")
                        break  # Not continue, to prevent order spamming

                    # Execute only if we can fully commit
                    required_bp = bracket.entry_price * bracket.quantity
                    if required_bp > self.remaining_bp:
                        logger.warning(f"Rejected {symbol}: Needs {required_bp}, has {self.remaining_bp}")
                        continue

                    if await self._execute_plan_safely(plan, bracket):
                        self.remaining_bp -= required_bp
                        logger.info(f"Committed {required_bp} for {symbol}, Remaining BP: {self.remaining_bp}")

                except Exception as e:
                    logger.error(f"Plan processing failed for {symbol}: {e}")

    async def _execute_plan_safely(self, plan: dict, bracket: BracketOrder) -> bool:
        """Full implementation with all dependencies"""
        symbol = plan['symbol']
        try:
            # Dry-run handling
            if self.config.dry_run:
                self._handle_dry_run_execution(plan, bracket)
                self.log_executed_order(plan, bracket, dry_run=True)
                return True

            # Live execution flow
            logger.info(f"Executing {symbol} qty={bracket.quantity}")
            
            # 1. Submit to broker
            success = await self.order_client.submit_bracket_order(
                bracket,
                account_id=self.config.account_id
            )
            if not success:
                logger.error(f"Broker rejected {symbol}")
                return False

            # 2. Verify execution
            if not await self._verify_broker_execution(symbol):
                logger.error(f"Failed verification for {symbol}")
                return False

            # 3. Get final execution price
            filled_price = await self.order_client.get_execution_price(symbol)
            if not filled_price:
                logger.error(f"No execution price for {symbol}")
                return False

            # 4. Persist state
            self._persist_executed_plan(symbol, filled_price, bracket.quantity)
            self.log_executed_order(plan, bracket, dry_run=False)
            
            logger.success(f"Successfully executed {symbol} @ {filled_price}")
            return True

        except Exception as e:
            logger.error(f"Critical error executing {symbol}: {e}")
            await self._revert_plan_status(symbol)
            return False
        
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
        """Dry-run with full capital tracking"""
        symbol = plan['symbol']
        self.plan.mark_executed(symbol, bracket.entry_price, bracket.quantity)
        self.active_orders[symbol] = bracket
        
        committed = bracket.entry_price * bracket.quantity
        logger.info(
            f"[DRY RUN] Executed {symbol} Qty:{bracket.quantity} "
            f"Value:{committed:.2f} | BP Remaining:{self.remaining_bp - committed:.2f}"
        )
        self._persist_executed_plan(symbol, bracket.entry_price, bracket.quantity)

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
        """Check broker for order fulfillment and clean up"""
        for symbol in list(self.active_orders.keys()):
            try:
                status = await self.order_client.get_order_status(symbol)
                
                if status == 'filled':
                    if symbol in self.plan.executed_plans:
                        continue  # Already processed
                        
                    filled_price = await self.order_client.get_execution_price(symbol)
                    self.plan.mark_executed(symbol, filled_price)
                    self.plan.save_to_file('config/trading_plan.json')
                    self.active_orders.pop(symbol)
                    
                elif status in ['canceled', 'rejected']:
                    logger.warning(f"Order {symbol} was {status}, releasing resources")
                    if symbol in self.plan.executed_plans:
                        self.plan.reset_execution_status(symbol)
                    self.active_orders.pop(symbol)
                    # Note: Capital will be refreshed on next _process_plans()

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
        """Logs detailed execution info to JSON files"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_data = {
                "symbol": plan["symbol"],
                "timestamp": timestamp,
                "dry_run": dry_run,
                "entry_price": bracket.entry_price,
                "stop_loss": bracket.stop_loss_price,
                "take_profit": bracket.take_profit_price,
                "quantity": bracket.quantity,
                "order_value": bracket.entry_price * bracket.quantity,
                "remaining_bp": self.remaining_bp,
                "risk_amount": (bracket.entry_price - bracket.stop_loss_price) * bracket.quantity,
                "plan_details": {
                    "reason": plan.get("reason"),
                    "strategy": plan.get("strategy")
                },
                "account_metrics": {
                    "committed_capital": self.committed_capital,
                    "remaining_bp": self.remaining_bp
                }
            }

            # Ensure log directory exists
            log_dir = Path("logs/executions")
            log_dir.mkdir(exist_ok=True)
            
            # Write to daily log file
            log_file = log_dir / f"executions_{datetime.now().date()}.json"
            with open(log_file, "a") as f:
                f.write(json.dumps(log_data) + "\n")
                
            # Also write individual execution file
            individual_file = log_dir / f"{plan['symbol']}_{timestamp}.json"
            with open(individual_file, "w") as f:
                json.dump(log_data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to log execution: {e}")
            
    async def _verify_order_execution(self, symbol: str) -> bool:
        """Confirm order exists with broker"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                status = await self.order_client.get_order_status(symbol)
                if status in ['filled', 'partially_filled', 'accepted']:
                    return True
                await asyncio.sleep(1 * (attempt + 1))  # Backoff
            except Exception as e:
                logger.warning(f"Verification attempt {attempt + 1} failed: {e}")
                continue
        return False
    
    async def _verify_broker_execution(self, symbol: str, timeout: int = 10) -> bool:
        """Verify order was actually executed with broker"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                status = await self.order_client.get_order_status(symbol)
                if status == 'filled':
                    return True
                elif status in ['canceled', 'rejected']:
                    logger.error(f"Order {symbol} was {status} by broker")
                    return False
                await asyncio.sleep(1)  # Polling interval
            except Exception as e:
                logger.warning(f"Verification failed for {symbol}: {e}")
                await asyncio.sleep(2)
        logger.error(f"Verification timeout for {symbol}")
        return False
    
    def _persist_executed_plan(self, symbol: str, price: float, quantity: int):
        """Atomic state persistence"""
        try:
            # Update in-memory state
            self.plan.mark_executed(symbol, price, quantity)
            
            # Write to temporary file first
            temp_path = 'config/trading_plan.json.tmp'
            with open(temp_path, 'w') as f:
                json.dump(self.plan.plans, f, indent=2)
            
            # Atomic rename
            os.replace(temp_path, 'config/trading_plan.json')
        except Exception as e:
            logger.critical(f"Persistence failed: {e}")
            raise

    async def _revert_plan_status(self, symbol: str):
        """Full rollback implementation"""
        try:
            # Cancel any open orders
            await self.order_client.cancel_order(symbol)
            
            # Revert state
            self.plan.reset_execution_status(symbol)
            self.active_orders.pop(symbol, None)
            
            # Persist reverted state
            self.plan.save_to_file('config/trading_plan.json')
            logger.warning(f"Rolled back {symbol}")
        except Exception as e:
            logger.error(f"Failed to revert {symbol}: {e}")    