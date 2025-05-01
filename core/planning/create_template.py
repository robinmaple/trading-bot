# core/planning/create_template.py
import argparse
from core.planning.template_builder import TradingPlanTemplate

def main():
    parser = argparse.ArgumentParser(description='Generate trading plan template with risk parameters')
    parser.add_argument('--accounts', nargs='+', required=True,
                       help='List of account IDs to include as sheets')
    parser.add_argument('--example', action='store_true',
                       help='Generate example template instead')
    args = parser.parse_args()
    
    builder = TradingPlanTemplate()
    
    if args.example:
        builder.create_example_template()
        print("Example template generated with sample risk parameters")
    else:
        builder.create_template(accounts=args.accounts)
        print(f"Template generated for accounts: {', '.join(args.accounts)}")

if __name__ == "__main__":
    main()