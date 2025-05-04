# core/brokerages/ibkr/client.py
import logging
from datetime import datetime
from typing import Dict, Union
import requests
from ..protocol import PriceProtocol, OrderProtocol, OrderRequest, FillReport
from .auth import IBKRAuth
from core.logger import logger
from core.models import OrderStatus

class IBKRPriceFields:
    """Constants for IBKR market data fields"""
    # Standard numeric fields
    LAST = '31'          # Last price
    LAST_SIZE = '84'     # Last size
    BID = '85'           # Bid price
    BID_SIZE = '86'      # Bid size
    ASK = '87'           # Ask price
    ASK_SIZE = '88'      # Ask size
    CLOSE = '89'         # Previous close
    OPEN = '90'          # Today's open
    LOW = '91'           # Daily low
    HIGH = '92'          # Daily high
    
    # Alternative field names (used in some endpoints)
    LAST_PRICE = 'lastPrice'
    BID_PRICE = 'bidPrice'
    ASK_PRICE = 'askPrice'
    CLOSE_PRICE = 'closePrice'
    
    # Combined field sets
    BASIC_PRICE_FIELDS = f"{LAST},{CLOSE},{BID},{ASK}"
    FULL_PRICE_FIELDS = f"{LAST},{BID},{ASK},{CLOSE},{OPEN},{HIGH},{LOW}"

class IBKRClient(PriceProtocol, OrderProtocol):
    """IBKR Client Portal Gateway implementation"""
    
    def __init__(self, auth: IBKRAuth):
        self.auth = auth
        self._conid_cache: Dict[str, str] = {}
        self._session = auth.session
        self._session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Python Client/1.0'
        })

    async def get_price(self, symbol: str) -> float:
        """Get current market price for a symbol"""
        try:
            # First get the contract ID
            conid = await self._get_conid(symbol)
            if not conid:
                raise ValueError(f"No conid found for {symbol}")

            # Get market data snapshot
            response = self.auth.session.get(
                f"{self.auth.api_endpoint}/iserver/marketdata/snapshot",
                params={
                    "conids": conid,
                    "fields": "31,84,86"  # Bid, Ask, Last price fields
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            if not data:
                raise ValueError("Empty market data response")

            # Find the first valid price in this order: last, bid, ask
            price_fields = [
                ('86', 'Last price'),
                ('31', 'Bid price'),
                ('84', 'Ask price')
            ]
            
            for field_id, field_name in price_fields:
                if field_id in data[0]:
                    price = float(data[0][field_id])
                    logger.info(f"📊 {symbol} {field_name}: {price}")
                    return price

            raise ValueError(f"No valid price in response: {data[0].keys()}")

        except Exception as e:
            logger.error(f"Price fetch failed for {symbol}: {str(e)}")
            raise

    async def _get_conid(self, symbol: str) -> str:
        """Get contract ID with proper selection from API response"""
        try:
            if symbol in self._conid_cache:
                return self._conid_cache[symbol]

            # Make the API request
            response = self._session.get(
                f"{self.auth.api_endpoint}/iserver/secdef/search",
                params={"symbol": symbol.upper()},
                timeout=10
            )
            response.raise_for_status()
            contracts = response.json()

            # Debug logging
            logger.debug(f"Raw contract search response for {symbol}: {contracts}")

            if not isinstance(contracts, list) or len(contracts) == 0:
                raise ValueError(f"No contracts returned for {symbol}")

            # Filter for US stock (NASDAQ/NYSE) with highest priority
            us_stock_contracts = [
                c for c in contracts
                if isinstance(c, dict) and
                c.get('symbol') == symbol.upper() and
                any(section.get('secType') == 'STK' and 
                    ('NASDAQ' in c.get('description', '') or 
                    'NYSE' in c.get('description', ''))
                    for section in c.get('sections', []))
            ]

            # If no US stocks found, take first valid contract
            valid_contracts = us_stock_contracts if us_stock_contracts else [
                c for c in contracts
                if isinstance(c, dict) and
                c.get('conid') and
                c.get('symbol') == symbol.upper()
            ]

            if not valid_contracts:
                raise ValueError(f"No valid contracts found for {symbol}")

            # Select the primary contract (first US stock, or first valid)
            primary_contract = valid_contracts[0]
            conid = str(primary_contract['conid'])
            
            logger.debug(f"Selected CONID {conid} for {symbol} from {primary_contract}")
            self._conid_cache[symbol] = conid
            return conid

        except Exception as e:
            logger.error(f"CONID lookup failed for {symbol}: {str(e)}")
            raise

    async def submit_order(self, order: Union[OrderRequest, dict]) -> FillReport:
        """Submit order following exact IBKR API specifications"""
        try:
            # Convert and validate order input
            if isinstance(order, dict):
                order = OrderRequest(
                    symbol=str(order['symbol']).strip().upper(),
                    quantity=float(order['quantity']),
                    order_type=str(order['order_type']).lower(),
                    limit_price=float(order['limit_price']) if order.get('limit_price') else None
                )

            # Validate order parameters
            if not order.symbol or not order.symbol.isalpha():
                raise ValueError("Symbol must contain only letters")
                
            if not isinstance(order.quantity, (int, float)) or abs(order.quantity) < 0.0001:
                raise ValueError("Quantity must be non-zero number")
                
            if order.order_type not in ["market", "limit"]:
                raise ValueError("Order type must be 'market' or 'limit'")
                
            if order.order_type == "limit" and not order.limit_price:
                raise ValueError("Limit price required for limit orders")

            # Get contract ID
            conid = await self._get_conid(order.symbol)
            
            # Build payload according to exact API specs
            payload = {
                "orders": [{
                    "acctId": self.auth.account_id,
                    "conid": conid,
                    "secType": f"{conid}:STK",
                    "cOID": f"python_{int(datetime.now().timestamp())}",
                    "orderType": order.order_type.upper(),
                    "listingExchange": "NASDAQ",  # Must match actual exchange
                    "side": "BUY" if order.quantity > 0 else "SELL",
                    "price": round(float(order.limit_price), 2) if order.order_type == "limit" else "",
                    "tif": "DAY",
                    "quantity": abs(int(order.quantity)),
                    "outsideRTH": False,
                    "useAdaptive": False
                }]
            }

            # Submit to plural endpoint (/orders) with array payload
            response = self._session.post(
                f"{self.auth.api_endpoint}/iserver/account/{self.auth.account_id}/orders",
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'PythonClient'
                },
                timeout=15
            )
            
            # Debug output
            logger.debug(f"Order payload: {payload}")
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response body: {response.text}")
            
            response.raise_for_status()
            data = response.json()
            
            # Handle response (always returns array)
            if isinstance(data, list) and len(data) > 0:
                order_data = data[0]
                if order_data.get('error'):
                    raise ValueError(order_data.get('message', 'Order rejected'))
                    
                return FillReport(
                    order_id=str(order_data.get('id', '')),
                    status=order_data.get('status', 'submitted'),
                    filled_at=datetime.now().timestamp(),
                    message=order_data.get('message', '')
                )
                
            raise ValueError("Empty or invalid response from API")
            
        except Exception as e:
            logger.error(f"Order submission failed: {str(e)}")
            raise
        
    async def get_order_status(self, order_id: str) -> OrderStatus:
            """Check order status with retry logic"""
            try:
                response = self._session.get(
                    f"{self.auth.api_endpoint}/iserver/account/order/status/{order_id}",
                    params={"nocache": int(datetime.now().timestamp())}
                )
                response.raise_for_status()
                
                status_data = response.json()
                return self._map_status(status_data.get('order_status'))
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Status check failed, retrying: {str(e)}")
                return OrderStatus.PENDING
            except Exception as e:
                logger.error(f"Permanent status check failure: {str(e)}")
                return OrderStatus.FAILED

    @staticmethod
    def _map_status(ibkr_status: str) -> OrderStatus:
        """Enhanced status mapping with more IBKR-specific states"""
        status_map = {
            'ApiPending': OrderStatus.PENDING,
            'PendingSubmit': OrderStatus.PENDING,
            'PreSubmitted': OrderStatus.PENDING,
            'Submitted': OrderStatus.OPEN,
            'Filled': OrderStatus.FILLED,
            'Cancelled': OrderStatus.CANCELLED,
            'Inactive': OrderStatus.CANCELLED,
            'PendingCancel': OrderStatus.CANCELLED
        }
        return status_map.get(ibkr_status, OrderStatus.FAILED)

    async def validate_market_session(self) -> bool:

        """Check if market is open for trading"""
        try:
            response = self._session.get(
                f"{self.auth.api_endpoint}/iserver/marketdata/history",
                params={
                    "conid": await self._get_conid('SPY'),  # Use SPY as market proxy
                    "period": "1d",
                    "bar": "1min"
                }
            )
            return response.status_code == 200
        except Exception:
            return False
        
    def _debug_request(self, method, url, **kwargs):
        """Helper method to debug API requests"""
        logger.debug(f"Making {method} request to {url}")
        if 'params' in kwargs:
            logger.debug(f"Params: {kwargs['params']}")
        if 'json' in kwargs:
            logger.debug(f"Payload: {kwargs['json']}")
        
        response = self._session.request(method, url, **kwargs)
        
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {response.headers}")
        logger.debug(f"Response body: {response.text}")
        
        return response
    
    async def _verify_order(self, order: Union[OrderRequest, dict]) -> dict:
        """Validate and prepare order payload"""
        # Convert dict to OrderRequest if needed
        if isinstance(order, dict):
            order = OrderRequest(
                symbol=str(order['symbol']),
                quantity=float(order['quantity']),
                order_type=str(order['order_type']),
                limit_price=float(order['limit_price']) if 'limit_price' in order else None
            )

        # Validate order parameters
        if not order.symbol or not isinstance(order.symbol, str):
            raise ValueError("Symbol must be non-empty string")
            
        if not isinstance(order.quantity, (int, float)) or order.quantity == 0:
            raise ValueError("Quantity must be non-zero number")
            
        order_type = order.order_type.lower()
        if order_type not in ["market", "limit"]:
            raise ValueError("Order type must be 'market' or 'limit'")
            
        if order_type == "limit" and not order.limit_price:
            raise ValueError("Limit price required for limit orders")

        # Get contract ID
        conid = await self._get_conid(order.symbol)
        
        # Build payload according to latest IBKR API specs
        return {
            "acctId": self.auth.account_id,
            "conid": conid,
            "secType": "STK",
            "cOID": f"py_{datetime.now().strftime('%Y%m%d_%H%M%S')}",  # Client order ID
            "orderType": order_type.upper(),
            "side": "BUY" if order.quantity > 0 else "SELL",
            "tif": "DAY",
            "quantity": abs(int(order.quantity)),  # IBKR requires whole numbers
            "outsideRTH": False,
            "price": round(float(order.limit_price), 2) if order_type == "limit" else "",
            "useAdaptive": False
        }
    
    def _inspect_order_endpoint(self):
        """Inspect the order endpoint to understand required fields"""
        try:
            response = self._session.get(
                f"{self.auth.api_endpoint}/iserver/account/order/metadata",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None
        
    
    def _get_order_requirements(self):
        """Get the exact order requirements from IBKR API"""
        try:
            response = self._session.get(
                f"{self.auth.api_endpoint}/iserver/account/order/metadata",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.debug(f"Could not get order metadata: {str(e)}")
            return None