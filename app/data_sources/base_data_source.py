"""
Base Data Source Interface

This module defines the abstract base class for all market data sources.
All data sources must implement this interface to ensure consistency across
the application.

The interface provides:
- Historical OHLCV data fetching
- Symbol validation
- Timeframe support query

Standard Data Format:
    All data sources must return candles in this format:
    [
        {
            'timestamp': datetime,
            'open': float,
            'high': float,
            'low': float,
            'close': float,
            'volume': int
        },
        ...
    ]

Typical Usage:
    class MyDataSource(BaseDataSource):
        async def fetch_historical_data(self, symbol, start_date, end_date, timeframe):
            # Implementation here
            return candles
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime

class BaseDataSource(ABC):
    """
    Abstract base class for all market data sources.
    
    All concrete data source implementations must inherit from this class
    and implement all abstract methods to ensure compatibility with the
    backtesting and screening engines.
    """
    
    @abstractmethod
    async def fetch_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str
    ) -> List[Dict]:
        """
        Fetch historical OHLCV data for a given symbol and time range.
        
        Args:
            symbol: Ticker symbol (e.g., 'AAPL', 'MSFT')
            start_date: Start of historical data range
            end_date: End of historical data range
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
        
        Returns:
            List of candles in chronological order, where each candle is:
            {
                'timestamp': datetime,  # Candle start time
                'open': float,          # Opening price
                'high': float,          # Highest price
                'low': float,           # Lowest price
                'close': float,         # Closing price
                'volume': int           # Trading volume
            }
        
        Raises:
            ValueError: If timeframe is not supported
            Exception: If data fetch fails
        """
        pass
    
    @abstractmethod
    async def validate_symbol(self, symbol: str) -> bool:
        """
        Check if a symbol is valid and available from this data source.
        
        Args:
            symbol: Ticker symbol to validate
        
        Returns:
            True if symbol is valid and tradable, False otherwise
        """
        pass
    
    @abstractmethod
    def get_supported_timeframes(self) -> List[str]:
        """
        Return list of timeframes supported by this data source.
        
        Returns:
            List of timeframe strings (e.g., ['1m', '5m', '15m', '1h', '4h', '1d'])
        """
        pass
    
    def validate_timeframe(self, timeframe: str) -> bool:
        """
        Check if a timeframe is supported by this data source.
        
        Args:
            timeframe: Timeframe to validate (e.g., '1m', '5m', '1h', '1d')
        
        Returns:
            True if timeframe is supported, False otherwise
        """
        return timeframe in self.get_supported_timeframes()
