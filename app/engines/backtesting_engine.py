"""
Backtesting Engine Module

This module provides unified backtesting functionality for both scalping
and swing trading strategies.

Features:
- Works with any BaseDataSource (IBKR, Yahoo Finance)
- Sequential candle-by-candle simulation
- Uses existing Rule Engine and Indicator Engine
- Generates signal history with timestamps
- Calculates performance metrics
- No order execution (signal generation only)

Data Flow:
Data Source → Indicator Engine → Rule Engine → Signal Recording

Typical Usage:
    from app.data_sources import YahooDataSource
    from app.engines.backtesting_engine import BacktestingEngine
    
    yahoo = YahooDataSource()
    engine = BacktestingEngine(data_source=yahoo, timeframe='1d')
    
    results = await engine.run_backtest(
        symbols=['AAPL', 'MSFT'],
        rule_id=1,
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2025, 1, 1)
    )
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import json

from ..core.rule_engine import RuleEngine
from ..core.indicator_engine import IndicatorEngine
from ..storage.sqlite_repo import SQLiteRepository
from ..data_sources.base_data_source import BaseDataSource

class BacktestingEngine:
    """
    Unified backtesting engine for strategy validation.
    
    This engine simulates historical trading by feeding past candle data
    through the indicator and rule engines to generate signals.
    """
    
    def __init__(self, data_source: BaseDataSource, timeframe: str = '1d'):
        """
        Initialize backtesting engine.
        
        Args:
            data_source: Data source instance (IBKR or Yahoo)
            timeframe: Candle timeframe to use
        """
        self.data_source = data_source
        self.timeframe = timeframe
        self.indicator_engine = IndicatorEngine(timeframe=timeframe)
        self.rule_engine = RuleEngine()
        self.repository = SQLiteRepository()
        self.logger = logging.getLogger(__name__)
        
        # Backtest state
        self.signals = []
        self.current_rule = None
    
    async def run_backtest(
        self,
        name: str,
        mode: str,
        symbols: List[str],
        rule_id: int,
        start_date: datetime,
        end_date: datetime,
        data_source_name: str
    ) -> Dict[str, Any]:
        """
        Run backtest for given symbols and date range.
        
        Args:
            name: Backtest run name
            mode: 'scalping' or 'swing'
            symbols: List of ticker symbols to backtest
            rule_id: Rule ID to use for signal generation
            start_date: Start date of backtest period
            end_date: End date of backtest period
            data_source_name: 'ibkr' or 'yahoo' (for record keeping)
        
        Returns:
            {
                'backtest_run_id': int,
                'signals': List[Dict],
                'metrics': {
                    'total_signals': int,
                    'signals_per_symbol': Dict[str, int],
                    'date_range': {'start': str, 'end': str},
                    'symbols_tested': int
                }
            }
        
        Raises:
            ValueError: If rule not found or symbols list is empty
            Exception: If data fetch or processing fails
        """
        # Validate inputs
        if not symbols:
            raise ValueError("Symbols list cannot be empty")
        
        # Load rule from database
        self.current_rule = self.repository.get_rule_by_id(rule_id)
        if not self.current_rule:
            raise ValueError(f"Rule with ID {rule_id} not found")
        
        self.logger.info(f"Starting backtest: {name} ({mode}) with rule '{self.current_rule['name']}'")
        self.logger.info(f"Symbols: {symbols}, Period: {start_date} to {end_date}, Timeframe: {self.timeframe}")
        
        # Reset state
        self.signals = []
        
        # Process each symbol
        signals_per_symbol = {}
        
        for symbol in symbols:
            self.logger.info(f"Processing {symbol}...")
            
            try:
                # Fetch historical data
                candles = await self.data_source.fetch_historical_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=self.timeframe
                )
                
                if not candles:
                    self.logger.warning(f"No data available for {symbol}, skipping")
                    signals_per_symbol[symbol] = 0
                    continue
                
                # Process candles sequentially
                symbol_signals = await self._process_symbol(symbol, candles)
                signals_per_symbol[symbol] = len(symbol_signals)
                
                self.logger.info(f"Generated {len(symbol_signals)} signals for {symbol}")
                
            except Exception as e:
                self.logger.error(f"Error processing {symbol}: {e}")
                signals_per_symbol[symbol] = 0
                continue
        
        # Calculate metrics
        total_signals = len(self.signals)
        metrics = {
            'total_signals': total_signals,
            'signals_per_symbol': signals_per_symbol,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'symbols_tested': len(symbols)
        }
        
        # Save backtest run to database
        backtest_run_id = self.repository.create_backtest_run(
            name=name,
            mode=mode,
            rule_id=rule_id,
            symbols=symbols,
            timeframe=self.timeframe,
            start_date=start_date,
            end_date=end_date,
            data_source=data_source_name,
            total_signals=total_signals,
            metadata=metrics
        )
        
        # Save signals to database
        if self.signals:
            self.repository.create_backtest_signals(backtest_run_id, self.signals)
        
        self.logger.info(f"Backtest completed: {total_signals} total signals generated")
        
        return {
            'backtest_run_id': backtest_run_id,
            'signals': self.signals,
            'metrics': metrics
        }
    
    async def _process_symbol(self, symbol: str, candles: List[Dict]) -> List[Dict]:
        """
        Process candles for a single symbol and generate signals.
        
        Args:
            symbol: Ticker symbol
            candles: List of historical candles
        
        Returns:
            List of signals generated for this symbol
        """
        symbol_signals = []
        
        # Reset indicator engine for this symbol
        self.indicator_engine = IndicatorEngine(timeframe=self.timeframe)
        
        # Prepare rule for evaluation (merge root fields with definition)
        rule_to_evaluate = {**self.current_rule, **self.current_rule['definition']}
        
        # Track cooldown
        last_signal_time = None
        cooldown_seconds = rule_to_evaluate.get('cooldown_sec', 60)
        
        # Feed candles sequentially
        for candle in candles:
            # Convert datetime to Unix timestamp if needed
            timestamp = candle['timestamp']
            if isinstance(timestamp, datetime):
                timestamp = timestamp.timestamp()
            
            # Update indicator engine
            candle_completed = self.indicator_engine.update_candle_data(
                symbol=symbol,
                open_price=candle['open'],
                high=candle['high'],
                low=candle['low'],
                close=candle['close'],
                timestamp=timestamp
            )
            
            # Only check rule when candle completes
            if not candle_completed:
                continue
            
            # Check if we have enough data for indicators
            if not self.indicator_engine.is_symbol_ready(symbol):
                continue
            
            # Check cooldown
            if last_signal_time:
                time_since_last = timestamp - last_signal_time
                if time_since_last < cooldown_seconds:
                    continue
            
            # Get current indicators
            indicators = self.indicator_engine.get_indicators(symbol)
            if not indicators:
                continue
            
            # Evaluate rule (returns boolean only)
            signal_triggered = self.rule_engine.evaluate(
                rule_to_evaluate,
                indicators
            )
            
            # Get signal type from rule definition (default to 'BUY' if not specified)
            signal_type = rule_to_evaluate.get('signal_type', 'BUY')
            
            if signal_triggered:
                # Create signal
                signal = {
                    'symbol': symbol,
                    'timestamp': candle['timestamp'],  # Keep original datetime for display
                    'signal_type': signal_type,
                    'price': candle['close'],
                    'indicators': indicators
                }
                
                symbol_signals.append(signal)
                self.signals.append(signal)
                last_signal_time = timestamp
                
                self.logger.debug(f"Signal generated: {symbol} {signal_type} at {candle['close']} on {candle['timestamp']}")
        
        return symbol_signals
    
    def get_supported_timeframes(self) -> List[str]:
        """
        Get timeframes supported by current data source.
        
        Returns:
            List of timeframe strings
        """
        return self.data_source.get_supported_timeframes()
