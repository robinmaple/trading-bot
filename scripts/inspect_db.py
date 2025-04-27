# inspect_db.py
from core.storage.db import TradingDB
from core.logger import logger
import pandas as pd

def inspect_database():
    """Query and display all trading database tables"""
    db = TradingDB()
    
    with db._get_conn() as conn:
        # Get all table names
        tables = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            AND name NOT LIKE 'sqlite_%'
        """).fetchall()
        
        results = {}
        for table in tables:
            table_name = table['name']
            data = conn.execute(f"SELECT * FROM {table_name}").fetchall()
            columns = [desc[0] for desc in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
            
            # Convert to pandas DataFrame for pretty printing
            df = pd.DataFrame(data, columns=columns)
            results[table_name] = df
            
            print(f"\n{table_name.upper()} ({len(df)} rows)")
            print(df.head(3))  # Show first 3 rows
    
    return results

if __name__ == "__main__":
    inspect_database()