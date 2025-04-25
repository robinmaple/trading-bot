import json
import os
import shutil
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

    def mark_executed(self, symbol: str, price: float, quantity: int):
        """Records execution details with quantity"""
        if symbol not in self.plans:
            raise ValueError(f"Invalid symbol {symbol}")
            
        self.executed_plans.add(symbol)
        self.plans[symbol].update({
            'active': False,
            'executed': True,
            'executed_at': datetime.now().isoformat(),
            'execution_price': price,
            'executed_quantity': quantity,
            'committed_value': price * quantity
        })
        
    def save_to_file(self, path: str):
        """Thread-safe file persistence"""
        try:
            # Create backup copy
            backup_path = f"{path}.bak"
            if os.path.exists(path):
                shutil.copyfile(path, backup_path)

            # Atomic write procedure
            temp_path = f"{path}.tmp"
            with open(temp_path, 'w') as f:
                json.dump(self.plans, f, indent=2)
            
            os.replace(temp_path, path)
            logger.info(f"Plans saved to {path}")

        except Exception as e:
            logger.error(f"Plan persistence failed: {e}")
            # Attempt to restore backup
            if os.path.exists(backup_path):
                shutil.copyfile(backup_path, path)
            raise