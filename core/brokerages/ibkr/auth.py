import requests
from typing import Optional, Dict
from core.logger import logger
from core.config.manager import config

class IBKRAuth:
    """Handles authentication with Interactive Brokers API."""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_server = config.get("IBKR_API_ENDPOINT", "https://api.ibkr.com/v1/api/")
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None

    def create_session(self) -> requests.Session:
        """Create and return an authenticated session."""
        session = requests.Session()
        
        if not self.access_token:
            self._refresh_access_token()
            
        session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        })
        return session

    def _refresh_access_token(self) -> None:
        """Refresh the OAuth access token."""
        token_url = config.get("IBKR_TOKEN_URL", "https://api.ibkr.com/v1/api/oauth/token")
        
        auth = (self.client_id, self.client_secret)
        data = {
            "grant_type": "client_credentials",
            "scope": "read write"
        }
        
        response = requests.post(token_url, auth=auth, data=data)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to authenticate with IBKR: {response.text}")
            
        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token", "")
        logger.info("Successfully authenticated with IBKR API")