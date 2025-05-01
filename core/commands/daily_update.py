#!/usr/bin/env python3
"""
Robust daily update script with:
- Proper IBKR initialization
- Volume filtering without local storage
- Error handling
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
from core.logger import logger
from core.storage.db import TradingDB
from core.pricing.service import MultiProviderPriceService
from core.brokerages.questrade.client import QuestradeClient
from core.brokerages.ibkr.client import IBKRClient
from core.brokerages.ibkr.auth import IBKRAuth
import pandas as pd

class DataManager:
    def __init__(self):
        """Initialize with proper error handling"""
        self.db = TradingDB()
        self.price_service = self._init_price_service()
        self.data_dir = Path("data/historical")
        self.log_dir = Path("data/logs")
        self.min_volume = 1_000_000  # Volume threshold
        
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)

    def _init_price_service(self) -> MultiProviderPriceService:
        """Initialize providers with proper error handling"""
        providers = []
        
        try:
            providers.append(QuestradeClient(self.db))
            logger.info("Questrade initialized")
        except Exception as e:
            logger.warning(f"Questrade init failed: {str(e)}")
                

        try:
            # Initialize with explicit parameters
            ibkr_auth = IBKRAuth(
                db=self.db,
                brokerage_name='IBKR',
                token_url='your_token_url',  # Or load from config
                client_id='your_client_id',
                client_secret='your_client_secret',
                api_server='your_api_server'
            )
            providers.append(IBKRClient(ibkr_auth))
            logger.info("IBKR initialized")
        except Exception as e:
            logger.warning(f"IBKR init failed: {str(e)}")

        if not providers:
            raise RuntimeError("No working price providers")
        return MultiProviderPriceService(providers)

    async def run(self, full_refresh: bool = False):
        """Main execution flow"""
        try:
            symbols = await self._get_active_symbols()
            logger.info(f"Processing {len(symbols)} active symbols")
            
            if full_refresh:
                await self._bulk_download(symbols)
            else:
                await self._incremental_update(symbols)
        except Exception as e:
            logger.critical(f"Update failed: {str(e)}")
            raise

    async def _get_active_symbols(self) -> List[str]:
        """Get active symbols from database"""
        with self.db._get_conn() as conn:
            result = conn.execute("""
                SELECT symbol FROM symbols 
                WHERE is_active = 1
                AND (country = 'US' OR country = 'CA')
            """).fetchall()
        return [row['symbol'] for row in result]

    async def _get_high_volume_symbols(self) -> List[str]:
        """Real-time volume check without local storage"""
        active_symbols = await self._get_active_symbols()
        high_volume = []
        
        for symbol in active_symbols:
            try:
                # Get last trading day's volume
                latest = await self.price_service.get_historical(
                    symbol,
                    start=datetime.now() - timedelta(days=5),  # 5-day window
                    end=datetime.now() - timedelta(days=1),
                    interval='1d',
                    limit=1
                )
                
                if latest and latest[0]['volume'] >= self.min_volume:
                    high_volume.append(symbol)
                
                await asyncio.sleep(0.5)  # Rate limit
                
            except Exception as e:
                logger.warning(f"Volume check failed for {symbol}: {str(e)}")
                continue
        
        return high_volume

    async def _bulk_download(self, symbols: List[str]):
        """Initial download with throttling"""
        batch_size = 50
        delay = 60
        
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(symbols)//batch_size)+1}")
            
            tasks = [self._process_symbol(s, full_refresh=True) for s in batch]
            await asyncio.gather(*tasks)
            
            if i + batch_size < len(symbols):
                await asyncio.sleep(delay)

    async def _incremental_update(self, symbols: List[str]):
        """Daily update with volume filter"""
        high_volume = await self._get_high_volume_symbols()
        logger.info(f"Found {len(high_volume)} high-volume symbols")
        
        for symbol in high_volume:
            await self._process_symbol(symbol)
            await asyncio.sleep(1)  # Gentle rate limiting

    async def _process_symbol(self, symbol: str, full_refresh: bool = False):
        """Process single symbol's data"""
        try:
            country = 'US' if '.' not in symbol else 'CA'
            file_path = self.data_dir / country / f"{symbol.split('.')[0]}.xlsx"
            
            # Determine date range
            if full_refresh or not file_path.exists():
                start_date = datetime(1980, 1, 1)
            else:
                start_date = self._get_last_recorded_date(file_path) + timedelta(days=1)
            
            end_date = datetime.now() - timedelta(days=1)
            
            if start_date > end_date:
                return  # Already up to date
            
            # Download and save data
            data = await self._fetch_data(symbol, start_date, end_date)
            if not data.empty:
                self._save_data(file_path, data)

        except Exception as e:
            logger.error(f"Failed processing {symbol}: {str(e)}")

    async def _fetch_data(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Fetch data with error handling"""
        data = []
        current = start
        
        while current <= end:
            try:    
                daily = await self.price_service.get_historical(
                    symbol,
                    start=current,
                    end=current,
                    interval='1d'
                )
                if daily:
                    data.append({
                        'date': current,
                        'open': daily['open'],
                        'high': daily['high'],
                        'low': daily['low'],
                        'close': daily['close'],
                        'volume': daily['volume']
                    })
                current += timedelta(days=1)
                await asyncio.sleep(0.1)  # Rate limit
            except Exception as e:
                logger.warning(f"Failed {symbol} for {current}: {str(e)}")
                continue
        
        return pd.DataFrame(data)

    def _get_last_recorded_date(self, file_path: Path) -> datetime:
        """Get latest date from existing data"""
        try:
            if file_path.exists():
                df = pd.read_excel(file_path)
                return pd.to_datetime(df['date'].max()).to_pydatetime()
        except Exception as e:
            logger.warning(f"Error reading {file_path}: {str(e)}")
        return datetime(1980, 1, 1)

    def _save_data(self, file_path: Path, new_data: pd.DataFrame):
        """Save data with proper merging"""
        try:
            if file_path.exists():
                existing = pd.read_excel(file_path)
                combined = pd.concat([existing, new_data]).drop_duplicates('date')
            else:
                combined = new_data
            combined.to_excel(file_path, index=False)
        except Exception as e:
            logger.error(f"Failed to save {file_path}: {str(e)}")
            raise

async def main():
    """Command-line entry point"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true', help='Full refresh')
    args = parser.parse_args()
    
    try:
        manager = DataManager()
        await manager.run(full_refresh=args.full)
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())