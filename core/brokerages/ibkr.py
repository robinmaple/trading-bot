from typing import Dict
from .protocol import BrokerageProtocol
from core.logger import logger
from core.models import OrderStatus
from .ibkr.client import IBKRClient
from .ibkr.auth import IBKRAuth

class IBKRAdapter(BrokerageProtocol):
    """Adapter for Interactive Brokers API."""
    
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

    async def submit_bracket_order(
        self, symbol: str, action: str, quantity: float, take_profit: float, stop_loss: float
    ) -> Dict:
        """Submit a bracket order to IBKR."""
        # IBKR requires parent and child orders to be submitted separately
        parent_order = {
            "orderType": "LMT",
            "price": take_profit,  # This would be your entry price
            "side": action.upper(),
            "quantity": quantity,
            "tif": "GTC",
            "ocaGroup": f"BRACKET_{symbol}_{quantity}",
            "ocaType": 1,  # Cancel all remaining orders with block
            "transmit": False  # Don't transmit until all children are ready
        }
        
        take_profit_order = {
            "orderType": "LMT",
            "price": take_profit,
            "side": "SELL" if action == "BUY" else "BUY",
            "quantity": quantity,
            "tif": "GTC",
            "parentId": 1,  # Reference to parent order
            "ocaGroup": f"BRACKET_{symbol}_{quantity}",
            "ocaType": 1,
            "transmit": False
        }
        
        stop_loss_order = {
            "orderType": "STP",
            "price": stop_loss,
            "side": "SELL" if action == "BUY" else "BUY",
            "quantity": quantity,
            "tif": "GTC",
            "parentId": 1,  # Reference to parent order
            "ocaGroup": f"BRACKET_{symbol}_{quantity}",
            "ocaType": 1,
            "transmit": True  # Transmit the whole group
        }
        
        # In practice, you'd need to submit these as a single batch
        orders = [parent_order, take_profit_order, stop_loss_order]
        
        try:
            response = await self.client._session.post(
                f"{self.client.auth.api_server}iserver/account/{self.account_id}/orders",
                json=orders
            )
            return response.json()
        except Exception as e:
            logger.error(f"Failed to submit bracket order: {e}")
            raise

    async def get_account_balance(self, account_id: str) -> float:
        """Fetch available balance for the account."""
        return await self.client.get_buying_power(account_id)