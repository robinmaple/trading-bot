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

# Initialize with debug=False by default
logger = setup_logger()