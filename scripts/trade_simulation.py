from core.brokerages.questrade.auth import QuestradeAuth
from core.brokerages.questrade.client import QuestradeClient
from core.pricing.service import MultiProviderPriceService
from core.trading.executor import OrderExecutor
from core.trading.history import TradeHistoryLogger
from core.orders.models import OrderRequest

import sys
print(sys.path)  # Ensure 'c:/Projects/questrade_bot' is listed

# 1. Initialize services
auth = QuestradeAuth()
questrade = QuestradeClient(auth)
price_service = MultiProviderPriceService([questrade])
history = TradeHistoryLogger()

# 2. Execute a trade
executor = OrderExecutor(questrade)
order = OrderRequest(symbol="AAPL", quantity=10, order_type="market")
fill = executor.execute(order)
history.log_fill(fill)

print(f"Order {fill.order_id} filled at {fill.filled_at}")
