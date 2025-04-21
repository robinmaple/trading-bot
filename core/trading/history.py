import csv
from pathlib import Path
from datetime import datetime
from ..brokerages.protocol import FillReport

class TradeHistoryLogger:
    def __init__(self, log_dir: Path = Path("logs")):
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = log_dir / "trades.csv"

    def log_fill(self, fill: FillReport):
        """Logs a fill report to CSV."""
        with open(self.log_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                fill.order_id,
                fill.filled_at,
                fill.status
            ])