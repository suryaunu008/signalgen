"""
Indicator Engine Module

This module provides technical indicator calculations for the SignalGen scalping system.
Uses pandas-ta library for efficient and accurate technical indicator calculations.

Key Features:
- Multi-symbol support (up to 5 symbols for MVP)
- Moving averages (MA20, MA50, MA100, MA200, EMA6, EMA9, EMA10, EMA13, EMA20, EMA21, EMA34, EMA50)
- MACD (Moving Average Convergence Divergence)
- RSI (Relative Strength Index)
- ADX (Average Directional Index)
- Bollinger Bands
- Previous value tracking for all indicators (for CROSS_UP/CROSS_DOWN)
- Rolling data management for efficient calculations
- Thread-safe operations for async environment
- Integration with rule engine for signal generation

Supported Indicators:
- PRICE, PREV_CLOSE, PREV_OPEN (candle data)
- MA20, MA50, MA100, MA200 (Simple Moving Averages)
- EMA6, EMA9, EMA10, EMA13, EMA20, EMA21, EMA34, EMA50 (Exponential Moving Averages)
- MACD, MACD_SIGNAL, MACD_HIST, MACD_HIST_PREV (MACD indicators)
- RSI14, RSI14_PREV (14-period RSI)
- ADX5, ADX5_PREV (5-period ADX)
- BB_UPPER, BB_MIDDLE, BB_LOWER, BB_WIDTH (Bollinger Bands)
- PRICE_EMA20_DIFF_PCT (calculated metric)
"""

import threading
import time
from collections import deque
from typing import Dict, List, Optional, Union
import logging

import pandas as pd
import numpy as np
import ta


class IndicatorEngine:
    """
    Technical indicator calculation engine for trading signals.
    
    Uses pandas-ta library for accurate and efficient indicator calculations.
    Thread-safe operations suitable for async environments.
    """
    
    def __init__(self, max_history: int = 250):
        """
        Initialize the indicator engine.
        
        Args:
            max_history: Maximum number of candle periods to store (default 250 for MA200)
        """
        self.max_history = max_history
        self.candle_data: Dict[str, deque] = {}  # Symbol -> deque of candle dicts (OHLC)
        self.indicators: Dict[str, Dict[str, float]] = {}  # Symbol -> indicator values
        self.prev_indicators: Dict[str, Dict[str, float]] = {}  # Symbol -> previous indicator values
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        self.logger = logging.getLogger(__name__)
        
        # Supported indicator periods
        self.ma_periods = [20, 50, 100, 200]
        self.ema_periods = [6, 9, 10, 13, 20, 21, 34, 50]
        self.rsi_period = 14
        self.adx_period = 5
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.bb_period = 20
        self.bb_std_dev = 2
    
    def initialize_symbol(self, symbol: str) -> None:
        """
        Initialize data structures for a new symbol.
        
        Args:
            symbol: Stock symbol to initialize (e.g., "AAPL")
        """
        with self.lock:
            if symbol not in self.candle_data:
                self.candle_data[symbol] = deque(maxlen=self.max_history)
                self.indicators[symbol] = {}
                self.prev_indicators[symbol] = {}
                self.logger.debug(f"Initialized indicator data for symbol: {symbol}")
    
    def clear_symbol_data(self, symbol: str) -> None:
        """
        Clear data for a symbol (when unsubscribed).
        
        Args:
            symbol: Stock symbol to clear
        """
        with self.lock:
            if symbol in self.candle_data:
                del self.candle_data[symbol]
                self.logger.debug(f"Cleared candle data for symbol: {symbol}")
            
            if symbol in self.indicators:
                del self.indicators[symbol]
                self.logger.debug(f"Cleared indicator data for symbol: {symbol}")
            
            if symbol in self.prev_indicators:
                del self.prev_indicators[symbol]
                self.logger.debug(f"Cleared previous indicator data for symbol: {symbol}")
    
    def update_candle_data(self, symbol: str, open_price: float, high: float, low: float, 
                          close: float, timestamp: Optional[float] = None) -> None:
        """
        Add new candle data for a symbol.
        
        Args:
            symbol: Stock symbol
            open_price: Candle open price
            high: Candle high price
            low: Candle low price
            close: Candle close price
            timestamp: Unix timestamp (defaults to current time)
            
        Raises:
            ValueError: If price is invalid
        """
        if not all(isinstance(p, (int, float)) and p > 0 for p in [open_price, high, low, close]):
            raise ValueError(f"Invalid price values: O={open_price}, H={high}, L={low}, C={close}")
        
        if timestamp is None:
            timestamp = time.time()
        
        with self.lock:
            # Initialize symbol if not exists
            if symbol not in self.candle_data:
                self.initialize_symbol(symbol)
            
            # Store previous indicator values before updating
            if symbol in self.indicators and self.indicators[symbol]:
                self.prev_indicators[symbol] = self.indicators[symbol].copy()
            
            # Add new candle data
            candle = {
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'timestamp': timestamp
            }
            self.candle_data[symbol].append(candle)
            
            # Calculate indicators for this symbol
            self._calculate_indicators_for_symbol(symbol)
            
            self.logger.debug(f"Updated candle data for {symbol}: O={open_price}, H={high}, L={low}, C={close}")
    
    def update_price_data(self, symbol: str, price: float, timestamp: Optional[float] = None) -> None:
        """
        Add new price data for a symbol (backward compatibility).
        Creates a candle with price as all OHLC values.
        
        Args:
            symbol: Stock symbol
            price: Current price
            timestamp: Unix timestamp (defaults to current time)
            
        Raises:
            ValueError: If price is invalid
        """
        self.update_candle_data(symbol, price, price, price, price, timestamp)
    
    def bulk_update_candle_data(self, symbol: str, candles: List[Dict]) -> None:
        """
        Bulk update candle data for a symbol (used for historical data).
        
        Args:
            symbol: Stock symbol
            candles: List of candle dicts with keys: open, high, low, close, timestamp
        """
        with self.lock:
            # Initialize symbol if not exists
            if symbol not in self.candle_data:
                self.initialize_symbol(symbol)
            
            # Add all historical candles
            for candle in candles:
                if all(k in candle for k in ['open', 'high', 'low', 'close']):
                    self.candle_data[symbol].append(candle)
            
            # Calculate indicators once after all data is loaded
            self._calculate_indicators_for_symbol(symbol, suppress_warnings=True)
            
            self.logger.info(f"Bulk updated {len(candles)} candles for {symbol}")
    
    def bulk_update_price_data(self, symbol: str, prices: List[tuple]) -> None:
        """
        Bulk update price data for a symbol (backward compatibility).
        
        Args:
            symbol: Stock symbol
            prices: List of (price, timestamp) tuples in chronological order
        """
        candles = [{
            'open': price,
            'high': price,
            'low': price,
            'close': price,
            'timestamp': ts
        } for price, ts in prices if isinstance(price, (int, float)) and price > 0]
        
        self.bulk_update_candle_data(symbol, candles)
    
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
        Calculate simple moving averages for given periods.
        
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
        s = pd.Series(prices)
        
        for period in periods:
            if len(prices) < period:
                raise ValueError(f"Insufficient data for MA{period}: need {period}, have {len(prices)}")
            
            ma = ta.trend.sma_indicator(s, window=period)
            results[period] = ma.iloc[-1]
        
        return results
    
    def calculate_ema(self, prices: List[float], period: int) -> float:
        """
        Calculate Exponential Moving Average for a given period.
        
        Args:
            prices: List of price values (chronological order, oldest first)
            period: EMA period
            
        Returns:
            EMA value
            
        Raises:
            ValueError: If insufficient data
        """
        if not prices or len(prices) < period:
            raise ValueError(f"Insufficient data for EMA{period}: need {period}, have {len(prices)}")
        
        s = pd.Series(prices)
        ema = ta.trend.ema_indicator(s, window=period)
        return ema.iloc[-1]
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """
        Calculate Relative Strength Index.
        
        Args:
            prices: List of price values (chronological order, oldest first)
            period: RSI period (default 14)
            
        Returns:
            RSI value (0-100)
            
        Raises:
            ValueError: If insufficient data
        """
        if len(prices) < period + 1:
            raise ValueError(f"Insufficient data for RSI{period}: need {period + 1}, have {len(prices)}")
        
        s = pd.Series(prices)
        rsi = ta.momentum.rsi(s, window=period)
        return rsi.iloc[-1]
    
    def calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            prices: List of price values (chronological order, oldest first)
            fast: Fast EMA period (default 12)
            slow: Slow EMA period (default 26)
            signal: Signal line period (default 9)
            
        Returns:
            Dict with 'macd', 'signal', 'histogram'
            
        Raises:
            ValueError: If insufficient data
        """
        if len(prices) < slow + signal:
            raise ValueError(f"Insufficient data for MACD: need {slow + signal}, have {len(prices)}")
        
        s = pd.Series(prices)
        macd_line = ta.trend.macd(s, window_fast=fast, window_slow=slow)
        macd_signal = ta.trend.macd_signal(s, window_fast=fast, window_slow=slow, window_sign=signal)
        macd_hist = ta.trend.macd_diff(s, window_fast=fast, window_slow=slow, window_sign=signal)
        
        return {
            'macd': macd_line.iloc[-1],
            'signal': macd_signal.iloc[-1],
            'histogram': macd_hist.iloc[-1]
        }
    
    def calculate_adx(self, candles: List[Dict], period: int = 5) -> float:
        """
        Calculate ADX (Average Directional Index).
        
        Args:
            candles: List of candle dicts with high, low, close
            period: ADX period (default 5)
            
        Returns:
            ADX value
            
        Raises:
            ValueError: If insufficient data
        """
        if len(candles) < period + 1:
            raise ValueError(f"Insufficient data for ADX{period}: need {period + 1}, have {len(candles)}")
        
        highs = pd.Series([c['high'] for c in candles])
        lows = pd.Series([c['low'] for c in candles])
        closes = pd.Series([c['close'] for c in candles])
        
        adx = ta.trend.adx(highs, lows, closes, window=period)
        return adx.iloc[-1]
    
    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2) -> Dict[str, float]:
        """
        Calculate Bollinger Bands.
        
        Args:
            prices: List of price values (chronological order, oldest first)
            period: BB period (default 20)
            std_dev: Number of standard deviations (default 2)
            
        Returns:
            Dict with 'upper', 'middle', 'lower', 'width'
            
        Raises:
            ValueError: If insufficient data
        """
        if len(prices) < period:
            raise ValueError(f"Insufficient data for BB{period}: need {period}, have {len(prices)}")
        
        s = pd.Series(prices)
        bb_upper = ta.volatility.bollinger_hband(s, window=period, window_dev=std_dev)
        bb_middle = ta.volatility.bollinger_mavg(s, window=period)
        bb_lower = ta.volatility.bollinger_lband(s, window=period, window_dev=std_dev)
        
        return {
            'lower': bb_lower.iloc[-1],
            'middle': bb_middle.iloc[-1],
            'upper': bb_upper.iloc[-1],
            'width': bb_upper.iloc[-1] - bb_lower.iloc[-1]
        }
    
    def _create_dataframe(self, symbol: str) -> pd.DataFrame:
        """
        Create DataFrame from candle data for pandas-ta calculations.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            DataFrame with OHLC data
        """
        candles = list(self.candle_data[symbol])
        
        df = pd.DataFrame({
            'open': [c['open'] for c in candles],
            'high': [c['high'] for c in candles],
            'low': [c['low'] for c in candles],
            'close': [c['close'] for c in candles],
        })
        
        return df
    
    def _calculate_indicators_for_symbol(self, symbol: str, suppress_warnings: bool = False) -> None:
        """
        Calculate all indicators for a specific symbol using ta library.
        
        Args:
            symbol: Stock symbol to calculate indicators for
            suppress_warnings: If True, don't log warnings for insufficient data
        """
        if symbol not in self.candle_data:
            return
        
        candles = list(self.candle_data[symbol])
        
        if not candles:
            return
        
        # Create DataFrame for calculations
        df = self._create_dataframe(symbol)
        
        if len(df) == 0:
            return
        
        current_price = float(df['close'].iloc[-1])
        
        # Initialize indicators dict
        indicators = {}
        
        # Basic price data
        indicators['PRICE'] = current_price
        
        # Previous candle data
        if len(df) >= 2:
            indicators['PREV_CLOSE'] = float(df['close'].iloc[-2])
            indicators['PREV_OPEN'] = float(df['open'].iloc[-2])
        
        try:
            # Simple Moving Averages
            for period in self.ma_periods:
                if len(df) >= period:
                    ma = ta.trend.sma_indicator(df['close'], window=period)
                    if ma is not None and not pd.isna(ma.iloc[-1]):
                        indicators[f'MA{period}'] = float(ma.iloc[-1])
            
            # Exponential Moving Averages
            for period in self.ema_periods:
                if len(df) >= period:
                    ema = ta.trend.ema_indicator(df['close'], window=period)
                    if ema is not None and not pd.isna(ema.iloc[-1]):
                        indicators[f'EMA{period}'] = float(ema.iloc[-1])
            
            # MACD
            if len(df) >= self.macd_slow + self.macd_signal:
                try:
                    macd_line = ta.trend.macd(df['close'], window_fast=self.macd_fast, window_slow=self.macd_slow)
                    macd_signal = ta.trend.macd_signal(df['close'], window_fast=self.macd_fast, window_slow=self.macd_slow, window_sign=self.macd_signal)
                    macd_diff = ta.trend.macd_diff(df['close'], window_fast=self.macd_fast, window_slow=self.macd_slow, window_sign=self.macd_signal)
                    
                    if (macd_line is not None and not pd.isna(macd_line.iloc[-1])):
                        indicators['MACD'] = float(macd_line.iloc[-1])
                        indicators['MACD_SIGNAL'] = float(macd_signal.iloc[-1])
                        indicators['MACD_HIST'] = float(macd_diff.iloc[-1])
                except:
                    pass
            
            # RSI
            if len(df) >= self.rsi_period + 1:
                rsi = ta.momentum.rsi(df['close'], window=self.rsi_period)
                if rsi is not None and not pd.isna(rsi.iloc[-1]):
                    indicators['RSI14'] = float(rsi.iloc[-1])
            
            # ADX
            if len(df) >= self.adx_period + 1:
                try:
                    adx = ta.trend.adx(high=df['high'], low=df['low'], close=df['close'], window=self.adx_period)
                    if adx is not None and not pd.isna(adx.iloc[-1]):
                        indicators['ADX5'] = float(adx.iloc[-1])
                except:
                    pass
            
            # Bollinger Bands
            if len(df) >= self.bb_period:
                try:
                    bb_upper = ta.volatility.bollinger_hband(df['close'], window=self.bb_period, window_dev=self.bb_std_dev)
                    bb_middle = ta.volatility.bollinger_mavg(df['close'], window=self.bb_period)
                    bb_lower = ta.volatility.bollinger_lband(df['close'], window=self.bb_period, window_dev=self.bb_std_dev)
                    
                    if (bb_upper is not None and not pd.isna(bb_upper.iloc[-1])):
                        indicators['BB_UPPER'] = float(bb_upper.iloc[-1])
                        indicators['BB_MIDDLE'] = float(bb_middle.iloc[-1])
                        indicators['BB_LOWER'] = float(bb_lower.iloc[-1])
                        indicators['BB_WIDTH'] = indicators['BB_UPPER'] - indicators['BB_LOWER']
                except:
                    pass
            
            # Calculated metrics
            if 'EMA20' in indicators:
                ema20 = indicators['EMA20']
                if ema20 != 0:
                    price_ema20_diff_pct = abs(current_price - ema20) / ema20
                    indicators['PRICE_EMA20_DIFF_PCT'] = float(price_ema20_diff_pct)
            
            # Add previous values with _PREV suffix
            if symbol in self.prev_indicators:
                prev = self.prev_indicators[symbol]
                for key, value in prev.items():
                    if key not in ['PRICE_EMA20_DIFF_PCT']:
                        indicators[f'{key}_PREV'] = value
        
        except Exception as e:
            if not suppress_warnings:
                self.logger.warning(f"Error calculating indicators for {symbol}: {e}")
        
        # Store calculated indicators
        self.indicators[symbol] = indicators
    
    def get_all_symbols(self) -> List[str]:
        """
        Get list of all symbols currently tracked.
        
        Returns:
            List of symbol strings
        """
        with self.lock:
            return list(self.candle_data.keys())
    
    def get_symbol_data_count(self, symbol: str) -> int:
        """
        Get the number of candle data points for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Number of candle data points
        """
        with self.lock:
            if symbol not in self.candle_data:
                return 0
            return len(self.candle_data[symbol])
    
    def is_symbol_ready(self, symbol: str) -> bool:
        """
        Check if a symbol has sufficient data for all indicators.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            True if symbol has enough data for complex indicators, False otherwise
        """
        with self.lock:
            if symbol not in self.candle_data:
                return False
            # Need enough data for MACD (slowest indicator)
            return len(self.candle_data[symbol]) >= self.macd_slow + self.macd_signal
    
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
            if symbol not in self.candle_data:
                result["valid"] = False
                result["errors"].append("Symbol not found")
                return result
            
            candles = self.candle_data[symbol]
            
            if not candles:
                result["valid"] = False
                result["errors"].append("No candle data available")
                return result
            
            # Check data count for complex indicators
            min_required = self.macd_slow + self.macd_signal
            if len(candles) < min_required:
                result["warnings"].append(
                    f"Insufficient data for all indicators: have {len(candles)}, need {min_required}"
                )
            
            # Check for price anomalies
            for i, candle in enumerate(candles):
                if any(candle.get(k, 0) <= 0 for k in ['open', 'high', 'low', 'close']):
                    result["valid"] = False
                    result["errors"].append(f"Invalid price values in candle {i}")
                    break
            
            # Check for duplicate timestamps
            timestamps = [c.get('timestamp') for c in candles]
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
            symbol_count = len(self.candle_data)
            symbols = list(self.candle_data.keys())
            
            # Count ready symbols
            ready_symbols = sum(1 for symbol in symbols if self.is_symbol_ready(symbol))
            
            return {
                "total_symbols": symbol_count,
                "ready_symbols": ready_symbols,
                "max_history": self.max_history,
                "supported_ma_periods": self.ma_periods,
                "supported_ema_periods": self.ema_periods,
                "rsi_period": self.rsi_period,
                "adx_period": self.adx_period,
                "bb_period": self.bb_period,
                "bb_std_dev": self.bb_std_dev,
                "symbols": symbols
            }