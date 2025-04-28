# core/config/constants.py
from core.config.spec import ConfigSpec

CONFIG_SPECS = {
    'dry_run': ConfigSpec(
        type=bool,
        default=False,
        description="Whether to run in test mode without real trades"
    ),
    'risk_of_capital': ConfigSpec(
        type=float,
        default=0.01,
        validator=lambda x: 0 < x <= 0.1,
        description="Max percentage of capital to risk per trade (0.01 = 1%)"
    ),
    'profit_to_loss_ratio': ConfigSpec(
        type=float,
        default=2.0,
        validator=lambda x: x >= 1.0,
        description="Minimum profit target as multiple of risk"
    ),
    'available_quantity_ratio': ConfigSpec(
        type=float,
        default=0.8,
        validator=lambda x: 0 < x <= 1.0,
        description="Max percentage of calculated position size to take"
    ),
    'daily_loss_limit_percent': ConfigSpec(
        type=float,
        default=2.0,
        validator=lambda x: 0 < x <= 5.0,
        description="Max daily loss before pausing trades (%)"
    ),
    'weekly_loss_limit_percent': ConfigSpec(
        type=float,
        default=5.0,
        validator=lambda x: 0 < x <= 10.0,
        description="Max weekly loss before pausing trades (%)"
    ),
    'monthly_loss_limit_percent': ConfigSpec(
        type=float,
        default=10.0,
        validator=lambda x: 0 < x <= 20.0,
        description="Max monthly loss before pausing trades (%)"
    ),
    'close_trades_buffer_minutes': ConfigSpec(
        type=int,
        default=5,
        validator=lambda x: 1 <= x <= 30,
        description="Minutes before market close to exit trades"
    )
}