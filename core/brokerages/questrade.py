from questrade_api import Questrade  # Hypothetical Questrade client
from typing import Dict
from .protocol import BrokerageProtocol
from core.logger import logger
from core.models import OrderStatus

class QuestradeAdapter(BrokerageProtocol):
    def __init__(self, api_key: str, account_id: str):
        self.client = Questrade(api_key=api_key)
        self.account_id = account_id

    async def submit_bracket_order(
        self, symbol: str, action: str, quantity: float, take_profit: float, stop_loss: float
    ) -> Dict:
        # Convert to Questrade-specific bracket order format
        order_params = {
            "symbol": symbol.replace("/", ""),  # Questrade uses "AUDCAD" instead of "AUD/CAD"
            "quantity": quantity,
            "side": "Buy" if action == "BUY" else "Sell",
            "takeProfit": take_profit,
            "stopLoss": stop_loss,
        }
        response = await self.client.place_order(account_id=self.account_id, **order_params)
        return response

    async def get_account_balance(self, account_id: str) -> float:
        balance = await self.client.get_account_balance(account_id)
        return balance["cashAvailable"]
    
    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get order status from Questrade API"""
        try:
            response = await self._get(f"v1/accounts/{self.account_id}/orders/{order_id}")
            qt_status = response['status']
            return self._map_status(qt_status)
        except Exception as e:
            logger.error(f"Failed to get status for order {order_id}: {e}")
            return 'rejected'

    def _map_status(self, qt_status: str) -> OrderStatus:
        """Map Questrade status to our standard"""
        status_map = {
            'Pending': 'pending',
            'Executed': 'filled',
            'PartiallyExecuted': 'partial',
            'Cancelled': 'canceled',
            'Rejected': 'rejected',
            'Expired': 'expired'
        }
        return status_map.get(qt_status, 'open')