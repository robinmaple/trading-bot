from abc import ABC, abstractmethod

class PriceService(ABC):
    @abstractmethod
    def get_price(self, symbol: str) -> float:
        pass
