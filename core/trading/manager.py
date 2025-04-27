import json
import os
from datetime import datetime
import time
import asyncio
import math

from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional
from core.logger import logger
from core.orders.bracket import BracketOrder
from core.brokerages.protocol import OrderProtocol, PriceProtocol
from core.trading.plan import TradingPlan
from config.env import DRY_RUN
from core.storage.db import TradingDB
from core.brokerages.questrade.auth import QuestradeAuth


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
        price_client: PriceProtocol
    ):
        self.order_client = order_client
        self.price_client = price_client
        self.active_orders: Dict[str, BracketOrder] = {}
        self._capital_lock = asyncio.Lock()
        self.remaining_bp = 0.0

        self._capital_lock = asyncio.Lock()
        self.remaining_bp = 0.0
        self.committed_capital = 0.0  # Track total committed

        self.db = TradingDB()
        self._init_brokerage()  # Replace .env loading
        self.config = TradingConfig()
        self.auth = QuestradeAuth(self.db)  # Initialize auth

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
        
    def _init_brokerage(self):
        """Initialize brokerage connection from database"""
        try:
            with self.db._get_conn() as conn:
                # Get brokerage config
                brokerage = conn.execute("""
                    SELECT name, token_url, api_endpoint, refresh_token 
                    FROM brokerages 
                    WHERE name = 'QUESTRADE'
                """).fetchone()
                
                if not brokerage:
                    raise ValueError("Questrade brokerage not configured")
                    
                # Get primary account
                account = conn.execute("""
                    SELECT account_id, name 
                    FROM accounts 
                    WHERE brokerage_id = (
                        SELECT id FROM brokerages WHERE name = 'QUESTRADE'
                    )
                """).fetchone()
                
                if not account:
                    raise ValueError("No primary Questrade account configured")
                
                # Initialize TradingConfig properly
                self.config = TradingConfig(
                    account_id=account['account_id'],
                    dry_run=DRY_RUN,
                    close_buffer_minutes=CLOSE_TRADES_BUFFER_MINUTES,
                    risk_of_capital=RISK_OF_CAPITAL,
                    available_quantity_ratio=AVAILABLE_QUANTITY_RATIO
                )
                logger.info(f"Initialized brokerage for account {account['account_id']}")
                
        except Exception as e:
            logger.critical(f"Brokerage initialization failed: {e}")
            raise
                    
    async def _get_valid_quote(self, symbol: str, max_retries: int = 3) -> Optional[dict]:
        """Get valid market quote with retries"""
        for attempt in range(max_retries):
            try:
                response = await self.price_client.get_price(symbol)
                if not response or 'quotes' not in response:
                    logger.warning(f"No quote data for {symbol}")
                    continue

                quote = response['quotes'][0]
                if not isinstance(quote, dict):
                    logger.error(f"Invalid quote format for {symbol}")
                    continue

                # Market status checks
                if quote.get('isHalted', False):
                    logger.warning(f"{symbol} trading is halted")
                    return None

                last_price = quote.get('lastTradePrice')
                if last_price is None:
                    logger.warning(f"No last price for {symbol}")
                    continue

                # Check for stale data
                last_trade_time = quote.get('lastTradeTime')
                if last_trade_time:
                    try:
                        trade_time = datetime.fromisoformat(last_trade_time.rstrip('Z'))
                        if (datetime.now() - trade_time).total_seconds() > 300:  # 5 minutes
                            logger.warning(f"Stale data for {symbol} from {last_trade_time}")
                            continue
                    except ValueError:
                        logger.warning(f"Invalid timestamp for {symbol}")

                return quote

            except Exception as e:
                logger.warning(f"Quote attempt {attempt+1} failed for {symbol}: {str(e)}")
                await asyncio.sleep(1)

        logger.error(f"Could not get valid quote for {symbol} after {max_retries} attempts")
        return None

    async def _should_trade(self) -> bool:
        """Check if market is open and active"""
        now = datetime.now()
        
        # NYSE hours (9:30 AM to 4:00 PM ET, Monday-Friday)
        if now.weekday() >= 5:  # Saturday or Sunday
            logger.info("Weekend - markets closed")
            return False
            
        # Convert ET to UTC (ET is UTC-4 or UTC-5 depending on DST)
        et_hour = (now.hour - 4) % 24  # Simple UTC to ET conversion
        if not (9 <= et_hour < 16):  # 9:30 AM-4:00 PM ET
            logger.info(f"Outside market hours (ET time: {et_hour})")
            return False
            
        # Additional checks could include:
        # - Market holidays
        # - Early closes
        # - Current volatility
        
        return True
    
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

    async def _execute_plan_with_db(self, plan: dict, bracket: BracketOrder) -> bool:
        """Execute trade with full DB state tracking"""
        account_id = self.config.get('ACCOUNT_ID')
        symbol = plan['symbol']
        
        try:
            # 1. Prepare execution data
            execution_data = {
                'planned_trade_id': plan.get('planned_trade_id'),
                'account_id': account_id,
                'symbol': symbol,
                'entry_price': bracket.entry_price,
                'quantity': bracket.quantity,
                'stop_loss': bracket.stop_loss_price,
                'take_profit': bracket.take_profit_price
            }

            # 2. Dry-run handling
            if self.config.get('DRY_RUN') == 'TRUE':
                with self.db._get_conn() as conn:
                    conn.execute("""
                        INSERT INTO executed_trades (
                            planned_trade_id, account_id, symbol,
                            actual_entry_price, actual_quantity, status,
                            execution_time
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        execution_data['planned_trade_id'],
                        account_id,
                        symbol,
                        execution_data['entry_price'],
                        execution_data['quantity'],
                        'filled',
                        datetime.now().isoformat()
                    ))
                return True

            # 3. Live execution
            result = await self.order_client.submit_bracket_order(
                bracket=bracket,
                account_id=account_id
            )

            # 4. Record execution
            if result.success:
                with self.db._get_conn() as conn:
                    # Update positions
                    conn.execute("""
                        INSERT OR REPLACE INTO positions (
                            account_id, symbol, quantity, entry_price
                        ) VALUES (?, ?, ?, ?)
                        ON CONFLICT(account_id, symbol) DO UPDATE SET
                            quantity = quantity + excluded.quantity
                    """, (
                        account_id,
                        symbol,
                        execution_data['quantity'],
                        execution_data['entry_price']
                    ))
                    
                    # Record execution
                    conn.execute("""
                        INSERT INTO executed_trades (
                            planned_trade_id, account_id, symbol,
                            actual_entry_price, actual_quantity, fees,
                            status, execution_time
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        execution_data['planned_trade_id'],
                        account_id,
                        symbol,
                        execution_data['entry_price'],
                        execution_data['quantity'],
                        result.fees,
                        'filled',
                        datetime.now().isoformat()
                    ))
                    
                return True
                
            return False

        except Exception as e:
            logger.error(f"DB execution failed for {symbol}: {e}")
            # Revert position if partially executed
            with self.db._get_conn() as conn:
                conn.execute("""
                    UPDATE positions
                    SET quantity = quantity - ?
                    WHERE account_id = ? AND symbol = ?
                """, (
                    execution_data['quantity'],
                    account_id,
                    symbol
                ))
            raise

    async def load_plans(self, account_id: str) -> Dict[str, dict]:
        """Load trading plans from database"""
        plans = {}
        try:
            with self.db._get_conn() as conn:
                active_plans = conn.execute("""
                    SELECT pt.planned_trade_id, pt.symbol, pt.entry_price, 
                        pt.stop_loss_price, pt.expiry_date
                    FROM planned_trades pt
                    LEFT JOIN executed_trades et ON pt.planned_trade_id = et.planned_trade_id
                    WHERE pt.account_id = ?
                    AND pt.expiry_date >= DATE('now')
                    AND (et.status IS NULL OR et.status != 'filled')
                """, (account_id,)).fetchall()

                for plan in active_plans:
                    plans[plan['symbol']] = {
                        'symbol': plan['symbol'],
                        'entry': plan['entry_price'],
                        'stop_loss': plan['stop_loss_price'],
                        'planned_trade_id': plan['planned_trade_id'],
                        'expiry_date': plan['expiry_date']
                    }
        except Exception as e:
            logger.error(f"Failed to load plans from database: {e}")
            raise
        
        return plans
    
    async def _process_plans(self):
        """Process trading plans with market status validation"""
        async with self._capital_lock:
            # Validate account
            account_id = self.config.account_id
            if not account_id:
                logger.error("No account ID configured")
                return

            # 1. Get buying power
            try:
                total_bp = await self.order_client.get_buying_power(account_id)
                logger.info(f"Buying power: {total_bp}")
            except Exception as e:
                logger.warning(f"BP API failed: {e}, using DB fallback")
                with self.db._get_conn() as conn:
                    total_bp = conn.execute(
                        "SELECT bp_override FROM accounts WHERE account_id = ?",
                        (account_id,)
                    ).fetchone()[0] or 0

            # 2. Calculate used BP from positions
            with self.db._get_conn() as conn:
                used_bp = conn.execute("""
                    SELECT COALESCE(SUM(entry_price * quantity), 0)
                    FROM positions
                    WHERE account_id = ?
                """, (account_id,)).fetchone()[0]
            
            self.remaining_bp = total_bp - used_bp

            # 3. Check market status before proceeding
            if not await self._should_trade():
                logger.info("Market conditions not suitable for trading")
                return

            # 4. Process active plans from DB
            with self.db._get_conn() as conn:
                active_plans = conn.execute("""
                    SELECT pt.planned_trade_id, pt.symbol, pt.entry_price, 
                        pt.stop_loss_price, pt.expiry_date
                    FROM planned_trades pt
                    LEFT JOIN executed_trades et ON pt.planned_trade_id = et.planned_trade_id
                    WHERE pt.account_id = ?
                    AND pt.expiry_date >= DATE('now')
                    AND (et.status IS NULL OR et.status != 'filled')
                """, (account_id,)).fetchall()

                for plan in active_plans:
                    symbol = plan['symbol']
                    try:
                        logger.info(f"Processing {symbol}")

                        # Validate required prices
                        if None in [plan['entry_price'], plan['stop_loss_price']]:
                            logger.error(f"Missing prices for {symbol}")
                            continue

                        # Get market data
                        quote = await self._get_valid_quote(symbol)
                        if not quote:
                            continue

                        # Convert and validate prices
                        try:
                            entry_price = float(plan['entry_price'])
                            stop_loss = float(plan['stop_loss_price'])
                            current_price = float(quote['lastTradePrice'])
                        except (TypeError, ValueError) as e:
                            logger.error(f"Price conversion failed for {symbol}: {e}")
                            continue

                        if entry_price <= stop_loss:
                            logger.error(f"Invalid prices for {symbol}: entry {entry_price} <= stop {stop_loss}")
                            continue

                        # Create and execute order
                        legacy_plan = {
                            'symbol': symbol,
                            'entry': entry_price,
                            'stop_loss': stop_loss,
                            'planned_trade_id': plan['planned_trade_id']
                        }

                        try:
                            bracket = BracketOrder.from_plan(legacy_plan, current_price)
                            bracket.quantity = self._calculate_safe_quantity(bracket)
                        except Exception as e:
                            logger.error(f"Bracket creation failed for {symbol}: {e}")
                            continue

                        # BP check
                        required_bp = bracket.entry_price * bracket.quantity
                        if self.remaining_bp < required_bp:
                            logger.warning(f"Insufficient BP for {symbol}")
                            continue

                        if await self._execute_plan_with_db(legacy_plan, bracket):
                            self.remaining_bp -= required_bp
                            logger.info(f"Executed {symbol}")

                    except Exception as e:
                        logger.error(f"Plan failed for {symbol}: {str(e)}")
                        continue

    async def _get_valid_quote(self, symbol: str, max_retries: int = 3) -> Optional[dict]:
        """Get valid market quote with retries"""
        for attempt in range(max_retries):
            try:
                response = await self.price_client.get_price(symbol)
                if not response or 'quotes' not in response:
                    logger.warning(f"No quote data for {symbol}")
                    continue

                quote = response['quotes'][0]
                if not isinstance(quote, dict):
                    logger.error(f"Invalid quote format for {symbol}")
                    continue

                # Market status checks
                if quote.get('isHalted', False):
                    logger.warning(f"{symbol} trading is halted")
                    return None

                last_price = quote.get('lastTradePrice')
                if last_price is None:
                    logger.warning(f"No last price for {symbol}")
                    continue

                # Check for stale data
                last_trade_time = quote.get('lastTradeTime')
                if last_trade_time:
                    try:
                        trade_time = datetime.fromisoformat(last_trade_time.rstrip('Z'))
                        if (datetime.now() - trade_time).total_seconds() > 300:  # 5 minutes
                            logger.warning(f"Stale data for {symbol} from {last_trade_time}")
                            continue
                    except ValueError:
                        logger.warning(f"Invalid timestamp for {symbol}")

                return quote

            except Exception as e:
                logger.warning(f"Quote attempt {attempt+1} failed for {symbol}: {str(e)}")
                await asyncio.sleep(1)

        logger.error(f"Could not get valid quote for {symbol} after {max_retries} attempts")
        return None

    async def _should_trade(self) -> bool:
        """Check if market is open and active"""
        now = datetime.now()
        
        # NYSE hours (9:30 AM to 4:00 PM ET, Monday-Friday)
        if now.weekday() >= 5:  # Saturday or Sunday
            logger.info("Weekend - markets closed")
            return False
            
        # Convert ET to UTC (ET is UTC-4 or UTC-5 depending on DST)
        et_hour = (now.hour - 4) % 24  # Simple UTC to ET conversion
        if not (9 <= et_hour < 16):  # 9:30 AM-4:00 PM ET
            logger.info(f"Outside market hours (ET time: {et_hour})")
            return False
            
        # Additional checks could include:
        # - Market holidays
        # - Early closes
        # - Current volatility
        
        return True    