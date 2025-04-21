import json
from pathlib import Path
from typing import Dict, List, Union
from core.logger import logger

class TradingPlan:
    def __init__(self, plans: Union[Dict[str, dict], List[dict]]):
        # Convert list to dict keyed by symbol if needed
        if isinstance(plans, list):
            self.plans = {plan['symbol']: plan for plan in plans}
        else:
            self.plans = plans
            
        # Initialize all plans as active if not specified
        for symbol, plan in self.plans.items():
            plan.setdefault('active', True)
        
    @classmethod
    def load_from_file(cls, path: str):
        """Load plans from JSON file, handling both list and dict formats"""
        try:
            with open(path) as f:
                plans = json.load(f)
                
            if not isinstance(plans, (dict, list)):
                raise ValueError("Trading plan should be a list or dictionary")
                
            return cls(plans)
            
        except Exception as e:
            logger.error(f"Failed to load trading plans: {e}")
            raise

    def get_active_plans(self) -> Dict[str, dict]:
        """Get all active trading plans"""
        return {
            symbol: plan 
            for symbol, plan in self.plans.items()
            if plan.get('active', True)
        }

    def mark_executed(self, symbol: str):
        """Mark a plan as completed"""
        if symbol in self.plans:
            self.plans[symbol]['active'] = False
            logger.info(f"Marked plan for {symbol} as executed")