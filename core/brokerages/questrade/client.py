from typing import Optional, Dict, Any
from dataclasses import asdict
from ..protocol import PriceProtocol, OrderProtocol, OrderRequest, FillReport
from .auth import QuestradeAuth
from core.logger import logger
from core.config.manager import ConfigManager
from core.models import OrderStatus
from core.storage.db import TradingDB

class QuestradeClient(PriceProtocol, OrderProtocol):
    """Questrade implementation of the brokerage protocols."""
    
class QuestradeClient(PriceProtocol, OrderProtocol):
    """Questrade implementation of the brokerage protocols."""
    
    def __init__(self, db: TradingDB):
        """
        Initialize Questrade client with database connection.
        Creates its own auth instance using the provided db.
        """
        self.auth = QuestradeAuth(db)
        self._session: Optional[Any] = None
        self._account_id: Optional[str] = None

    @property
    def account_id(self) -> str:
        """Lazy-load and cache the account ID."""
        if self._account_id is None:
            self._account_id = self._get_primary_account_id()
        return self._account_id

    def _get_primary_account_id(self) -> str:
        """Get the primary account ID from Questrade."""
        if not self._session:
            self._session = self.auth.create_session()

        url = f"{self.auth.api_server}v1/accounts"
        response = self._session.get(url)
        if response.status_code != 200:
            raise RuntimeError("Failed to fetch account information")

        accounts = response.json().get("accounts", [])
        if not accounts:
            raise RuntimeError("No Questrade accounts found")

        # Return the first account ID (typically the primary account)
        return str(accounts[0]["number"])
    
    # --- PriceProtocol Implementation ---
    async def get_price(self, symbol: str) -> float:
        """Fetches the current market price for a symbol like 'AAPL'."""
        symbol_id = await self.lookup_symbol_id(symbol)

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

        return float(price)
   
    async def lookup_symbol_id(self, symbol: str) -> int:
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

        return int(data["symbols"][0]["symbolId"])

    # --- OrderProtocol Implementation ---
    async def submit_order(self, order: OrderRequest) -> FillReport:
        """Submits an order via Questrade API or simulates it if in Dry Run mode."""
        dry_run = self.config.get_bool("dry_run", default=False)
        if dry_run:
            logger.info(f"[DRY RUN] Would submit order: {order}")
            return FillReport(
                order_id="DRYRUN123",
                filled_at=0.0,
                status=OrderStatus.SIMULATED
            )

        if not self._session:
            self._session = self.auth.create_session()
        
        questrade_order = {
            "symbol": order.symbol,
            "quantity": abs(order.quantity),  # Ensure positive quantity
            "type": order.order_type.upper(),
            "action": "Buy" if order.quantity > 0 else "Sell",
            "timeInForce": order.time_in_force if hasattr(order, 'time_in_force') else "Day"
        }
        
        # Add limit price if this is a limit order
        if order.order_type.lower() == "limit" and hasattr(order, 'limit_price'):
            questrade_order["limitPrice"] = order.limit_price
            
        logger.info(f"Submitting order: {questrade_order}")
        
        account_id = self.config.get("questrade_account_id", required=True)
        url = f"{self.auth.api_server}v1/accounts/{account_id}/orders"
        logger.info(f"Post endpoint url: {url}")
        
        response = self._session.post(url, json=questrade_order)
        response_json = response.json()

        logger.info(f"Order response text: {response.status_code} - {response.text}")
        logger.info(f"Order response json: {response_json}")

        if not response.ok or "orderId" not in response_json:
            error_msg = response_json.get('message', 'Unknown error')
            logger.error(f"Order submission failed: {error_msg}")
            raise Exception(f"Order failed: {error_msg}")

        return FillReport(
            order_id=str(response_json["orderId"]),
            filled_at=float(response_json.get("avgPrice", 0.0)),
            status=OrderStatus.FILLED if response.ok else OrderStatus.REJECTED
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancels an order in Questrade."""
        if not self._session:
            self._session = self.auth.create_session()
            
        account_id = self.config.get("questrade_account_id", required=True)
        url = f"{self.auth.api_server}v1/accounts/{account_id}/orders/{order_id}"
        response = self._session.delete(url)
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

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get the status of an existing order."""
        if not self._session:
            self._session = self.auth.create_session()
            
        account_id = self.config.get("questrade_account_id", required=True)
        url = f"{self.auth.api_server}v1/accounts/{account_id}/orders/{order_id}"
        response = self._session.get(url)
        
        if response.status_code != 200:
            logger.error(f"Failed to get order status: {response.text}")
            return OrderStatus.UNKNOWN
            
        status = response.json().get("state", "Unknown")
        return self._map_order_status(status)
    
    def _map_order_status(self, qt_status: str) -> OrderStatus:
        """Map Questrade status to our OrderStatus enum."""
        status_map = {
            "Pending": OrderStatus.PENDING,
            "Executed": OrderStatus.FILLED,
            "PartiallyExecuted": OrderStatus.PARTIALLY_FILLED,
            "Cancelled": OrderStatus.CANCELLED,
            "Rejected": OrderStatus.REJECTED,
            "Expired": OrderStatus.EXPIRED
        }
        return status_map.get(qt_status, OrderStatus.UNKNOWN)