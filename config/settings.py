import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# API Settings
QUESTRADE_TOKEN_URL = "https://login.questrade.com/oauth2/token"
API_BASE_ENDPOINT = "{server}v1/"  # {server} will be replaced