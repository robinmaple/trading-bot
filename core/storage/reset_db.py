# core/storage/reset_db.py
import sqlite3
from pathlib import Path
from core.logger import logger

def print_message(message: str):
    """Print visible message to console"""
    print(f"*** {message} ***")

def reset_database() -> bool:
    """Reset the database with proper error handling and messaging."""
    try:
        print_message("DATABASE RESET STARTED")
        logger.info("Starting database reset process...")
        db_path = Path("data/trading.db")
        schema_path = Path("core/storage/schema.sql")
        data_path = Path("core/storage/init_data.sql")
        # Remove existing database
        db_file = Path(db_path)
        if db_file.exists():
            db_file.unlink()
            print_message("Removed existing database file")
            logger.info("Removed existing database")
        
        # Create new database
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        
        # Load schema
        print_message("Creating database schema")
        with open(schema_path) as f:
            conn.executescript(f.read())
        print_message("Database schema created successfully")
        logger.info("Database schema created successfully")
        
        # Verify tables
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print_message(f"Created {len(tables)} tables")
        logger.info(f"Created {len(tables)} tables: {', '.join(tables)}")
        
        # Load initial data
        print_message("Loading initial data")
        try:
            with open(data_path) as f:
                # Print each message from the SQL script
                conn.set_trace_callback(lambda stmt: print(f"SQL: {stmt.strip()}") if "SELECT '" in stmt else None)
                conn.executescript(f.read())
            print_message("Initial data loaded successfully")
            logger.info("Initial data loaded successfully")
        except sqlite3.Error as e:
            print_message(f"DATA LOADING FAILED: {e}")
            logger.error(f"Initial data loading failed: {e}")
            conn.rollback()
            print_message("Continuing with database creation (some sample data may be missing)")
        finally:
            conn.commit()
        
        # Final verification
        print_message("Running final verification")
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master")
            print_message(f"Database contains {cursor.fetchone()[0]} objects")
            print_message("DATABASE RESET COMPLETED SUCCESSFULLY")
            return True
        except Exception as e:
            print_message(f"VERIFICATION FAILED: {e}")
            return False
        
    except Exception as e:
        print_message(f"DATABASE RESET FAILED: {e}")
        logger.error(f"Database reset failed: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    import sys    
    success = reset_database()
    sys.exit(0 if success else 1)