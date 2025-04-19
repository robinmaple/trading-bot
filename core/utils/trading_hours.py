from datetime import datetime, time, timedelta
import pytz
from typing import List, Tuple, Union
from config.env import TRADING_HOURS
from core.logger import logger

class TradingHours:
    def __init__(self):
        self.tz = pytz.timezone('US/Eastern')
        self.time_ranges = self._load_time_ranges()
    
    def _parse_time(self, time_str: str) -> time:
        """Convert 'HH:MM' string to time object"""
        hours, minutes = map(int, time_str.split(':'))
        return time(hours, minutes)

    def _load_time_ranges(self) -> List[Tuple[time, time]]:
        """Convert already-parsed trading hour strings into time objects"""
        try:
            logger.info(f"TRADING_HOURS from env: {TRADING_HOURS} ({type(TRADING_HOURS)})")

            # At this point, TRADING_HOURS is a list of (str, str)
            result = []
            for start_str, end_str in TRADING_HOURS:
                logger.debug(f"Parsing start='{start_str}' end='{end_str}'")
                start = self._parse_time(start_str)
                end = self._parse_time(end_str)
                result.append((start, end))

            logger.info(f"Final parsed time ranges: {result}")
            return result

        except Exception as e:
            logger.warning(f"Failed to parse TRADING_HOURS (using fallback): {e}")
            return [(time(9, 30), time(16, 0))]  # Fallback to NYSE hours

    def is_market_open(self) -> bool:
        """Check if current time falls within any trading range"""
        now = datetime.now(self.tz).time()
        return any(start <= now < end for start, end in self.time_ranges)
    
    def get_current_session(self) -> Union[Tuple[time, time], None]:
        """Get the current active trading session range"""
        now = datetime.now(self.tz).time()
        for session in self.time_ranges:
            if session[0] <= now < session[1]:
                return session
        return None
    
    def time_until_next_session(self) -> float:
        """Minutes until next trading session starts"""
        now = datetime.now(self.tz)
        current_time = now.time()
        
        for start, _ in self.time_ranges:
            if current_time < start:
                next_open = datetime.combine(now.date(), start)
                return (next_open - now).total_seconds() / 60
        
        # If no more sessions today, use first session tomorrow
        next_day = now.date() + timedelta(days=1)
        next_open = datetime.combine(next_day, self.time_ranges[0][0])
        return (next_open - now).total_seconds() / 60