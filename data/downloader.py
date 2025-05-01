import asyncio
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
from core.pricing.service import MultiProviderPriceService
from core.logger import logger
from core.storage.db import TradingDB

class HistoricalDataDownloader:
    def __init__(self, price_service: MultiProviderPriceService):
        self.price_service = price_service
        self.data_dir = Path("data/historical")
        self.log_file = Path("data/logs/download_history.csv")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(exist_ok=True)

    async def download_all_symbols(self):
        """Download data for all active symbols"""
        symbols = self._get_active_symbols()
        for symbol in symbols:
            await self._download_symbol_data(symbol)

    def _get_active_symbols(self) -> list:
        """Get active US/Canadian symbols from database"""
        with TradingDB()._get_conn() as conn:
            us_symbols = conn.execute("""
                SELECT symbol FROM symbols 
                WHERE country = 'US' AND is_active = 1
            """).fetchall()
            ca_symbols = conn.execute("""
                SELECT symbol FROM symbols 
                WHERE country = 'CA' AND is_active = 1
            """).fetchall()
        return [s['symbol'] for s in us_symbols + ca_symbols]

    async def _download_symbol_data(self, symbol: str):
        """Download and append historical data for a single symbol"""
        country = 'US' if '.' not in symbol else 'CA'
        file_path = self.data_dir / country / f"{symbol.split('.')[0]}.xlsx"
        
        # Get existing data
        existing_data = self._load_existing_data(file_path)
        start_date = self._get_start_date(existing_data)
        
        # Download missing data
        new_data = await self._fetch_historical_data(symbol, start_date)
        
        if not new_data.empty:
            # Merge and save
            combined = pd.concat([existing_data, new_data]).drop_duplicates()
            combined.to_excel(file_path, index=False)
            self._log_download(symbol, len(new_data))

    def _load_existing_data(self, file_path: Path) -> pd.DataFrame:
        """Load existing historical data"""
        if file_path.exists():
            df = pd.read_excel(file_path)
            df['date'] = pd.to_datetime(df['date'])
            return df
        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])

    def _get_start_date(self, df: pd.DataFrame) -> datetime:
        """Determine start date for data download"""
        if not df.empty:
            return df['date'].max() + timedelta(days=1)
        return datetime(1980, 1, 1)  # Default start date

    async def _fetch_historical_data(self, symbol: str, start_date: datetime) -> pd.DataFrame:
        """Fetch historical data from multiple providers"""
        end_date = datetime.now() - timedelta(days=1)  # Yesterday
        
        if start_date > end_date:
            return pd.DataFrame()
        
        logger.info(f"Downloading {symbol} data from {start_date.date()} to {end_date.date()}")
        
        # Initialize dataframe
        data = []
        current_date = start_date
        
        while current_date <= end_date:
            try:
                # Get daily bars using best available price
                daily_data = await self.price_service.get_historical(
                    symbol,
                    start=current_date,
                    end=current_date,
                    interval='1d'
                )
                
                if daily_data:
                    data.append({
                        'date': current_date,
                        'open': daily_data['open'],
                        'high': daily_data['high'],
                        'low': daily_data['low'],
                        'close': daily_data['close'],
                        'volume': daily_data['volume']
                    })
                
                current_date += timedelta(days=1)
                
                # Rate limit protection
                await asyncio.sleep(0.1)  # 100ms between requests
                
            except Exception as e:
                logger.error(f"Error fetching {symbol} data for {current_date}: {str(e)}")
                continue
        
        return pd.DataFrame(data)

    def _log_download(self, symbol: str, records: int):
        """Log successful downloads"""
        log_entry = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'symbol': symbol,
            'records_added': records,
            'timestamp': datetime.now().isoformat()
        }
        
        if self.log_file.exists():
            log_df = pd.read_csv(self.log_file)
            log_df = log_df.append(log_entry, ignore_index=True)
        else:
            log_df = pd.DataFrame([log_entry])
        
        log_df.to_csv(self.log_file, index=False)