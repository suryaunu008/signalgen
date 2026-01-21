"""
WebSocket Broadcaster Module

This module provides real-time communication capabilities using Socket.IO for the SignalGen system.
It handles broadcasting of trading signals, engine status updates, and other real-time events
to connected clients.

Key Features:
- Real-time bidirectional communication using Socket.IO
- Broadcasting capabilities for multiple clients
- Room-based broadcasting for different event types
- Client connection management
- Event validation and formatting
- Error handling for failed broadcasts
- Comprehensive logging of WebSocket activities

Events Published:
- Signal events with trading signals
- Engine status updates (started, stopped, error)
- Rule activation/deactivation
- Watchlist changes
- Connection status to IBKR
- Error notifications

Typical Usage:
    broadcaster = SocketIOBroadcaster()
    await broadcaster.initialize()
    await broadcaster.broadcast_signal(signal_data)
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import socketio
from socketio import AsyncServer
import json


class SocketIOBroadcaster:
    """
    WebSocket broadcaster using Socket.IO for real-time communication.
    
    This class manages WebSocket connections and broadcasts real-time events
    to connected clients. It supports room-based broadcasting for different
    types of events and provides comprehensive error handling.
    """
    
    def __init__(self, cors_origins: List[str] = None, repository=None):
        """
        Initialize the Socket.IO broadcaster.
        
        Args:
            cors_origins: List of allowed CORS origins
            repository: SQLite repository instance for Telegram notifier
        """
        self.logger = logging.getLogger(__name__)
        
        # Default CORS origins for local development
        if cors_origins is None:
            cors_origins = ["http://localhost:3456", "http://127.0.0.1:3456"]
        
        # Create async Socket.IO server
        self.sio = AsyncServer(
            async_mode='asgi',
            cors_allowed_origins=cors_origins,
            logger=False,
            engineio_logger=False
        )
        
        # Connected clients tracking
        self.connected_clients: Dict[str, Dict[str, Any]] = {}
        
        # Room definitions for different event types
        self.ROOMS = {
            'signals': 'signals',
            'engine': 'engine_status',
            'rules': 'rules',
            'watchlists': 'watchlists',
            'ibkr': 'ibkr_status',
            'errors': 'errors',
            'prices': 'prices'
        }
        
        # Event loop reference for thread-safe broadcasting
        self._loop = None
        
        # Telegram notifier (optional)
        self.telegram_notifier = None
        self.repository = repository
        
        # Register event handlers
        self._register_handlers()
        
        self.logger.info("SocketIOBroadcaster initialized")
    
    def _register_handlers(self) -> None:
        """Register Socket.IO event handlers."""
        
        @self.sio.event
        async def connect(sid, environ):
            """Handle new client connections."""
            await self.handle_client_connect(sid, environ)
        
        @self.sio.event
        async def disconnect(sid):
            """Handle client disconnections."""
            await self.handle_client_disconnect(sid)
        
        @self.sio.event
        async def join_room(sid, data):
            """Handle client room subscription."""
            try:
                room = data.get('room')
                if room in self.ROOMS.values():
                    await self.sio.enter_room(sid, room)
                    self.logger.info(f"Client {sid} joined room {room}")
                    await self.sio.emit('room_joined', {'room': room}, room=sid)
                else:
                    await self.sio.emit('error', {'message': f'Invalid room: {room}'}, room=sid)
            except Exception as e:
                self.logger.error(f"Error joining room: {e}")
                await self.sio.emit('error', {'message': 'Failed to join room'}, room=sid)
        
        @self.sio.event
        async def leave_room(sid, data):
            """Handle client room unsubscription."""
            try:
                room = data.get('room')
                if room in self.ROOMS.values():
                    await self.sio.leave_room(sid, room)
                    self.logger.info(f"Client {sid} left room {room}")
                    await self.sio.emit('room_left', {'room': room}, room=sid)
            except Exception as e:
                self.logger.error(f"Error leaving room: {e}")
                await self.sio.emit('error', {'message': 'Failed to leave room'}, room=sid)
        
        @self.sio.event
        async def get_status(sid):
            """Handle client status request."""
            try:
                status = {
                    'connected_clients': len(self.connected_clients),
                    'rooms': list(self.ROOMS.values()),
                    'timestamp': datetime.utcnow().isoformat()
                }
                await self.sio.emit('status', status, room=sid)
            except Exception as e:
                self.logger.error(f"Error getting status: {e}")
                await self.sio.emit('error', {'message': 'Failed to get status'}, room=sid)
    
    async def handle_client_connect(self, sid: str, environ: Dict[str, Any]) -> None:
        """
        Handle new client connections.
        
        Args:
            sid: Session ID of the connected client
            environ: Connection environment information
        """
        try:
            # Capture the running event loop used by the Socket.IO server
            try:
                self._loop = asyncio.get_running_loop()
                self.logger.info(f"Captured event loop {id(self._loop)} on client connect")
            except RuntimeError:
                self._loop = None
                self.logger.warning("No running loop available on client connect")
            
            # Extract client information
            client_info = {
                'sid': sid,
                'connected_at': datetime.utcnow().isoformat(),
                'ip_address': environ.get('REMOTE_ADDR', 'unknown'),
                'user_agent': environ.get('HTTP_USER_AGENT', 'unknown'),
                'rooms': []
            }
            
            # Store client information
            self.connected_clients[sid] = client_info
            
            # Add client to default rooms
            await self.sio.enter_room(sid, self.ROOMS['signals'])
            await self.sio.enter_room(sid, self.ROOMS['engine'])
            client_info['rooms'].extend([self.ROOMS['signals'], self.ROOMS['engine']])
            
            # Send welcome message
            welcome_data = {
                'message': 'Connected to SignalGen WebSocket',
                'sid': sid,
                'available_rooms': list(self.ROOMS.values()),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            await self.sio.emit('connected', welcome_data, room=sid)
            
            self.logger.info(f"Client connected: {sid} from {client_info['ip_address']}")
            
        except Exception as e:
            self.logger.error(f"Error handling client connect: {e}")
            await self.sio.emit('error', {'message': 'Connection failed'}, room=sid)
    
    async def handle_client_disconnect(self, sid: str) -> None:
        """
        Handle client disconnections.
        
        Args:
            sid: Session ID of the disconnected client
        """
        try:
            # Get client info before removal
            client_info = self.connected_clients.get(sid, {})
            
            # Remove client from tracking
            if sid in self.connected_clients:
                del self.connected_clients[sid]
            
            self.logger.info(f"Client disconnected: {sid} (was connected for {self._get_connection_duration(client_info)})")
            
        except Exception as e:
            self.logger.error(f"Error handling client disconnect: {e}")
    
    def _get_connection_duration(self, client_info: Dict[str, Any]) -> str:
        """Calculate connection duration from client info."""
        try:
            if 'connected_at' in client_info:
                connected_time = datetime.fromisoformat(client_info['connected_at'].replace('Z', '+00:00'))
                duration = datetime.utcnow() - connected_time.replace(tzinfo=None)
                return str(duration).split('.')[0]  # Remove microseconds
            return "unknown"
        except:
            return "unknown"
    
    async def broadcast_signal(self, signal_data: Dict[str, Any]) -> None:
        """
        Broadcast signal events to all connected clients and Telegram.
        
        Args:
            signal_data: Signal data with format:
                {
                    "symbol": "AAPL",
                    "price": 189.20,
                    "rule_id": 2,
                    "timestamp": "2025-12-16T09:31:00Z"
                }
        """
        try:
            # Validate signal data
            if not self._validate_signal_data(signal_data):
                raise ValueError("Invalid signal data format")
            
            # Format signal event according to PROJECT_MVP.md specification
            # The event should be sent directly without wrapping in 'data' field
            signal_event = {
                "event": "signal",
                "symbol": signal_data['symbol'],
                "price": signal_data['price'],
                "rule_id": signal_data['rule_id'],
                "timestamp": signal_data.get('timestamp', datetime.utcnow().isoformat())
            }
            
            # Broadcast to signals room (WebSocket)
            await self.sio.emit('signal', signal_event, room=self.ROOMS['signals'])
            
            # Send to Telegram if configured
            if self.telegram_notifier:
                try:
                    await self.telegram_notifier.send_signal(signal_data)
                except Exception as telegram_error:
                    self.logger.warning(f"Failed to send Telegram notification: {telegram_error}")
            
            self.logger.info(f"Signal broadcasted: {signal_data.get('symbol')} @ {signal_data.get('price')}")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting signal: {e}")
            await self.broadcast_error({
                'type': 'broadcast_error',
                'message': f'Failed to broadcast signal: {str(e)}',
                'data': signal_data
            })
    
    async def broadcast_price_update(self, symbol: str, price: float, timestamp: float) -> None:
        """
        Broadcast real-time price updates to all connected clients.
        
        Args:
            symbol: Trading symbol (e.g., "AAPL")
            price: Current price
            timestamp: Unix timestamp of price update
        """
        try:
            # Skip if no connected clients
            if not self.connected_clients:
                return
            
            # Format price event
            price_event = {
                "symbol": symbol,
                "price": price,
                "timestamp": datetime.fromtimestamp(timestamp).isoformat()
            }
            
            # Broadcast to prices room
            await self.sio.emit('price_update', price_event, room=self.ROOMS['prices'])
            
            self.logger.debug(f"Price update broadcasted: {symbol} @ {price}")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting price update: {e}")
    
    def broadcast_price_update_sync(self, price_data: Dict[str, Any]) -> None:
        """
        Synchronous wrapper for broadcasting price updates from non-async contexts.
        
        This method handles thread-safe emission of price updates using the Socket.IO
        server's event loop when available, falling back to a background thread.
        
        Args:
            price_data: Price data to broadcast
        """
        try:
            # Validate required fields
            if 'symbol' not in price_data or 'price' not in price_data:
                self.logger.warning("Invalid price data - missing symbol or price")
                return
            
            # Prefer emitting into the Socket.IO server loop directly
            if self._loop:
                try:
                    if self._loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            self.broadcast_price_update(price_data),
                            self._loop
                        )
                        self.logger.debug(f"Price update for {price_data['symbol']} scheduled on server loop")
                        return
                    else:
                        self.logger.warning(f"Server loop {id(self._loop)} is not running, using fallback")
                except Exception as e:
                    self.logger.error(f"Failed to schedule price emit on server loop: {e}")
            else:
                self.logger.debug("No server loop available, using fallback thread")
            
            # Fallback: emit directly using Socket.IO's internal mechanism
            # This is risky but necessary when no loop is captured
            try:
                # Try to use the Socket.IO server's internal event loop
                import threading
                def do_emit_fallback():
                    try:
                        # Check if there's ANY running loop we can use
                        try:
                            loop = asyncio.get_running_loop()
                            asyncio.run_coroutine_threadsafe(
                                self.broadcast_price_update(price_data),
                                loop
                            )
                            self.logger.debug(f"Price update scheduled on discovered loop {id(loop)}")
                        except RuntimeError:
                            # No running loop, create temporary one
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self.broadcast_price_update(price_data))
                            loop.close()
                            self.logger.debug("Price update emitted via temporary loop")
                    except Exception as e:
                        self.logger.error(f"Error emitting price in fallback thread: {e}", exc_info=True)
                threading.Thread(target=do_emit_fallback, daemon=True).start()
            except Exception as e:
                self.logger.error(f"Failed to start fallback thread: {e}", exc_info=True)
        except Exception as e:
            self.logger.error(f"Error in sync price broadcast: {e}")
    
    async def broadcast_engine_status(self, status: Dict[str, Any]) -> None:
        """
        Broadcast engine status updates to all connected clients.
        
        Args:
            status: Engine status data
        """
        try:
            # Format engine status event
            status_event = {
                'event': 'engine_status',
                'data': status,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Broadcast to engine room
            await self.sio.emit('engine_status', status_event, room=self.ROOMS['engine'])
            
            self.logger.info(f"Engine status broadcasted: {status.get('state', 'unknown')}")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting engine status: {e}")
            await self.broadcast_error({
                'type': 'broadcast_error',
                'message': f'Failed to broadcast engine status: {str(e)}',
                'data': status
            })
    
    def broadcast_engine_status_sync(self, status: Dict[str, Any]) -> None:
        """
        Thread-safe synchronous version of broadcast_engine_status.
        Can be called from any thread.
        
        Args:
            status: Engine status data
        """
        try:
            self.logger.info(f"broadcast_engine_status_sync called with: {status.get('is_running', 'N/A')}")
            
            # Use threading to call emit in a thread-safe way
            import threading
            def do_emit():
                try:
                    # Get the Socket.IO async server's loop
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.run_coroutine_threadsafe(
                                self._emit_engine_status(status),
                                loop
                            )
                            self.logger.info("Scheduled emit in running loop")
                        else:
                            # Create a new loop and run the coroutine
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self._emit_engine_status(status))
                            loop.close()
                            self.logger.info("Emitted in new loop")
                    except RuntimeError:
                        # No event loop in current thread, create one
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self._emit_engine_status(status))
                        loop.close()
                        self.logger.info("Emitted in new loop (no existing loop)")
                except Exception as e:
                    self.logger.error(f"Error emitting in thread: {e}", exc_info=True)
            
            threading.Thread(target=do_emit, daemon=True).start()
            
        except Exception as e:
            self.logger.error(f"Error in sync broadcast: {e}", exc_info=True)
    
    async def _emit_engine_status(self, status: Dict[str, Any]) -> None:
        """Helper to emit engine status."""
        self.logger.info(f"_emit_engine_status called, emitting to room: {self.ROOMS['engine']}")
        await self.sio.emit('engine_status', status, room=self.ROOMS['engine'])
        self.logger.info("Engine status emitted successfully")
    
    async def broadcast_watchlist_update(self, watchlist: Dict[str, Any]) -> None:
        """
        Broadcast watchlist changes to all connected clients.
        
        Args:
            watchlist: Watchlist data
        """
        try:
            # Format watchlist event
            watchlist_event = {
                'event': 'watchlist_update',
                'data': watchlist,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Broadcast to watchlists room
            await self.sio.emit('watchlist_update', watchlist_event, room=self.ROOMS['watchlists'])
            
            self.logger.info(f"Watchlist update broadcasted: {watchlist.get('name', 'unknown')}")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting watchlist update: {e}")
            await self.broadcast_error({
                'type': 'broadcast_error',
                'message': f'Failed to broadcast watchlist update: {str(e)}',
                'data': watchlist
            })
    
    async def broadcast_rule_update(self, rule: Dict[str, Any]) -> None:
        """
        Broadcast rule updates to all connected clients.
        
        Args:
            rule: Rule data
        """
        try:
            # Format rule event
            rule_event = {
                'event': 'rule_update',
                'data': rule,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Broadcast to rules room
            await self.sio.emit('rule_update', rule_event, room=self.ROOMS['rules'])
            
            self.logger.info(f"Rule update broadcasted: {rule.get('name', 'unknown')}")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting rule update: {e}")
            await self.broadcast_error({
                'type': 'broadcast_error',
                'message': f'Failed to broadcast rule update: {str(e)}',
                'data': rule
            })
    
    async def broadcast_ibkr_status(self, status: Dict[str, Any]) -> None:
        """
        Broadcast IBKR connection status to all connected clients.
        
        Args:
            status: IBKR connection status
        """
        try:
            # Format IBKR status event
            ibkr_event = {
                'event': 'ibkr_status',
                'data': status,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Broadcast to IBKR room
            await self.sio.emit('ibkr_status', ibkr_event, room=self.ROOMS['ibkr'])
            
            self.logger.info(f"IBKR status broadcasted: {status.get('connected', 'unknown')}")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting IBKR status: {e}")
            await self.broadcast_error({
                'type': 'broadcast_error',
                'message': f'Failed to broadcast IBKR status: {str(e)}',
                'data': status
            })
    
    async def broadcast_error(self, error_data: Dict[str, Any]) -> None:
        """
        Broadcast error notifications to all connected clients.
        
        Args:
            error_data: Error information
        """
        try:
            # Format error event
            error_event = {
                'event': 'error',
                'data': error_data,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Broadcast to errors room
            await self.sio.emit('error', error_event, room=self.ROOMS['errors'])
            
            self.logger.warning(f"Error broadcasted: {error_data.get('type', 'unknown')}")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting error notification: {e}")
    
    def _validate_signal_data(self, signal_data: Dict[str, Any]) -> bool:
        """
        Validate signal data format.
        
        Args:
            signal_data: Signal data to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            required_fields = ['symbol', 'price', 'rule_id']
            
            for field in required_fields:
                if field not in signal_data:
                    self.logger.error(f"Missing required field in signal data: {field}")
                    return False
            
            # Validate data types
            if not isinstance(signal_data['symbol'], str):
                self.logger.error("Symbol must be a string")
                return False
            
            if not isinstance(signal_data['price'], (int, float)):
                self.logger.error("Price must be a number")
                return False
            
            if not isinstance(signal_data['rule_id'], int):
                self.logger.error("Rule ID must be an integer")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating signal data: {e}")
            return False
    
    async def get_connected_clients(self) -> List[Dict[str, Any]]:
        """
        Get list of connected clients.
        
        Returns:
            List of connected client information
        """
        try:
            return list(self.connected_clients.values())
        except Exception as e:
            self.logger.error(f"Error getting connected clients: {e}")
            return []
    
    async def get_room_clients(self, room: str) -> List[str]:
        """
        Get list of clients in a specific room.
        
        Args:
            room: Room name
            
        Returns:
            List of client session IDs in the room
        """
        try:
            # This would require access to Socket.IO's internal room management
            # For now, return empty list as placeholder
            return []
        except Exception as e:
            self.logger.error(f"Error getting room clients: {e}")
            return []
    
    def create_asgi_app(self):
        """
        Create ASGI application for Socket.IO server.
        
        Returns:
            ASGI application
        """
        # Attempt early loop capture if in async context
        try:
            self._loop = asyncio.get_running_loop()
            self.logger.info(f"Captured event loop {id(self._loop)} in create_asgi_app")
        except RuntimeError:
            self.logger.debug("No running loop in create_asgi_app (normal for sync startup)")
        
        return socketio.ASGIApp(self.sio)
    
    async def initialize(self) -> None:
        """Initialize the broadcaster and Telegram notifier."""
        self.logger.info("SocketIOBroadcaster initialized and ready")
        
        # Initialize Telegram notifier if repository is available
        if self.repository:
            try:
                from ..notifications.telegram_notifier import TelegramNotifier
                self.telegram_notifier = TelegramNotifier(self.repository)
                await self.telegram_notifier.initialize()
                self.logger.info("Telegram notifier integration initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Telegram notifier: {e}")
                self.telegram_notifier = None
        else:
            self.logger.info("Repository not provided, Telegram notifications disabled")
    
    async def shutdown(self) -> None:
        """Shutdown the broadcaster and cleanup resources."""
        try:
            # Disconnect all clients
            for sid in list(self.connected_clients.keys()):
                await self.sio.disconnect(sid)
            
            self.connected_clients.clear()
            self.logger.info("SocketIOBroadcaster shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
    
    async def broadcast_rule_activation(self, rule_id: int, activated: bool) -> None:
        """
        Broadcast rule activation/deactivation event.
        
        Args:
            rule_id: ID of the rule being activated/deactivated
            activated: True if rule is activated, False if deactivated
        """
        try:
            # Format rule activation event
            activation_event = {
                'event': 'rule_activation',
                'data': {
                    'rule_id': rule_id,
                    'activated': activated
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Broadcast to rules room
            await self.sio.emit('rule_activation', activation_event, room=self.ROOMS['rules'])
            
            action = "activated" if activated else "deactivated"
            self.logger.info(f"Rule {action} broadcasted: rule ID {rule_id}")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting rule activation: {e}")
            await self.broadcast_error({
                'type': 'broadcast_error',
                'message': f'Failed to broadcast rule activation: {str(e)}',
                'data': {'rule_id': rule_id, 'activated': activated}
            })