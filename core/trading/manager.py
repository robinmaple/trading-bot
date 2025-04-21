# core/trading/manager.py
import asyncio
from dataclasses import dataclass
from typing import Dict
from core.logger import logger
from core.orders.bracket import BracketOrder
from core.brokerages.protocol import OrderProtocol, PriceProtocol
from core.trading.plan import TradingPlan
from config.env import DRY_RUN, ACCOUNT_ID, CLOSE_TRADES_BUFFER_MINUTES

@dataclass
class TradingConfig:
    dry_run: bool = DRY_RUN
    account_id: str = ACCOUNT_ID
    close_buffer_minutes: int = CLOSE_TRADES_BUFFER_MINUTES

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

    async def run(self):
        """Main trading event loop"""
        logger.info("Starting trading manager")
        
        while True:
            if not await self._should_trade():
                await asyncio.sleep(60)
                continue
                
            await self._process_plans()
            await asyncio.sleep(5)

    async def _should_trade(self) -> bool:
        """Check market conditions"""
        # Implement your market hours/risk checks here
        return True

    async def _process_plans(self):
        """Check and execute all active plans"""
        for symbol, plan in self.plan.get_active_plans().items():
            current_price = await self.price_client.get_price(symbol)
            
            if self._should_trigger(plan, current_price):
                await self._execute_plan(plan, current_price)

    def _should_trigger(self, plan: dict, price: float) -> bool:
        """Check plan-specific conditions"""
        # Implement your trigger logic
        return True

    async def _execute_plan(self, plan: dict, current_price: float):
        """Execute a single trading plan"""
        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would execute: {plan}")
            return
            
        try:
            bracket = BracketOrder.from_plan(plan, current_price)
            result = await self.order_client.submit_bracket_order(
                bracket, 
                account_id=self.config.account_id
            )
            
            if result.success:
                self.plan.mark_executed(plan['symbol'])
                self.active_orders[plan['symbol']] = bracket
                logger.info(f"Order executed: {result}")
                
        except Exception as e:
            logger.error(f"Order failed: {e}")