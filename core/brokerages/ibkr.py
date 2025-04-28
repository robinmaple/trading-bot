from typing import Dict
from .protocol import BrokerageProtocol
from core.logger import logger
from core.models import OrderStatus
from .ibkr.client import IBKRClient
from .ibkr.auth import IBKRAuth
from core.orders.bracket import BracketOrder
import time

class IBKRAdapter(BrokerageProtocol):
    """Adapter for Interactive Brokers API."""
    @property
    def supports_native_bracket(self) -> bool:
        return True

    def __init__(self, client_id: str, client_secret: str, account_id: str):
        auth = IBKRAuth(client_id, client_secret)
        self.client = IBKRClient(auth)
        self.account_id = account_id

    async def connect(self) -> bool:
        """Establish connection to IBKR."""
        try:
            # Test connection by getting account info
            await self.client.get_buying_power(self.account_id)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            return False

    async def get_account_balance(self, account_id: str) -> float:
        """Fetch available balance for the account."""
        return await self.client.get_buying_power(account_id)
    
    # In IBKRAdapter class

    async def submit_bracket_order(self, bracket: BracketOrder) -> Dict:
        """Submit bracket order using native IBKR API if available, otherwise fallback."""
        try:
            # First try native IBKR bracket orders
            return await self._submit_native_bracket(bracket)
        except NotImplementedError:
            # Fallback to generic implementation
            logger.info("Native bracket orders not supported, using generic implementation")
            return await self._submit_generic_bracket(bracket)

    async def _submit_native_bracket(self, bracket: BracketOrder) -> Dict:
        """Submit using IBKR's native bracket order API."""
        conid = self._get_conid(bracket.symbol)
        
        # IBKR requires specific bracket order structure
        orders = {
            "orders": [
                {
                    "acctId": self.account_id,
                    "conid": conid,
                    "secType": f"{conid}:STK",
                    "orderType": bracket.entry_type.upper(),
                    "side": bracket.side.upper(),
                    "price": bracket.entry_price,
                    "tif": "GTC",
                    "quantity": abs(bracket.quantity),
                    "ocaGroup": f"BRACKET_{bracket.symbol}_{int(time.time())}",
                    "transmit": False,
                    "parentId": ""  # Empty for parent order
                },
                {
                    "acctId": self.account_id,
                    "conid": conid,
                    "secType": f"{conid}:STK",
                    "orderType": "LMT",
                    "side": "SELL" if bracket.side.lower() == "buy" else "BUY",
                    "price": bracket.take_profit_price,
                    "tif": "GTC",
                    "quantity": abs(bracket.quantity),
                    "ocaGroup": f"BRACKET_{bracket.symbol}_{int(time.time())}",
                    "parentId": 1,  # Reference to parent order
                    "transmit": False
                },
                {
                    "acctId": self.account_id,
                    "conid": conid,
                    "secType": f"{conid}:STK",
                    "orderType": "STP",
                    "side": "SELL" if bracket.side.lower() == "buy" else "BUY",
                    "price": bracket.stop_loss_price,
                    "tif": "GTC",
                    "quantity": abs(bracket.quantity),
                    "ocaGroup": f"BRACKET_{bracket.symbol}_{int(time.time())}",
                    "parentId": 1,  # Reference to parent order
                    "transmit": True  # Transmit the whole group
                }
            ]
        }
        
        response = await self.client._session.post(
            f"{self.client.auth.api_server}iserver/account/{self.account_id}/orders",
            json=orders
        )
        
        if not response.ok:
            raise RuntimeError(f"Native bracket order failed: {response.text}")
        
        return response.json()

    async def _submit_generic_bracket(self, bracket: BracketOrder) -> Dict:
        """Fallback implementation using individual orders."""
        orders = bracket.to_order_requests()
        results = []
        
        for order in orders:
            try:
                result = await self.submit_order(order)
                results.append(result)
            except Exception as e:
                # Attempt to cancel any successfully placed orders
                for r in results:
                    if 'order_id' in r:
                        await self.cancel_order(r['order_id'])
                raise RuntimeError(f"Bracket order failed: {e}")
        
        return {
            "status": "success",
            "order_ids": [r.get('order_id') for r in results],
            "details": results
        }