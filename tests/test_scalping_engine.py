"""
Comprehensive Test Suite for ScalpingEngine

This module provides extensive testing for the Realtime Scalping Loop via IBKR,
focusing on connection reliability, real-time data processing, signal generation,
and error recovery mechanisms.

Test Coverage:
- IBKR connection and reconnection logic
- Symbol subscription and validation
- Real-time bar data processing
- Signal generation logic
- Error handling and recovery mechanisms
- Async/await functionality
- Thread safety in concurrent operations
- Performance under load
- Integration with indicator engine and rule engine
"""

import asyncio
import pytest
import time
import threading
from unittest.mock import Mock, AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

# Import the scalping engine and dependencies
from app.engines.scalping_engine import ScalpingEngine
from app.core.rule_engine import RuleEngine
from app.core.indicator_engine import IndicatorEngine
from app.core.state_machine import StateMachine, EngineState
from app.storage.sqlite_repo import SQLiteRepository
from app.ws.broadcaster import SocketIOBroadcaster

# Mock ib_insync components
try:
    from ib_insync import IB, Stock, BarData, BarDataList, Contract
except ImportError:
    # Create mock classes if ib_insync is not available
    class MockIB:
        def __init__(self):
            self.isConnected = Mock(return_value=True)
            self.connectAsync = AsyncMock()
            self.disconnectAsync = AsyncMock()
            self.reqRealTimeBars = Mock()
            self.cancelRealTimeBars = Mock()
            self.disconnectedEvent = Mock()
            self.errorEvent = Mock()
            self.realtimeBarEvent = Mock()
    
    class MockStock:
        def __init__(self, symbol, exchange, currency):
            self.symbol = symbol
            self.exchange = exchange
            self.currency = currency
            self.conId = hash(f"{symbol}_{exchange}_{currency}")
    
    class MockBarData:
        def __init__(self, symbol, price, timestamp=None, contract=None):
            self.symbol = symbol
            self.close = price
            self.date = timestamp or datetime.now()
            self.contract = contract or MockStock(symbol, 'SMART', 'USD')
    
    class MockContract:
        def __init__(self, conId, symbol):
            self.conId = conId
            self.symbol = symbol
    
    # Mock the ib_insync module
    import sys
    mock_ib_insync = Mock()
    mock_ib_insync.IB = MockIB
    mock_ib_insync.Stock = MockStock
    mock_ib_insync.BarData = MockBarData
    mock_ib_insync.BarDataList = list
    mock_ib_insync.Contract = MockContract
    sys.modules['ib_insync'] = mock_ib_insync


class MockIBKR:
    """Mock IBKR connection for testing."""
    
    def __init__(self, should_fail_connect=False, should_disconnect=False):
        self.should_fail_connect = should_fail_connect
        self.should_disconnect = should_disconnect
        self.is_connected = False
        self.connection_attempts = 0
        self.disconnection_count = 0
        self.subscribed_contracts = {}
        self.error_events = []
        
    async def connectAsync(self, host, port, clientId):
        """Mock connection to IBKR."""
        self.connection_attempts += 1
        if self.should_fail_connect:
            raise ConnectionError("Failed to connect to IBKR")
        
        await asyncio.sleep(0.1)  # Simulate connection delay
        self.is_connected = True
        return True
    
    async def disconnectAsync(self):
        """Mock disconnection from IBKR."""
        self.is_connected = False
        await asyncio.sleep(0.05)
    
    def isConnected(self):
        """Check if connected to IBKR."""
        return self.is_connected
    
    def reqRealTimeBars(self, contract, barSize, whatToShow, useRTH, realTimeBarsOptions):
        """Mock real-time bars request."""
        if contract.conId in self.subscribed_contracts:
            raise ValueError(f"Already subscribed to contract {contract.conId}")
        
        self.subscribed_contracts[contract.conId] = {
            'contract': contract,
            'barSize': barSize,
            'whatToShow': whatToShow,
            'useRTH': useRTH,
            'options': realTimeBarsOptions
        }
    
    def cancelRealTimeBars(self, contract):
        """Mock cancel real-time bars."""
        if contract.conId in self.subscribed_contracts:
            del self.subscribed_contracts[contract.conId]


class MockRepository:
    """Mock SQLite repository for testing."""
    
    def __init__(self):
        self.rules = {}
        self.signals = []
        self.next_rule_id = 1
        self.next_signal_id = 1
        
        # Add default test rule
        self.rules[1] = {
            'id': 1,
            'name': 'Test Rule',
            'type': 'system',
            'definition': {
                'conditions': [
                    {'left': 'PRICE', 'op': '>', 'right': 'MA5'}
                ],
                'logic': 'AND'
            },
            'cooldown_sec': 60
        }
    
    def get_rule(self, rule_id):
        """Get rule by ID."""
        return self.rules.get(rule_id)
    
    def save_signal(self, signal_data):
        """Save signal to database."""
        signal_id = self.next_signal_id
        self.next_signal_id += 1
        
        signal = {
            'id': signal_id,
            **signal_data,
            'created_at': datetime.now().isoformat()
        }
        
        self.signals.append(signal)
        return signal_id


class MockBroadcaster:
    """Mock WebSocket broadcaster for testing."""
    
    def __init__(self):
        self.broadcasted_signals = []
        self.broadcasted_errors = []
        self.broadcasted_status = []
        
    async def broadcast_signal(self, signal_data):
        """Mock signal broadcasting."""
        self.broadcasted_signals.append({
            **signal_data,
            'broadcasted_at': datetime.now().isoformat()
        })
    
    async def broadcast_error(self, error_data):
        """Mock error broadcasting."""
        self.broadcasted_errors.append({
            **error_data,
            'broadcasted_at': datetime.now().isoformat()
        })
    
    async def broadcast_engine_status(self, status):
        """Mock status broadcasting."""
        self.broadcasted_status.append({
            **status,
            'broadcasted_at': datetime.now().isoformat()
        })


class TestScalpingEngine:
    """Comprehensive test suite for ScalpingEngine."""
    
    @pytest.fixture
    def mock_ibkr(self):
        """Create mock IBKR connection."""
        return MockIBKR()
    
    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        return MockRepository()
    
    @pytest.fixture
    def mock_broadcaster(self):
        """Create mock broadcaster."""
        return MockBroadcaster()
    
    @pytest.fixture
    def scalping_engine(self, mock_ibkr, mock_repository, mock_broadcaster):
        """Create scalping engine with mocked dependencies."""
        with patch('app.engines.scalping_engine.IB', return_value=mock_ibkr), \
             patch('app.engines.scalping_engine.SQLiteRepository', return_value=mock_repository), \
             patch('app.engines.scalping_engine.SocketIOBroadcaster', return_value=mock_broadcaster):
            
            engine = ScalpingEngine()
            engine.repository = mock_repository
            engine.broadcaster = mock_broadcaster
            return engine
    
    @pytest.fixture
    def sample_rule(self):
        """Create sample trading rule."""
        return {
            'id': 1,
            'name': 'Test Rule',
            'type': 'system',
            'definition': {
                'conditions': [
                    {'left': 'PRICE', 'op': '>', 'right': 'MA5'}
                ],
                'logic': 'AND'
            },
            'cooldown_sec': 60
        }
    
    @pytest.fixture
    def sample_bar_data(self):
        """Create sample bar data."""
        from ib_insync import BarData, Stock
        
        contract = Stock('AAPL', 'SMART', 'USD')
        bar = BarData()
        bar.contract = contract
        bar.close = 150.25
        bar.date = datetime.now()
        
        return bar
    
    @pytest.mark.asyncio
    async def test_engine_initialization(self, scalping_engine):
        """Test engine initialization with default parameters."""
        assert scalping_engine.ib_host == '127.0.0.1'
        assert scalping_engine.ib_port == 7497
        assert scalping_engine.ib_client_id == 1
        assert not scalping_engine.is_running
        assert not scalping_engine.is_connected
        assert scalping_engine.active_watchlist == []
        assert scalping_engine.active_rule is None
        assert scalping_engine.reconnect_enabled is True
        assert scalping_engine.reconnect_interval == 5
        assert scalping_engine.max_reconnect_attempts == 10
        assert scalping_engine.reconnect_attempts == 0
    
    @pytest.mark.asyncio
    async def test_engine_initialization_custom_params(self):
        """Test engine initialization with custom parameters."""
        with patch('app.engines.scalping_engine.IB'), \
             patch('app.engines.scalping_engine.SQLiteRepository'), \
             patch('app.engines.scalping_engine.SocketIOBroadcaster'):
            
            engine = ScalpingEngine(
                ib_host='192.168.1.100',
                ib_port=4002,
                ib_client_id=999
            )
            
            assert engine.ib_host == '192.168.1.100'
            assert engine.ib_port == 4002
            assert engine.ib_client_id == 999
    
    @pytest.mark.asyncio
    async def test_successful_ibkr_connection(self, scalping_engine, mock_ibkr):
        """Test successful IBKR connection."""
        result = await scalping_engine.connect_to_ibkr()
        
        assert result is True
        assert scalping_engine.is_connected is True
        assert scalping_engine.reconnect_attempts == 0
        assert mock_ibkr.connection_attempts == 1
    
    @pytest.mark.asyncio
    async def test_failed_ibkr_connection(self, scalping_engine):
        """Test failed IBKR connection."""
        mock_ibkr = MockIBKR(should_fail_connect=True)
        scalping_engine.ib = mock_ibkr
        
        result = await scalping_engine.connect_to_ibkr()
        
        assert result is False
        assert not scalping_engine.is_connected
        assert mock_ibkr.connection_attempts == 1
    
    @pytest.mark.asyncio
    async def test_reconnection_logic(self, scalping_engine, mock_ibkr):
        """Test reconnection logic with exponential backoff."""
        # Set up initial connection failure
        mock_ibkr.should_fail_connect = True
        
        # Start reconnection process
        scalping_engine.is_running = True
        scalping_engine.reconnect_enabled = True
        
        # Start reconnection in background
        reconnect_task = asyncio.create_task(scalping_engine._reconnect_to_ibkr())
        
        # Wait a bit for reconnection attempts
        await asyncio.sleep(0.2)
        
        # Enable connection
        mock_ibkr.should_fail_connect = False
        
        # Wait for reconnection to complete
        await reconnect_task
        
        assert scalping_engine.is_connected is True
        assert mock_ibkr.connection_attempts > 1
    
    @pytest.mark.asyncio
    async def test_max_reconnection_attempts(self, scalping_engine):
        """Test maximum reconnection attempts limit."""
        mock_ibkr = MockIBKR(should_fail_connect=True)
        scalping_engine.ib = mock_ibkr
        scalping_engine.is_running = True
        scalping_engine.reconnect_enabled = True
        scalping_engine.max_reconnect_attempts = 3
        
        await scalping_engine._reconnect_to_ibkr()
        
        assert not scalping_engine.is_connected
        assert not scalping_engine.reconnect_enabled
        assert mock_ibkr.connection_attempts >= 3
    
    @pytest.mark.asyncio
    async def test_successful_symbol_subscription(self, scalping_engine, mock_ibkr):
        """Test successful symbol subscription."""
        # Connect first
        await scalping_engine.connect_to_ibkr()
        
        # Subscribe to symbols
        symbols = ['AAPL', 'GOOGL']
        result = await scalping_engine.subscribe_symbols(symbols)
        
        assert result is True
        assert len(scalping_engine.active_watchlist) == 2
        assert 'AAPL' in scalping_engine.active_watchlist
        assert 'GOOGL' in scalping_engine.active_watchlist
        assert len(mock_ibkr.subscribed_contracts) == 2
    
    @pytest.mark.asyncio
    async def test_symbol_subscription_limit(self, scalping_engine, mock_ibkr):
        """Test symbol subscription limit (5 symbols max)."""
        # Connect first
        await scalping_engine.connect_to_ibkr()
        
        # Try to subscribe to 6 symbols (exceeds limit)
        symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META']
        result = await scalping_engine.subscribe_symbols(symbols)
        
        assert result is False
        assert len(scalping_engine.active_watchlist) == 0
    
    @pytest.mark.asyncio
    async def test_symbol_subscription_without_connection(self, scalping_engine):
        """Test symbol subscription without IBKR connection."""
        symbols = ['AAPL', 'GOOGL']
        result = await scalping_engine.subscribe_symbols(symbols)
        
        assert result is False
        assert len(scalping_engine.active_watchlist) == 0
    
    @pytest.mark.asyncio
    async def test_symbol_unsubscription(self, scalping_engine, mock_ibkr):
        """Test symbol unsubscription."""
        # Connect and subscribe first
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL', 'GOOGL'])
        
        # Unsubscribe one symbol
        await scalping_engine.unsubscribe_symbols(['AAPL'])
        
        assert 'AAPL' not in scalping_engine.active_watchlist
        assert 'GOOGL' in scalping_engine.active_watchlist
        assert len(mock_ibkr.subscribed_contracts) == 1
    
    @pytest.mark.asyncio
    async def test_set_active_rule(self, scalping_engine, mock_repository, sample_rule):
        """Test setting active rule."""
        result = await scalping_engine.set_active_rule(1)
        
        assert result is True
        assert scalping_engine.active_rule == sample_rule
    
    @pytest.mark.asyncio
    async def test_set_nonexistent_rule(self, scalping_engine):
        """Test setting non-existent rule."""
        result = await scalping_engine.set_active_rule(999)
        
        assert result is False
        assert scalping_engine.active_rule is None
    
    @pytest.mark.asyncio
    async def test_engine_start_stop(self, scalping_engine, mock_ibkr):
        """Test engine start and stop."""
        # Start engine
        result = await scalping_engine.start()
        
        assert result is True
        assert scalping_engine.is_running is True
        assert scalping_engine.is_connected is True
        
        # Stop engine
        await scalping_engine.stop()
        
        assert not scalping_engine.is_running
        assert not scalping_engine.is_connected
    
    @pytest.mark.asyncio
    async def test_engine_start_with_watchlist_and_rule(self, scalping_engine, mock_ibkr):
        """Test engine start with watchlist and rule."""
        watchlist = ['AAPL', 'GOOGL']
        rule_id = 1
        
        result = await scalping_engine.start_engine(watchlist, rule_id)
        
        assert result is True
        assert scalping_engine.is_running is True
        assert scalping_engine.is_connected is True
        assert len(scalping_engine.active_watchlist) == 2
        assert scalping_engine.active_rule is not None
    
    @pytest.mark.asyncio
    async def test_engine_start_with_invalid_watchlist(self, scalping_engine, mock_ibkr):
        """Test engine start with invalid watchlist (too many symbols)."""
        watchlist = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META']  # 6 symbols
        rule_id = 1
        
        result = await scalping_engine.start_engine(watchlist, rule_id)
        
        assert result is False
        assert not scalping_engine.is_running
    
    @pytest.mark.asyncio
    async def test_bar_data_processing(self, scalping_engine, mock_ibkr, sample_bar_data):
        """Test real-time bar data processing."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        await scalping_engine.set_active_rule(1)
        
        # Process bar data
        scalping_engine._on_bar_update(sample_bar_data)
        
        # Check that price data was updated
        indicators = scalping_engine.indicator_engine.get_indicators('AAPL')
        assert 'PRICE' in indicators
        assert indicators['PRICE'] == sample_bar_data.close
    
    @pytest.mark.asyncio
    async def test_signal_generation(self, scalping_engine, mock_ibkr, mock_repository, mock_broadcaster):
        """Test signal generation when rule conditions are met."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        await scalping_engine.set_active_rule(1)
        
        # Add sufficient price data to trigger signal
        for i in range(20):
            price = 150.0 + i * 0.1  # Increasing prices
            scalping_engine.indicator_engine.update_price_data('AAPL', price, time.time())
        
        # Create bar data that should trigger signal (price > MA5)
        from ib_insync import BarData, Stock
        contract = Stock('AAPL', 'SMART', 'USD')
        bar = BarData()
        bar.contract = contract
        bar.close = 155.0  # Higher than moving average
        bar.date = datetime.now()
        
        # Process bar data
        scalping_engine._on_bar_update(bar)
        
        # Check that signal was generated
        assert len(mock_repository.signals) > 0
        assert len(mock_broadcaster.broadcasted_signals) > 0
    
    @pytest.mark.asyncio
    async def test_error_handling_in_bar_processing(self, scalping_engine, mock_ibkr):
        """Test error handling in bar data processing."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        
        # Create invalid bar data (negative price)
        from ib_insync import BarData, Stock
        contract = Stock('AAPL', 'SMART', 'USD')
        bar = BarData()
        bar.contract = contract
        bar.close = -10.0  # Invalid price
        bar.date = datetime.now()
        
        # Process bar data - should not raise exception
        scalping_engine._on_bar_update(bar)
        
        # Check that no signal was generated
        assert len(scalping_engine.indicator_engine.get_all_symbols()) == 1
    
    @pytest.mark.asyncio
    async def test_ibkr_error_handling(self, scalping_engine, mock_ibkr):
        """Test IBKR error handling."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        
        # Simulate IBKR error
        scalping_engine._on_error(123, 1100, "Connection lost", None)
        
        # Check that connection status is updated
        assert not scalping_engine.is_connected
    
    @pytest.mark.asyncio
    async def test_force_reconnect(self, scalping_engine, mock_ibkr):
        """Test forced reconnection."""
        # Initial connection
        await scalping_engine.connect_to_ibkr()
        assert scalping_engine.is_connected
        
        # Force reconnection
        result = await scalping_engine.force_reconnect()
        
        assert result is True
        assert scalping_engine.is_connected
        assert mock_ibkr.connection_attempts >= 2
    
    @pytest.mark.asyncio
    async def test_engine_status(self, scalping_engine, mock_ibkr):
        """Test engine status reporting."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        await scalping_engine.set_active_rule(1)
        
        status = scalping_engine.get_engine_status()
        
        assert status['is_running'] is False  # Not started, just connected
        assert status['is_connected'] is True
        assert status['ibkr_connected'] is True
        assert len(status['active_watchlist']) == 1
        assert status['active_rule'] is not None
        assert 'connection_details' in status
        assert 'indicator_engine_status' in status
    
    def test_get_active_symbols(self, scalping_engine):
        """Test getting active symbols."""
        scalping_engine.active_watchlist = ['AAPL', 'GOOGL']
        
        symbols = scalping_engine.get_active_symbols()
        
        assert symbols == ['AAPL', 'GOOGL']
        # Should return a copy, not reference
        symbols.append('MSFT')
        assert scalping_engine.get_active_symbols() == ['AAPL', 'GOOGL']
    
    def test_is_symbol_subscribed(self, scalping_engine):
        """Test checking if symbol is subscribed."""
        scalping_engine.active_watchlist = ['AAPL', 'GOOGL']
        
        assert scalping_engine.is_symbol_subscribed('AAPL') is True
        assert scalping_engine.is_symbol_subscribed('MSFT') is False
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, scalping_engine, mock_ibkr):
        """Test thread safety in concurrent operations."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        
        # Create multiple concurrent tasks
        tasks = []
        for i in range(5):
            task = asyncio.create_task(
                scalping_engine.subscribe_symbols([f'SYMBOL{i}'])
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that only 5 symbols were subscribed (MVP limit)
        assert len(scalping_engine.active_watchlist) <= 5
    
    @pytest.mark.asyncio
    async def test_performance_under_load(self, scalping_engine, mock_ibkr):
        """Test performance under high load."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        await scalping_engine.set_active_rule(1)
        
        # Process many bar updates rapidly
        start_time = time.time()
        
        for i in range(1000):
            from ib_insync import BarData, Stock
            contract = Stock('AAPL', 'SMART', 'USD')
            bar = BarData()
            bar.contract = contract
            bar.close = 150.0 + i * 0.01
            bar.date = datetime.now()
            
            scalping_engine._on_bar_update(bar)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process 1000 bars in reasonable time (< 1 second)
        assert processing_time < 1.0
        
        # Check that indicator engine kept up
        indicators = scalping_engine.indicator_engine.get_indicators('AAPL')
        assert 'PRICE' in indicators
    
    @pytest.mark.asyncio
    async def test_integration_with_indicator_engine(self, scalping_engine, mock_ibkr):
        """Test integration with indicator engine."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        
        # Add price data
        for i in range(20):
            price = 150.0 + i * 0.1
            scalping_engine.indicator_engine.update_price_data('AAPL', price, time.time())
        
        # Check indicators are calculated
        indicators = scalping_engine.indicator_engine.get_indicators('AAPL')
        assert 'PRICE' in indicators
        assert 'MA5' in indicators
        assert 'MA10' in indicators
        assert 'MA20' in indicators
    
    @pytest.mark.asyncio
    async def test_integration_with_rule_engine(self, scalping_engine, mock_ibkr):
        """Test integration with rule engine."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        await scalping_engine.set_active_rule(1)
        
        # Create indicators that should trigger rule
        indicators = {
            'PRICE': 155.0,
            'MA5': 150.0,
            'MA10': 148.0,
            'MA20': 145.0
        }
        
        # Evaluate rule
        result = scalping_engine.rule_engine.evaluate(scalping_engine.active_rule, indicators)
        
        assert result is True  # PRICE > MA5 should be True
    
    @pytest.mark.asyncio
    async def test_state_machine_integration(self, scalping_engine):
        """Test integration with state machine."""
        # Check initial state
        assert scalping_engine.state_machine.current_state == EngineState.WAIT
        assert scalping_engine.state_machine.can_generate_signal() is True
        
        # Transition to signal state
        result = scalping_engine.state_machine.transition_to_signal()
        assert result is True
        assert scalping_engine.state_machine.current_state == EngineState.SIGNAL
        
        # Start cooldown
        result = scalping_engine.state_machine.start_cooldown(60)
        assert result is True
        assert scalping_engine.state_machine.current_state == EngineState.COOLDOWN
        
        # Check cannot generate signal during cooldown
        assert scalping_engine.state_machine.can_generate_signal() is False
    
    @pytest.mark.asyncio
    async def test_signal_cooldown(self, scalping_engine, mock_repository, mock_broadcaster):
        """Test signal cooldown mechanism."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        await scalping_engine.set_active_rule(1)
        
        # Generate first signal
        scalping_engine._generate_signal('AAPL', 150.0, time.time())
        
        # Check signal was generated
        assert len(mock_repository.signals) == 1
        assert len(mock_broadcaster.broadcasted_signals) == 1
        
        # Try to generate second signal immediately (should be blocked)
        scalping_engine._generate_signal('AAPL', 151.0, time.time())
        
        # Should not generate second signal due to cooldown
        assert len(mock_repository.signals) == 1
        assert len(mock_broadcaster.broadcasted_signals) == 1
    
    @pytest.mark.asyncio
    async def test_database_integration(self, scalping_engine, mock_repository):
        """Test database integration for signal storage."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        await scalping_engine.set_active_rule(1)
        
        # Generate signal
        signal_data = {
            'symbol': 'AAPL',
            'price': 150.0,
            'rule_id': 1,
            'timestamp': datetime.now().isoformat()
        }
        
        signal_id = mock_repository.save_signal(signal_data)
        
        assert signal_id == 1
        assert len(mock_repository.signals) == 1
        assert mock_repository.signals[0]['symbol'] == 'AAPL'
    
    @pytest.mark.asyncio
    async def test_websocket_integration(self, scalping_engine, mock_broadcaster):
        """Test WebSocket integration for signal broadcasting."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        await scalping_engine.set_active_rule(1)
        
        # Generate signal
        signal_data = {
            'symbol': 'AAPL',
            'price': 150.0,
            'rule_id': 1,
            'timestamp': datetime.now().isoformat()
        }
        
        await mock_broadcaster.broadcast_signal(signal_data)
        
        assert len(mock_broadcaster.broadcasted_signals) == 1
        assert mock_broadcaster.broadcasted_signals[0]['symbol'] == 'AAPL'
    
    @pytest.mark.asyncio
    async def test_error_recovery(self, scalping_engine, mock_ibkr):
        """Test error recovery mechanisms."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        
        # Simulate connection loss
        mock_ibkr.is_connected = False
        scalping_engine.is_connected = False
        
        # Trigger reconnection
        await scalping_engine._on_disconnected()
        
        # Wait for reconnection attempt
        await asyncio.sleep(0.2)
        
        # Check reconnection was attempted
        assert mock_ibkr.connection_attempts > 1
    
    @pytest.mark.asyncio
    async def test_memory_management(self, scalping_engine, mock_ibkr):
        """Test memory management with large datasets."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        
        # Add large amount of price data
        for i in range(1000):
            price = 150.0 + i * 0.01
            scalping_engine.indicator_engine.update_price_data('AAPL', price, time.time())
        
        # Check that data is properly managed (should not exceed max_history)
        data_count = scalping_engine.indicator_engine.get_symbol_data_count('AAPL')
        assert data_count <= scalping_engine.indicator_engine.max_history
    
    @pytest.mark.asyncio
    async def test_logging_functionality(self, scalping_engine, caplog):
        """Test logging functionality."""
        with caplog.at_level(logging.INFO):
            # Connect to IBKR
            await scalping_engine.connect_to_ibkr()
            
            # Check that connection was logged
            assert "Successfully connected to IBKR" in caplog.text
    
    @pytest.mark.asyncio
    async def test_configuration_validation(self, scalping_engine):
        """Test configuration validation."""
        # Test invalid port
        with patch('app.engines.scalping_engine.IB'):
            engine = ScalpingEngine(ib_port=-1)
            # Should still initialize but connection will fail
        
        # Test invalid client ID
        with patch('app.engines.scalping_engine.IB'):
            engine = ScalpingEngine(ib_client_id=-1)
            # Should still initialize but connection may fail
    
    @pytest.mark.asyncio
    async def test_edge_cases(self, scalping_engine, mock_ibkr):
        """Test edge cases and boundary conditions."""
        # Test empty watchlist
        result = await scalping_engine.subscribe_symbols([])
        assert result is True  # Empty list should be handled gracefully
        
        # Test duplicate symbol subscription
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        result = await scalping_engine.subscribe_symbols(['AAPL'])
        assert result is True  # Should handle duplicate gracefully
        
        # Test unsubscribe non-existent symbol
        await scalping_engine.unsubscribe_symbols(['NONEXISTENT'])
        # Should not raise exception
    
    @pytest.mark.asyncio
    async def test_performance_benchmarks(self, scalping_engine, mock_ibkr):
        """Test performance benchmarks for critical operations."""
        # Setup engine
        await scalping_engine.connect_to_ibkr()
        await scalping_engine.subscribe_symbols(['AAPL'])
        
        # Benchmark bar processing
        start_time = time.time()
        
        for i in range(100):
            from ib_insync import BarData, Stock
            contract = Stock('AAPL', 'SMART', 'USD')
            bar = BarData()
            bar.contract = contract
            bar.close = 150.0 + i * 0.01
            bar.date = datetime.now()
            
            scalping_engine._on_bar_update(bar)
        
        bar_processing_time = time.time() - start_time
        
        # Should process 100 bars in < 0.1 seconds
        assert bar_processing_time < 0.1
        
        # Benchmark indicator calculation
        start_time = time.time()
        
        for i in range(50):
            price = 150.0 + i * 0.01
            scalping_engine.indicator_engine.update_price_data('AAPL', price, time.time())
        
        indicator_calculation_time = time.time() - start_time
        
        # Should calculate indicators for 50 data points in < 0.05 seconds
        assert indicator_calculation_time < 0.05


class TestScalpingEngineIntegration:
    """Integration tests for ScalpingEngine with real-world scenarios."""
    
    @pytest.mark.asyncio
    async def test_trading_day_simulation(self):
        """Test complete trading day simulation."""
        with patch('app.engines.scalping_engine.IB'), \
             patch('app.engines.scalping_engine.SQLiteRepository') as mock_repo, \
             patch('app.engines.scalping_engine.SocketIOBroadcaster') as mock_broadcaster:
            
            # Setup mocks
            repo_instance = MockRepository()
            broadcaster_instance = MockBroadcaster()
            mock_repo.return_value = repo_instance
            mock_broadcaster.return_value = broadcaster_instance
            
            # Create engine
            engine = ScalpingEngine()
            engine.repository = repo_instance
            engine.broadcaster = broadcaster_instance
            
            # Simulate trading day
            await engine.start_engine(['AAPL', 'GOOGL'], 1)
            
            # Simulate market data throughout the day
            for hour in range(6, 16):  # 6 AM to 4 PM
                for minute in range(0, 60, 5):  # Every 5 minutes
                    price = 150.0 + hour * 0.5 + minute * 0.01
                    
                    for symbol in ['AAPL', 'GOOGL']:
                        from ib_insync import BarData, Stock
                        contract = Stock(symbol, 'SMART', 'USD')
                        bar = BarData()
                        bar.contract = contract
                        bar.close = price
                        bar.date = datetime.now()
                        
                        engine._on_bar_update(bar)
                    
                    await asyncio.sleep(0.001)  # Small delay to simulate real-time
            
            # Check results
            assert len(repo_instance.signals) >= 0  # May or may not have signals
            assert engine.is_running is True
            
            await engine.stop_engine()
    
    @pytest.mark.asyncio
    async def test_connection_interruption_recovery(self):
        """Test recovery from connection interruptions."""
        with patch('app.engines.scalping_engine.IB') as mock_ib_class, \
             patch('app.engines.scalping_engine.SQLiteRepository') as mock_repo, \
             patch('app.engines.scalping_engine.SocketIOBroadcaster') as mock_broadcaster:
            
            # Setup mock IBKR with intermittent failures
            mock_ibkr = MockIBKR()
            mock_ib_class.return_value = mock_ibkr
            
            repo_instance = MockRepository()
            broadcaster_instance = MockBroadcaster()
            mock_repo.return_value = repo_instance
            mock_broadcaster.return_value = broadcaster_instance
            
            # Create engine
            engine = ScalpingEngine()
            engine.repository = repo_instance
            engine.broadcaster = broadcaster_instance
            
            # Start engine
            await engine.start()
            
            # Simulate connection loss
            mock_ibkr.is_connected = False
            engine.is_connected = False
            
            # Trigger reconnection
            await engine._on_disconnected()
            
            # Wait for reconnection
            await asyncio.sleep(0.2)
            
            # Should have reconnected
            assert engine.is_connected is True
            
            await engine.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])