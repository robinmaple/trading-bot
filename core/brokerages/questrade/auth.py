import requests
import time
from threading import Lock
from datetime import datetime, timedelta
from typing import Optional
from core.logger import logger, redact_sensitive
from core.storage.db import TradingDB

class QuestradeAuth:
    def __init__(self, db: TradingDB):
        self.lock = Lock()
        self.db = db
        self.brokerage_name = 'QUESTRADE'

        # Load initial tokens and URLs from database
        self.token_url, self.refresh_token, self.api_server = self._load_brokerage_info()
        logger.info(f"Using refresh_token: {redact_sensitive(self.refresh_token)}")

        self.access_token: Optional[str] = None
        self.expiry_time: float = 0

        if not self.refresh_token or not self.token_url:
            raise ValueError("Brokerage info missing in database")

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

    def _refresh_tokens(self) -> None:
        """Refreshes access_token and updates expiry."""
        with self.lock:
            logger.debug(f"Refreshing tokens via {self.token_url}")
            response = requests.post(
                f"{self.token_url}?grant_type=refresh_token",
                params={'refresh_token': self.refresh_token}
            )
            response.raise_for_status()
            data = response.json()

            # Update in-memory tokens
            self.access_token = data['access_token']
            self.refresh_token = data['refresh_token']  # New refresh token
            self.api_server = data['api_server']  # Sometimes it's 'api_server' or 'api_endpoint' depending on API
            self.expiry_time = time.time() + data['expires_in']

            # Persist the new tokens
            self._save_tokens()

    def _save_tokens(self) -> None:
        """Persists updated tokens to database."""
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
