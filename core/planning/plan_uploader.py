# core/planning/plan_uploader.py
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict
from core.storage.db import TradingDB
from core.logger import logger

class PlanUploader:
    def __init__(self, db: TradingDB):
        """Initialize with database connection"""
        self.db = db
        self.upload_dir = Path("plans/uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _validate_plan(self, df: pd.DataFrame) -> bool:
        """Validate plan structure"""
        required_cols = {"Symbol", "Entry Price", "Stop Loss"}
        return required_cols.issubset(df.columns)

    # core/planning/plan_uploader.py (with comprehensive logging)

    def upload_plan(self, file_path: Path, account_id: str) -> Dict:
        """Process uploaded trading plan with proper SQL syntax"""
        try:
            logger.info(f"Starting plan upload for account {account_id}")
            
            # Verify and archive file
            if not file_path.exists():
                raise FileNotFoundError(f"Plan file not found at {file_path}")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_path = self.upload_dir / f"{timestamp}_trading_plan_{account_id}.xlsx"
            file_path.rename(archive_path)
            logger.info(f"Archived plan to {archive_path}")
            
            # Read and validate data
            logger.info(f"Reading sheet '{account_id}' from Excel file")
            df = pd.read_excel(archive_path, sheet_name=account_id)
            df = df.where(pd.notnull(df), None)
            logger.debug(f"Raw data:\n{df.to_string()}")
            
            if not self._validate_plan(df):
                logger.error("Validation failed - missing required columns")
                raise ValueError("Invalid plan format")
            logger.info("Plan validation passed")
            
            with self.db._get_conn() as conn:
                # Find existing active plan
                logger.info("Checking for existing active plan...")
                existing_plan = conn.execute("""
                    SELECT plan_id FROM plans 
                    WHERE account_id = ? 
                    AND status = 'active'
                    AND expiry_time >= date('now')
                """, (str(account_id),)).fetchone()
                
                if existing_plan:
                    plan_id = existing_plan['plan_id']
                    action = "updated"
                    logger.info(f"Found active plan {plan_id}, will update trades")
                else:
                    max_expiry = str(df['Expiry Date'].max()) if 'Expiry Date' in df.columns else None
                    logger.info(f"Creating new plan with expiry {max_expiry}")
                    cursor = conn.execute("""
                        INSERT INTO plans (account_id, status, expiry_time)
                        VALUES (?, 'active', ?)
                        RETURNING plan_id
                    """, (str(account_id), max_expiry))
                    plan_id = cursor.fetchone()['plan_id']
                    action = "created"
                    logger.info(f"Created new plan {plan_id}")
                
                # Process trades
                trades_processed = 0
                for _, row in df.iterrows():
                    try:
                        symbol = str(row['Symbol'])
                        logger.info(f"Processing {symbol}...")
                        
                        trade_data = {
                            'symbol': symbol,
                            'entry': float(row['Entry Price']),
                            'stop': float(row['Stop Loss']),
                            'take_profit': float(row['Take Profit']) if pd.notna(row.get('Take Profit')) else None,
                            'quantity': int(row['Quantity']) if pd.notna(row.get('Quantity')) else None,
                            'expiry': str(row['Expiry Date']) if pd.notna(row.get('Expiry Date')) else None
                        }
                        logger.debug(f"Trade data: {trade_data}")
                        
                        if existing_plan:
                            existing_trade = conn.execute("""
                                SELECT trade_id FROM planned_trades
                                WHERE plan_id = ? AND symbol = ?
                            """, (plan_id, symbol)).fetchone()
                            
                            if existing_trade:
                                logger.info(f"Updating existing trade {existing_trade['trade_id']}")
                                conn.execute("""
                                    UPDATE planned_trades 
                                    SET entry_price = ?,
                                        stop_loss_price = ?,
                                        take_profit_price = ?,
                                        quantity = ?,
                                        expiry_date = ?,
                                        status = 'pending'
                                    WHERE trade_id = ?
                                """, (
                                    trade_data['entry'],
                                    trade_data['stop'],
                                    trade_data['take_profit'],
                                    trade_data['quantity'],
                                    trade_data['expiry'],
                                    existing_trade['trade_id']
                                ))
                            else:
                                logger.info("Inserting new trade for existing plan")
                                conn.execute("""
                                    INSERT INTO planned_trades (
                                        plan_id, symbol, entry_price, 
                                        stop_loss_price, take_profit_price, 
                                        quantity, expiry_date, status
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                                """, (
                                    plan_id,
                                    symbol,
                                    trade_data['entry'],
                                    trade_data['stop'],
                                    trade_data['take_profit'],
                                    trade_data['quantity'],
                                    trade_data['expiry']
                                ))
                        else:
                            logger.info("Inserting trade for new plan")
                            conn.execute("""
                                INSERT INTO planned_trades (
                                    plan_id, symbol, entry_price, 
                                    stop_loss_price, take_profit_price, 
                                    quantity, expiry_date, status
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                            """, (
                                plan_id,
                                symbol,
                                trade_data['entry'],
                                trade_data['stop'],
                                trade_data['take_profit'],
                                trade_data['quantity'],
                                trade_data['expiry']
                            ))
                        
                        trades_processed += 1
                        logger.info(f"Successfully processed {symbol}")
                        
                    except Exception as trade_error:
                        logger.error(f"Failed to process {symbol}", exc_info=True)
                        continue
                
                logger.info(f"Completed processing {trades_processed} trades")
                conn.commit()
                return {
                    "status": "success",
                    "action": action,
                    "plan_id": plan_id,
                    "trades_processed": trades_processed
                }
                
        except Exception as e:
            logger.critical(f"Plan upload failed", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }

if __name__ == "__main__":
    import argparse
    from pathlib import Path
    
    parser = argparse.ArgumentParser(description='Upload trading plan')
    parser.add_argument('--file', required=True, help='Path to Excel plan file')
    parser.add_argument('--account', required=True, help='Account ID/tab name to process')
    
    args = parser.parse_args()
    
    try:
        db = TradingDB()
        uploader = PlanUploader(db)
        result = uploader.upload_plan(Path(args.file), args.account)
        
        print("Upload Result:")
        print(f"Status: {result['status']}")
        print(f"Action: {result.get('action', 'N/A')}")
        print(f"Plan ID: {result.get('plan_id', 'N/A')}")
        print(f"Trades Processed: {result.get('trades_processed', 0)}")
        if result['status'] == 'error':
            print(f"Error: {result['message']}")
    except Exception as e:
        print(f"Critical error: {str(e)}")