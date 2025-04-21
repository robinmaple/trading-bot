from dataclasses import dataclass
from .models import OrderRequest

@dataclass
class BracketOrder:
    """A bracket order (entry + take-profit + stop-loss)."""
    symbol: str
    entry_price: float
    take_profit_price: float
    stop_loss_price: float
    quantity: float  # Absolute value (direction inferred from sign)

    def validate(self) -> bool:
        """Checks if prices form a valid bracket."""
        return (
            self.take_profit_price > self.entry_price > self.stop_loss_price
            if self.quantity > 0  # Long position
            else self.take_profit_price < self.entry_price < self.stop_loss_price  # Short
        )

    def to_order_requests(self) -> list[OrderRequest]:
        """Converts to executable OrderRequest objects."""
        if not self.validate():
            raise ValueError("Invalid bracket prices")

        return [
            # Entry order
            OrderRequest(
                symbol=self.symbol,
                quantity=self.quantity,
                order_type="limit",
                price=self.entry_price
            ),
            # Take-profit (limit order)
            OrderRequest(
                symbol=self.symbol,
                quantity=-self.quantity,  # Opposite direction
                order_type="limit",
                price=self.take_profit_price
            ),
            # Stop-loss (stop order)
            OrderRequest(
                symbol=self.symbol,
                quantity=-self.quantity,
                order_type="stop",
                stop_price=self.stop_loss_price
            )
        ]