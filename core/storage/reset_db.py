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
        # Setup directory structure
        Path('data').mkdir(exist_ok=True)
        
        # Remove existing database if it exists
        if Path(db_path).exists():
            try:
                os.remove(db_path)
                logger.info("Removed existing database")
            except Exception as e:
                logger.error(f"Error removing old database: {e}")
                return False
        
        # Initialize new database
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            
            # Load schema in single transaction
            try:
                with open(schema_path) as f:
                    schema_sql = f.read()
                conn.executescript(schema_sql)
                logger.info("Database schema created successfully")
            except sqlite3.Error as e:
                logger.critical(f"Schema creation failed: {e}")
                return False
            
            # Verify tables were created
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            logger.info(f"Created {len(tables)} tables")
            
            # Load initial data (if exists)
            if init_path.exists():
                try:
                    with open(init_path) as f:
                        init_sql = f.read()
                    # Execute as script (auto-commits)
                    conn.executescript(init_sql) 
                    logger.info("Initial data loaded successfully")
                except sqlite3.Error as e:
                    logger.error(f"Initial data loading failed: {e}")
                    # Continue even if init data fails
            
            # Verify basic data integrity
            try:
                test_query = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='config'")
                if not test_query.fetchone():
                    raise ValueError("Core tables not created")
            except Exception as e:
                logger.error(f"Database verification failed: {e}")
                return False
                
        return True
        
    except Exception as e:
        logger.critical(f"Unexpected error during database reset: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting database reset process...")
    if reset_database():
        logger.info("Database reset completed successfully")
        exit(0)
    else:
        logger.error("Database reset failed")
        exit(1)