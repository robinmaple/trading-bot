import requests
from core.auth import QuestradeAuth  # Import existing auth

class AccountService:
    """Handles all account-related operations"""
    def __init__(self, auth_client: QuestradeAuth):
        self.auth = auth_client

    def get_all_accounts(self):
        """Get all trading accounts"""
        return self._make_request("accounts")

    def get_account_balances(self, account_id):
        """Get balances for specific account"""
        return self._make_request(f"accounts/{account_id}/balances")

    def _make_request(self, endpoint):
        headers = {'Authorization': f'Bearer {self.auth.access_token}'}
        url = f"{self.auth.api_server}v1/{endpoint}"
        return requests.get(url, headers=headers).json()