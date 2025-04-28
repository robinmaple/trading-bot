from typing import Optional, Dict
from dataclasses import asdict
from ..protocol import PriceProtocol, OrderProtocol, OrderRequest, FillReport
from .auth import IBKRAuth
from core.logger import logger
from core.config.manager import config
from core.models import OrderStatus

class IBKRClient(PriceProtocol, OrderProtocol):
    """IBKR implementation of the brokerage protocols."""
    
    def __init__(self, auth: IBKRAuth):
        self.auth = auth
        self._session = None  # Will hold authenticated IBKR API session

    # --- PriceProtocol Implementation ---
    async def get_price(self, symbol: str) -> float:
        """Fetches the current market price for a symbol."""
        if not self._session:
            self._session = self.auth.create_session()

        url = f"{self.auth.api_server}iserver/marketdata/snapshot?conids={self._get_conid(symbol)}&fields=31"
        response = self._session.get(url)
        logger.info(f"Quote response: {response.status_code} - {response.text}")

        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch quote for {symbol}")

        quote_data = response.json()
        if not quote_data:
            raise RuntimeError(f"No price data available for {symbol}")

        # Field 31 is last price in IBKR's system
        price = quote_data[0].get("31")
        if not price:
            raise RuntimeError(f"No price available for {symbol}")

        return float(price)
    
    def _get_conid(self, symbol: str) -> str:
        """Get IBKR's contract ID (conid) for a symbol."""
        # In a real implementation, you'd want to cache this
        url = f"{self.auth.api_server}iserver/secdef/search?symbol={symbol}"
        response = self._session.get(url)
        
        if response.status_code != 200:
            raise RuntimeError(f"Symbol lookup failed for {symbol}")
            
        data = response.json()
        if not data:
            raise RuntimeError(f"No matching contract found for {symbol}")
            
        return str(data[0]["conid"])

    # --- OrderProtocol Implementation ---
    async def submit_order(self, order: OrderRequest) -> FillReport:
        """Submits an order via IBKR API."""
        if config.get("DRY_RUN"):
            logger.info(f"[DRY RUN] Would submit order: {order}")
            return FillReport(
                order_id="DRYRUN123",
                filled_at=0.0,
                status="simulated"
            )

        if not self._session:
            self._session = self.auth.create_session()
        
        conid = self._get_conid(order.symbol)
        ibkr_order = {
            "acctId": config.get("IBKR_ACCOUNT_ID"),
            "conid": conid,
            "secType": f"{conid}:STK",  # Assuming stock, adjust for other types
            "orderType": order.order_type.upper(),
            "side": "BUY" if order.quantity > 0 else "SELL",
            "tif": "DAY",  # Time in force
            "quantity": abs(order.quantity),
        }
        
        if order.order_type.lower() == "limit":
            ibkr_order["price"] = order.limit_price
            
        logger.info(f"Submitting order: {ibkr_order}")
        url = f"{self.auth.api_server}iserver/account/{config.get('IBKR_ACCOUNT_ID')}/order"
        
        response = self._session.post(url, json=ibkr_order)
        response_json = response.json()

        logger.info(f"Order response: {response.status_code} - {response.text}")

        if not response.ok:
            error = response_json.get("error", "Unknown error")
            raise Exception(f"Order failed: {error}")

        # IBKR returns order ID in a reply array
        order_id = response_json.get("id", "")
        if not order_id:
            order_id = response_json[0].get("id", "") if isinstance(response_json, list) else ""

        return FillReport(
            order_id=order_id,
            filled_at=0.0,  # Will be updated later
            status="submitted"
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancels an order in IBKR."""
        url = f"{self.auth.api_server}iserver/account/{config.get('IBKR_ACCOUNT_ID')}/order/{order_id}"
        response = self._session.delete(url)
        return response.ok

    async def get_buying_power(self, account_id: str) -> float:
        """Fetch available buying power for the given IBKR account."""
        if not self._session:
            self._session = self.auth.create_session()

        url = f"{self.auth.api_server}portfolio/{account_id}/summary"
        response = self._session.get(url)
        logger.info(f"Buying power response: {response.status_code} - {response.text}")

        if response.status_code != 200:
            raise RuntimeError(f"Failed to retrieve buying power for account {account_id}")

        data = response.json()
        buying_power = data.get("buyingPower", {}).get("amount", 0.0)

        logger.info(f"Buying power for account {account_id}: {buying_power}")
        return float(buying_power)

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get order status from IBKR API"""
        try:
            url = f"{self.auth.api_server}iserver/account/orders/{order_id}"
            response = self._session.get(url)
            ibkr_status = response.json().get('status')
            return self._map_status(ibkr_status)
        except Exception as e:
            logger.error(f"Failed to get status for order {order_id}: {e}")
            return 'rejected'

    def _map_status(self, ibkr_status: str) -> OrderStatus:
        """Map IBKR status to our standard"""
        status_map = {
            'PendingSubmit': 'pending',
            'PreSubmitted': 'pending',
            'Submitted': 'open',
            'Filled': 'filled',
            'PartiallyFilled': 'partial',
            'Cancelled': 'canceled',
            'Inactive': 'rejected',
            'ApiCancelled': 'canceled'
        }
        return status_map.get(ibkr_status, 'open')