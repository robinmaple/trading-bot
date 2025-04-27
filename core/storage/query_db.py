# core/storage/query_db.py

import sqlite3
import sys
from tabulate import tabulate  # nice table output

DB_PATH = 'data/trading.db'

def run_query(query):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query)
        conn.commit()
        rows = cursor.fetchall()
        
        if rows:
            print(tabulate([dict(row) for row in rows], headers="keys", tablefmt="psql"))
        else:
            print("Query executed successfully, but no rows returned.")

    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python query_db.py \"SELECT * FROM config;\"")
    else:
        query = sys.argv[1]
        run_query(query)
