from core.logger import logger
from core.config.manager import config

class DailyLossTracker:
    def __init__(self):
        self.daily_pnl = 0.0
        self.limit_percent = 2.0  # Default
        
        try:
            self.limit_percent = float(config.get("daily_loss_limit_percent"))
        except ImportError:
            pass
    
    def update_pnl(self, amount):
        """Update running PnL (positive for gains, negative for losses)"""
        self.daily_pnl += amount
        logger.info(f"Updated daily PnL: {self.daily_pnl:.2f}")
    
    def is_limit_breached(self, account_value):
        """Check if daily loss limit was hit"""
        loss_percent = abs(self.daily_pnl) / account_value * 100
        if loss_percent >= self.limit_percent and self.daily_pnl < 0:
            logger.warning(f"Daily loss limit breached: {loss_percent:.2f}%")
            return True
        return False