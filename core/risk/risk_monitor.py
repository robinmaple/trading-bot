# core/risk/risk_monitor.py
from datetime import datetime, timedelta
from enum import Enum
import threading
import time
from typing import Dict, Literal 
from core.models import PeriodType
from dataclasses import dataclass
from core.logger import logger
from core.config.manager import config

@dataclass
class RiskReport():  # Optional data model
    pnl: float
    limit_pct: float
    utilization_pct: float
    is_breached: bool
    last_reset: datetime

class RiskMonitor:
    def __init__(self):
        self.limits = {
            PeriodType.DAILY: float(config.get("daily_loss_limit_percent", 2.0)),
            PeriodType.WEEKLY: float(config.get("weekly_loss_limit_percent", 5.0)),
            PeriodType.MONTHLY: float(config.get("monthly_loss_limit_percent", 10.0))
        }
        self.period_data = {
            PeriodType.DAILY: {"pnl": 0.0, "breached": False, "last_reset": None},
            PeriodType.WEEKLY: {"pnl": 0.0, "breached": False, "last_reset": None},
            PeriodType.MONTHLY: {"pnl": 0.0, "breached": False, "last_reset": None}
        }
        self._lock = threading.Lock()
        self._initialize_reset_dates()

    def _initialize_reset_dates(self):
        """Set initial reset dates based on current time"""
        now = datetime.now()
        self.period_data[PeriodType.DAILY]["last_reset"] = now.date()
        self.period_data[PeriodType.WEEKLY]["last_reset"] = now - timedelta(days=now.weekday())
        self.period_data[PeriodType.MONTHLY]["last_reset"] = now.replace(day=1)

    def update_pnl(self, amount: float):
        """Update PnL for all periods"""
        with self._lock:
            self._check_resets()
            for period in PeriodType:
                self.period_data[period]["pnl"] += amount
            logger.info(f"Updated PnL: {amount:.2f} | Current Totals - "
                       f"Daily: {self.get_pnl(PeriodType.DAILY):.2f}, "
                       f"Weekly: {self.get_pnl(PeriodType.WEEKLY):.2f}, "
                       f"Monthly: {self.get_pnl(PeriodType.MONTHLY):.2f}")

    def is_limit_breached(self, period: PeriodType, account_value: float) -> bool:
        """Check if specified period limit was hit"""
        if self.period_data[period]["breached"]:
            return True
            
        loss_percent = abs(self.period_data[period]["pnl"]) / account_value * 100
        if loss_percent >= self.limits[period] and self.period_data[period]["pnl"] < 0:
            self.period_data[period]["breached"] = True
            logger.critical(
                f"{period.value.capitalize()} loss limit breached: {loss_percent:.2f}% "
                f"(PnL: {self.period_data[period]['pnl']:.2f}, "
                f"Limit: {self.limits[period]}%)"
            )
            return True
        return False

    def _check_resets(self):
        """Auto-reset periods when appropriate"""
        now = datetime.now()
        if now.date() != self.period_data[PeriodType.DAILY]["last_reset"]:
            if self._is_after_close(now):
                self._reset_period(PeriodType.DAILY)
                
        if now - self.period_data[PeriodType.WEEKLY]["last_reset"] >= timedelta(weeks=1):
            self._reset_period(PeriodType.WEEKLY)
            
        if now.month != self.period_data[PeriodType.MONTHLY]["last_reset"].month:
            self._reset_period(PeriodType.MONTHLY)

    def _reset_period(self, period: PeriodType):
        """Reset tracking for a specific period"""
        with self._lock:
            self.period_data[period]["pnl"] = 0.0
            self.period_data[period]["breached"] = False
            self.period_data[period]["last_reset"] = datetime.now()
            logger.info(f"Reset {period.value} PnL tracking")

    def _is_after_close(self, dt: datetime) -> bool:
        """Check if current time is after market close"""
        return False  # Placeholder for actual market close logic

    def get_pnl(self, period: PeriodType) -> float:
        """Get current PnL for specified period"""
        return self.period_data[period]["pnl"]
    
    def get_risk_report(self) -> dict:
        """Add this method for better visibility"""
        account_value = self._get_account_value()
        return {
            period.value: {
                "pnl": self.risk_monitor.get_pnl(period),
                "limit_percent": self.risk_monitor.limits[period],
                "utilization_percent": (
                    abs(self.risk_monitor.get_pnl(period)) / 
                    account_value * 100
                ),
                "breached": self.risk_monitor.is_limit_breached(period, account_value)
            }
            for period in PeriodType
        }
    
def get_risk_report(self, account_value: float) -> Dict[str, Dict[Literal['daily', 'weekly', 'monthly'], RiskReport]]:
        """
        Generates a comprehensive risk report with:
        - Current PnL for each period
        - Limit percentages
        - Utilization percentages
        - Breach status
        - Last reset time
        
        Args:
            account_value: Current total account value for utilization calculations
            
        Returns:
            {
                "daily": {
                    "pnl": -1500.0,
                    "limit_pct": 2.0,
                    "utilization_pct": 75.0,
                    "is_breached": False,
                    "last_reset": "2023-07-20T00:00:00"
                },
                ...
            }
        """
        report = {}
        
        for period in PeriodType:
            pnl = self.period_data[period]["pnl"]
            limit = self.limits[period]
            
            report[period.value] = {
                "pnl": pnl,
                "limit_pct": limit,
                "utilization_pct": abs(pnl) / account_value * 100 if account_value > 0 else 0,
                "is_breached": self.period_data[period]["breached"],
                "last_reset": self.period_data[period]["last_reset"]
            }
            
        return report
