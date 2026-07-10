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
from ..data_sources.cached_data_source import CachedDataSource
from ..data_sources.yahoo_data_source import YahooDataSource

class SwingScreeningEngine:
    """
    Swing trading screening engine for batch analysis of multiple tickers.
    
    This engine screens a universe of tickers against a trading rule
    and returns current signal status.
    """

    # Number of trailing candles the per-symbol IndicatorEngine keeps. Warmup
    # fetches are sized to fully saturate this window so that the indicators
    # as-of a given end date are identical regardless of how wide the evaluation
    # window (Latest lookback vs Historical start/end) was specified. This is
    # what makes Latest and Historical screening reproducible for the same end
    # date. Must match the IndicatorEngine instances created in _screen_ticker.
    INDICATOR_HISTORY = 250

    def __init__(self, timeframe: str = '1d'):
        """
        Initialize swing screening engine.

        Args:
            timeframe: Candle timeframe ('1h', '4h', '1d' recommended for swing trading)
        """
        self.timeframe = timeframe
        self.repository = SQLiteRepository()
        self.data_source = CachedDataSource(
            YahooDataSource(),
            self.repository,
            data_source_name='yahoo'
        )
        self.logger = logging.getLogger(__name__)
        self.max_concurrency = 8
        self.max_retries = 3
        
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
        lookback_days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
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
        
        # Calculate evaluation date range. If explicit dates are omitted,
        # keep the existing lookback behavior.
        evaluation_end = end_date or datetime.now()
        evaluation_start = start_date or (evaluation_end - timedelta(days=lookback_days))
        if evaluation_end <= evaluation_start:
            raise ValueError("Screening end date must be later than start date")

        rule_to_evaluate = {**rule, **rule['definition']}
        # Anchor warmup to the end of the evaluation window (not the start) so
        # the fetched candle range depends only on the end date. See #3.
        fetch_start = self._calculate_warmup_start(evaluation_end, rule_to_evaluate)
        
        # Process tickers with bounded concurrency + retry/backoff.
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def guarded_screen(ticker: str) -> Dict[str, Any]:
            async with semaphore:
                return await self._screen_ticker_with_retry(
                    ticker,
                    rule,
                    fetch_start,
                    evaluation_start,
                    evaluation_end
                )

        gathered = await asyncio.gather(*[guarded_screen(t) for t in tickers], return_exceptions=True)
        results = []

        for ticker, result in zip(tickers, gathered):
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
        
        # Log summary
        signals_found = sum(1 for r in results if r['signal'] is not None)
        errors = sum(1 for r in results if r['status'] == 'error')
        self.logger.info(f"Screening complete: {signals_found} signals found, {errors} errors")
        
        return results

    async def _screen_ticker_with_retry(
        self,
        symbol: str,
        rule: Dict,
        fetch_start: datetime,
        evaluation_start: datetime,
        evaluation_end: datetime
    ) -> Dict[str, Any]:
        """
        Screen a single ticker with simple exponential backoff for transient failures.
        """
        last_result = None

        for attempt in range(1, self.max_retries + 1):
            result = await self._screen_ticker(symbol, rule, fetch_start, evaluation_start, evaluation_end)
            last_result = result

            if result.get('status') == 'success':
                return result

            error_message = (result.get('error_message') or '').lower()
            non_retryable = (
                'insufficient data' in error_message or
                'no data available' in error_message or
                'not found' in error_message
            )
            if non_retryable or attempt == self.max_retries:
                return result

            backoff_seconds = 0.5 * (2 ** (attempt - 1))
            self.logger.warning(
                f"Retrying {symbol} after error on attempt {attempt}/{self.max_retries}: "
                f"{result.get('error_message')} (sleep={backoff_seconds:.1f}s)"
            )
            await asyncio.sleep(backoff_seconds)

        return last_result
    
    async def _screen_ticker(
        self,
        symbol: str,
        rule: Dict,
        fetch_start: datetime,
        evaluation_start: datetime,
        evaluation_end: datetime
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
                start_date=fetch_start,
                end_date=evaluation_end,
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
            indicator_engine = IndicatorEngine(
                timeframe=self.timeframe,
                max_history=self.INDICATOR_HISTORY
            )
            rule_engine = RuleEngine()
            rule_to_evaluate = {**rule, **rule['definition']}
            indicator_engine.set_required_operands(rule_to_evaluate)
            latest_evaluation_candle = None
            open_candle = None  # most recent still-forming (non-final) candle in window

            # Feed only CLOSED (final) candles to the indicator engine so the
            # signal reflects a completed candle, never a still-forming one. The
            # forming candle (if any) is evaluated separately below as the
            # "current condition". This also keeps the signal stable intraday and
            # reproducible across Latest/Historical runs (see #3, #5).
            for candle in candles:
                # Convert datetime to Unix timestamp if needed
                timestamp = candle['timestamp']
                if isinstance(timestamp, datetime):
                    candle_dt = timestamp.replace(tzinfo=None) if timestamp.tzinfo else timestamp
                    timestamp = timestamp.timestamp()
                else:
                    candle_dt = datetime.fromtimestamp(timestamp)

                in_evaluation_window = evaluation_start <= candle_dt < evaluation_end

                if not candle.get('is_final', True):
                    # Stash the latest in-window forming candle; don't feed it yet.
                    if in_evaluation_window:
                        open_candle = candle
                    continue

                if in_evaluation_window:
                    latest_evaluation_candle = candle

                indicator_engine.update_candle_data(
                    symbol=symbol,
                    open_price=candle['open'],
                    high=candle['high'],
                    low=candle['low'],
                    close=candle['close'],
                    timestamp=timestamp,
                    volume=candle.get('volume', 0)
                )

            if latest_evaluation_candle is None:
                return {
                    'symbol': symbol,
                    'signal': None,
                    'price': None,
                    'timestamp': None,
                    'indicators': {},
                    'status': 'error',
                    'error_message': 'No data available in selected screening period'
                }

            # The CandleBuilder leaves the most recently fed bar "forming", so
            # force-close it. Without this the signal would be evaluated on the
            # second-to-last candle while reporting the last candle's timestamp
            # (an off-by-one that made completed signals look misaligned, see #5).
            indicator_engine.finalize_current_candle(symbol)

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
            
            # Evaluate rule on the last CLOSED candle -> the signal. The detailed
            # form also tells us which conditions matched, so the UI can explain
            # why a ticker passed screening (see #4).
            detailed = rule_engine.evaluate_detailed(
                rule_to_evaluate,
                indicators
            )
            signal_triggered = detailed['triggered']

            # Get signal type from rule definition (default to 'BUY' if not specified)
            signal_type = rule_to_evaluate.get('signal_type', 'BUY') if signal_triggered else None

            # Current condition: re-evaluate including the still-forming candle so
            # the UI can distinguish a completed signal ("generated at") from the
            # live bar state ("current condition"). None when no forming candle.
            current_condition = None
            current_timestamp = None
            current_price = None
            if open_candle is not None:
                open_ts = open_candle['timestamp']
                open_ts_unix = open_ts.timestamp() if isinstance(open_ts, datetime) else open_ts
                indicator_engine.update_candle_data(
                    symbol=symbol,
                    open_price=open_candle['open'],
                    high=open_candle['high'],
                    low=open_candle['low'],
                    close=open_candle['close'],
                    timestamp=open_ts_unix,
                    volume=open_candle.get('volume', 0)
                )
                # Force-close the forming candle so its own values are reflected.
                indicator_engine.finalize_current_candle(symbol)
                open_indicators = indicator_engine.get_indicators(symbol)
                if open_indicators:
                    current_condition = rule_engine.evaluate(rule_to_evaluate, open_indicators)
                    current_timestamp = open_candle['timestamp']
                    current_price = open_candle['close']

            return {
                'symbol': symbol,
                'signal': signal_type if signal_triggered else None,
                'price': latest_evaluation_candle['close'],
                'timestamp': latest_evaluation_candle['timestamp'],
                'signal_timestamp': latest_evaluation_candle['timestamp'],
                'evaluated_final': True,
                'has_open_candle': open_candle is not None,
                'current_condition': current_condition,
                'current_timestamp': current_timestamp,
                'current_price': current_price,
                'matched_conditions': detailed['matched'],
                'total_conditions': detailed['total'],
                'conditions_detail': detailed['conditions'],
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
        lookback_days: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
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
        return await self.screen_tickers(
            tickers,
            rule_id,
            lookback_days,
            start_date=start_date,
            end_date=end_date
        )

    def _calculate_warmup_start(self, evaluation_end: datetime, rule: Dict[str, Any]) -> datetime:
        """Compute how far back to fetch candles so screening is reproducible.

        The start of the fetch window is derived purely from ``evaluation_end``
        (the end of the screening period), never from the evaluation start or
        lookback length. Combined with fetching enough candles to fully saturate
        the IndicatorEngine deque (``INDICATOR_HISTORY``), this guarantees that
        two runs ending on the same date see the identical trailing candle window
        and therefore compute identical indicators and signals — regardless of
        whether the caller used Latest (lookback) or Historical (start/end) mode.
        See #3.
        """
        rule_warmup_bars = RuleEngine.estimate_rule_warmup(rule)
        # Feed at least a full deque of candles (plus the rule's own warmup and a
        # safety buffer) so recursive indicators (EMA/RSI/ADX) are fully converged
        # and the trailing window is identical across window widths.
        target_bars = max(rule_warmup_bars, self.INDICATOR_HISTORY) + 20
        # Convert the required number of *trading* candles into a calendar span,
        # padding for weekends/holidays so the fetch reliably covers target_bars.
        if self.timeframe == '1d':
            warmup_days = int(target_bars * 1.6) + 10
        elif self.timeframe == '4h':
            warmup_days = int(target_bars / 1.5) + 14
        else:  # '1h'
            warmup_days = int(target_bars / 6) + 7
        return evaluation_end - timedelta(days=warmup_days)
    
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
