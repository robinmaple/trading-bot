from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.brokerages.protocol import OrderRequest

# Rest of your code can use OrderRequest/FillReport as types
from dataclasses import dataclass
from .models import OrderRequest
from typing import Optional 

@dataclass
class BracketOrder:
    """A bracket order (entry + take-profit + stop-loss)."""
    symbol: str
    entry_price: float
    take_profit_price: Optional[float]
    stop_loss_price: float
    quantity: float  # Absolute value (direction inferred from sign)
    side: Optional[str] = None  # e.g., 'Buy' or 'Sell', optional if you're inferring from quantity
    entry_type: str = "limit"  # 'limit' or 'stop_limit'
    entry_stop_trigger: Optional[float] = None  # Required for stop_limit
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
    
    @classmethod
    def from_plan(cls, plan: dict, current_price: float = None):
        """
        Creates order from plan using EITHER:
        - plan['entry'] if specified, OR
        - current_price if provided, OR
        - raises ValueError if neither exists
        """
        if current_price is None and 'entry' not in plan:
            raise ValueError("Requires either current_price or plan['entry']")

        entry = plan.get('entry', current_price)
        stop = plan['stop']
        
        # Auto-calculate take profit if not specified (2:1 risk-reward)
        take_profit = plan.get('take_profit')
        if take_profit is None:
            risk = abs(entry - stop)
            take_profit = entry + risk*2 if plan['side'].lower() == 'buy' else entry - risk*2

        return cls(
            symbol=plan['symbol'],
            entry_price=entry,
            take_profit_price=take_profit,
            stop_loss_price=stop,
            quantity=0,  # To be calculated later
            side=plan['side'].lower(),
            entry_type=plan.get('entry_type', 'limit'),
            entry_stop_trigger=plan.get('entry_stop_trigger')
        )