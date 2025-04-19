import random
from core.logger import logger
from config.env import PROFIT_TO_LOSS_RATIO
from core.api.orders import BracketOrder
from typing import Dict
from .price_service import BasePriceService

class MockPriceService(BasePriceService):
    def get_price(self, symbol: str) -> float:
        return round(169 + random.uniform(-1, 1), 2)

    def simulate_exit(self, bracket_order: BracketOrder, symbol: str, order_data: Dict) -> None:
        direction = order_data.get("side", "Buy")
        entry = order_data["entry"]
        stop = order_data["stop"]
        risk = abs(entry - stop)
        profit_target = (entry + risk * PROFIT_TO_LOSS_RATIO if direction == "Buy"
                         else entry - risk * PROFIT_TO_LOSS_RATIO)
        logger.info(f"[SIMULATION] Watching {symbol}: Entry={entry}, SL={stop}, TP={profit_target}")
        simulated_exit_price = random.choice([stop, profit_target])
        logger.info(f"[SIMULATION] Exit triggered for {symbol} at {simulated_exit_price}")
