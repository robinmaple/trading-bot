import json
from pathlib import Path
from typing import Dict, List, Union, Set
from datetime import datetime
from core.logger import logger

class TradingPlan:
    def __init__(self, plans: Union[Dict[str, dict], List[dict]]):
        """Initialize with execution tracking and persistence"""
        self.plans = self._normalize_input(plans)
        self.executed_plans: Set[str] = set()
        self._load_execution_status()

    def _normalize_input(self, plans: Union[Dict[str, dict], List[dict]]) -> Dict[str, dict]:
        """Convert input to standardized dictionary format"""
        if isinstance(plans, list):
            return {plan['symbol']: plan for plan in plans}
        return plans

    def _load_execution_status(self):
        """Initialize execution tracking from existing plans"""
        for symbol, plan in self.plans.items():
            plan.setdefault('active', True)
            if plan.get('executed', False):
                self.executed_plans.add(symbol)
                plan['active'] = False

    @classmethod
    def load_from_file(cls, path: str):
        """Load plans with execution status preservation"""
        try:
            path = Path(path)
            if not path.exists():
                logger.warning(f"Plan file {path} not found, starting empty")
                return cls({})

            with open(path) as f:
                plans = json.load(f)
                return cls(plans)

        except Exception as e:
            logger.error(f"Failed to load trading plans: {e}")
            raise

    def get_active_plans(self) -> Dict[str, dict]:
        """Get non-executed, active plans"""
        return {
            symbol: plan 
            for symbol, plan in self.plans.items()
            if plan.get('active', True) and symbol not in self.executed_plans
        }

    def mark_executed(self, symbol: str, execution_price: float = None):
        """Permanently mark plan as executed"""
        if symbol not in self.plans:
            logger.warning(f"Attempted to mark non-existent symbol {symbol} as executed")
            return

        self.executed_plans.add(symbol)
        self.plans[symbol].update({
            'active': False,
            'executed': True,
            'executed_at': datetime.now().isoformat(),
            'execution_price': execution_price
        })
        logger.info(f"Marked {symbol} as executed at {execution_price}")

    def save_to_file(self, path: str):
        """Persist execution status to JSON file"""
        try:
            with open(path, 'w') as f:
                json.dump(self.plans, f, indent=2)
            logger.debug(f"Saved trading plans to {path}")
        except Exception as e:
            logger.error(f"Failed to save trading plans: {e}")

    def reset_execution_status(self, symbol: str):
        """Re-activate a previously executed plan (for testing/recovery)"""
        if symbol in self.executed_plans:
            self.executed_plans.remove(symbol)
            self.plans[symbol].update({
                'active': True,
                'executed': False,
                'executed_at': None,
                'execution_price': None
            })
            logger.warning(f"Reset execution status for {symbol}")