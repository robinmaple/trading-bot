import json
import os
from typing import Optional, Dict

from core.brokerages.questrade.auth import QuestradeAuth  # Reuse your existing auth
from core.logger import logger


class SymbolResolver:
    def __init__(self):
        self.auth = QuestradeAuth()
        self.base_url = f"{self.auth.api_server}/v1/symbols/search"
        self.headers = {'Authorization': f'Bearer {self.auth.get_valid_token()}'}

        # Cache to avoid repeated API calls
        self.symbol_cache: Dict[str, Dict] = {}

    def resolve(self, symbol: str) -> Optional[Dict]:
        """
        Resolves a symbol to a symbol_id and any price service–normalized names.
        """
        if symbol in self.symbol_cache:
            return self.symbol_cache[symbol]

        url = f"{self.base_url}/v1/symbols/search?prefix={symbol}"
        response = self.auth.session.get(url, headers=self.headers)
        if response.status_code != 200:
            logger.error(f"Failed to resolve symbol {symbol}: {response.text}")
            return None

        matches = response.json().get("symbols", [])
        if not matches:
            logger.warning(f"No matches found for symbol {symbol}")
            return None

        # Try to pick the best match (exact + active)
        match = next(
            (s for s in matches if s["symbol"].upper() == symbol.upper() and s["isTradable"]),
            matches[0]
        )

        resolved = {
            "symbol": match["symbol"],
            "symbol_id": match["symbolId"],
            "exchange": match.get("listingExchange") or match.get("exchange"),
            "asset_type": match.get("securityType", "").lower(),
            "price_service_symbol": {
                "alpha_vantage": match["symbol"],
                "finnhub": match["symbol"].replace("-", "/")  # simple crypto transform
            },
            "broker_symbol_id": {
                "questrade": match["symbolId"]
            }
        }

        self.symbol_cache[symbol] = resolved
        return resolved

    def resolve_batch(self, symbols: list[str]) -> dict[str, Optional[Dict]]:
        return {symbol: self.resolve(symbol) for symbol in symbols}

    def save_cache(self, file_path="symbol_cache.json"):
        with open(file_path, "w") as f:
            json.dump(self.symbol_cache, f, indent=2)

    def load_cache(self, file_path="symbol_cache.json"):
        if os.path.exists(file_path):
            with open(file_path) as f:
                self.symbol_cache = json.load(f)
