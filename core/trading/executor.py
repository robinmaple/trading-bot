from typing import List
from ..brokerages.protocol import OrderProtocol, FillReport
from ..orders.bracket import BracketOrder
from ..orders.models import OrderRequest

class OrderExecutor:
    def __init__(self, broker: OrderProtocol):
        self.broker = broker

    def execute(self, order: OrderRequest) -> FillReport:
        """Submits a single order and returns fill report."""
        return self.broker.submit_order(order)

    def execute_bracket(self, bracket: BracketOrder) -> List[FillReport]:
        """
        Submits a bracket order (entry + take-profit + stop-loss).
        
        Args:
            bracket: BracketOrder containing entry/TP/SL prices.
        
        Returns:
            List of FillReports in order: [entry, take_profit, stop_loss]
        
        Raises:
            ValueError: If bracket prices are invalid.
        """
        if not bracket.validate():
            raise ValueError("Invalid bracket prices")
        
        # Generate OrderRequest objects from BracketOrder
        entry_order, tp_order, sl_order = bracket.to_order_requests()
        
        # Submit all orders and return fills
        return [
            self.broker.submit_order(entry_order),
            self.broker.submit_order(tp_order),
            self.broker.submit_order(sl_order)
        ]