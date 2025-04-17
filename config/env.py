# config/env.py
import os

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
RISK_OF_CAPITAL = float(os.getenv("RISK_OF_CAPITAL", "1"))
PROFIT_TO_LOSS_RATIO = float(os.getenv("PROFIT_TO_LOSS_RATIO", "2"))
AVAILABLE_QUANTITY_RATIO = float(os.getenv("AVAILABLE_QUANTITY_RATIO", "0.5"))
