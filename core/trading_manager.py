import time
import json
from datetime import datetime, timedelta
from typing import Dict, Optional
from core.logger import logger
from core.trading_plan import TradingPlanManager
from core.api.orders import OrderService, BracketOrder
from core.utils.trading_hours import TradingHours
from core.risk.daily_loss_tracker import DailyLossTracker
from core.price_services.multiprovider_service import MultiProviderPriceService


class TradingManager:
    def __init__(self, auth_client):
        self.auth = auth_client
        self.trading_hours = TradingHours()
        self.loss_tracker = DailyLossTracker()
        self._init_services()
        self._load_config()
        self.active_positions: Dict[str, dict] = {}
        
    def _init_services(self):
        """Initialize all required services"""
        self.order_service = OrderService(self.auth)
        self.price_service = self.price_service = MultiProviderPriceService()

        self.plan_manager = TradingPlanManager()
    
    def _load_config(self):
        """Load runtime configuration"""
        from config.env import (
            DRY_RUN,
            ACCOUNT_ID,
            DAILY_LOSS_LIMIT_PERCENT,
            CLOSE_POSITIONS_BEFORE_CLOSE,
            CLOSE_TRADES_BUFFER_MINUTES
        )
        self.dry_run = DRY_RUN
        self.account_id = ACCOUNT_ID
        self.close_positions_flag = CLOSE_POSITIONS_BEFORE_CLOSE
        self.close_trades_buffer = CLOSE_TRADES_BUFFER_MINUTES
        self.loss_tracker.limit_percent = float(DAILY_LOSS_LIMIT_PERCENT)
    
    async def run(self):
        """Main trading loop"""
        logger.info("Starting trading manager")
        
        while True:
            if not self._pre_trade_checks():
                time.sleep(60)  # Wait 1 minute before rechecking
                continue
                
            await self._monitor_prices()
            await self._execute_orders()
            self._manage_positions()
            
            time.sleep(5)  # Throttle API calls
    
    def _pre_trade_checks(self) -> bool:
        """Validate all trading conditions"""
        if not self.trading_hours.is_market_open():
            logger.info("Outside trading hours")
            current_session = self.trading_hours.get_current_session()
            if current_session and self._should_close_positions(current_session):
                self._close_all_positions()
            return False
            
        account_value = self._get_account_value()
        if self.loss_tracker.is_limit_breached(account_value):
            logger.warning("Daily loss limit breached - trading paused")
            return False
            
        return True
    
    def _should_close_positions(self, session) -> bool:
        """Check if positions should be closed before session end"""
        session_end = datetime.combine(datetime.today(), session[1])
        return (
            self.close_positions_flag and
            (session_end - datetime.now()) < timedelta(minutes=self.close_trades_buffer)
        )
    
    async def _monitor_prices(self):
        """Monitor all tickers in trading plan"""
        for order in self.plan_manager.get_active_orders():
            symbol = order['symbol']
            current_price = await self.price_service.get_price(symbol)
            logger.debug(f"{symbol} price: {current_price}")
            # Add price alert logic here
    
    def make_status_callback(self):
        def callback(event_type, symbol, details=None):
            msg = f"[Order Event] {event_type.upper()} - {symbol}"
            if details:
                msg += f" | Details: {details}"
            self.logger.info(msg)
        return callback

    async def _execute_orders(self):
        """Process all triggerable orders"""
        account_value = self._get_account_value()
        
        for order in self.plan_manager.get_active_orders():
            if await self._should_trigger_order(order, account_value):
                await self._place_bracket_order(order)
    
    async def _should_trigger_order(self, order, account_value) -> bool:
        """Check order triggering conditions"""
        # Add your custom entry logic here
        current_price = await self.price_service.get_price(order['symbol'])

        if current_price is None:
                logger.warning(f"Price not available for {order['symbol']}, skipping order.")
                return False  # or raise depending on strategy

        if order['side'] == 'Buy':
            return current_price <= order['entry']
        else:
            return current_price >= order['entry']
    
    async def _place_bracket_order(self, order):
        """Execute bracket order with risk management"""
        try:
            # Build the BracketOrder object
            bracket_order = BracketOrder(
                symbol=order['symbol'],
                symbol_id=order.get('symbol_id'),
                entry_price=order['entry'],
                stop_price=order['stop'],
                account_id=self.account_id,
                direction=order['side'],
                quantity=order.get('quantity'),
                entry_type=order.get('entry_type', 'limit'),
                entry_stop_trigger=order.get('entry_stop_trigger')
            )
            # Optional: Attach status callback
            status_callback = self.make_status_callback(order['symbol'], bracket_order)

            # Place the order
            result = bracket_order.place_with_config(
                current_price=await self.price_service.get_price(order['symbol']),
                price_service=self.price_service,
                status_callback=status_callback
            )

            # Post-placement actions
            if result:
                self.plan_manager.mark_expired(order['symbol'])
                self.active_positions[order['symbol']] = order

        except Exception as e:
            logger.error(f"Order failed for {order['symbol']}: {str(e)}")
        
    def _manage_positions(self):
        """Monitor and manage open positions"""
        for symbol, position in list(self.active_positions.items()):
            if self._should_exit_position(position):
                self._close_position(symbol)
    
    def _close_all_positions(self):
        """Liquidate all positions at market price"""
        logger.info("Closing all positions before session end")
        for symbol in list(self.active_positions.keys()):
            self._close_position(symbol)
    
    def _close_position(self, symbol):
        """Close single position"""
        # Implement position closing logic
        logger.info(f"Closing position for {symbol}")
        del self.active_positions[symbol]
    
    def _get_account_value(self) -> float:
        """Get current account equity"""
        # Replace with real account balance check
        return 10000  # Mock value
    
    def make_status_callback(self, plan_name: str, bracket_order: BracketOrder):
        def callback(status: str, symbol: str, data: dict):
            log_data = {
                "plan": plan_name,
                "symbol": symbol,
                "status": status,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            }
            logger.info(f"Order status update: {json.dumps(log_data)}")
        return callback