# core/planning/template_builder.py
import pandas as pd
from pathlib import Path
import sys
from core.logger import logger

class TradingPlanTemplate:
    def __init__(self):
        self.template_dir = Path("plans/templates")
        self.template_dir.mkdir(parents=True, exist_ok=True)
        
    def create_template(self, accounts: list):
        """Generate multi-tab Excel template for given accounts"""
        try:
            template_path = self.template_dir / "trading_plan_template.xlsx"
            
            # Create empty DataFrame with required columns
            df = pd.DataFrame(columns=[
                "Symbol", 
                "Entry Price", 
                "Stop Loss", 
                "Take Profit",
                "Quantity",
                "Notes",
                "Expiry Date"
            ])
            
            # Create Excel file with one sheet per account
            with pd.ExcelWriter(template_path, engine='openpyxl') as writer:
                for account in accounts:
                    df.to_excel(
                        writer, 
                        sheet_name=str(account), 
                        index=False
                    )
            
            logger.info(f"Template created at {template_path}")
            return template_path
            
        except ImportError:
            logger.critical("Required package 'openpyxl' not installed. Run: pip install openpyxl")
            sys.exit(1)
        except Exception as e:
            logger.critical(f"Template creation failed: {str(e)}")
            sys.exit(1)