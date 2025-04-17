from core.auth import QuestradeAuth
from core.api.accounts import AccountService
from core.logger import logger
from core.api.orders import OrderService
import time
import requests
from core.api.orders import BracketOrder, MockPriceService  # Ensure 'orders' is in the PYTHONPATH or the same directory

def main(refresh_token):
    # Initialize with existing auth.py
    auth = QuestradeAuth(refresh_token)
    auth.get_valid_token()
    account_service = AccountService(auth)
    accounts = account_service.get_all_accounts()
    
    try:
        # Get accounts
        for account in accounts['accounts']:
            logger.info(f"Account {account['number']} ({account['type']})")
            
            # Get balances
            balances = account_service.get_account_balances(account['number'])
            logger.info(f"Balances: {balances['perCurrencyBalances']}")
            
    except Exception as e:
        logger.error(f"Failed: {str(e)}")
        raise

    # Inside main():

    order_service = OrderService(auth)

    # Define entry parameters
    symbol_id = 9292  # Example: Questrade ID for AAPL
    entry_price = 60.00
    quantity = 1
    action = "Buy"

    first_account = accounts['accounts'][0]  # Use the first account for simplicity
    logger.info(f"Current auth token: {auth.get_valid_token()[:15]}...")  # Log first 15 chars
    logger.info(f"Monitoring account {first_account.get('number')}...")
    logger.info(f"Account type: {first_account.get('type')}")    
    
    '''
    # Monitor price until condition met
    while True:
        quote = requests.get(f"{auth.api_server}v1/markets/quotes/{symbol_id}",
                            headers={'Authorization': f'Bearer {auth.get_valid_token()}'}).json()
        current_price = quote['quotes'][0]['lastTradePrice']

        # Log all order details before submission
        logger.info(f"""Placing order with:
            Account: {first_account.get('number')}
            Symbol ID: {symbol_id}
            Price: {entry_price}
            Quantity: {quantity}
            Action: {action}""")
        
        if current_price <= entry_price:
            logger.info(f"Current price {current_price} <= {entry_price}, placing limit order...")
            result = order_service.place_limit_order(first_account.get('number'), symbol_id, entry_price, quantity, action)
            logger.info(f"Order placed: {result}")
            break

        logger.info(f"Waiting... Current price: {current_price}")
        time.sleep(10)
    '''

    bracket = BracketOrder(order_service, MockPriceService())
    bracket.place(
        symbol="AAPL",
        entry_price=170,
        stop_loss_price=168,
        account_id=account['number']
)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh-token', required=False, help='Optional: Questrade refresh token. If not provided, tokens.json will be used.')
    args = parser.parse_args()
    main(args.refresh_token)