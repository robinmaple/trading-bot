import requests
import time
from threading import Lock
from core.logger import logger, redact_sensitive
from core.brokerages.auth.base import BaseBrokerageAuth

class QuestradeAuth(BaseBrokerageAuth):
    def __init__(self, db=None, **kwargs):
        self.lock = Lock()
        self.brokerage_name = 'QUESTRADE'
        super().__init__(db, **kwargs)
        
        if db:  # DB initialization path
            self.token_url, self.refresh_token, self.api_server = self._load_brokerage_info()
        else:   # Direct initialization path
            self.token_url = kwargs['token_url']
            self.refresh_token = kwargs['refresh_token']
            self.api_server = kwargs['api_server']
            
        logger.info(f"Using refresh_token: {redact_sensitive(self.refresh_token)}")

    def _load_db_config(self, db, brokerage_name) -> dict:
        """Load from DB - now returns dict instead of tuple"""
        result = db.execute("""
            SELECT token_url, refresh_token, api_endpoint 
            FROM brokerages 
            WHERE name = ?
        """, (brokerage_name,)).fetchone()

        if not result:
            raise ValueError(f"Brokerage {brokerage_name} not found in database")

        return {
            'token_url': result['token_url'],
            'refresh_token': result['refresh_token'],
            'api_server': result['api_endpoint']
        }

    def _refresh_tokens(self) -> None:
        """Refresh tokens - now uses self._config if needed"""
        with self.lock:
            logger.debug(f"Refreshing tokens via {self.token_url}")
            response = requests.post(
                f"{self.token_url}?grant_type=refresh_token",
                params={'refresh_token': self.refresh_token}
            )
            response.raise_for_status()
            data = response.json()

            # Update tokens
            self.access_token = data['access_token']
            self.refresh_token = data['refresh_token']
            self.api_server = data['api_server']
            self.expiry_time = time.time() + data['expires_in']

            # Persist if using DB
            if self.db:
                self._save_tokens()

    def _save_tokens(self) -> None:
        """DB-specific save logic"""
        with self.db._get_conn() as conn:
            conn.execute("""
                UPDATE brokerages 
                SET refresh_token = ?, api_endpoint = ?
                WHERE name = ?
            """, (
                self.refresh_token,
                self.api_server,
                self.brokerage_name
            ))

    def _load_brokerage_info(self) -> tuple[str, str, str]:
        """Loads token_url, refresh_token, and api_server from database."""
        with self.db._get_conn() as conn:
            result = conn.execute("""
                SELECT token_url, refresh_token, api_endpoint 
                FROM brokerages 
                WHERE name = ?
            """, (self.brokerage_name,)).fetchone()

            if not result:
                raise ValueError(f"Brokerage {self.brokerage_name} not found in database")

            return result['token_url'], result['refresh_token'], result['api_endpoint']


    def get_valid_token(self) -> str:
        """Returns a valid access_token, refreshing if needed."""
        try:
            if time.time() > self.expiry_time - 300:  # 5 minutes buffer
                self._refresh_tokens()
            return self.access_token
        except Exception as e:
            logger.critical(f"Token refresh failed: {e}")
            raise

    def create_session(self) -> requests.Session:
        """Creates an authenticated requests.Session."""
        session = requests.Session()
        session.headers.update({
            'Authorization': f'Bearer {self.get_valid_token()}'
        })
        return session

    def get_accounts(self):
        """Example method to call Questrade accounts endpoint."""
        url = f"{self.api_server}v1/accounts"
        response = self.create_session().get(url)
        response.raise_for_status()
        return response.json()
