# logger.py
import logging
from pathlib import Path

def setup_logger(debug=False):
    """Configure logger with optional debug mode"""
    level = logging.DEBUG if debug else logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def redact_sensitive(text: str) -> str:
    if not text:
        return text
        
    # Redact standalone tokens (like refresh tokens)
    if len(text) in range(20, 100):  # Typical token length range
        if text.isalnum() or '-' in text or '_' in text:
            return f"{text[:4]}...{text[-4:]}"  # Show first/last 4 chars
    
    # Redact tokens in key=value pairs
    sensitive_keys = ['token=', 'apikey=', 'password=', 'secret=', 'refresh_token=']
    for key in sensitive_keys:
        if key in text.lower():
            start = text.lower().find(key) + len(key)
            text = text[:start] + 'REDACTED' + text[start+20:]
    return text

# Initialize with debug=False by default
logger = setup_logger()