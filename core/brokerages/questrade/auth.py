import requests
import time
import json
from threading import Lock
from pathlib import Path
from typing import Optional
from config.settings import QUESTRADE_TOKEN_URL, BASE_DIR
from core.logger import logger, redact_sensitive

import time
from threading import Lock
from datetime import datetime, timedelta
from core.storage.db import TradingDB
from core.logger import logger, redact_sensitive

class QuestradeAuth:
    def __init__(self, db: TradingDB):
        self.lock = Lock()
        self.db = db
        self.brokerage_name = 'QUESTRADE'
        
        # Load initial token from database
        self.refresh_token = self._load_refresh_token()
        logger.info(f"Using refresh_token: {redact_sensitive(self.refresh_token)}")

        self.access_token: Optional[str] = None
        self.api_server: Optional[str] = None
        self.expiry_time: float = 0

        # Validate token
        if not self.refresh_token:
            raise ValueError("No refresh_token found in database")

    def _load_refresh_token(self) -> Optional[str]:
        """Loads refresh_token from database."""
        with self.db._get_conn() as conn:
            result = conn.execute("""
                SELECT refresh_token 
                FROM brokerages 
                WHERE name = ?
            """, (self.brokerage_name,)).fetchone()
            return result['refresh_token'] if result else None

    def _refresh_tokens(self) -> None:
        """Refreshes access_token and updates expiry."""
        with self.lock:
            response = requests.post(
                f"{QUESTRADE_TOKEN_URL}?grant_type=refresh_token",
                params={'refresh_token': self.refresh_token}
            )
            response.raise_for_status()
            data = response.json()
            
            # Update tokens
            self.access_token = data['access_token']
            self.refresh_token = data['refresh_token']  # New refresh token
            self.api_server = data['api_endpoint']
            self.expiry_time = time.time() + data['expires_in']
            
            # Save to database
            self._save_tokens()

    def _save_tokens(self) -> None:
        """Persists tokens to database."""
        expiry_time = datetime.now() + timedelta(seconds=self.expiry_time - time.time())
        
        with self.db._get_conn() as conn:
            conn.execute("""
                UPDATE brokerages 
                SET refresh_token = ?,
                    api_endpoint = ?,
                    token_url = ?
                WHERE name = ?
            """, (
                self.refresh_token,
                self.api_server,
                self.token_url,
                self.brokerage_name
            ))

    def get_valid_token(self) -> str:
        try:
            if time.time() > self.expiry_time - 300:
                self._refresh_tokens()
            return self.access_token
        except Exception as e:
            logger.critical(f"Token refresh failed: {e}")
            # Add notification logic here
            raise

    def create_session(self) -> requests.Session:
        """Creates an authenticated requests.Session."""
        session = requests.Session()
        session.headers.update({
            'Authorization': f'Bearer {self.get_valid_token()}'
        })
        return session
    
    # Keep your existing methods (e.g., get_accounts)
    def get_accounts(self):
        url = f"{self.api_server}v1/accounts"
        return self.create_session().get(url).json()