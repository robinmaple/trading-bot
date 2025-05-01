# core/planning/plan_uploader.py
import json
import sqlite3
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from core.storage.db import TradingDB
from core.logger import logger

class PlanUploader:
    def __init__(self, db: TradingDB):
        """Initialize with database connection"""
        self.db = db
        self.upload_dir = Path("plans/uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _validate_plan_dataframe(self, df: pd.DataFrame) -> bool:
        """Validate Excel file structure"""
        required_cols = {
            "Symbol",
            "Entry Price",
            "Stop Loss",
            "Risk Per Trade",
            "Profit/Loss Ratio",
            "Available Qty Ratio"
        }
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"Missing required columns: {', '.join(missing)}")
        return True


    def _process_excel_file(self, file_path: Path, sheet_name: str) -> list:
        """Read Excel file and return list of trade dicts with proper date handling"""
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            trades = []
            for _, row in df.iterrows():
                # Handle expiry date conversion
                expiry_date = row.get('Expiry Date')
                if pd.isna(expiry_date):
                    expiry_date_str = None
                elif isinstance(expiry_date, pd.Timestamp):
                    expiry_date_str = expiry_date.strftime('%Y-%m-%d')
                else:
                    try:
                        # Try parsing string dates
                        expiry_date_str = str(expiry_date).strip()
                        if expiry_date_str:  # Validate format if not empty
                            datetime.strptime(expiry_date_str, '%Y-%m-%d')
                    except ValueError:
                        logger.warning(f"Invalid date format: {expiry_date}, using None")
                        expiry_date_str = None

                trade = {
                    'symbol': str(row['Symbol']).strip(),
                    'entry_price': float(row['Entry Price']),
                    'stop_loss_price': float(row['Stop Loss']),
                    'risk_per_trade': float(row.get('Risk Per Trade', 0.005)),
                    'profit_to_loss_ratio': float(row.get('Profit/Loss Ratio', 2.0)),
                    'available_quantity_ratio': float(row.get('Available Qty Ratio', 0.8)),
                    'expiry_date': expiry_date_str
                }
                trades.append(trade)
            return trades
            
        except Exception as e:
            logger.error(f"Excel processing failed: {str(e)}", exc_info=True)
            raise ValueError(f"Invalid Excel data: {str(e)}")
        
    def upload_plans_from_file(self, file_path: str, account_id: str, user_id: str = None) -> dict:
        """Upload plans by first creating a plan header then adding trades"""
        try:
            self._deactivate_previous_plans(account_id)
            path = Path(file_path)
            if not path.exists():
                raise ValueError(f"File not found: {file_path}")

            # Create a new plan first
            with self.db._get_conn() as conn:
                cursor = conn.execute("""
                    INSERT INTO plans (
                        account_id,
                        upload_time,
                        status
                    ) VALUES (?, ?, ?)
                """, (
                    account_id,
                    datetime.now().isoformat(),
                    'active'
                ))
                plan_id = cursor.lastrowid
                conn.commit()

            # Process trades and associate with this plan
            trades = self._process_excel_file(path, account_id)
            results = {
                'success': 0,
                'failed': 0,
                'trade_ids': []
            }

            for trade in trades:
                try:
                    trade_id = self._upload_trade_to_plan(
                        plan_id=plan_id,
                        trade_data=trade,
                        user_id=user_id
                    )
                    results['success'] += 1
                    results['trade_ids'].append(trade_id)
                except Exception as e:
                    logger.error(f"Failed to upload trade: {str(e)}")
                    results['failed'] += 1

            self._archive_uploaded_file(path, account_id)

            return {
                'status': 'completed',
                'plan_id': plan_id,
                'message': f"Created plan {plan_id} with {results['success']} trades",
                'trade_ids': results['trade_ids']
            }

        except Exception as e:
            logger.critical(f"Plan upload failed: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'plan_id': None,
                'trade_ids': []
            }
    
    def upload_plan(self, account_id: str, plan_data: dict, user_id: str = None) -> dict:
        """Upload single plan to database with enhanced validation"""
        try:
            # Ensure plan_data is not None and is a dictionary
            if not plan_data or not isinstance(plan_data, dict):
                raise ValueError("Invalid plan data format")

            # Required fields with validation
            required_fields = {
                'symbol': (str, lambda x: x and x.strip()),
                'entry_price': (float, lambda x: x > 0),
                'stop_loss_price': (float, lambda x: x > 0),
                'risk_per_trade': (float, lambda x: 0.001 <= x <= 0.1),
                'profit_to_loss_ratio': (float, lambda x: 1.0 <= x <= 10.0),
                'available_quantity_ratio': (float, lambda x: 0.1 <= x <= 1.0)
            }

            # Validate and convert fields
            validated = {}
            for field, (field_type, validator) in required_fields.items():
                value = plan_data.get(field)
                if value is None:
                    raise ValueError(f"Missing required field: {field}")
                
                try:
                    converted = field_type(value)
                    if not validator(converted):
                        raise ValueError(f"Invalid value for {field}: {value}")
                    validated[field] = converted
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid {field}: {str(e)}")

            # Additional validations
            if validated['entry_price'] <= validated['stop_loss_price']:
                raise ValueError("Entry price must be greater than stop loss")

            # Handle expiry date (optional field)
            expiry_date = plan_data.get('expiry_date')
            if expiry_date:
                try:
                    if isinstance(expiry_date, pd.Timestamp):
                        expiry_date = expiry_date.strftime('%Y-%m-%d')
                    validated['expiry_date'] = str(expiry_date)
                except Exception as e:
                    raise ValueError(f"Invalid expiry date: {str(e)}")
            else:
                validated['expiry_date'] = None

            # Database operations
            with self.db._get_conn() as conn:
                try:
                    cursor = conn.execute("""
                        INSERT INTO planned_trades (
                            account_id, symbol, entry_price, stop_loss_price,
                            expiry_date, risk_per_trade, profit_to_loss_ratio,
                            available_quantity_ratio, created_by, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        account_id,
                        validated['symbol'],
                        validated['entry_price'],
                        validated['stop_loss_price'],
                        validated['expiry_date'],
                        validated['risk_per_trade'],
                        validated['profit_to_loss_ratio'],
                        validated['available_quantity_ratio'],
                        user_id or 'system',
                        datetime.now().isoformat()
                    ))

                    plan_id = cursor.lastrowid
                    conn.commit()
                    
                    logger.info(f"Successfully uploaded plan for {validated['symbol']} (ID: {plan_id})")
                    return {
                        'success': True,
                        'plan_id': plan_id,
                        'message': 'Plan uploaded successfully'
                    }

                except sqlite3.Error as e:
                    conn.rollback()
                    logger.error(f"Database error uploading plan: {str(e)}")
                    raise ValueError(f"Database error: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to upload plan: {str(e)}")
            return {
                'success': False,
                'message': str(e),
                'plan_id': None
            }
        
    def _upload_trade_to_plan(self, plan_id: int, trade_data: dict, user_id: str = None) -> int:
        """Upload single trade to an existing plan with proper validation"""
        # Define validation rules
        required_fields = {
            'symbol': {
                'type': str,
                'validate': lambda x: bool(x.strip()) if x else False,
                'error': "Symbol cannot be empty"
            },
            'entry_price': {
                'type': float,
                'validate': lambda x: x > 0,
                'error': "Entry price must be positive"
            },
            'stop_loss_price': {
                'type': float,
                'validate': lambda x: x > 0,
                'error': "Stop loss must be positive"
            },
            'risk_per_trade': {
                'type': float,
                'default': 0.005,
                'validate': lambda x: 0.0005 <= x <= 0.1,
                'error': "Risk must be between 0.1% and 10%"
            },
            'profit_to_loss_ratio': {
                'type': float,
                'default': 2.0,
                'validate': lambda x: x >= 1.0,
                'error': "Profit/Loss ratio must be >= 1.0"
            },
            'available_quantity_ratio': {
                'type': float,
                'default': 0.8,
                'validate': lambda x: 0.1 <= x <= 1.0,
                'error': "Available quantity must be between 10% and 100%"
            }
        }

        # Validate and prepare data
        validated = {}
        errors = []
        
        for field, rules in required_fields.items():
            try:
                value = trade_data.get(field, rules.get('default'))
                if value is None:
                    raise ValueError(f"Missing required field: {field}")
                    
                # Type conversion
                converted = rules['type'](value)
                
                # Validation
                if not rules['validate'](converted):
                    raise ValueError(rules['error'])
                    
                validated[field] = converted
                
            except (ValueError, TypeError) as e:
                errors.append(str(e))

        # Additional business logic validation
        try:
            if validated['entry_price'] <= validated['stop_loss_price']:
                errors.append("Entry price must be greater than stop loss")
        except KeyError:
            pass  # Already caught by previous validation

        if errors:
            raise ValueError(" | ".join(errors))

        # Handle expiry date (optional field)
        expiry_date = None
        if 'expiry_date' in trade_data and trade_data['expiry_date']:
            try:
                if isinstance(trade_data['expiry_date'], pd.Timestamp):
                    expiry_date = trade_data['expiry_date'].strftime('%Y-%m-%d')
                else:
                    expiry_date = str(trade_data['expiry_date'])
            except Exception as e:
                logger.warning(f"Invalid expiry date format: {str(e)}")

        # Database operation
        with self.db._get_conn() as conn:
            try:
                cursor = conn.execute("""
                    INSERT INTO planned_trades (
                        plan_id,
                        symbol,
                        entry_price,
                        stop_loss_price,
                        expiry_date,
                        risk_per_trade,
                        profit_to_loss_ratio,
                        available_quantity_ratio
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    plan_id,
                    validated['symbol'],
                    validated['entry_price'],
                    validated['stop_loss_price'],
                    expiry_date,
                    validated['risk_per_trade'],
                    validated['profit_to_loss_ratio'],
                    validated['available_quantity_ratio']
                ))
                trade_id = cursor.lastrowid
                conn.commit()
                return trade_id

            except sqlite3.Error as e:
                conn.rollback()
                logger.error(f"Database error inserting trade: {str(e)}")
                raise ValueError(f"Database error: {str(e)}")

    # Add this new method to the PlanUploader class
    def _deactivate_previous_plans(self, account_id: str) -> None:
        """Mark all active plans for this account as inactive (ADDED FEATURE)"""
        with self.db._get_conn() as conn:
            conn.execute("""
                UPDATE plans 
                SET status = 'canceled'
                WHERE account_id = ?
                AND status = 'active'
            """, (account_id,))
            conn.commit()

    # Add to PlanUploader class
    def _archive_uploaded_file(self, original_path: Path, account_id: str) -> None:
        """Archive uploaded file with timestamp and account ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{timestamp}_{original_path.stem}_{account_id}{original_path.suffix}"
        archive_path = self.upload_dir / archive_name
        
        try:
            original_path.rename(archive_path)
            logger.info(f"Archived plan file to: {archive_path}")
        except Exception as e:
            logger.error(f"Failed to archive file: {str(e)}")
            # Fallback to copy if rename fails
            try:
                import shutil
                shutil.copy2(original_path, archive_path)
                original_path.unlink()
            except Exception as e:
                logger.error(f"Failed to copy archive file: {str(e)}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Upload trading plan from Excel file')
    parser.add_argument('--file', required=True, help='Path to Excel plan file')
    parser.add_argument('--account', required=True, help='Account ID to process')
    parser.add_argument('--user', help='User ID for audit tracking')
    
    args = parser.parse_args()
    
    try:
        db = TradingDB()
        uploader = PlanUploader(db)
        
        result = uploader.upload_plans_from_file(
            file_path=args.file,
            account_id=args.account,
            user_id=args.user
        )
        
        print("\nUpload Results:")
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")
        print(f"Plans Uploaded: {result['trades_processed']}")
        print(f"Plan IDs: {', '.join(map(str, result['plan_ids'])) if result['plan_ids'] else 'None'}")
        
        if result['status'] == 'error':
            sys.exit(1)
            
    except Exception as e:
        print(f"Critical error: {str(e)}")
        sys.exit(1)