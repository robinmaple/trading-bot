from datetime import datetime
from random import uniform
from ..protocol import PriceProtocol, OrderProtocol, OrderRequest, FillReport
from typing import Optional

class MockClient(PriceProtocol, OrderProtocol):
    def __init__(self, fixed_price: Optional[float] = None):
        self.fixed_price = fixed_price

    def get_price(self, symbol: str) -> float:
        return self.fixed_price or round(uniform(100, 200), 2)  # Random price

    def submit_order(self, order: OrderRequest) -> FillReport:
        return FillReport(
            order_id=f"mock_{datetime.now().timestamp()}",
            filled_at=order.price if order.price else self.get_price(order.symbol),
            status="filled"
        )

    def cancel_order(self, order_id: str) -> bool:
        return True  # Always succeeds