# core/brokerages/ibkr/auth.py
from core.brokerages.auth.base import BaseBrokerageAuth
from core.logger import logger
import requests, time

class IBKRAuth(BaseBrokerageAuth):
    def __init__(self, db=None, **kwargs):
        self.brokerage_name = 'IBKR'
        super().__init__(db, **kwargs)
        
        if db:
            config = self._load_db_config(db, self.brokerage_name)
            self.token_url = config['token_url']
            self.client_id = config['client_id']
            self.client_secret = config['client_secret']
            self.api_server = config['api_server']
        else:
            self.token_url = kwargs['token_url']
            self.client_id = kwargs['client_id']
            self.client_secret = kwargs['client_secret']
            self.api_server = kwargs['api_server']

    def _load_db_config(self, db, brokerage_name) -> dict:
        result = db.execute("""
            SELECT token_url, client_id, client_secret, api_endpoint
            FROM brokerages
            WHERE name = ?
        """, (brokerage_name,)).fetchone()
        
        return {
            'token_url': result['token_url'],
            'client_id': result['client_id'],
            'client_secret': result['client_secret'],
            'api_server': result['api_endpoint']
        }

    def _refresh_tokens(self) -> None:
        """IBKR-specific token refresh"""
        response = requests.post(
            self.token_url,
            auth=(self.client_id, self.client_secret),
            data={'grant_type': 'client_credentials'}
        )
        response.raise_for_status()
        data = response.json()
        
        self.access_token = data['access_token']
        self.expiry_time = time.time() + data['expires_in']