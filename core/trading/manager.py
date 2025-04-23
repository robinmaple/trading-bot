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
        return True  # Placeholder for real logic

    async def _process_plans(self):
        """Check and execute all active plans with comprehensive error handling"""
        
        active_plans = self.plan.get_active_plans()
        if not active_plans:
            logger.debug("No active trading plans found")
            return

        for symbol, plan in active_plans.items():
            try:
                # Handle forex symbol formatting if needed
                normalized_symbol = self._normalize_symbol(symbol)
                
                # Get price with error handling
                current_price = await self.price_client.get_price(normalized_symbol)
                
                if current_price is None:
                    logger.warning(
                        f"Skipping {symbol} (normalized: {normalized_symbol}) - "
                        "no price available"
                    )
                    continue

                # Validate price is numeric
                if not isinstance(current_price, (int, float)):
                    logger.error(
                        f"Invalid price type {type(current_price)} for {symbol}"
                    )
                    continue

                # Check trigger conditions
                if self._should_trigger(plan, current_price):
                    if DRY_RUN:
                        logger.info(
                            f"[DRY RUN] Would execute: {plan} "
                            f"at current price: {current_price}"
                        )
                    else:
                        await self._execute_plan(plan, current_price)
                        
            except KeyError as e:
                logger.error(f"Missing key in plan {symbol}: {str(e)}")
            except ValueError as e:
                logger.error(f"Invalid value in plan {symbol}: {str(e)}")
            except Exception as e:
                logger.error(
                    f"Unexpected error processing {symbol}: {str(e)}",
                    exc_info=True
                )

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol format for the price client"""
        if '/' in symbol:  # Forex pair
            return symbol.replace('/', '')
        return symbol

    def _should_trigger(self, plan: dict, price: float) -> bool:
        """Check plan-specific conditions"""
        return True  # Placeholder for real logic

    async def _execute_plan(self, plan: dict, current_price: float):
        """Execute a single trading plan"""
        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would execute: {plan}")
            return

        try:
            bracket = BracketOrder.from_plan(plan, current_price)
            buying_power = await self.order_client.get_buying_power()

            adjusted_qty = self.adjust_quantity_for_capital(
                buying_power=buying_power,
                entry_price=bracket.entry_price,
                stop_loss_price=bracket.stop_loss_price,
                risk_of_capital=self.config.risk_of_capital,
                available_quantity_ratio=self.config.available_quantity_ratio
            )

            if adjusted_qty == 0:
                logger.info(
                    f"Skipped {plan['symbol']}: insufficient capital for min quantity "
                    f"(Required: {self.config.risk_of_capital * self.config.available_quantity_ratio})"
                )
                return

            bracket.quantity = adjusted_qty

            result = await self.order_client.submit_bracket_order(
                bracket,
                account_id=self.config.account_id
            )

            if result.success:
                self.plan.mark_executed(plan['symbol'])
                self.active_orders[plan['symbol']] = bracket
                logger.info(f"Order executed: {result}")

        except Exception as e:
            logger.error(f"Order failed for {plan['symbol']}: {e}")

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
