import logging
import requests
from requests.cookies import cookiejar_from_dict
from cryptography.fernet import Fernet, InvalidToken
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
from core.logger import logger

# Disable SSL warnings
disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)

class IBKRAuth:
    def __init__(self, db, account_id: str):
        self.db = db
        self.account_id = account_id
        self.session = self._create_session()
        self._load_config()

    def _create_session(self):
        """Create a requests session with proper cookie handling"""
        session = requests.Session()
        session.verify = False  # Disable SSL verification for localhost
        session.headers.update({
            'User-Agent': 'Python Trading App',
            'Content-Type': 'application/json'
        })
        return session

    def _load_config(self):
        """Load configuration including API endpoint"""
        try:
            with self.db._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        b.token_url,
                        b.api_endpoint,
                        b.username,
                        b.password,
                        a.bp_override
                    FROM brokerages b
                    JOIN accounts a ON b.id = a.brokerage_id
                    WHERE a.account_id = ?
                """, (self.account_id,))

                config = cursor.fetchone()
                if not config:
                    raise ValueError(f"No configuration for account {self.account_id}")

                # Load encryption key
                cursor.execute("SELECT key_value FROM encryption_keys WHERE key_name='brokerage_creds'")
                key_row = cursor.fetchone()
                if not key_row:
                    raise ValueError("Encryption key not found")

                self.cipher = Fernet(key_row[0].encode())
                self.token_url = config['token_url'].rstrip('/')
                self.api_endpoint = config['api_endpoint'].rstrip('/')
                self.username = self._decrypt(config['username'])
                self.password = self._decrypt(config['password'])
                self.bp_override = config['bp_override']

                logger.info(f'API Endpoint: {self.api_endpoint}')
                logger.info(f'Token URL: {self.token_url}')

        except Exception as e:
            logger.error(f"Config load failed: {e}")
            raise

    def _decrypt(self, encrypted: str) -> str:
        """Safely decrypt a value"""
        if not encrypted or not encrypted.startswith('enc:'):
            return encrypted
        try:
            return self.cipher.decrypt(encrypted[4:].encode()).decode()
        except InvalidToken:
            logger.error("Decryption failed - invalid token or key mismatch")
            raise

    def is_authenticated(self) -> bool:
        """Check if session is alive and get cookies"""
        try:
            response = self.session.get(
                f"{self.api_endpoint}/tickle",
                timeout=5
            )
            
            if response.status_code == 200:
                # Get all cookies
                cookies = response.cookies.get_dict()
                # Log all cookies found
                logger.info(f"Session cookies: {cookies}")
                
                # Check for IBKR session cookies
                if 'x-sess-uuid' in cookies or 'JSESSIONID' in cookies:
                    return True
            return False
        except requests.RequestException as e:
            logger.error(f"Auth check failed: {e}")
            return False

    def authenticate(self) -> bool:
        """Full authentication flow with cookie capture"""
        try:
            # First try to reuse existing session
            if self.is_authenticated():
                return True
                
            # Force new authentication
            login_url = f"{self.api_endpoint}/v1/api/login"
            response = self.session.post(
                login_url,
                json={
                    "username": self.username,
                    "password": self.password
                },
                timeout=10
            )
            
            if response.status_code == 200:
                # Capture cookies from Set-Cookie header
                cookies = response.cookies.get_dict()
                if cookies:
                    self.session.cookies = cookiejar_from_dict(cookies)
                    logger.info(f"🔑 Authentication successful. Cookies: {cookies}")
                    return True
                
            logger.error(f"Authentication failed. Status: {response.status_code}")
            return False
            
        except Exception as e:
            logger.error(f"Auth failed. Error: {str(e)}")
            return False

    def submit_order(self, order_data: dict) -> dict:
        """Submit order with proper session handling"""
        try:
            # First validate the order
            validate_url = f"{self.api_endpoint}/v1/api/iserver/account/{self.account_id}/orders/validate"
            validate_resp = self.session.post(
                validate_url,
                json=order_data,
                timeout=10
            )
            
            if validate_resp.status_code != 200:
                logger.error(f"Order validation failed: {validate_resp.text}")
                return {"success": False, "error": validate_resp.text}
            
            # Submit the actual order
            order_url = f"{self.api_endpoint}/v1/api/iserver/account/{self.account_id}/orders"
            order_resp = self.session.post(
                order_url,
                json=order_data,
                timeout=10
            )
            
            if order_resp.status_code == 200:
                return {"success": True, "data": order_resp.json()}
            else:
                logger.error(f"Order submission failed: {order_resp.text}")
                return {"success": False, "error": order_resp.text}
                
        except Exception as e:
            logger.error(f"Order submission error: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_buying_power(self) -> float:
        """Get buying power with override support"""
        if self.bp_override is not None:
            return float(self.bp_override)
        
        try:
            resp = self.session.get(
                f"{self.api_endpoint}/portfolio/{self.account_id}/summary",
                timeout=10
            )
            resp.raise_for_status()
            return float(resp.json().get('buyingPower', {}).get('amount', 0.0))
        except requests.RequestException as e:
            logger.error(f"Failed to get buying power: {e}")
            return 0.0