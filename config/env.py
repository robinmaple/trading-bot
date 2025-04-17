# config/env.py
import os

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
RISK_OF_CAPITAL = float(os.getenv("RISK_OF_CAPITAL", "100"))
PROFIT_TO_LOSS_RATIO = float(os.getenv("PROFIT_TO_LOSS_RATIO", "2"))
