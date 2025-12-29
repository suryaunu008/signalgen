"""
Scalping Engine Module

This module provides the main scalping engine with IBKR integration for the SignalGen system.
It orchestrates data flow from IBKR to signal generation and WebSocket broadcasting.

Key Features:
- Real-time data from IBKR TWS/Gateway via ib_insync
- Async, event-driven architecture
- Single event loop for performance
- Isolated from UI thread
- Automatic reconnection handling

Data Flow:
IBKR Bar Update → Indicator Engine → Rule Engine → Signal Generator → WebSocket Emit

MVP Limitations:
- Maximum 5 tickers per run
- Single active watchlist
- No watchlist changes during engine operation
- 1-minute or 5-second bar intervals

Typical Usage:
    engine = ScalpingEngine()
    await engine.connect_to_ibkr()
    await engine.start_engine()
    # Engine runs in background, generating signals
"""

import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Callable
from ib_insync import IB, Stock, BarDataList, BarData, Contract
from datetime import datetime

from ..core.rule_engine import RuleEngine
from ..core.indicator_engine import IndicatorEngine
from ..core.state_machine import StateMachine, EngineState
from ..storage.sqlite_repo import SQLiteRepository
from ..ws.broadcaster import SocketIOBroadcaster

class ScalpingEngine:
    """
    Main scalping engine that orchestrates real-time signal generation.
    
    This class manages the complete flow from IBKR data ingestion to signal
    generation and broadcasting, with proper state management and error handling.
    """
    
    def __init__(self, ib_host: str = '127.0.0.1', ib_port: int = 7497, ib_client_id: int = 1, timeframe: str = '1m'):
        """
        Initialize scalping engine with IBKR connection parameters.
        
        Args:
            ib_host: IBKR TWS/Gateway host address
            ib_port: IBKR TWS/Gateway port (7497 for TWS, 4002 for Gateway)
            ib_client_id: Client ID for IBKR connection (will be overridden with random ID)
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)
        """
        self.ib = IB()
        self.ib_host = ib_host
        self.ib_port = ib_port
        # Use random client ID to avoid conflicts on reconnect
        self.ib_client_id = None  # Will be set on each connect
        
        self.timeframe = timeframe
        self.rule_engine = RuleEngine()
        self.indicator_engine = IndicatorEngine(timeframe=timeframe)
        self.state_machine = StateMachine()
        self.repository = SQLiteRepository()
        self.broadcaster = SocketIOBroadcaster()
        
        # Engine state
        self.is_running = False
        self.is_connected = False
        self.active_watchlist: List[str] = []
        self.active_rule: Optional[Dict] = None
        
        # IBKR subscription tracking
        self.subscribed_contracts: Dict[str, Contract] = {}  # symbol -> contract mapping
        self.contract_symbol_map: Dict[int, str] = {}  # contract conId -> symbol mapping
        self.real_time_bars: Dict[str, object] = {}  # symbol -> RealTimeBars object mapping
        
        # Per-symbol cooldown tracking
        self.symbol_cooldowns: Dict[str, float] = {}  # symbol -> cooldown_end_time mapping
        
        # Reconnection settings
        self.reconnect_enabled = True
        self.reconnect_interval = 5  # seconds
        self.max_reconnect_attempts = 10
        self.reconnect_attempts = 0
        
        # Event loop for async operations
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        
        self.logger = logging.getLogger(__name__)
    
    async def connect_to_ibkr(self) -> bool:
        """
        Connect to IBKR TWS or Gateway with reconnection logic.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Ensure not already connected
            if self.ib.isConnected():
                return True
            
            # Create fresh IB instance to avoid any client ID conflicts
            # This is critical - reusing old instance can cause TWS to reject connection
            self.ib = IB()
            self.ib.autoReconnect = False
            
            # Generate random client ID to avoid conflicts
            self.ib_client_id = random.randint(1000, 9999)
            
            self.logger.info(f"Connecting to IBKR at {self.ib_host}:{self.ib_port} with client ID {self.ib_client_id}")
            await self.ib.connectAsync(self.ib_host, self.ib_port, clientId=self.ib_client_id, timeout=10)
            
            # IMPORTANT: Update is_connected after successful connection
            self.is_connected = True
            self.reconnect_attempts = 0
            self.logger.info(f"Successfully connected to IBKR at {self.ib_host}:{self.ib_port}")
            
            # Set up connection event handlers
            self.ib.disconnectedEvent += self._on_disconnected
            self.ib.errorEvent += self._on_error
            
            return True
                
        except Exception as e:
            self.logger.error(f"Failed to connect to IBKR: {e}")
            self.is_connected = False
            return False
    
    def _on_disconnected(self) -> None:
        """Handle IBKR disconnection event."""
        self.is_connected = False
        self.logger.info("Disconnected from IBKR")
        
        if self.reconnect_enabled and self.is_running:
            self.logger.info("Attempting to reconnect to IBKR...")
            # Schedule reconnection in the event loop
            asyncio.ensure_future(self._reconnect_to_ibkr())
    
    def _on_error(self, reqId, errorCode, errorString, contract) -> None:
        """Handle IBKR error events."""
        self.logger.error(f"IBKR Error {errorCode}: {errorString}")
        
        # Handle specific error codes
        if errorCode == 1100:  # Connection between IB and TWS has been lost
            self.is_connected = False
        elif errorCode == 200:  # No security definition has been found for the request
            self.logger.error(f"Invalid contract: {contract}")
    
    async def _reconnect_to_ibkr(self) -> None:
        """Attempt to reconnect to IBKR with exponential backoff."""
        while self.reconnect_enabled and self.reconnect_attempts < self.max_reconnect_attempts and not self.is_connected:
            self.reconnect_attempts += 1
            wait_time = min(self.reconnect_interval * (2 ** (self.reconnect_attempts - 1)), 60)  # Max 60 seconds
            
            self.logger.info(f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} in {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            
            if await self.connect_to_ibkr():
                # Resubscribe to market data after reconnection
                if self.is_running and self.active_watchlist:
                    await self._subscribe_to_market_data()
                break
            else:
                self.logger.warning(f"Reconnection attempt {self.reconnect_attempts} failed")
        
        if not self.is_connected:
            self.logger.error(f"Failed to reconnect after {self.max_reconnect_attempts} attempts")
            self.reconnect_enabled = False
    
    async def disconnect_from_ibkr(self) -> None:
        """Disconnect from IBKR and cleanup resources."""
        self.reconnect_enabled = False  # Disable reconnection during shutdown
        
        if self.ib.isConnected():
            try:
                # Remove bar update handler if registered
                if hasattr(self, '_bar_handler_registered') and self._bar_handler_registered:
                    try:
                        self.ib.barUpdateEvent -= self._on_bar_update
                        self._bar_handler_registered = False
                    except Exception:
                        pass
                
                # Remove connection event handlers before disconnect
                try:
                    self.ib.disconnectedEvent -= self._on_disconnected
                    self.ib.errorEvent -= self._on_error
                except Exception:
                    pass
                
                # Disable auto-reconnect to prevent silent reconnection
                self.ib.autoReconnect = False
                
                # Disconnect from TWS/Gateway
                self.ib.disconnect()
                self.logger.info("Sent disconnect command to IBKR")
                
                # Short delay to ensure clean disconnect
                await asyncio.sleep(1.0)
            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")
            
        self.is_connected = False
        self.logger.info("Disconnected from IBKR")
        
        # Broadcast disconnection status update
        try:
            status = {
                'is_running': self.is_running,
                'is_connected': False,
                'ibkr_connected': False,
                'state': {'state': 'running' if self.is_running else 'stopped'},
                'active_watchlist': self.active_watchlist.copy(),
                'active_rule': self.active_rule,
                'subscribed_symbols': [],
                'reconnect_enabled': self.reconnect_enabled,
                'reconnect_attempts': self.reconnect_attempts,
                'connection_details': {}
            }
            self.broadcaster.broadcast_engine_status_sync(status)
            self.logger.info("Broadcasted IBKR disconnected status")
        except Exception as e:
            self.logger.error(f"Error broadcasting IBKR disconnection status: {e}")
    
    async def start(self) -> bool:
        """
        Start the scalping engine and connect to IBKR.
        
        Returns:
            bool: True if engine started successfully, False otherwise
        """
        if self.is_running:
            self.logger.warning("Engine is already running")
            return False
        
        # Get the currently running event loop
        try:
            self.event_loop = asyncio.get_running_loop()
            self.logger.debug(f"Using running event loop: {id(self.event_loop)}")
        except RuntimeError:
            # Fallback to get_event_loop if no running loop
            self.event_loop = asyncio.get_event_loop()
            self.logger.debug(f"Using fallback event loop: {id(self.event_loop)}")
        
        # Connect to IBKR
        if not await self.connect_to_ibkr():
            self.logger.error("Failed to connect to IBKR - engine not started")
            return False
        
        self.is_running = True
        self.reconnect_enabled = True
        
        # Broadcast IBKR connected status after is_running is set
        try:
            status = {
                'is_running': True,
                'is_connected': True,
                'ibkr_connected': True,
                'state': {'state': 'running'},
                'active_watchlist': self.active_watchlist.copy(),
                'active_rule': self.active_rule,
                'subscribed_symbols': list(self.subscribed_contracts.keys()),
                'reconnect_enabled': self.reconnect_enabled,
                'reconnect_attempts': self.reconnect_attempts,
                'connection_details': {'host': self.ib_host, 'port': self.ib_port, 'client_id': self.ib_client_id}
            }
            self.broadcaster.broadcast_engine_status_sync(status)
            self.logger.info("Broadcasted engine running + IBKR connected status")
        except Exception as e:
            self.logger.error(f"Error broadcasting status after start: {e}")
        
        self.logger.info("Scalping engine started successfully")
        return True
    
    async def stop(self) -> None:
        """Stop the engine and disconnect from IBKR."""
        if not self.is_running:
            return
        
        self.logger.info("Stopping scalping engine...")
        self.is_running = False
        self.reconnect_enabled = False
        
        # Clear per-symbol cooldowns
        self.symbol_cooldowns.clear()
        self.logger.debug("Cleared all symbol cooldowns")
        
        # Unsubscribe from all market data
        await self.unsubscribe_symbols(self.active_watchlist.copy())
        
        # Disconnect from IBKR
        await self.disconnect_from_ibkr()
        
        # Broadcast engine stopped status
        try:
            status = {
                'is_running': False,
                'is_connected': False,
                'ibkr_connected': False,
                'state': {'state': 'stopped'},
                'active_watchlist': [],
                'active_rule': None,
                'subscribed_symbols': [],
                'reconnect_enabled': False,
                'reconnect_attempts': 0,
                'connection_details': {'host': self.ib_host, 'port': self.ib_port, 'client_id': None}
            }
            self.broadcaster.broadcast_engine_status_sync(status)
            self.logger.info("Broadcasted engine stopped status")
        except Exception as e:
            self.logger.error(f"Error broadcasting engine stopped status: {e}")
        
        self.logger.info("Scalping engine stopped")
    
    async def request_historical_data(self, symbol: str, contract: Contract) -> bool:
        """
        Request historical bar data to populate indicators and initial prices.
        Adjusts duration and bar size based on selected timeframe.
        
        Args:
            symbol: Stock symbol
            contract: IB contract object
            
        Returns:
            bool: True if historical data retrieved successfully
        """
        try:
            self.logger.info(f"Requesting historical data for {symbol} with timeframe {self.timeframe}...")
            
            # Determine duration and bar size based on timeframe
            # Need enough bars for MA200 (200 candles) + buffer
            timeframe_config = {
                '1m': {'duration': '1 D', 'bar_size': '1 min'},      # 1 day of 1-min bars (~390 bars in trading day)
                '5m': {'duration': '5 D', 'bar_size': '5 mins'},     # 5 days of 5-min bars (~390 bars)
                '15m': {'duration': '2 W', 'bar_size': '15 mins'},   # 2 weeks of 15-min bars (~260 bars)
                '1h': {'duration': '2 M', 'bar_size': '1 hour'},     # 2 months of 1-hour bars (~260 bars)
                '4h': {'duration': '6 M', 'bar_size': '4 hours'},    # 6 months of 4-hour bars (~260 bars)
                '1d': {'duration': '1 Y', 'bar_size': '1 day'},      # 1 year of daily bars (~252 bars)
            }
            
            config = timeframe_config.get(self.timeframe, {'duration': '1 D', 'bar_size': '1 min'})
            
            self.logger.info(
                f"Fetching historical data: duration={config['duration']}, "
                f"bar_size={config['bar_size']}"
            )
            
            bars = await self.ib.reqHistoricalDataAsync(
                contract=contract,
                endDateTime='',  # Current time
                durationStr=config['duration'],
                barSizeSetting=config['bar_size'],
                whatToShow='TRADES',  # Changed from MIDPOINT to get volume data
                useRTH=False,  # Include extended hours
                formatDate=1
            )
            
            if not bars:
                self.logger.warning(f"No historical data received for {symbol}")
                return False
            
            self.logger.info(f"Received {len(bars)} historical bars for {symbol}")
            
            # Prepare historical candle data for bulk update
            candle_data_list = []
            for bar in bars:
                if bar.close > 0:
                    timestamp = bar.date.timestamp() if hasattr(bar.date, 'timestamp') else time.time()
                    candle_data_list.append({
                        'open': bar.open,
                        'high': bar.high,
                        'low': bar.low,
                        'close': bar.close,
                        'volume': getattr(bar, 'volume', 0),
                        'timestamp': timestamp
                    })
            
            # Bulk update indicator engine with historical bars (more efficient)
            if candle_data_list:
                self.indicator_engine.bulk_update_candle_data(symbol, candle_data_list)
            
            # Send initial price to frontend if we have data
            if bars:
                last_bar = bars[-1]
                if last_bar.close > 0:
                    # Broadcast initial price
                    timestamp = last_bar.date.timestamp() if hasattr(last_bar.date, 'timestamp') else time.time()
                    await self.broadcaster.broadcast_price_update(symbol, last_bar.close, timestamp)
                    
                    self.logger.info(f"Sent initial price for {symbol}: {last_bar.close}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to request historical data for {symbol}: {e}")
            return False
    
    async def subscribe_symbols(self, symbols: List[str]) -> bool:
        """
        Subscribe to market data for symbols.
        
        Args:
            symbols: List of symbols to subscribe to (max 5 for MVP)
            
        Returns:
            bool: True if subscription successful, False otherwise
        """
        if not self.is_connected:
            self.logger.error("Cannot subscribe - not connected to IBKR")
            return False
        
        if len(symbols) > 5:
            self.logger.error("Cannot subscribe to more than 5 symbols for MVP")
            return False
        
        # Check if already at limit
        total_symbols = len(self.active_watchlist) + len(symbols)
        if total_symbols > 5:
            self.logger.error(f"Cannot subscribe - would exceed 5 symbol limit (current: {len(self.active_watchlist)}, requested: {len(symbols)})")
            return False
        
        try:
            # Initialize symbols in indicator engine
            for symbol in symbols:
                if symbol not in self.active_watchlist:
                    self.indicator_engine.initialize_symbol(symbol)
            
            # Subscribe to real-time bars for each symbol
            for symbol in symbols:
                if symbol not in self.active_watchlist:
                    # Build contract and qualify to ensure valid conId mapping
                    base_contract = Stock(symbol, 'SMART', 'USD')
                    try:
                        qualified = await self.ib.qualifyContractsAsync(base_contract)
                        contract = qualified[0] if qualified else base_contract
                    except Exception as e:
                        self.logger.error(f"Failed to qualify contract for {symbol}: {e}")
                        contract = base_contract

                    # Track qualified contract and symbol mapping using conId
                    self.subscribed_contracts[symbol] = contract
                    if getattr(contract, 'conId', 0):
                        self.contract_symbol_map[contract.conId] = symbol
                    else:
                        # Fallback mapping will be set on first ticker update if needed
                        self.logger.warning(f"Contract for {symbol} has no conId after qualification; mapping deferred")
                    
                    # Request historical data first to populate indicators
                    await self.request_historical_data(symbol, contract)
                    
                    # PRIMARY: Request real-time 5-second bars for price updates
                    # This is the RECOMMENDED approach per ib-insync docs for streaming data
                    # More reliable than tick-by-tick as it won't miss updates
                    bars = self.ib.reqRealTimeBars(
                        contract,
                        5,  # 5-second bars (smallest available)
                        'TRADES',  # Use TRADES for actual market activity
                        False,  # Include extended hours
                        []
                    )
                    self.real_time_bars[symbol] = bars
                    self.logger.info(f"Real-time bars subscription active for {symbol}")
                    
                    # CRITICAL: Attach handler to this specific bars object
                    bars.updateEvent += self._on_bar_update
                    self.logger.info(f"Bars object created: contract={bars.contract.symbol if bars.contract else 'None'}, len={len(bars)}, updateEvent subscribers={len(bars.updateEvent)}")
                    
                    # SECONDARY: Subscribe to market data for instant price display (UI only)
                    # This provides current bid/ask/last for immediate UI updates
                    # Note: Per docs, ticks can go missing; we rely on bars for trading logic
                    ticker = self.ib.reqMktData(
                        contract,
                        '',  # No generic ticks needed
                        False,  # Not a snapshot
                        False,  # Not regulatory snapshot
                        []
                    )
                    ticker.updateEvent += self._on_ticker_update
                    
                    # Log initial ticker state
                    self.logger.info(f"Market data subscription for {symbol}: bid={ticker.bid}, ask={ticker.ask}, last={ticker.last}")
                    
                    # Store ticker mapping for cleanup
                    if not hasattr(self, 'subscribed_tickers'):
                        self.subscribed_tickers = {}
                    self.subscribed_tickers[symbol] = ticker
                    
                    self.active_watchlist.append(symbol)
                    
                    # Verify subscription status
                    self.logger.info(f"[OK] Subscribed: {symbol} | Bars: {len(bars)} | Bar subscribers: {len(bars.updateEvent)} | Ticker subscribers: {len(ticker.updateEvent)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to subscribe to symbols {symbols}: {e}")
            return False
    
    async def unsubscribe_symbols(self, symbols: List[str]) -> None:
        """
        Unsubscribe from market data for symbols.
        
        Args:
            symbols: List of symbols to unsubscribe from
        """
        if not symbols:
            return
        
        try:
            for symbol in symbols:
                if symbol in self.subscribed_contracts:
                    contract = self.subscribed_contracts[symbol]
                    
                    # Cancel real-time bars subscription using stored RealTimeBars object
                    if self.ib.isConnected() and symbol in self.real_time_bars:
                        try:
                            bars = self.real_time_bars[symbol]
                            self.ib.cancelRealTimeBars(bars)
                            self.logger.info(f"Cancelled real-time bars for {symbol}")
                        except Exception as e:
                            self.logger.error(f"Error canceling bars for {symbol}: {e}")
                    
                    # Cancel market data subscription for price tickers
                    if self.ib.isConnected():
                        try:
                            if hasattr(self, 'subscribed_tickers') and symbol in self.subscribed_tickers:
                                self.ib.cancelMktData(contract)
                                del self.subscribed_tickers[symbol]
                                self.logger.info(f"Cancelled market data for {symbol}")
                        except Exception as e:
                            self.logger.error(f"Error canceling market data for {symbol}: {e}")
                    
                    # Now safe to clean up mappings
                    del self.subscribed_contracts[symbol]
                    if contract.conId in self.contract_symbol_map:
                        del self.contract_symbol_map[contract.conId]
                    if symbol in self.real_time_bars:
                        del self.real_time_bars[symbol]
                    
                    # Remove from active watchlist
                    if symbol in self.active_watchlist:
                        self.active_watchlist.remove(symbol)
                    
                    # Clear symbol data from indicator engine
                    self.indicator_engine.clear_symbol_data(symbol)
                    
                    self.logger.info(f"Unsubscribed from real-time data for {symbol}")
        
        except Exception as e:
            self.logger.error(f"Failed to unsubscribe from symbols {symbols}: {e}")
    
    async def set_active_rule(self, rule_id: int) -> bool:
        """
        Set the active rule for signal generation.
        
        Args:
            rule_id: ID of the rule to set as active
            
        Returns:
            bool: True if rule set successfully, False otherwise
        """
        try:
            rule = self.repository.get_rule(rule_id)
            if not rule:
                self.logger.error(f"Rule with ID {rule_id} not found")
                return False
            
            self.active_rule = rule
            self.logger.info(f"Set active rule: {rule['name']} (ID: {rule_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set active rule {rule_id}: {e}")
            return False
    
    async def start_engine(self, watchlist: List[str], rule_id: int) -> bool:
        """
        Start the scalping engine with specified watchlist and rule.
        
        Args:
            watchlist: List of symbols to monitor (max 5 for MVP)
            rule_id: ID of the rule to use for signal generation
            
        Returns:
            bool: True if engine started successfully, False otherwise
        """
        if not await self.start():
            return False
        
        if len(watchlist) > 5:
            self.logger.error("Watchlist cannot exceed 5 symbols for MVP")
            await self.stop()
            return False
        
        # Set active rule
        if not await self.set_active_rule(rule_id):
            await self.stop()
            return False
        
        # Subscribe to market data
        if not await self.subscribe_symbols(watchlist):
            await self.stop()
            return False
        
        self.logger.info(f"Engine started with watchlist: {watchlist}, rule: {self.active_rule['name']}")
        
        # Schedule a debug check after a few seconds to verify tickers are working
        async def delayed_ticker_check():
            await asyncio.sleep(5)
            self.debug_ticker_status()
        
        if self.event_loop:
            asyncio.ensure_future(delayed_ticker_check(), loop=self.event_loop)
        
        return True
    
    async def stop_engine(self) -> None:
        """Stop the scalping engine and cleanup resources."""
        await self.stop()
    
    async def _subscribe_to_market_data(self) -> None:
        """Subscribe to real-time bar data for all symbols in watchlist."""
        await self.subscribe_symbols(self.active_watchlist)
    
    def _on_bar_update(self, bars: BarDataList, hasNewBar: bool) -> None:
        """
        Handle real-time bar updates from IBKR.
        
        Args:
            bars: RealTimeBars object containing bar data from IBKR
            hasNewBar: Whether a new bar was added
        """
        # Log bar updates at debug level
        contract = getattr(bars, 'contract', None)
        if contract:
            symbol = self.contract_symbol_map.get(contract.conId, getattr(contract, 'symbol', 'UNKNOWN'))
            self.logger.debug(f"BAR UPDATE: {symbol} | hasNewBar={hasNewBar} | len={len(bars)}")
        
        if not self.is_running or not bars or not self.is_connected:
            return
        
        # Only process when a new bar is available
        if not hasNewBar:
            return
        
        try:
            # Get contract from the bars object (not from individual bar)
            contract = getattr(bars, 'contract', None)
            if not contract:
                self.logger.warning("Received bar data without contract information")
                return
            
            symbol = self.contract_symbol_map.get(contract.conId)
            if not symbol:
                self.logger.warning(f"Received bar data for unknown contract conId: {contract.conId}")
                return
            
            # Get the most recent bar from the list
            if len(bars) == 0:
                return
            
            bar_data = bars[-1]
            
            # Validate bar data
            if bar_data.close <= 0:
                self.logger.warning(f"Invalid price data for {symbol}: {bar_data.close}")
                return
            
            # Update candle data in indicator engine using OHLC from bar
            # RealTimeBar has 'time' attribute, not 'date'
            # RealTimeBar uses 'open_' (with underscore), not 'open'
            timestamp = bar_data.time.timestamp() if bar_data.time else time.time()
            
            # Update candle builder with full OHLC data
            # Note: RealTimeBar attributes are open_, high, low, close (open has underscore!)
            # RealTimeBar also has volume attribute
            candle_completed = self.indicator_engine.update_candle_data(
                symbol=symbol,
                open_price=bar_data.open_,  # RealTimeBar uses open_ (with underscore)
                high=bar_data.high,
                low=bar_data.low,
                close=bar_data.close,
                timestamp=timestamp,
                volume=getattr(bar_data, 'volume', 0)  # Include volume from real-time bar
            )
            
            # CRITICAL: Broadcast price update to UI from bars (primary source)
            asyncio.create_task(self._broadcast_price_async(symbol, bar_data.close, timestamp))
            self.logger.debug(f"Bar update: {symbol} @ {bar_data.close:.2f}, hasNewBar={hasNewBar}, candle_completed={candle_completed}")
            
            # Get current indicators for this symbol
            indicators = self.indicator_engine.get_indicators(symbol)
            
            # Check if we have sufficient data for rule evaluation
            if not self.indicator_engine.is_symbol_ready(symbol):
                self.logger.debug(f"Insufficient data for {symbol} - skipping rule evaluation")
                return
            
            # Evaluate rule only if symbol is not in cooldown
            if self._can_generate_signal_for_symbol(symbol) and self.active_rule:
                try:
                    # Extract rule definition if stored in nested format
                    rule_to_evaluate = self.active_rule
                    if 'definition' in self.active_rule and isinstance(self.active_rule['definition'], dict):
                        # Merge definition fields with root for evaluation
                        rule_to_evaluate = {**self.active_rule, **self.active_rule['definition']}
                    
                    rule_result = self.rule_engine.evaluate(rule_to_evaluate, indicators)
                    
                    if rule_result:
                        # Generate signal with indicator values for debugging
                        # Use indicators['PRICE'] for consistency with rule evaluation
                        signal_price = indicators.get('PRICE', bar_data.close)
                        self._generate_signal(symbol, signal_price, timestamp, indicators)
                        
                except Exception as e:
                    self.logger.error(f"Error evaluating rule for {symbol}: {e}")
                    
        except KeyError as e:
            self.logger.warning(f"Symbol not initialized in indicator engine: {e}")
        except ValueError as e:
            self.logger.error(f"Invalid price data: {e}")
        except Exception as e:
            self.logger.error(f"Error processing bar update: {e}")
    
    async def _broadcast_price_async(self, symbol: str, price: float, timestamp: float) -> None:
        """Helper to broadcast price update asynchronously from bar handler."""
        try:
            await self.broadcaster.broadcast_price_update(symbol, price, timestamp)
        except Exception as e:
            self.logger.error(f"Failed to broadcast price for {symbol}: {e}")
    
    def _can_generate_signal_for_symbol(self, symbol: str) -> bool:
        """
        Check if a signal can be generated for the given symbol.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            bool: True if symbol is not in cooldown, False otherwise
        """
        current_time = time.time()
        cooldown_end = self.symbol_cooldowns.get(symbol, 0)
        return current_time >= cooldown_end
    
    def _start_symbol_cooldown(self, symbol: str, cooldown_seconds: int) -> None:
        """
        Start cooldown period for a specific symbol.
        
        Args:
            symbol: Symbol to place on cooldown
            cooldown_seconds: Cooldown duration in seconds
        """
        self.symbol_cooldowns[symbol] = time.time() + cooldown_seconds
        self.logger.debug(f"Started {cooldown_seconds}s cooldown for {symbol}")
    
    def _generate_signal(self, symbol: str, price: float, timestamp: float, indicators: Dict[str, float]) -> None:
        """
        Generate and broadcast trading signal with indicator values.
        
        Args:
            symbol: Symbol that generated the signal
            price: Current price at signal generation
            timestamp: Unix timestamp of signal generation
            indicators: Current indicator values at signal generation
        """
        try:
            # Get signal type from rule definition (default to 'BUY' if not specified)
            signal_type = self.active_rule.get('signal_type', 'BUY')
            if 'definition' in self.active_rule and isinstance(self.active_rule['definition'], dict):
                signal_type = self.active_rule['definition'].get('signal_type', signal_type)
            
            # Create signal data with indicator values for debugging
            signal_data = {
                'symbol': symbol,
                'signal_type': signal_type,
                'price': price,
                'rule_id': self.active_rule['id'],
                'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
                'indicators': indicators.copy()  # Include all indicator values
            }
            
            # Log detailed signal generation with relevant indicators
            rule_name = self.active_rule.get('name', 'Unknown')
            self.logger.info(
                f"SIGNAL GENERATED | Symbol: {symbol} | Price: {price:.2f} | Rule: {rule_name}"
            )
            
            # Log key indicators based on rule conditions
            conditions = self.active_rule.get('definition', {}).get('conditions', [])
            if not conditions:
                conditions = self.active_rule.get('conditions', [])
            
            self.logger.info(f"Indicator Values at Signal:")
            for condition in conditions:
                left = condition.get('left', '')
                right = condition.get('right', '')
                op = condition.get('op', '')
                
                # Log left operand value
                if left in indicators:
                    self.logger.info(f"   {left} = {indicators[left]:.4f}")
                
                # Log right operand value if it's an indicator
                if isinstance(right, str) and right in indicators:
                    self.logger.info(f"   {right} = {indicators[right]:.4f}")
                
                # Log the condition evaluation
                left_val = indicators.get(left, left)
                right_val = indicators.get(right, right) if isinstance(right, str) else right
                self.logger.info(f"   Condition: {left} ({left_val:.4f}) {op} {right} ({right_val:.4f})")
            
            # Also log PRICE for reference
            if 'PRICE' in indicators:
                self.logger.info(f"   PRICE = {indicators['PRICE']:.4f}")
            
            # Store signal in database
            signal_id = self.repository.save_signal(signal_data)
            
            # Add signal ID to data for broadcasting
            signal_data['id'] = signal_id
            
            # Broadcast signal via WebSocket
            if self.event_loop and self.broadcaster:
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.broadcaster.broadcast_signal(signal_data),
                        self.event_loop
                    )
                except Exception as e:
                    self.logger.error(f"Failed to schedule signal broadcast: {e}")
            
            # Start cooldown period for this symbol
            cooldown_sec = self.active_rule.get('cooldown_sec', 60)
            self._start_symbol_cooldown(symbol, cooldown_sec)
            
            self.logger.info(f"Signal generated for {symbol} at {price} (ID: {signal_id}), cooldown: {cooldown_sec}s")
            
        except Exception as e:
            self.logger.error(f"Error generating signal for {symbol}: {e}")
    
    def _on_ticker_update(self, ticker) -> None:
        """
        Handle ticker updates (SECONDARY price source for instant UI updates only).
        Per ib-insync docs, ticks can go missing - we rely on reqRealTimeBars for trading logic.
        This provides immediate bid/ask/last for UI display between 5-second bars.
        
        Args:
            ticker: Ticker object from ib_insync
        """
        if not self.is_running or not ticker or not self.is_connected:
            return
        
        # Log ticker updates at debug level
        contract = getattr(ticker, 'contract', None)
        if contract:
            symbol = self.contract_symbol_map.get(contract.conId, getattr(contract, 'symbol', 'UNKNOWN'))
            self.logger.debug(f"TICKER: {symbol} | bid={ticker.bid}, ask={ticker.ask}, last={ticker.last}")
        
        try:
            # Get contract and map to symbol
            contract = getattr(ticker, 'contract', None)
            if not contract:
                return
            
            symbol = self.contract_symbol_map.get(contract.conId)
            if not symbol:
                # Late-binding: map conId to symbol if missing
                derived_symbol = getattr(contract, 'symbol', None)
                if derived_symbol and contract.conId:
                    self.contract_symbol_map[contract.conId] = derived_symbol
                    symbol = derived_symbol
                    self.logger.info(f"Late-mapped ticker conId {contract.conId} to {symbol}")
                else:
                    return
            
            # Get price - prefer last trade, fallback to midpoint
            price = None
            if ticker.last and ticker.last > 0:
                price = ticker.last
            elif ticker.marketPrice() and ticker.marketPrice() > 0:
                price = ticker.marketPrice()
            else:
                return  # No valid price
            
            timestamp = time.time()
            
            # Broadcast to UI for instant updates (bars handle every 5 seconds)
            # This gives smoother UI updates between bars
            asyncio.create_task(self._broadcast_price_async(symbol, price, timestamp))
            
            self.logger.debug(f"Tick: {symbol} @ {price:.2f} (bid={ticker.bid}, ask={ticker.ask}, last={ticker.last})")
                
        except Exception as e:
            self.logger.error(f"Error processing ticker update: {e}")
    
    async def get_engine_status(self) -> Dict:
        """
        Get current engine status and statistics.
        
        Returns:
            Dict: Engine status information
        """
        return {
            'is_running': self.is_running,
            'is_connected': self.is_connected,
            'ibkr_connected': self.is_connected,  # Add field for EngineStatus model compatibility
            'state': self.state_machine.get_state_info(),
            'active_watchlist': self.active_watchlist.copy(),
            'active_rule': self.active_rule,
            'subscribed_symbols': list(self.subscribed_contracts.keys()),
            'reconnect_enabled': self.reconnect_enabled,
            'reconnect_attempts': self.reconnect_attempts,
            'connection_details': {
                'host': self.ib_host,
                'port': self.ib_port,
                'client_id': self.ib_client_id
            },
            'indicator_engine_status': self.indicator_engine.get_engine_status()
        }
    
    def get_engine_status_sync(self) -> Dict:
        """
        Synchronous version of get_engine_status for non-async contexts.
        
        Returns:
            Dict: Engine status information
        """
        try:
            return {
                'is_running': self.is_running,
                'is_connected': self.is_connected,
                'ibkr_connected': self.is_connected,
                'state': self.state_machine.get_state_info(),
                'active_watchlist': self.active_watchlist.copy(),
                'active_rule': self.active_rule,
                'subscribed_symbols': list(self.subscribed_contracts.keys()),
                'reconnect_enabled': self.reconnect_enabled,
                'reconnect_attempts': self.reconnect_attempts,
                'connection_details': {
                    'host': self.ib_host,
                    'port': self.ib_port,
                    'client_id': self.ib_client_id
                },
                'indicator_engine_status': {}  # Skip for now to avoid blocking
            }
        except Exception as e:
            self.logger.error(f"Error getting engine status sync: {e}", exc_info=True)
            return {
                'is_running': False,
                'is_connected': False,
                'ibkr_connected': False,
                'state': {},
                'active_watchlist': [],
                'active_rule': None,
                'subscribed_symbols': [],
                'reconnect_enabled': False,
                'reconnect_attempts': 0,
                'connection_details': {},
                'indicator_engine_status': {}
            }
    
    def get_active_symbols(self) -> List[str]:
        """
        Get list of currently subscribed symbols.
        
        Returns:
            List[str]: List of active symbols
        """
        return self.active_watchlist.copy()
    
    def debug_ticker_status(self) -> None:
        """Debug method to log current ticker states."""
        if not hasattr(self, 'subscribed_tickers'):
            self.logger.warning("No subscribed_tickers attribute")
            return
        
        self.logger.info(f"=== Ticker Status Debug ===")
        for symbol, ticker in self.subscribed_tickers.items():
            try:
                self.logger.info(f"{symbol}: last={ticker.last}, bid={ticker.bid}, ask={ticker.ask}, "
                               f"marketPrice={ticker.marketPrice()}, time={ticker.time}")
            except Exception as e:
                self.logger.error(f"Error checking ticker for {symbol}: {e}")
        self.logger.info(f"=== End Ticker Status ===")
    
    def get_active_rule(self) -> Optional[Dict]:
        """
        Get the currently active rule.
        
        Returns:
            Optional[Dict]: Active rule or None if not set
        """
        return self.active_rule
    
    def is_symbol_subscribed(self, symbol: str) -> bool:
        """
        Check if a symbol is currently subscribed.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            bool: True if symbol is subscribed, False otherwise
        """
        return symbol in self.active_watchlist
    
    async def force_reconnect(self) -> bool:
        """
        Force a reconnection to IBKR.
        
        Returns:
            bool: True if reconnection successful, False otherwise
        """
        self.logger.info("Forcing reconnection to IBKR...")
        self.reconnect_enabled = True
        self.reconnect_attempts = 0
        
        # Disconnect first
        if self.ib.isConnected():
            self.ib.disconnect()
            self.is_connected = False
        
        # Reconnect
        return await self.connect_to_ibkr()
    
    def change_timeframe(self, new_timeframe: str) -> None:
        """
        Change the active timeframe for candle aggregation.
        Note: Engine should be stopped before changing timeframe.
        
        Args:
            new_timeframe: New timeframe to use (1m, 5m, 15m, 1h, 4h, 1d)
            
        Raises:
            ValueError: If timeframe is invalid
            RuntimeError: If engine is running
        """
        if self.is_running:
            raise RuntimeError("Cannot change timeframe while engine is running. Stop the engine first.")
        
        self.timeframe = new_timeframe
        self.indicator_engine.change_timeframe(new_timeframe)
        self.logger.info(f"Timeframe changed to {new_timeframe}")
    
    def get_timeframe(self) -> str:
        """
        Get the current timeframe.
        
        Returns:
            str: Current timeframe (e.g., '1m', '5m')
        """
        return self.timeframe