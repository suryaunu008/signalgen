"""
Yahoo Finance Data Source Module

This module provides market data from Yahoo Finance using yfinance.
Suitable for swing trading and daily/weekly backtests.

Features:
- Free historical data access
- No authentication required
- Wide symbol coverage (stocks, ETFs, indices)
- Support for multiple timeframes

Limitations:
- Rate limits: ~2000 requests/hour
- Intraday data limited to last 60 days (1m/5m intervals)
- 4h timeframe requires aggregation from 1h data
- No weekend/holiday data
- Delayed data (15-20 minutes)

Typical Usage:
    yahoo = YahooDataSource()
    candles = await yahoo.fetch_historical_data(
        symbol='AAPL',
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2025, 1, 1),
        timeframe='1d'
    )
"""

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd

from .base_data_source import BaseDataSource

class YahooDataSource(BaseDataSource):
    """
    Yahoo Finance data source implementation using yfinance.
    
    This class provides free market data suitable for swing trading
    and longer-term backtesting.
    """
    
    # Timeframe to yfinance interval mapping
    TIMEFRAME_MAP = {
        '1m': '1m',
        '5m': '5m',
        '15m': '15m',
        '1h': '1h',
        '4h': '1h',  # Will aggregate from 1h
        '1d': '1d'
    }
    
    def __init__(self):
        """Initialize Yahoo Finance data source."""
        self.logger = logging.getLogger(__name__)
        self._cache = {}  # Simple cache for recently fetched data
    
    async def fetch_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str
    ) -> List[Dict]:
        """
        Fetch historical OHLCV data from Yahoo Finance.
        
        Args:
            symbol: Stock ticker symbol
            start_date: Start date for historical data
            end_date: End date for historical data
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
        
        Returns:
            List of candles in standardized format
        
        Raises:
            ValueError: If timeframe is not supported
            Exception: If data fetch fails
        """
        # Validate timeframe
        if not self.validate_timeframe(timeframe):
            raise ValueError(f"Timeframe '{timeframe}' not supported. Use one of: {self.get_supported_timeframes()}")
        
        # Run in thread pool since yfinance is synchronous
        loop = asyncio.get_event_loop()
        candles = await loop.run_in_executor(
            None,
            self._fetch_data_sync,
            symbol,
            start_date,
            end_date,
            timeframe
        )
        
        return candles
    
    def _fetch_data_sync(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str
    ) -> List[Dict]:
        """
        Synchronous data fetch (runs in thread pool).
        
        Args:
            symbol: Stock ticker symbol
            start_date: Start date
            end_date: End date
            timeframe: Candle timeframe
        
        Returns:
            List of candles
        """
        try:
            ticker = yf.Ticker(symbol.upper())
            interval = self.TIMEFRAME_MAP[timeframe]
            
            self.logger.info(f"Fetching {interval} data for {symbol} from Yahoo Finance")
            
            # Download data
            df = ticker.history(
                start=start_date,
                end=end_date,
                interval=interval,
                auto_adjust=False  # Keep original OHLC without adjustments
            )
            
            if df.empty:
                self.logger.warning(f"No data returned for {symbol}")
                return []
            
            # Handle 4h timeframe aggregation
            if timeframe == '4h':
                df = self._aggregate_to_4h(df)
            
            # Convert to standard format
            candles = []
            for timestamp, row in df.iterrows():
                candles.append({
                    'timestamp': timestamp.to_pydatetime(),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume'])
                })
            
            self.logger.info(f"Fetched {len(candles)} candles for {symbol}")
            return candles
            
        except Exception as e:
            self.logger.error(f"Failed to fetch data for {symbol}: {e}")
            raise
    
    def _aggregate_to_4h(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate 1h data to 4h candles.
        
        Args:
            df: DataFrame with 1h OHLCV data
        
        Returns:
            DataFrame with 4h OHLCV data
        """
        # Resample to 4-hour intervals
        # Align to market open (9:30 AM ET)
        aggregated = df.resample('4H', label='left', closed='left').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        })
        
        # Remove rows with NaN (incomplete periods)
        aggregated = aggregated.dropna()
        
        return aggregated
    
    async def validate_symbol(self, symbol: str) -> bool:
        """
        Validate if symbol exists on Yahoo Finance.
        
        Args:
            symbol: Stock ticker symbol
        
        Returns:
            True if symbol is valid, False otherwise
        """
        try:
            # Run in thread pool
            loop = asyncio.get_event_loop()
            is_valid = await loop.run_in_executor(
                None,
                self._validate_symbol_sync,
                symbol
            )
            return is_valid
        except Exception as e:
            self.logger.error(f"Symbol validation failed for {symbol}: {e}")
            return False
    
    def _validate_symbol_sync(self, symbol: str) -> bool:
        """
        Synchronous symbol validation.
        
        Args:
            symbol: Stock ticker symbol
        
        Returns:
            True if valid, False otherwise
        """
        try:
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info
            
            # Check if basic price info exists
            return 'regularMarketPrice' in info or 'currentPrice' in info
        except Exception:
            return False
    
    def get_supported_timeframes(self) -> List[str]:
        """
        Return list of supported timeframes.
        
        Returns:
            List of timeframe strings
        """
        return list(self.TIMEFRAME_MAP.keys())
