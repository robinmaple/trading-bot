import argparse
from core.auth import QuestradeAuth
from core.logger import logger

def main(refresh_token):
    auth = QuestradeAuth(refresh_token)
    
    try:
        accounts = auth.get_accounts()
        for account in accounts['accounts']:
            logger.info(f"Account {account['number']}: {account['type']}")    
            # Add balance fetching logic here
    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh-token', required=True, help='Questrade refresh token')
    args = parser.parse_args()
    
    main(args.refresh_token)