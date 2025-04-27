import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager
from core.logger import logger

class TradingDB:
    def __init__(self, db_path='data/trading.db'):
        self.db_path = db_path
        self._ensure_data_dir()
        self._init_db()
    
    def _ensure_data_dir(self):
        """Silently create data directory if needed"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        except:
            pass
        
    def _init_db(self):
        """Idempotent database initialization"""
        with self._get_conn() as conn:
            try:
                # Check if config table exists
                table_check = conn.execute("""
                    SELECT count(*) FROM sqlite_master 
                    WHERE type='table' AND name='config'
                """).fetchone()[0]
                
                if table_check == 0:
                    self._safe_execute_schema(conn)
                    logger.info("Database tables created successfully")
                else:
                    logger.debug("Database already initialized")
                    
            except Exception as e:
                logger.error(f"Database check failed: {e}")
                # Try creating tables anyway as last resort
                self._safe_execute_schema(conn)

    def _safe_execute_schema(self, conn):
        """Execute schema while ignoring comments and empty lines"""
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path) as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('--'):
                    continue
                    
                try:
                    conn.execute(line)
                except sqlite3.OperationalError as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Skipping: {line[:60]}... (Error: {str(e)[:50]})")

    @contextmanager
    def _get_conn(self):
        """Get a database connection with automatic cleanup"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            logger.critical(f"Database connection failed: {e}")
            raise
        finally:
            if conn:
                conn.close()