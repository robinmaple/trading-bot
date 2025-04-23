import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "broker_config.yaml"

def load_broker_config(broker_name: str) -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f).get(broker_name, {})
    except FileNotFoundError:
        return {}
