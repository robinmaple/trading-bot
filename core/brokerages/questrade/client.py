from typing import Optional
from dataclasses import asdict
from ..protocol import PriceProtocol, OrderProtocol, OrderRequest, FillReport
from .auth import QuestradeAuth

class QuestradeClient(PriceProtocol, OrderProtocol):
    """Questrade implementation of the brokerage protocols."""
    
    def __init__(self, auth: QuestradeAuth):
        self.auth = auth
        self._session = None  # Will hold authenticated Questrade API session

    # --- PriceProtocol Implementation ---
    def get_price(self, symbol: str) -> float:
        """Fetches current market price for a symbol from Questrade."""
        if not self._session:
            self._session = self.auth.create_session()
        
        # Example: Questrade API call (simplified)
        response = self._session.get(f"markets/quotes/{symbol}")
        return response.json()["lastPrice"]

    # --- OrderProtocol Implementation ---
    def submit_order(self, order: OrderRequest) -> FillReport:
        """Submits an order via Questrade API."""
        if not self._session:
            self._session = self.auth.create_session()
        
        # Convert OrderRequest to Questrade-specific format
        questrade_order = {
            "symbol": order.symbol,
            "quantity": order.quantity,
            "type": order.order_type.upper(),
            "action": "Buy" if order.quantity > 0 else "Sell"
        }
        
        response = self._session.post("orders", json=questrade_order)
        return FillReport(
            order_id=response.json()["orderId"],
            filled_at=response.json()["avgPrice"],
            status="filled" if response.ok else "rejected"
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancels an order in Questrade."""
        response = self._session.delete(f"orders/{order_id}")
        return response.ok