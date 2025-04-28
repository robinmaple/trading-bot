from typing import Optional
from dataclasses import asdict
from ..protocol import PriceProtocol, OrderProtocol, OrderRequest, FillReport
from .auth import QuestradeAuth
from core.logger import logger
from core.config.manager import config

class QuestradeClient(PriceProtocol, OrderProtocol):
    """Questrade implementation of the brokerage protocols."""
    
    def __init__(self, auth: QuestradeAuth):
        self.auth = auth
        self._session = None  # Will hold authenticated Questrade API session

    # --- PriceProtocol Implementation ---
    async def get_price(self, symbol: str) -> float:
        """Fetches the current market price for a symbol like 'AAPL'."""
        symbol_id = self.lookup_symbol_id(symbol)

        url = f"{self.auth.api_server}v1/markets/quotes/{symbol_id}"
        response = self._session.get(url)
        logger.info(f"Quote response: {response.status_code} - {response.text}")

        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch quote for {symbol} (ID: {symbol_id})")

        quote_data = response.json()
        quote = quote_data.get("quotes", [{}])[0]

        # Prefer lastTradePrice, then fallback to bid or ask
        price = quote.get("lastTradePrice") or quote.get("bidPrice") or quote.get("askPrice")

        if not price:
            raise RuntimeError(f"No price available for {symbol}: {quote_data}")

        return price
   
    def lookup_symbol_id(self, symbol: str) -> int:
        """Looks up the Questrade symbolId for a given stock symbol like 'AAPL'."""
        if not self._session:
            self._session = self.auth.create_session()

        url = f"{self.auth.api_server}v1/symbols?names={symbol}"
        response = self._session.get(url)
        logger.info(f"Symbol lookup response: {response.status_code} - {response.text}")

        if response.status_code != 200:
            raise RuntimeError(f"Symbol lookup failed for {symbol}")

        data = response.json()
        if not data["symbols"]:
            raise RuntimeError(f"No matching symbol found for {symbol}")

        return data["symbols"][0]["symbolId"]

    # --- OrderProtocol Implementation ---
    async def submit_order(self, order: OrderRequest) -> FillReport:
        """Submits an order via Questrade API or simulates it if in Dry Run mode."""
        if config.get("DRY_RUN"):
            logger.info(f"[DRY RUN] Would submit order: {order}")
            return FillReport(
                order_id="DRYRUN123",
                filled_at=0.0,
                status="simulated"
            )

        if not self._session:
            self._session = self.auth.create_session()
        
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

    async def cancel_order(self, order_id: str) -> bool:
        """Cancels an order in Questrade."""
        response = self._session.delete(f"orders/{order_id}")
        return response.ok

    async def get_buying_power(self, account_id: str) -> float:
        """Fetch available buying power for the given Questrade account."""
        if not self._session:
            self._session = self.auth.create_session()

        url = f"{self.auth.api_server}v1/accounts/{account_id}/balances"
        response = self._session.get(url)
        logger.info(f"Buying power response: {response.status_code} - {response.text}")

        if response.status_code != 200:
            raise RuntimeError(f"Failed to retrieve buying power for account {account_id}")

        data = response.json()
        combined = data.get("combinedBalances", [{}])[0]
        buying_power = combined.get("buyingPower", 0.0)

        logger.info(f"Buying power for account {account_id}: {buying_power}")
        return float(buying_power)
