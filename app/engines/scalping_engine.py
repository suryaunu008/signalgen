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
    
    def __init__(self, ib_host: str = '127.0.0.1', ib_port: int = 7497, ib_client_id: int = 1):
        """
        Initialize scalping engine with IBKR connection parameters.
        
        Args:
            ib_host: IBKR TWS/Gateway host address
            ib_port: IBKR TWS/Gateway port (7497 for TWS, 4002 for Gateway)
            ib_client_id: Client ID for IBKR connection
        """
        self.ib = IB()
        self.ib_host = ib_host
        self.ib_port = ib_port
        self.ib_client_id = ib_client_id
        
        self.rule_engine = RuleEngine()
        self.indicator_engine = IndicatorEngine()
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
            self.logger.info(f"Connecting to IBKR at {self.ib_host}:{self.ib_port} with client ID {self.ib_client_id}")
            await self.ib.connectAsync(self.ib_host, self.ib_port, clientId=self.ib_client_id)
            
            if self.ib.isConnected():
                self.is_connected = True
                self.reconnect_attempts = 0
                self.logger.info(f"Successfully connected to IBKR at {self.ib_host}:{self.ib_port}")
                
                # Set up connection event handlers
                self.ib.disconnectedEvent += self._on_disconnected
                self.ib.errorEvent += self._on_error
                
                return True
            else:
                self.logger.error("Connection to IBKR failed - not connected after connectAsync")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to IBKR: {e}")
            self.is_connected = False
            return False
    
    async def _on_disconnected(self) -> None:
        """Handle IBKR disconnection event."""
        self.is_connected = False
        self.logger.warning("Disconnected from IBKR")
        
        if self.reconnect_enabled and self.is_running:
            self.logger.info("Attempting to reconnect to IBKR...")
            await self._reconnect_to_ibkr()
    
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
            await self.ib.disconnectAsync()
            self.is_connected = False
            self.logger.info("Disconnected from IBKR")
    
    async def start(self) -> bool:
        """
        Start the scalping engine and connect to IBKR.
        
        Returns:
            bool: True if engine started successfully, False otherwise
        """
        if self.is_running:
            self.logger.warning("Engine is already running")
            return False
        
        # Set event loop
        self.event_loop = asyncio.get_event_loop()
        
        # Connect to IBKR
        if not await self.connect_to_ibkr():
            self.logger.error("Failed to connect to IBKR - engine not started")
            return False
        
        self.is_running = True
        self.reconnect_enabled = True
        
        self.logger.info("Scalping engine started successfully")
        return True
    
    async def stop(self) -> None:
        """Stop the engine and disconnect from IBKR."""
        if not self.is_running:
            return
        
        self.logger.info("Stopping scalping engine...")
        self.is_running = False
        self.reconnect_enabled = False
        
        # Unsubscribe from all market data
        await self.unsubscribe_symbols(self.active_watchlist.copy())
        
        # Disconnect from IBKR
        await self.disconnect_from_ibkr()
        
        self.logger.info("Scalping engine stopped")
    
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
            
            # Set up bar update event handler if not already set
            if not hasattr(self, '_bar_handler_registered'):
                self.ib.realtimeBarEvent += self._on_bar_update
                self._bar_handler_registered = True
            
            # Subscribe to real-time bars for each symbol
            for symbol in symbols:
                if symbol not in self.active_watchlist:
                    contract = Stock(symbol, 'SMART', 'USD')
                    self.subscribed_contracts[symbol] = contract
                    self.contract_symbol_map[contract.conId] = symbol
                    
                    # Request real-time 5-second bars
                    self.ib.reqRealTimeBars(
                        contract,
                        5,  # 5-second bars
                        'MIDPOINT',
                        False,  # Regular trading hours only
                        []
                    )
                    
                    self.active_watchlist.append(symbol)
                    self.logger.info(f"Subscribed to real-time data for {symbol}")
            
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
                    
                    # Cancel real-time bars
                    self.ib.cancelRealTimeBars(contract)
                    
                    # Clean up mappings
                    del self.subscribed_contracts[symbol]
                    if contract.conId in self.contract_symbol_map:
                        del self.contract_symbol_map[contract.conId]
                    
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
        return True
    
    async def stop_engine(self) -> None:
        """Stop the scalping engine and cleanup resources."""
        await self.stop()
    
    async def _subscribe_to_market_data(self) -> None:
        """Subscribe to real-time bar data for all symbols in watchlist."""
        await self.subscribe_symbols(self.active_watchlist)
    
    def _on_bar_update(self, bar_data: BarData) -> None:
        """
        Handle real-time bar updates from IBKR.
        
        Args:
            bar_data: Single bar data from IBKR
        """
        if not self.is_running or not bar_data or not self.is_connected:
            return
        
        try:
            # Extract symbol from contract using our mapping
            contract = getattr(bar_data, 'contract', None)
            if not contract:
                self.logger.warning("Received bar data without contract information")
                return
            
            symbol = self.contract_symbol_map.get(contract.conId)
            if not symbol:
                self.logger.warning(f"Received bar data for unknown contract conId: {contract.conId}")
                return
            
            # Validate bar data
            if bar_data.close <= 0:
                self.logger.warning(f"Invalid price data for {symbol}: {bar_data.close}")
                return
            
            # Update price data in indicator engine
            timestamp = bar_data.date.timestamp() if bar_data.date else time.time()
            self.indicator_engine.update_price_data(
                symbol=symbol,
                price=bar_data.close,
                timestamp=timestamp
            )
            
            # Get current indicators for this symbol
            indicators = self.indicator_engine.get_indicators(symbol)
            
            # Check if we have sufficient data for rule evaluation
            if not self.indicator_engine.is_symbol_ready(symbol):
                self.logger.debug(f"Insufficient data for {symbol} - skipping rule evaluation")
                return
            
            # Evaluate rule only if we can generate a signal
            if self.state_machine.can_generate_signal() and self.active_rule:
                try:
                    rule_result = self.rule_engine.evaluate(self.active_rule, indicators)
                    
                    if rule_result:
                        # Generate signal
                        self._generate_signal(symbol, bar_data.close, timestamp)
                        
                except Exception as e:
                    self.logger.error(f"Error evaluating rule for {symbol}: {e}")
                    
        except KeyError as e:
            self.logger.warning(f"Symbol not initialized in indicator engine: {e}")
        except ValueError as e:
            self.logger.error(f"Invalid price data: {e}")
        except Exception as e:
            self.logger.error(f"Error processing bar update: {e}")
    
    def _generate_signal(self, symbol: str, price: float, timestamp: float) -> None:
        """
        Generate and broadcast trading signal.
        
        Args:
            symbol: Symbol that generated the signal
            price: Current price at signal generation
            timestamp: Unix timestamp of signal generation
        """
        if not self.state_machine.transition_to_signal():
            return
        
        try:
            # Create signal data
            signal_data = {
                'symbol': symbol,
                'price': price,
                'rule_id': self.active_rule['id'],
                'timestamp': datetime.fromtimestamp(timestamp).isoformat()
            }
            
            # Store signal in database
            signal_id = self.repository.save_signal(signal_data)
            
            # Add signal ID to data for broadcasting
            signal_data['id'] = signal_id
            
            # Broadcast signal via WebSocket
            if self.event_loop and self.broadcaster:
                asyncio.create_task(self.broadcaster.broadcast_signal(signal_data))
            
            # Start cooldown period
            cooldown_sec = self.active_rule.get('cooldown_sec', 60)
            self.state_machine.start_cooldown(cooldown_sec)
            
            self.logger.info(f"Signal generated for {symbol} at {price} (ID: {signal_id})")
            
        except Exception as e:
            self.logger.error(f"Error generating signal for {symbol}: {e}")
            # Reset state on error
            self.state_machine.force_wait_state()
    
    async def get_engine_status(self) -> Dict:
        """
        Get current engine status and statistics.
        
        Returns:
            Dict: Engine status information
        """
        return {
            'is_running': self.is_running,
            'is_connected': self.is_connected,
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
    
    def get_active_symbols(self) -> List[str]:
        """
        Get list of currently subscribed symbols.
        
        Returns:
            List[str]: List of active symbols
        """
        return self.active_watchlist.copy()
    
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
            await self.ib.disconnectAsync()
            self.is_connected = False
        
        # Reconnect
        return await self.connect_to_ibkr()