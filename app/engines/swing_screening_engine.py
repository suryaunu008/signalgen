"""
Swing Screening Engine Module

This module provides batch screening functionality for swing trading using Yahoo Finance data.

Features:
- On-demand screening of multiple tickers
- Uses Yahoo Finance data source
- Works with existing Rule Engine and Indicator Engine
- Returns current signal status for all tickers
- Supports daily, 4h, 1h timeframes (typical for swing trading)

Workflow:
1. User selects ticker universe (list of stocks)
2. User selects rule and timeframe
3. Engine fetches recent data for all tickers
4. Engine evaluates rule against current indicators
5. Returns list of tickers with signals

Typical Usage:
    from app.engines.swing_screening_engine import SwingScreeningEngine
    
    engine = SwingScreeningEngine(timeframe='1d')
    results = await engine.screen_tickers(
        tickers=['AAPL', 'MSFT', 'GOOGL'],
        rule_id=1,
        lookback_days=30
    )
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from ..core.rule_engine import RuleEngine
from ..core.indicator_engine import IndicatorEngine
from ..storage.sqlite_repo import SQLiteRepository
from ..data_sources.yahoo_data_source import YahooDataSource

class SwingScreeningEngine:
    """
    Swing trading screening engine for batch analysis of multiple tickers.
    
    This engine screens a universe of tickers against a trading rule
    and returns current signal status.
    """
    
    def __init__(self, timeframe: str = '1d'):
        """
        Initialize swing screening engine.
        
        Args:
            timeframe: Candle timeframe ('1h', '4h', '1d' recommended for swing trading)
        """
        self.data_source = YahooDataSource()
        self.timeframe = timeframe
        self.repository = SQLiteRepository()
        self.logger = logging.getLogger(__name__)
        
        # Validate timeframe
        if timeframe not in ['1h', '4h', '1d']:
            self.logger.warning(
                f"Timeframe '{timeframe}' is unusual for swing trading. "
                "Recommended: '1h', '4h', or '1d'"
            )
    
    async def screen_tickers(
        self,
        tickers: List[str],
        rule_id: int,
        lookback_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Screen multiple tickers for swing trading signals.
        
        Args:
            tickers: List of ticker symbols to screen
            rule_id: Trading rule ID to apply
            lookback_days: Number of days of historical data to fetch
        
        Returns:
            List of screening results:
            [
                {
                    'symbol': 'AAPL',
                    'signal': 'BUY' or None,
                    'price': 150.25,
                    'timestamp': datetime,
                    'indicators': {...},
                    'status': 'success' or 'error',
                    'error_message': str (if error)
                },
                ...
            ]
        
        Raises:
            ValueError: If rule not found or tickers list is empty
        """
        # Validate inputs
        if not tickers:
            raise ValueError("Tickers list cannot be empty")
        
        # Load rule
        rule = self.repository.get_rule_by_id(rule_id)
        if not rule:
            raise ValueError(f"Rule with ID {rule_id} not found")
        
        self.logger.info(f"Screening {len(tickers)} tickers with rule '{rule['name']}' on {self.timeframe} timeframe")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Process tickers concurrently (but respect rate limits)
        # Yahoo Finance allows ~2000 requests/hour
        # Process in batches of 10 with small delays
        batch_size = 10
        results = []
        
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[self._screen_ticker(ticker, rule, start_date, end_date) for ticker in batch],
                return_exceptions=True
            )
            
            # Handle exceptions
            for ticker, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error screening {ticker}: {result}")
                    results.append({
                        'symbol': ticker,
                        'signal': None,
                        'price': None,
                        'timestamp': None,
                        'indicators': {},
                        'status': 'error',
                        'error_message': str(result)
                    })
                else:
                    results.append(result)
            
            # Small delay between batches to respect rate limits
            if i + batch_size < len(tickers):
                await asyncio.sleep(1)
        
        # Log summary
        signals_found = sum(1 for r in results if r['signal'] is not None)
        errors = sum(1 for r in results if r['status'] == 'error')
        self.logger.info(f"Screening complete: {signals_found} signals found, {errors} errors")
        
        return results
    
    async def _screen_ticker(
        self,
        symbol: str,
        rule: Dict,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Screen a single ticker.
        
        Args:
            symbol: Ticker symbol
            rule: Rule dictionary
            start_date: Start date for data
            end_date: End date for data
        
        Returns:
            Screening result dictionary
        """
        try:
            # Fetch historical data
            candles = await self.data_source.fetch_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe=self.timeframe
            )
            
            if not candles:
                return {
                    'symbol': symbol,
                    'signal': None,
                    'price': None,
                    'timestamp': None,
                    'indicators': {},
                    'status': 'error',
                    'error_message': 'No data available'
                }
            
            # Create indicator engine for this symbol
            indicator_engine = IndicatorEngine(timeframe=self.timeframe)
            rule_engine = RuleEngine()
            
            # Feed all candles to indicator engine
            for candle in candles:
                # Convert datetime to Unix timestamp if needed
                timestamp = candle['timestamp']
                if isinstance(timestamp, datetime):
                    timestamp = timestamp.timestamp()
                
                indicator_engine.update_candle_data(
                    symbol=symbol,
                    open_price=candle['open'],
                    high=candle['high'],
                    low=candle['low'],
                    close=candle['close'],
                    timestamp=timestamp
                )
            
            # Check if we have enough data for indicators
            if not indicator_engine.is_symbol_ready(symbol):
                return {
                    'symbol': symbol,
                    'signal': None,
                    'price': None,
                    'timestamp': None,
                    'indicators': {},
                    'status': 'error',
                    'error_message': 'Insufficient data for indicators (need at least 26 candles)'
                }
            
            # Get current indicators (based on latest candle)
            indicators = indicator_engine.get_indicators(symbol)
            if not indicators:
                return {
                    'symbol': symbol,
                    'signal': None,
                    'price': None,
                    'timestamp': None,
                    'indicators': {},
                    'status': 'error',
                    'error_message': 'Insufficient data for indicators'
                }
            
            # Prepare rule for evaluation (merge root fields with definition)
            rule_to_evaluate = {**rule, **rule['definition']}
            
            # Evaluate rule (returns boolean only)
            signal_triggered = rule_engine.evaluate(
                rule_to_evaluate,
                indicators
            )
            
            # Get signal type from rule definition (default to 'BUY' if not specified)
            signal_type = rule_to_evaluate.get('signal_type', 'BUY') if signal_triggered else None
            
            # Get latest candle
            latest_candle = candles[-1]
            
            return {
                'symbol': symbol,
                'signal': signal_type if signal_triggered else None,
                'price': latest_candle['close'],
                'timestamp': latest_candle['timestamp'],
                'indicators': indicators,
                'status': 'success',
                'error_message': None
            }
            
        except Exception as e:
            self.logger.error(f"Error screening {symbol}: {e}")
            return {
                'symbol': symbol,
                'signal': None,
                'price': None,
                'timestamp': None,
                'indicators': {},
                'status': 'error',
                'error_message': str(e)
            }
    
    async def screen_universe(
        self,
        universe_id: int,
        rule_id: int,
        lookback_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Screen all tickers in a universe.
        
        Args:
            universe_id: Ticker universe ID
            rule_id: Trading rule ID
            lookback_days: Number of days of historical data
        
        Returns:
            List of screening results
        
        Raises:
            ValueError: If universe not found
        """
        # Get universe
        universe = self.repository.get_ticker_universe(universe_id)
        if not universe:
            raise ValueError(f"Ticker universe with ID {universe_id} not found")
        
        tickers = universe['tickers']
        if not tickers:
            self.logger.warning(f"Universe '{universe['name']}' is empty")
            return []
        
        self.logger.info(f"Screening universe '{universe['name']}' with {len(tickers)} tickers")
        
        # Screen all tickers
        return await self.screen_tickers(tickers, rule_id, lookback_days)
    
    def get_supported_timeframes(self) -> List[str]:
        """
        Get supported timeframes for swing trading.
        
        Returns:
            List of recommended timeframes
        """
        return ['1h', '4h', '1d']
    
    def change_timeframe(self, new_timeframe: str) -> None:
        """
        Change the screening timeframe.
        
        Args:
            new_timeframe: New timeframe to use
        
        Raises:
            ValueError: If timeframe not supported
        """
        if new_timeframe not in self.data_source.get_supported_timeframes():
            raise ValueError(
                f"Timeframe '{new_timeframe}' not supported. "
                f"Use one of: {self.data_source.get_supported_timeframes()}"
            )
        
        self.timeframe = new_timeframe
        self.logger.info(f"Timeframe changed to {new_timeframe}")
