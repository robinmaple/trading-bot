from typing import Optional
from dataclasses import asdict
from ..protocol import PriceProtocol, OrderProtocol, OrderRequest, FillReport
from .auth import QuestradeAuth
from core.logger import logger
from config.env import DRY_RUN

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
        """Submits an order via Questrade API or simulates it if in Dry Run mode."""
        if DRY_RUN:
            logger.info(f"[DRY RUN] Would submit order: {order}")
            return FillReport(
                order_id="DRYRUN123",
                filled_at=0.0,
                status="simulated"
            )

        if not self._session:
            self._session = self.auth.create_session()
        
        # Convert OrderRequest to Questrade-specific format
        questrade_order = {
            "symbol": order.symbol,
            "quantity": order.quantity,
            "type": order.order_type.upper(),
            "action": "Buy" if order.quantity > 0 else "Sell"
        }
        logger.info(f"Submitting order: {questrade_order}")
        
        url = f"{self.auth.api_server}v1/accounts/27348656/orders"
        logger.info(f"Post endpoint url: {url}")
        
        response = self._session.post(url, json=questrade_order)
        response_json = response.json()

        logger.info(f"Order response text: {response.status_code} - {response.text}")
        logger.info(f"Order response json: {response_json}")

        if not response.ok or "orderId" not in response_json:
            logger.error("Order submission failed or response invalid")
            raise Exception(f"Order failed: {response_json.get('message', 'Unknown error')}")

        return FillReport(
            order_id=response_json["orderId"],
            filled_at=response_json.get("avgPrice", 0.0),
            status="filled" if response.ok else "rejected"
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancels an order in Questrade."""
        response = self._session.delete(f"orders/{order_id}")
        return response.ok