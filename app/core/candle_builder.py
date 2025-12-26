"""
Candle Builder Module

This module provides candle aggregation functionality for the SignalGen system.
It builds candles from raw bar data based on selected timeframes.

Key Features:
- Multi-timeframe support (1m, 5m, 15m, 1h, 4h, 1d)
- Timestamp-based aggregation to prevent duplicates
- Thread-safe operations
- Rolling window management for efficiency
- OHLC (Open, High, Low, Close) calculation

Supported Timeframes:
- 1m: 1 minute
- 5m: 5 minutes
- 15m: 15 minutes
- 1h: 1 hour
- 4h: 4 hours
- 1d: 1 day

Data Flow:
Raw Bar → Candle Builder → Aggregated Candle → Indicator Engine
"""

import threading
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import logging


class CandleBuilder:
    """
    Builds aggregated candles from raw bar data based on timeframe.
    
    Thread-safe candle aggregation with timestamp deduplication.
    """
    
    # Timeframe definitions in seconds
    TIMEFRAMES = {
        '1m': 60,           # 1 minute
        '5m': 300,          # 5 minutes
        '15m': 900,         # 15 minutes
        '1h': 3600,         # 1 hour
        '4h': 14400,        # 4 hours
        '1d': 86400,        # 1 day
    }
    
    def __init__(self, timeframe: str = '1m', max_candles: int = 500):
        """
        Initialize candle builder.
        
        Args:
            timeframe: Selected timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            max_candles: Maximum number of completed candles to retain per symbol
            
        Raises:
            ValueError: If timeframe is not supported
        """
        if timeframe not in self.TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}. Must be one of {list(self.TIMEFRAMES.keys())}")
        
        self.timeframe = timeframe
        self.timeframe_seconds = self.TIMEFRAMES[timeframe]
        self.max_candles = max_candles
        
        # Symbol -> completed candles (deque of dicts)
        self.completed_candles: Dict[str, deque] = {}
        
        # Symbol -> current building candle (dict)
        self.current_candles: Dict[str, Optional[Dict]] = {}
        
        # Symbol -> set of processed timestamps (to avoid duplicates)
        self.processed_timestamps: Dict[str, set] = {}
        
        # Symbol -> last candle close time
        self.last_candle_times: Dict[str, float] = {}
        
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
    
    def change_timeframe(self, new_timeframe: str) -> None:
        """
        Change the active timeframe and clear all candle data.
        
        Args:
            new_timeframe: New timeframe to use
            
        Raises:
            ValueError: If timeframe is not supported
        """
        if new_timeframe not in self.TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {new_timeframe}")
        
        with self.lock:
            self.timeframe = new_timeframe
            self.timeframe_seconds = self.TIMEFRAMES[new_timeframe]
            
            # Clear all data for fresh start
            self.completed_candles.clear()
            self.current_candles.clear()
            self.processed_timestamps.clear()
            self.last_candle_times.clear()
            
            self.logger.info(f"Timeframe changed to {new_timeframe} ({self.timeframe_seconds}s)")
    
    def initialize_symbol(self, symbol: str) -> None:
        """
        Initialize data structures for a new symbol.
        
        Args:
            symbol: Stock symbol to initialize
        """
        with self.lock:
            if symbol not in self.completed_candles:
                self.completed_candles[symbol] = deque(maxlen=self.max_candles)
                self.current_candles[symbol] = None
                self.processed_timestamps[symbol] = set()
                self.last_candle_times[symbol] = 0
                self.logger.debug(f"Initialized candle builder for {symbol}")
    
    def clear_symbol_data(self, symbol: str) -> None:
        """
        Clear all data for a symbol.
        
        Args:
            symbol: Stock symbol to clear
        """
        with self.lock:
            if symbol in self.completed_candles:
                del self.completed_candles[symbol]
            if symbol in self.current_candles:
                del self.current_candles[symbol]
            if symbol in self.processed_timestamps:
                del self.processed_timestamps[symbol]
            if symbol in self.last_candle_times:
                del self.last_candle_times[symbol]
            
            self.logger.debug(f"Cleared candle data for {symbol}")
    
    def _get_candle_start_time(self, timestamp: float) -> float:
        """
        Calculate the start time of the candle that contains this timestamp.
        
        Args:
            timestamp: Unix timestamp
            
        Returns:
            float: Start time of the candle period
        """
        # Align to timeframe boundaries
        # For example, if timeframe is 5m (300s), align to 00:00, 00:05, 00:10, etc.
        return (int(timestamp) // self.timeframe_seconds) * self.timeframe_seconds
    
    def _should_finalize_candle(self, current_candle_start: float, new_timestamp: float) -> bool:
        """
        Determine if the current candle should be finalized.
        
        Args:
            current_candle_start: Start time of current candle
            new_timestamp: Timestamp of new bar
            
        Returns:
            bool: True if candle should be finalized
        """
        new_candle_start = self._get_candle_start_time(new_timestamp)
        return new_candle_start > current_candle_start
    
    def add_bar(self, symbol: str, open_price: float, high: float, low: float, 
                close: float, timestamp: float, volume: int = 0) -> Tuple[bool, Optional[Dict]]:
        """
        Add a bar and build candles based on timeframe.
        
        Args:
            symbol: Stock symbol
            open_price: Bar open price
            high: Bar high price
            low: Bar low price
            close: Bar close price
            timestamp: Unix timestamp of the bar
            volume: Trading volume (optional)
            
        Returns:
            Tuple[bool, Optional[Dict]]: (candle_completed, completed_candle_data)
                - candle_completed: True if a candle was finalized
                - completed_candle_data: Dict with OHLC data if candle completed, None otherwise
                
        Raises:
            ValueError: If prices are invalid
        """
        if not all(isinstance(p, (int, float)) and p > 0 for p in [open_price, high, low, close]):
            raise ValueError(f"Invalid price values: O={open_price}, H={high}, L={low}, C={close}")
        
        with self.lock:
            # Initialize symbol if needed
            if symbol not in self.completed_candles:
                self.initialize_symbol(symbol)
            
            # Check for duplicate timestamp
            timestamp_key = int(timestamp)
            if timestamp_key in self.processed_timestamps[symbol]:
                self.logger.debug(f"Skipping duplicate timestamp for {symbol}: {timestamp_key}")
                return False, None
            
            # Mark timestamp as processed
            self.processed_timestamps[symbol].add(timestamp_key)
            
            # Keep only recent timestamps to prevent memory bloat
            if len(self.processed_timestamps[symbol]) > 10000:
                # Remove oldest 20% when limit reached
                sorted_timestamps = sorted(self.processed_timestamps[symbol])
                to_remove = sorted_timestamps[:2000]
                self.processed_timestamps[symbol] -= set(to_remove)
            
            # Calculate which candle period this bar belongs to
            candle_start = self._get_candle_start_time(timestamp)
            
            # Check if we need to finalize the current candle
            current_candle = self.current_candles[symbol]
            completed_candle = None
            candle_completed = False
            
            if current_candle is not None:
                # Check if this bar belongs to a new candle period
                if self._should_finalize_candle(current_candle['start_time'], timestamp):
                    # Finalize current candle
                    completed_candle = {
                        'open': current_candle['open'],
                        'high': current_candle['high'],
                        'low': current_candle['low'],
                        'close': current_candle['close'],
                        'volume': current_candle['volume'],
                        'timestamp': current_candle['close_time'],
                        'start_time': current_candle['start_time'],
                        'close_time': current_candle['close_time']
                    }
                    
                    # Store completed candle
                    self.completed_candles[symbol].append(completed_candle)
                    self.last_candle_times[symbol] = current_candle['close_time']
                    
                    candle_completed = True
                    
                    self.logger.debug(
                        f"Completed candle for {symbol}: "
                        f"O={completed_candle['open']:.2f}, H={completed_candle['high']:.2f}, "
                        f"L={completed_candle['low']:.2f}, C={completed_candle['close']:.2f}, "
                        f"Time={datetime.fromtimestamp(completed_candle['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    
                    # Start new candle
                    self.current_candles[symbol] = {
                        'open': open_price,
                        'high': high,
                        'low': low,
                        'close': close,
                        'volume': volume,
                        'start_time': candle_start,
                        'close_time': candle_start + self.timeframe_seconds
                    }
                else:
                    # Update current candle
                    current_candle['high'] = max(current_candle['high'], high)
                    current_candle['low'] = min(current_candle['low'], low)
                    current_candle['close'] = close
                    current_candle['volume'] += volume
            else:
                # Create first candle for this symbol
                self.current_candles[symbol] = {
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume,
                    'start_time': candle_start,
                    'close_time': candle_start + self.timeframe_seconds
                }
                
                self.logger.debug(f"Started new candle for {symbol} at {datetime.fromtimestamp(candle_start)}")
            
            return candle_completed, completed_candle
    
    def get_completed_candles(self, symbol: str, count: Optional[int] = None) -> List[Dict]:
        """
        Get completed candles for a symbol.
        
        Args:
            symbol: Stock symbol
            count: Number of most recent candles to return (None for all)
            
        Returns:
            List[Dict]: List of completed candles (oldest to newest)
        """
        with self.lock:
            if symbol not in self.completed_candles:
                return []
            
            candles = list(self.completed_candles[symbol])
            
            if count is not None and count > 0:
                return candles[-count:]
            
            return candles
    
    def get_current_candle(self, symbol: str) -> Optional[Dict]:
        """
        Get the current building candle for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Optional[Dict]: Current candle data or None if no candle is building
        """
        with self.lock:
            return self.current_candles.get(symbol)
    
    def get_all_candles(self, symbol: str, include_current: bool = True) -> List[Dict]:
        """
        Get all candles (completed + current) for a symbol.
        
        Args:
            symbol: Stock symbol
            include_current: Whether to include the current building candle
            
        Returns:
            List[Dict]: All candles in chronological order
        """
        with self.lock:
            candles = self.get_completed_candles(symbol)
            
            if include_current:
                current = self.get_current_candle(symbol)
                if current:
                    # Create a copy to avoid mutations
                    candles.append({
                        'open': current['open'],
                        'high': current['high'],
                        'low': current['low'],
                        'close': current['close'],
                        'volume': current['volume'],
                        'timestamp': current['close_time'],
                        'start_time': current['start_time'],
                        'close_time': current['close_time'],
                        'is_building': True  # Flag to indicate this candle is not complete
                    })
            
            return candles
    
    def get_timeframe(self) -> str:
        """
        Get the current timeframe.
        
        Returns:
            str: Current timeframe (e.g., '1m', '5m')
        """
        return self.timeframe
    
    def get_timeframe_seconds(self) -> int:
        """
        Get the current timeframe in seconds.
        
        Returns:
            int: Timeframe duration in seconds
        """
        return self.timeframe_seconds
    
    def get_candle_count(self, symbol: str) -> int:
        """
        Get the number of completed candles for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            int: Number of completed candles
        """
        with self.lock:
            if symbol not in self.completed_candles:
                return 0
            return len(self.completed_candles[symbol])
    
    @classmethod
    def get_supported_timeframes(cls) -> List[str]:
        """
        Get list of supported timeframes.
        
        Returns:
            List[str]: List of supported timeframe strings
        """
        return list(cls.TIMEFRAMES.keys())
    
    @classmethod
    def validate_timeframe(cls, timeframe: str) -> bool:
        """
        Validate if a timeframe is supported.
        
        Args:
            timeframe: Timeframe string to validate
            
        Returns:
            bool: True if timeframe is valid
        """
        return timeframe in cls.TIMEFRAMES
