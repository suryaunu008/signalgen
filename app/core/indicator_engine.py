"""
Indicator Engine Module

This module provides technical indicator calculations for the SignalGen scalping system.
It calculates moving averages from price data for multiple symbols with thread-safe operations.

Key Features:
- Multi-symbol support (up to 5 symbols for MVP)
- Moving averages (MA5, MA10, MA20) - required for MVP
- Rolling data management for efficient calculations
- Thread-safe operations for async environment
- Integration with rule engine for signal generation

MVP Requirements:
- Support PRICE, MA5, MA10, MA20 indicators
- Maintain rolling data for each symbol
- Handle data updates from IBKR (price bars)
- Return indicator values in format compatible with rule engine
- Thread-safe operations for async scalping engine
"""

import threading
import time
from collections import deque
from typing import Dict, List, Optional, Union
import logging


class IndicatorEngine:
    """
    Technical indicator calculation engine for trading signals.
    
    This class calculates moving averages from price data for multiple symbols
    with thread-safe operations suitable for async environments.
    """
    
    def __init__(self, max_history: int = 20):
        """
        Initialize the indicator engine.
        
        Args:
            max_history: Maximum number of price periods to store (default 20 for MA20)
        """
        self.max_history = max_history
        self.price_data: Dict[str, deque] = {}  # Symbol -> deque of (price, timestamp)
        self.indicators: Dict[str, Dict[str, float]] = {}  # Symbol -> indicator values
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        self.logger = logging.getLogger(__name__)
        
        # Supported MA periods for MVP
        self.ma_periods = [5, 10, 20]
    
    def initialize_symbol(self, symbol: str) -> None:
        """
        Initialize data structures for a new symbol.
        
        Args:
            symbol: Stock symbol to initialize (e.g., "AAPL")
        """
        with self.lock:
            if symbol not in self.price_data:
                self.price_data[symbol] = deque(maxlen=self.max_history)
                self.indicators[symbol] = {}
                self.logger.debug(f"Initialized indicator data for symbol: {symbol}")
    
    def clear_symbol_data(self, symbol: str) -> None:
        """
        Clear data for a symbol (when unsubscribed).
        
        Args:
            symbol: Stock symbol to clear
        """
        with self.lock:
            if symbol in self.price_data:
                del self.price_data[symbol]
                self.logger.debug(f"Cleared price data for symbol: {symbol}")
            
            if symbol in self.indicators:
                del self.indicators[symbol]
                self.logger.debug(f"Cleared indicator data for symbol: {symbol}")
    
    def update_price_data(self, symbol: str, price: float, timestamp: Optional[float] = None) -> None:
        """
        Add new price data for a symbol.
        
        Args:
            symbol: Stock symbol
            price: Current price
            timestamp: Unix timestamp (defaults to current time)
            
        Raises:
            ValueError: If price is invalid
        """
        if not isinstance(price, (int, float)) or price <= 0:
            raise ValueError(f"Invalid price value: {price}")
        
        if timestamp is None:
            timestamp = time.time()
        
        with self.lock:
            # Initialize symbol if not exists
            if symbol not in self.price_data:
                self.initialize_symbol(symbol)
            
            # Add new price data
            self.price_data[symbol].append((price, timestamp))
            
            # Calculate indicators for this symbol
            self._calculate_indicators_for_symbol(symbol)
            
            self.logger.debug(f"Updated price data for {symbol}: {price} at {timestamp}")
    
    def bulk_update_price_data(self, symbol: str, prices: List[tuple]) -> None:
        """
        Bulk update price data for a symbol (used for historical data).
        
        Args:
            symbol: Stock symbol
            prices: List of (price, timestamp) tuples in chronological order
        """
        with self.lock:
            # Initialize symbol if not exists
            if symbol not in self.price_data:
                self.initialize_symbol(symbol)
            
            # Add all historical prices
            for price, timestamp in prices:
                if isinstance(price, (int, float)) and price > 0:
                    self.price_data[symbol].append((price, timestamp))
            
            # Calculate indicators once after all data is loaded (suppress warnings during bulk load)
            self._calculate_indicators_for_symbol(symbol, suppress_warnings=True)
            
            self.logger.info(f"Bulk updated {len(prices)} price points for {symbol}")
    
    def get_indicators(self, symbol: str) -> Dict[str, float]:
        """
        Get all current indicator values for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict containing indicator values (PRICE, MA5, MA10, MA20)
            
        Raises:
            KeyError: If symbol is not found
        """
        with self.lock:
            if symbol not in self.indicators:
                raise KeyError(f"Symbol not found: {symbol}")
            
            # Return a copy to prevent external modification
            return self.indicators[symbol].copy()
    
    def calculate_moving_averages(self, prices: List[float], periods: List[int]) -> Dict[int, float]:
        """
        Calculate moving averages for given periods.
        
        Args:
            prices: List of price values (chronological order, oldest first)
            periods: List of MA periods to calculate
            
        Returns:
            Dict mapping period -> MA value
            
        Raises:
            ValueError: If insufficient data for any period
        """
        if not prices:
            raise ValueError("No price data provided")
        
        results = {}
        
        for period in periods:
            if len(prices) < period:
                raise ValueError(f"Insufficient data for MA{period}: need {period}, have {len(prices)}")
            
            # Calculate simple moving average
            recent_prices = prices[-period:]  # Last 'period' prices
            ma_value = sum(recent_prices) / period
            results[period] = ma_value
        
        return results
    
    def _calculate_indicators_for_symbol(self, symbol: str, suppress_warnings: bool = False) -> None:
        """
        Calculate all indicators for a specific symbol.
        
        Args:
            symbol: Stock symbol to calculate indicators for
            suppress_warnings: If True, don't log warnings for insufficient data
        """
        if symbol not in self.price_data:
            return
        
        price_deque = self.price_data[symbol]
        
        if not price_deque:
            return
        
        # Extract prices from deque (chronological order)
        prices = [item[0] for item in price_deque]
        current_price = prices[-1]  # Latest price
        
        # Initialize indicators dict for this symbol
        self.indicators[symbol] = {"PRICE": current_price}
        
        try:
            # Calculate moving averages
            ma_values = self.calculate_moving_averages(prices, self.ma_periods)
            
            # Add MA values to indicators
            for period, ma_value in ma_values.items():
                self.indicators[symbol][f"MA{period}"] = ma_value
                
        except ValueError as e:
            # Handle insufficient data gracefully
            if not suppress_warnings:
                self.logger.warning(f"Insufficient data for {symbol}: {e}")
            # Keep only PRICE if insufficient data for MAs
            pass
    
    def get_all_symbols(self) -> List[str]:
        """
        Get list of all symbols currently tracked.
        
        Returns:
            List of symbol strings
        """
        with self.lock:
            return list(self.price_data.keys())
    
    def get_symbol_data_count(self, symbol: str) -> int:
        """
        Get the number of price data points for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Number of price data points
        """
        with self.lock:
            if symbol not in self.price_data:
                return 0
            return len(self.price_data[symbol])
    
    def is_symbol_ready(self, symbol: str) -> bool:
        """
        Check if a symbol has sufficient data for all indicators.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            True if symbol has enough data for MA20, False otherwise
        """
        with self.lock:
            if symbol not in self.price_data:
                return False
            return len(self.price_data[symbol]) >= self.max_history
    
    def validate_symbol_data(self, symbol: str) -> Dict[str, Union[bool, str]]:
        """
        Validate data integrity for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with validation results
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        with self.lock:
            if symbol not in self.price_data:
                result["valid"] = False
                result["errors"].append("Symbol not found")
                return result
            
            price_deque = self.price_data[symbol]
            
            if not price_deque:
                result["valid"] = False
                result["errors"].append("No price data available")
                return result
            
            # Check data count
            if len(price_deque) < self.max_history:
                result["warnings"].append(
                    f"Insufficient data for MA20: have {len(price_deque)}, need {self.max_history}"
                )
            
            # Check for price anomalies
            prices = [item[0] for item in price_deque]
            if any(p <= 0 for p in prices):
                result["valid"] = False
                result["errors"].append("Invalid price values detected (<= 0)")
            
            # Check for duplicate timestamps
            timestamps = [item[1] for item in price_deque]
            if len(timestamps) != len(set(timestamps)):
                result["warnings"].append("Duplicate timestamps detected")
        
        return result
    
    def get_engine_status(self) -> Dict[str, Union[int, List[str]]]:
        """
        Get overall engine status and statistics.
        
        Returns:
            Dict with engine status information
        """
        with self.lock:
            symbol_count = len(self.price_data)
            symbols = list(self.price_data.keys())
            
            # Count ready symbols
            ready_symbols = sum(1 for symbol in symbols if self.is_symbol_ready(symbol))
            
            return {
                "total_symbols": symbol_count,
                "ready_symbols": ready_symbols,
                "max_history": self.max_history,
                "supported_periods": self.ma_periods,
                "symbols": symbols
            }