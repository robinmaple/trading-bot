# core/storage/reset_db.py
import os
import sqlite3
from pathlib import Path
from core.logger import logger

def reset_database():
    db_path = 'data/trading.db'
    schema_path = Path(__file__).parent / 'schema.sql'
    init_path = Path(__file__).parent / 'init_data.sql'
    
    try:
        # Remove existing database
        if Path(db_path).exists():
            os.remove(db_path)
            logger.info("Removed existing database")
        
        # Create new database
        with sqlite3.connect(db_path) as conn:
            # Create schema
            with open(schema_path) as f:
                conn.executescript(f.read())
            logger.info("Database schema created")
            
            # Insert initial data
            if init_path.exists():
                with open(init_path) as f:
                    conn.executescript(f.read())
                logger.info("Initial data loaded")
            
        return True
        
    except Exception as e:
        logger.critical(f"Database reset failed: {str(e)}")
        return False

if __name__ == "__main__":
    if reset_database():
        logger.info("Database reset completed successfully")
        
        # Verify the database
        from scripts.verify_db import verify_database
        verify_database()
        exit(0)
    else:
        logger.error("Database reset failed")
        exit(1)