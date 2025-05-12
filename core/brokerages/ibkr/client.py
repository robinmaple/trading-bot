import json
import logging
from datetime import datetime, time
import re
from typing import Dict, Union
import requests
from ..protocol import PriceProtocol, OrderProtocol, OrderRequest, FillReport
from .auth import IBKRAuth
from core.logger import logger
from core.models import OrderStatus

class IBKRPriceFields:
    """Constants for IBKR market data fields"""
    LAST = '31'          # Last price
    BID = '84'          # Bid price
    ASK = '86'          # Ask price
    BASIC_FIELDS = f"{LAST},{BID},{ASK}"

class IBKRClient:
    def __init__(self, auth: IBKRAuth):
        self.auth = auth
        self._conid_cache: Dict[str, str] = {}
        self._session = auth.session
        self._session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Python Client/1.0',
            'Accept': 'application/json'
        })
        self._session.verify = False  # Disable SSL verification for localhost
        requests.packages.urllib3.disable_warnings()

    async def _get_conid(self, symbol: str) -> str:
        """Robust contract ID lookup with multiple fallbacks"""
        symbol = symbol.upper()
        
        if symbol in self._conid_cache:
            return self._conid_cache[symbol]
        
        # First try the /trsrv/stocks endpoint (most reliable)
        try:
            response = self._session.get(
                f"{self.auth.api_endpoint}/trsrv/stocks",
                params={"symbols": symbol},
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            if isinstance(data, dict) and symbol in data:
                contracts = data[symbol].get('contracts', [])
                for contract in contracts:
                    if contract.get('contractType') == 'STK':
                        conid = str(contract['conid'])
                        self._conid_cache[symbol] = conid
                        logger.info(f"Found CONID {conid} for {symbol} via /trsrv/stocks")
                        return conid
        except Exception as e:
            logger.debug(f"/trsrv/stocks lookup failed: {str(e)}")
        
        # Fallback to /trsrv/secdef endpoint
        try:
            response = self._session.get(
                f"{self.auth.api_endpoint}/trsrv/secdef",
                params={"symbols": symbol},
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            if isinstance(data, dict) and symbol in data:
                contracts = data[symbol].get('contracts', [])
                for contract in contracts:
                    if contract.get('contractType') == 'STK':
                        conid = str(contract['conid'])
                        self._conid_cache[symbol] = conid
                        logger.info(f"Found CONID {conid} for {symbol} via /trsrv/secdef")
                        return conid
        except Exception as e:
            logger.debug(f"/trsrv/secdef lookup failed: {str(e)}")
        raise ValueError(f"Could not find contract for {symbol}")

    async def get_price(self, symbol: str) -> float:
        """Get current market price with proper error handling"""
        try:
            conid = await self._get_conid(symbol)
            
            response = self._session.get(
                f"{self.auth.api_endpoint}/iserver/marketdata/snapshot",
                params={
                    "conids": conid,
                    "fields": IBKRPriceFields.BASIC_FIELDS
                },
                timeout=10
            )
            
            logger.debug(f"Price response: {response.status_code} {response.text}")
            
            if response.status_code != 200:
                raise ValueError(f"API error {response.status_code}: {response.text}")
                
            data = response.json()
            
            if not isinstance(data, list) or len(data) == 0:
                raise ValueError("Invalid response format - expected array")
                
            price_data = data[0]
            
            # Check all possible price fields
            if IBKRPriceFields.LAST in price_data:
                return float(price_data[IBKRPriceFields.LAST])
            elif IBKRPriceFields.BID in price_data and IBKRPriceFields.ASK in price_data:
                return (float(price_data[IBKRPriceFields.BID]) + float(price_data[IBKRPriceFields.ASK])) / 2
            else:
                raise ValueError("No valid price fields in response")
                
        except Exception as e:
            logger.error(f"Price fetch failed for {symbol}: {str(e)}")
            raise

    async def submit_order(self, order: Union[OrderRequest, dict]) -> FillReport:
        """Submit order with properly typed parameters"""
        try:
            order = await self._validate_order_input(order)
            conid = await self._get_conid(order.symbol)
            
            # Build payload with exact parameter types expected by IBKR
            payload = {
                "acctId": str(self.auth.account_id),
                "conid": int(conid),
                "secType": f"{conid}:STK",
                "cOID": f"pybot_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "orderType": order.order_type.upper(),
                "side": "BUY" if order.quantity > 0 else "SELL",
                "tif": "DAY",
                "quantity": int(abs(order.quantity)),
                "outsideRTH": False,
                "listingExchange": "SMART",
                "currency": "USD"
            }
            
            # Add price only for limit orders
            if order.order_type == "limit":
                payload["price"] = float(round(order.limit_price, 2))
            
            logger.debug(f"Order payload: {json.dumps(payload, indent=2)}")
            
            response = self._session.post(
                f"{self.auth.api_endpoint}/iserver/account/{self.auth.account_id}/orders",
                json={"orders": [payload]},
                timeout=15
            )
            
            logger.debug(f"Order response: {response.status_code} {response.text}")
            
            if response.status_code != 200:
                error = response.json().get('error', 'Unknown error')
                raise ValueError(f"Order rejected: {error}")
                
            return self._parse_order_response(response.json())
            
        except Exception as e:
            logger.error(f"Order submission failed: {str(e)}")
            raise

    def _parse_order_response(self, response_data: list) -> FillReport:
        """Process order response with proper error handling"""
        if not response_data or not isinstance(response_data, list):
            raise ValueError("Invalid order response format")
            
        order_data = response_data[0]
        
        return FillReport(
            order_id=str(order_data.get('id', '')),
            status=order_data.get('order_status', 'submitted'),
            filled_at=datetime.now().timestamp(),
            message=order_data.get('message', '')
        )

    async def _try_contract_info_endpoint(self, symbol: str) -> str:
        """Alternative endpoint if primary search fails"""
        try:
            response = self._session.get(
                f"{self.auth.api_endpoint}/trsrv/stocks",
                params={"symbols": symbol},
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            if isinstance(data, dict) and symbol in data:
                contracts = data[symbol].get('contracts', [])
                for contract in contracts:
                    if contract.get('contractType') == 'STK':
                        conid = str(contract['conid'])
                        self._conid_cache[symbol] = conid
                        return conid
            
            raise ValueError(f"No stock contract found for {symbol}")
        except Exception as e:
            logger.error(f"Alternative contract lookup failed: {str(e)}")
            raise

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Check order status with proper error handling"""
        try:
            response = self._session.get(
                f"{self.auth.api_endpoint}/iserver/account/order/status/{order_id}",
                timeout=10
            )
            
            if response.status_code != 200:
                return OrderStatus.UNKNOWN
                
            status_data = response.json()
            return self._map_status(status_data.get('order_status'))
            
        except Exception:
            return OrderStatus.UNKNOWN

    @staticmethod
    def _map_status(ibkr_status: str) -> OrderStatus:
        """Map IBKR status to our status enum"""
        status_map = {
            'ApiPending': OrderStatus.PENDING,
            'PendingSubmit': OrderStatus.PENDING,
            'PreSubmitted': OrderStatus.PENDING,
            'Submitted': OrderStatus.OPEN,
            'Filled': OrderStatus.FILLED,
            'Cancelled': OrderStatus.CANCELLED
        }
        return status_map.get(ibkr_status, OrderStatus.FAILED)

    async def _validate_order_input(self, order: Union[OrderRequest, dict]) -> OrderRequest:
        """Validate order parameters with type checking"""
        if isinstance(order, dict):
            order = OrderRequest(
                symbol=str(order['symbol']).strip().upper(),
                quantity=float(order['quantity']),
                order_type=str(order['order_type']).lower(),
                limit_price=float(order['limit_price']) if order.get('limit_price') else None
            )

        if not re.match(r'^[A-Z]{1,5}$', order.symbol):
            raise ValueError(f"Invalid symbol: {order.symbol}")
            
        if not (0 < abs(order.quantity) <= 1000000):
            raise ValueError(f"Invalid quantity: {order.quantity}")
            
        if order.order_type not in ["market", "limit"]:
            raise ValueError(f"Invalid order type: {order.order_type}")
            
        if order.order_type == "limit" and not order.limit_price:
            raise ValueError("Limit price required for limit orders")
            
        return order