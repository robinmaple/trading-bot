import requests
import time
import json
from threading import Lock
from pathlib import Path
from typing import Optional
from config.settings import QUESTRADE_TOKEN_URL, BASE_DIR
from core.logger import logger

class QuestradeAuth:
    def __init__(self, refresh_token: Optional[str] = None):
        self.lock = Lock()
        self.token_file = BASE_DIR / 'tokens.json'
        self.refresh_token = refresh_token or self._load_refresh_token()

        logger.info(f"Using refresh_token: {self.refresh_token}")

        self.access_token: Optional[str] = None
        self.api_server: Optional[str] = None
        self.expiry_time: float = 0

        # Validate token
        if not self.refresh_token:
            raise ValueError("refresh_token must be provided or exist in tokens.json")

    def _load_refresh_token(self) -> Optional[str]:
        """Loads refresh_token from file if exists."""
        if self.token_file.exists():
            with open(self.token_file) as f:
                return json.load(f).get('refresh_token')
        return None

    def _refresh_tokens(self) -> None:
        """Refreshes access_token and updates expiry."""
        with self.lock:
            response = requests.post(
                f"{QUESTRADE_TOKEN_URL}?grant_type=refresh_token",
                params={'refresh_token': self.refresh_token}
            )
            response.raise_for_status()
            data = response.json()
            
            self.access_token = data['access_token']
            self.refresh_token = data['refresh_token']  # Updates refresh token
            self.api_server = data['api_server']
            self.expiry_time = time.time() + data['expires_in']
            
            self._save_tokens()

    def _save_tokens(self) -> None:
        """Persists refresh_token to disk."""
        with open(self.token_file, 'w') as f:
            json.dump({'refresh_token': self.refresh_token}, f)

    def get_valid_token(self) -> str:
        """Returns a valid access_token, refreshing if needed."""
        if time.time() > self.expiry_time - 300:  # Refresh 5 mins early
            self._refresh_tokens()
        return self.access_token

    def create_session(self) -> requests.Session:
        """Creates an authenticated requests.Session."""
        session = requests.Session()
        session.headers.update({
            'Authorization': f'Bearer {self.get_valid_token()}',
            'Content-Type': 'application/json'
        })
        return session

    # Keep your existing methods (e.g., get_accounts)
    def get_accounts(self):
        url = f"{self.api_server}v1/accounts"
        return self.create_session().get(url).json()
    
# At BOTTOM of auth.py
if __name__ == "__main__":
    print("✅ auth.py is accessible and running directly")
    print(f"🔍 Class is defined: {QuestradeAuth.__module__}.{QuestradeAuth.__name__}")