from pathlib import Path
from typing import List
from dataclasses import asdict
import json
from datetime import datetime
from ..brokerages.protocol import OrderProtocol, FillReport
from ..orders.bracket import BracketOrder
from ..orders.models import OrderRequest

class OrderExecutor:
    def __init__(self, broker: OrderProtocol, log_dir: str = "logs/executions"):
        self.broker = broker
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)  # Ensure dir exists

    async def _log_execution(self, fill_report: FillReport, order: OrderRequest) -> None:
        """Logs execution details to a JSON file."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "broker": self.broker.name,  # e.g., "binance"
            **asdict(order),  # Captures symbol, quantity, type, etc.
            "execution_metadata": asdict(fill_report),  # Fees, slippage, latency
            "status": fill_report.status,
        }
        
        log_file = self.log_dir / f"executions_{datetime.utcnow().date()}.json"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    async def execute(self, order: OrderRequest) -> FillReport:
        """Submits and logs a single order."""
        fill = await self.broker.submit_order(order)
        await self._log_execution(fill, order)  # Log after execution
        return fill
    
    async def execute_bracket(self, bracket: BracketOrder) -> List[FillReport]:
        """
        Submits a bracket order (entry + take-profit + stop-loss).
        
        Args:
            bracket: BracketOrder containing entry/TP/SL prices.
        
        Returns:
            List of FillReports in order: [entry, take_profit, stop_loss]
        
        Raises:
            ValueError: If bracket prices are invalid.
        """
        if not bracket.validate():
            raise ValueError("Invalid bracket prices")
        
        # Generate OrderRequest objects from BracketOrder
        entry_order, tp_order, sl_order = bracket.to_order_requests()
        
        # Submit all orders and return fills
        return [
            self.broker.submit_order(entry_order),
            self.broker.submit_order(tp_order),
            self.broker.submit_order(sl_order)
        ]