"""
IBKR Data Source Module

This module provides market data from Interactive Brokers using ib_insync.
Suitable for intraday scalping backtests and real-time data.

Features:
- Historical bar data from IBKR TWS/Gateway
- Support for multiple timeframes
- Automatic connection management
- Symbol validation via contract search

Limitations:
- Requires active IBKR TWS or Gateway connection
- Historical data availability depends on IBKR subscription
- Rate limits apply (60 requests per 10 minutes)

Typical Usage:
    ibkr = IBKRDataSource(host='127.0.0.1', port=7497)
    candles = await ibkr.fetch_historical_data(
        symbol='AAPL',
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
        timeframe='5m'
    )
"""

import asyncio
import logging
import random
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from ib_insync import IB, Stock, util

from .base_data_source import BaseDataSource

class IBKRDataSource(BaseDataSource):
    """
    IBKR data source implementation using ib_insync.
    
    This class handles connection to Interactive Brokers and provides
    standardized historical data for backtesting engines.
    """
    
    # Timeframe to IBKR bar size mapping
    TIMEFRAME_MAP = {
        '1m': '1 min',
        '5m': '5 mins',
        '15m': '15 mins',
        '1h': '1 hour',
        '4h': '4 hours',
        '1d': '1 day'
    }
    
    # Timeframe to duration calculation (for historical data request)
    DURATION_MAP = {
        '1m': lambda days: f"{days} D",
        '5m': lambda days: f"{days} D",
        '15m': lambda days: f"{min(days * 2, 30)} D",  # Cap at 30 days
        '1h': lambda days: f"{min(days, 365)} D",
        '4h': lambda days: f"{min(days, 365)} D",
        '1d': lambda days: f"{min(days, 365)} D"
    }
    
    def __init__(self, host: str = '127.0.0.1', port: int = 7497, client_id: Optional[int] = None):
        """
        Initialize IBKR data source.
        
        Args:
            host: IBKR TWS/Gateway host address
            port: IBKR TWS/Gateway port (7497 for TWS, 4002 for Gateway)
            client_id: Optional client ID (random if not provided)
        """
        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id or random.randint(1000, 9999)
        self.is_connected = False
        self.logger = logging.getLogger(__name__)
    
    async def _ensure_connected(self) -> None:
        """Ensure connection to IBKR is active."""
        if not self.ib.isConnected():
            try:
                self.logger.info(f"Connecting to IBKR at {self.host}:{self.port}")
                await self.ib.connectAsync(
                    self.host,
                    self.port,
                    clientId=self.client_id,
                    timeout=10
                )
                self.is_connected = True
                self.logger.info("Successfully connected to IBKR")
            except Exception as e:
                self.logger.error(f"Failed to connect to IBKR: {e}")
                self.is_connected = False
                raise
    
    async def disconnect(self) -> None:
        """Disconnect from IBKR."""
        if self.ib.isConnected():
            self.ib.disconnect()
            self.is_connected = False
            self.logger.info("Disconnected from IBKR")
    
    async def fetch_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str
    ) -> List[Dict]:
        """
        Fetch historical OHLCV data from IBKR.
        
        Args:
            symbol: Stock ticker symbol
            start_date: Start date for historical data
            end_date: End date for historical data
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
        
        Returns:
            List of candles in standardized format
        
        Raises:
            ValueError: If timeframe is not supported
            Exception: If IBKR connection or data fetch fails
        """
        # Validate timeframe
        if not self.validate_timeframe(timeframe):
            raise ValueError(f"Timeframe '{timeframe}' not supported. Use one of: {self.get_supported_timeframes()}")
        
        # Ensure connection
        await self._ensure_connected()
        
        # Create contract
        contract = Stock(symbol.upper(), 'SMART', 'USD')
        
        # Qualify contract
        qualified_contracts = await self.ib.qualifyContractsAsync(contract)
        if not qualified_contracts:
            raise ValueError(f"Symbol '{symbol}' not found on IBKR")
        
        contract = qualified_contracts[0]
        
        # Calculate duration
        days = (end_date - start_date).days
        bar_size = self.TIMEFRAME_MAP[timeframe]
        
        # Determine duration string
        if timeframe in ['1m', '5m']:
            # For minute bars, IBKR limits to short durations
            duration = f"{min(days, 30)} D"
        else:
            duration = f"{min(days, 365)} D"
        
        # Request historical data
        try:
            self.logger.info(f"Fetching {duration} of {bar_size} bars for {symbol}")
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime=end_date,
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,  # Regular trading hours only
                formatDate=1
            )
            
            # Convert to standard format
            candles = []
            for bar in bars:
                candles.append({
                    'timestamp': bar.date,
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume)
                })
            
            # Filter by start_date (IBKR might return more data)
            candles = [c for c in candles if c['timestamp'] >= start_date]
            
            self.logger.info(f"Fetched {len(candles)} candles for {symbol}")
            return candles
            
        except Exception as e:
            self.logger.error(f"Failed to fetch historical data for {symbol}: {e}")
            raise
    
    async def validate_symbol(self, symbol: str) -> bool:
        """
        Validate if symbol exists on IBKR.
        
        Args:
            symbol: Stock ticker symbol
        
        Returns:
            True if symbol is valid, False otherwise
        """
        try:
            await self._ensure_connected()
            contract = Stock(symbol.upper(), 'SMART', 'USD')
            qualified = await self.ib.qualifyContractsAsync(contract)
            return len(qualified) > 0
        except Exception as e:
            self.logger.error(f"Symbol validation failed for {symbol}: {e}")
            return False
    
    def get_supported_timeframes(self) -> List[str]:
        """
        Return list of supported timeframes.
        
        Returns:
            List of timeframe strings
        """
        return list(self.TIMEFRAME_MAP.keys())
