# core/config/constants.py
from core.config.spec import ConfigSpec

CONFIG_SPECS = {
    'dry_run': ConfigSpec(
        type=bool,
        default=False,
        description="Whether to run in test mode without real trades"
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