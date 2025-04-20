# logger.py
import logging
from pathlib import Path
from config.settings import BASE_DIR

def setup_logger(debug=False):
    """Configure logger with optional debug mode"""
    level = logging.DEBUG if debug else logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.FileHandler(BASE_DIR / 'questrade.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def redact_sensitive(text: str) -> str:
    sensitive_keys = ['token=', 'apikey=', 'password=', 'secret=']
    for key in sensitive_keys:
        if key in text.lower():
            start = text.lower().find(key) + len(key)
            # Redact the next 20 characters (adjust as needed)
            text = text[:start] + 'REDACTED' + text[start+20:]
    return text

# Initialize with debug=False by default
logger = setup_logger()