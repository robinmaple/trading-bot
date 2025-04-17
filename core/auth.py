import requests
import time
import json
from threading import Lock
from pathlib import Path
from config.settings import QUESTRADE_TOKEN_URL, BASE_DIR

class QuestradeAuth:
    def __init__(self, refresh_token=None):
        self.lock = Lock()
        self.token_file = BASE_DIR / 'tokens.json'

        # Load from file if not passed
        if not refresh_token and self.token_file.exists():
            with open(self.token_file) as f:
                refresh_token = json.load(f).get('refresh_token')

        if not refresh_token:
            raise ValueError("A refresh_token must be provided either via argument or tokens.json")

        self.refresh_token = refresh_token
        self.access_token = None
        self.api_server = None
        self.expiry_time = 0

    def _refresh_tokens(self):
        with self.lock:
            response = requests.post(
                f"{QUESTRADE_TOKEN_URL}?grant_type=refresh_token",
                params={'refresh_token': self.refresh_token}
            )
            response.raise_for_status()
            data = response.json()
            
            self.access_token = data['access_token']
            self.refresh_token = data['refresh_token']
            self.api_server = data['api_server']
            self.expiry_time = time.time() + data['expires_in']
            
            self._save_tokens()
            return data

    def _save_tokens(self):
        with open(self.token_file, 'w') as f:
            json.dump({'refresh_token': self.refresh_token}, f)

    def get_valid_token(self):
        if time.time() > self.expiry_time - 300:  # Refresh 5 mins early
            self._refresh_tokens()
        return self.access_token

    def get_accounts(self):
        headers = {'Authorization': f'Bearer {self.get_valid_token()}'}
        url = f"{self.api_server}v1/accounts"
        return requests.get(url, headers=headers).json()