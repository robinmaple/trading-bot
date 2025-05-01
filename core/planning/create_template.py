# create_template.py
import argparse
from core.planning.template_builder import TradingPlanTemplate

def main():
    parser = argparse.ArgumentParser(description='Generate trading plan template')
    parser.add_argument('--accounts', nargs='+', required=True,
                        help='List of account IDs to include as sheets')
    args = parser.parse_args()
    
    builder = TradingPlanTemplate()
    builder.create_template(accounts=args.accounts)

if __name__ == "__main__":
    main()