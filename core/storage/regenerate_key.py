# core/storage/key_management.py
from cryptography.fernet import Fernet
from core.logger import logger
from core.storage.db import TradingDB

class KeyManager:
    def __init__(self):
        self.db = TradingDB()
        
    def _get_connection(self):
        """Get database connection based on your TradingDB implementation"""
        # Choose the appropriate method for your DB class:
        if hasattr(self.db, '_get_conn'):
            return self.db._get_conn()
        elif hasattr(self.db, 'conn'):
            return self.db.conn
        else:
            raise AttributeError("TradingDB has no connection access method")

    def regenerate_key(self):
        """Generate and store a new encryption key"""
        new_key = Fernet.generate_key().decode()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO encryption_keys 
                (key_name, key_value) 
                VALUES (?, ?)
            """, ('brokerage_creds', new_key))
            conn.commit()
        
        logger.info(f"Successfully regenerated encryption key")
        return new_key

def regenerate_key_cli():
    """Command-line interface for key regeneration"""
    manager = KeyManager()
    try:
        new_key = manager.regenerate_key()
        print(f"✅ New key generated and stored:\n{new_key}")
    except Exception as e:
        logger.error(f"Key regeneration failed: {e}")
        raise

# scripts/regenerate_key.py
if __name__ == "__main__":
    regenerate_key_cli()