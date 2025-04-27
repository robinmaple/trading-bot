# scripts/verify_db.py
import sqlite3
from core.logger import logger

def verify_database():
    try:
        with sqlite3.connect('data/trading.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check config table
            cursor.execute("SELECT key, value, description FROM config")
            configs = cursor.fetchall()
            logger.info("\nCONFIGURATION:")
            for row in configs:
                logger.info(f"{row['key']}: {row['value']} ({row['description']})")
            
            # Check brokerages
            cursor.execute("SELECT id, name, token_url, api_endpoint FROM brokerages")
            brokerages = cursor.fetchall()
            logger.info("\nBROKERAGES:")
            for row in brokerages:
                logger.info(f"{row['id']}: {row['name']}")
                logger.info(f"  Token URL: {row['token_url']}")
                logger.info(f"  API Endpoint: {row['api_endpoint']}")
            
            # Check accounts
            cursor.execute("""
                SELECT a.account_id, a.name as account_name, b.name as brokerage_name 
                FROM accounts a
                JOIN brokerages b ON a.brokerage_id = b.id
            """)
            accounts = cursor.fetchall()
            logger.info("\nACCOUNTS:")
            for row in accounts:
                logger.info(f"{row['account_id']}: {row['account_name']} ({row['brokerage_name']})")
            
            return True
            
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return False

if __name__ == "__main__":
    if verify_database():
        logger.info("Database verification successful")
        exit(0)
    else:
        logger.error("Database verification failed")
        exit(1)