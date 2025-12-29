"""
FastAPI Application Module

This module provides the main FastAPI application for the SignalGen scalping system.
It handles REST API endpoints and integrates with the Socket.IO broadcaster.

Key Features:
- REST API for rule management
- REST API for watchlist management
- REST API for engine control
- Integration with Socket.IO for real-time updates
- CORS support for PyWebView frontend
- Automatic API documentation

API Endpoints:
- /api/rules/: CRUD operations for trading rules
- /api/watchlists/: CRUD operations for watchlists
- /api/engine/: Engine control and status
- /api/signals/: Signal history and retrieval
- /api/settings/: Application settings

Typical Usage:
    app = SignalGenApp()
    app.initialize_database()
    app.start_server()
    # API runs on http://localhost:3456
"""

import asyncio
import logging
import threading
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, validator
from pathlib import Path

from .storage.sqlite_repo import SQLiteRepository
from .ws.broadcaster import SocketIOBroadcaster
from .engines.scalping_engine import ScalpingEngine

# Pydantic models for API requests/responses
class RuleCreate(BaseModel):
    """Model for creating a new rule."""
    name: str = Field(..., min_length=1, max_length=100)
    definition: Dict[str, Any] = Field(...)
    
    @validator('definition')
    def validate_definition(cls, v):
        required_fields = ['logic', 'conditions']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Missing required field in rule definition: {field}")
        return v

class RuleUpdate(BaseModel):
    """Model for updating an existing rule."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    definition: Optional[Dict[str, Any]] = Field(None)
    
    @validator('definition')
    def validate_definition(cls, v):
        if v is not None:
            required_fields = ['logic', 'conditions']
            for field in required_fields:
                if field not in v:
                    raise ValueError(f"Missing required field in rule definition: {field}")
        return v

class WatchlistCreate(BaseModel):
    """Model for creating a new watchlist."""
    name: str = Field(..., min_length=1, max_length=100)
    symbols: List[str] = Field(..., min_items=1, max_items=5)
    
    @validator('symbols')
    def validate_symbols(cls, v):
        # Ensure symbols are uppercase and unique
        symbols = [s.upper().strip() for s in v if s.strip()]
        if len(set(symbols)) != len(symbols):
            raise ValueError("Duplicate symbols are not allowed")
        return symbols

class WatchlistUpdate(BaseModel):
    """Model for updating an existing watchlist."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    symbols: Optional[List[str]] = Field(None, min_items=1, max_items=5)
    
    @validator('symbols')
    def validate_symbols(cls, v):
        if v is not None:
            symbols = [s.upper().strip() for s in v if s.strip()]
            if len(set(symbols)) != len(symbols):
                raise ValueError("Duplicate symbols are not allowed")
            return symbols
        return v

class EngineStart(BaseModel):
    """Model for starting the engine."""
    watchlist_id: int = Field(..., gt=0)
    rule_id: int = Field(..., gt=0)

class EngineStatus(BaseModel):
    """Model for engine status response."""
    is_running: bool
    is_connected: bool
    state: Dict[str, Any]
    active_watchlist: List[str]
    active_rule: Optional[Dict[str, Any]]
    ibkr_connected: bool
    reconnect_attempts: int
    connection_details: Dict[str, Any]

class SignalResponse(BaseModel):
    """Model for signal response."""
    id: int
    time: str
    symbol: str
    price: float
    rule_id: Optional[int]
    created_at: str

class SystemStatus(BaseModel):
    """Model for overall system status."""
    engine: EngineStatus
    database: Dict[str, Any]
    websocket: Dict[str, Any]
    uptime: str
    version: str = "1.0.0"

class SettingsResponse(BaseModel):
    """Model for settings response."""
    key: str
    value: Any

class SettingsUpdate(BaseModel):
    """Model for updating settings."""
    value: Any

class BacktestRequest(BaseModel):
    """Model for backtest request."""
    name: str = Field(..., min_length=1, max_length=100)
    mode: str = Field(..., pattern='^(scalping|swing)$')
    rule_id: int = Field(..., gt=0)
    symbols: List[str] = Field(..., min_items=1, max_items=50)
    timeframe: str = Field(...)
    start_date: str = Field(...)  # ISO format date string
    end_date: str = Field(...)    # ISO format date string
    data_source: str = Field(..., pattern='^(ibkr|yahoo)$')

class SwingScreenRequest(BaseModel):
    """Model for swing screening request."""
    rule_id: int = Field(..., gt=0)
    ticker_universe_id: int = Field(..., gt=0)
    timeframe: str = Field(default='1d')
    lookback_days: int = Field(default=30, ge=1, le=365)

class UniverseCreate(BaseModel):
    """Model for creating ticker universe."""
    name: str = Field(..., min_length=1, max_length=100)
    tickers: List[str] = Field(..., min_items=0, max_items=200)
    description: Optional[str] = Field(None, max_length=500)

class UniverseUpdate(BaseModel):
    """Model for updating ticker universe."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    tickers: Optional[List[str]] = Field(None, min_items=0, max_items=200)
    description: Optional[str] = Field(None, max_length=500)

class ModeChange(BaseModel):
    """Model for changing operational mode."""
    mode: str = Field(..., pattern='^(scalping|backtesting|swing|swing_backtest)$')

class SignalGenApp:
    """
    Main FastAPI application for SignalGen system.
    
    This class provides REST API endpoints for all system operations
    and integrates with the WebSocket broadcaster for real-time updates.
    """
    
    def __init__(self, db_path: str = 'signalgen.db'):
        """
        Initialize the FastAPI application.
        
        Args:
            db_path: Path to SQLite database
        """
        # Get the directory of this file to resolve paths
        current_dir = Path(__file__).parent
        ui_dir = current_dir / "ui"
        static_dir = ui_dir / "static"
        templates_dir = ui_dir / "templates"
        
        self.app = FastAPI(
            title="SignalGen API",
            description="Real-time scalping signal generator API",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Mount static files
        if static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        # Setup templates
        self.templates = Jinja2Templates(directory=str(templates_dir)) if templates_dir.exists() else None
        
        self.repository = SQLiteRepository(db_path)
        
        # Initialize database schema and default data
        # Must be done before accessing settings or creating engine
        self.repository.initialize_database()
        from .storage.init_db import initialize_database as init_db
        init_db(db_path)
        
        self.broadcaster = SocketIOBroadcaster()
        
        # Get timeframe from settings, default to '1m'
        timeframe = self.repository.get_setting('timeframe') or '1m'
        self.scalping_engine = ScalpingEngine(timeframe=timeframe)
        
        self.logger = logging.getLogger(__name__)
        
        # Engine state management
        self._engine_lock = threading.Lock()
        self._engine_running = False
        self._engine_start_time = None
        
        # Set broadcaster reference in scalping engine
        self.scalping_engine.broadcaster = self.broadcaster
        
        # Configure CORS with specific origins for security
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3456", "http://127.0.0.1:3456", "file://"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )
        
        # Register routes
        self._register_routes()
        
        # Log startup
        self.logger.info("SignalGen application initialized")
    
    def _register_routes(self) -> None:
        """Register all API routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def serve_ui(request: Request):
            """Serve the main UI dashboard."""
            if self.templates:
                return self.templates.TemplateResponse("index.html", {"request": request})
            else:
                # Fallback if templates directory doesn't exist
                return HTMLResponse("""
                <html>
                    <head><title>SignalGen</title></head>
                    <body>
                        <h1>SignalGen UI</h1>
                        <p>Templates directory not found. Please check your installation.</p>
                        <p><a href="/docs">API Documentation</a></p>
                    </body>
                </html>
                """)
        
        @self.app.get("/api")
        async def root():
            """Root endpoint with API information."""
            return {
                "name": "SignalGen API",
                "version": "1.0.0",
                "description": "Real-time scalping signal generator",
                "docs": "/docs",
                "status": "running"
            }
        
        @self.app.get("/api/health")
        async def health_check():
            """Health check endpoint."""
            try:
                # Check database connection
                db_stats = self.repository.get_database_stats()
                
                # Check engine status
                engine_status = await self._get_safe_engine_status()
                
                return {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "database": {
                        "status": "connected",
                        "stats": db_stats
                    },
                    "websocket": {
                        "status": "running",
                        "connected_clients": len(await self.broadcaster.get_connected_clients())
                    },
                    "engine": engine_status
                }
            except Exception as e:
                self.logger.error(f"Health check failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Service unavailable"
                )
        
        @self.app.get("/api/status", response_model=SystemStatus)
        def get_system_status():
            """Get overall system status."""
            try:
                # Get actual engine status from scalping engine (with timeout protection)
                if self.scalping_engine:
                    try:
                        # Use direct attribute access instead of method to avoid blocking
                        engine_status = {
                            'is_running': self.scalping_engine.is_running,
                            'is_connected': self.scalping_engine.is_connected,
                            'ibkr_connected': self.scalping_engine.is_connected,
                            'state': {'state': 'running' if self.scalping_engine.is_running else 'idle'},
                            'active_watchlist': self.scalping_engine.active_watchlist.copy() if self.scalping_engine.active_watchlist else [],
                            'active_rule': self.scalping_engine.active_rule,
                            'reconnect_attempts': self.scalping_engine.reconnect_attempts,
                            'connection_details': {
                                'host': self.scalping_engine.ib_host,
                                'port': self.scalping_engine.ib_port,
                                'client_id': self.scalping_engine.ib_client_id
                            }
                        }
                    except Exception as e:
                        self.logger.warning(f"Error getting engine status details: {e}")
                        # Fallback to basic status
                        engine_status = {
                            'is_running': self.scalping_engine.is_running if hasattr(self.scalping_engine, 'is_running') else False,
                            'is_connected': self.scalping_engine.is_connected if hasattr(self.scalping_engine, 'is_connected') else False,
                            'ibkr_connected': self.scalping_engine.is_connected if hasattr(self.scalping_engine, 'is_connected') else False,
                            'state': {'state': 'idle'},
                            'active_watchlist': [],
                            'active_rule': None,
                            'reconnect_attempts': 0,
                            'connection_details': {}
                        }
                else:
                    # Fallback if engine not initialized
                    engine_status = {
                        'is_running': False,
                        'is_connected': False,
                        'state': {'state': 'idle'},
                        'active_watchlist': [],
                        'active_rule': None,
                        'ibkr_connected': False,
                        'reconnect_attempts': 0,
                        'connection_details': {}
                    }
                
                # Get database stats
                db_stats = self.repository.get_database_stats()
                
                # Get WebSocket status (simplified)
                connected_clients = 0  # Simplified for MVP
                
                # Calculate uptime
                uptime = "0:00:00"
                if self._engine_start_time:
                    uptime_seconds = (datetime.utcnow() - self._engine_start_time).total_seconds()
                    hours, remainder = divmod(uptime_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    uptime = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
                
                return SystemStatus(
                    engine=EngineStatus(**engine_status),
                    database=db_stats,
                    websocket={
                        "connected_clients": connected_clients,
                        "rooms": self.broadcaster.ROOMS
                    },
                    uptime=uptime
                )
            except Exception as e:
                self.logger.error(f"Error getting system status: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to get system status"
                )
        
        # Rules endpoints
        @self.app.get("/api/rules", response_model=List[Dict])
        def get_all_rules():
            """Get all trading rules."""
            try:
                rules = self.repository.get_all_rules()
                return JSONResponse(content=rules)
            except Exception as e:
                self.logger.error(f"Error getting rules: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.get("/api/rules/{rule_id}", response_model=Dict)
        def get_rule(rule_id: int):
            """Get a specific rule by ID."""
            try:
                rule = self.repository.get_rule(rule_id)
                if not rule:
                    raise HTTPException(status_code=404, detail="Rule not found")
                return JSONResponse(content=rule)
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error getting rule {rule_id}: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.post("/api/rules", response_model=Dict)
        def create_rule(rule: RuleCreate):
            """Create a new trading rule."""
            try:
                rule_id = self.repository.create_rule(
                    name=rule.name,
                    rule_type="custom",
                    definition=rule.definition
                )
                
                # Get created rule
                created_rule = self.repository.get_rule(rule_id)
                
                # Broadcast update (fire and forget)
                # asyncio.create_task(
                #     self.broadcaster.broadcast_rule_update(created_rule)
                # )
                
                return JSONResponse(content=created_rule, status_code=201)
            except Exception as e:
                self.logger.error(f"Error creating rule: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.put("/api/rules/{rule_id}", response_model=Dict)
        def update_rule(rule_id: int, rule: RuleUpdate):
            """Update an existing rule."""
            try:
                success = self.repository.update_rule(
                    rule_id=rule_id,
                    name=rule.name,
                    definition=rule.definition
                )
                
                if not success:
                    raise HTTPException(status_code=404, detail="Rule not found or is system rule")
                
                # Get updated rule
                updated_rule = self.repository.get_rule(rule_id)
                
                # Broadcast update (fire and forget)
                # asyncio.create_task(
                #     self.broadcaster.broadcast_rule_update(updated_rule)
                # )
                
                return JSONResponse(content=updated_rule)
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error updating rule {rule_id}: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.delete("/api/rules/{rule_id}")
        def delete_rule(rule_id: int):
            """Delete a custom rule."""
            try:
                success = self.repository.delete_rule(rule_id)
                if not success:
                    raise HTTPException(status_code=404, detail="Rule not found or is system rule")
                
                return {"message": "Rule deleted successfully"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error deleting rule {rule_id}: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        # Watchlists endpoints
        @self.app.get("/api/watchlists", response_model=List[Dict])
        def get_all_watchlists():
            """Get all watchlists."""
            try:
                watchlists = self.repository.get_all_watchlists()
                return JSONResponse(content=watchlists)
            except Exception as e:
                self.logger.error(f"Error getting watchlists: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.post("/api/watchlists", response_model=Dict)
        def create_watchlist(watchlist: WatchlistCreate):
            """Create a new watchlist."""
            try:
                watchlist_id = self.repository.create_watchlist(
                    name=watchlist.name,
                    symbols=watchlist.symbols
                )
                
                # Get created watchlist
                created_watchlist = self.repository.get_watchlist(watchlist_id)
                
                # Broadcast update (fire and forget)
                # asyncio.create_task(
                #     self.broadcaster.broadcast_watchlist_update(created_watchlist)
                # )
                
                return JSONResponse(content=created_watchlist, status_code=201)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                self.logger.error(f"Error creating watchlist: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.put("/api/watchlists/{watchlist_id}", response_model=Dict)
        def update_watchlist(watchlist_id: int, watchlist: WatchlistUpdate):
            """Update an existing watchlist."""
            try:
                # Check if engine is running (MVP constraint)
                if self._engine_running:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Cannot modify watchlist while engine is running"
                    )
                
                success = self.repository.update_watchlist(watchlist_id, watchlist.dict(exclude_unset=True))
                if not success:
                    raise HTTPException(status_code=404, detail="Watchlist not found")
                
                # Get updated watchlist
                updated_watchlist = self.repository.get_watchlist(watchlist_id)
                
                # Broadcast update (fire and forget)
                # asyncio.create_task(
                #     self.broadcaster.broadcast_watchlist_update(updated_watchlist)
                # )
                
                return JSONResponse(content=updated_watchlist)
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error updating watchlist {watchlist_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.delete("/api/watchlists/{watchlist_id}")
        def delete_watchlist(watchlist_id: int):
            """Delete a watchlist."""
            try:
                # Check if engine is running (MVP constraint)
                if self._engine_running:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Cannot delete watchlist while engine is running"
                    )
                
                success = self.repository.delete_watchlist(watchlist_id)
                if not success:
                    raise HTTPException(status_code=404, detail="Watchlist not found")
                
                return {"message": "Watchlist deleted successfully"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error deleting watchlist {watchlist_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.put("/api/watchlists/{watchlist_id}/activate")
        def activate_watchlist(watchlist_id: int):
            """Set a watchlist as active."""
            try:
                # Check if engine is running (MVP constraint)
                if self._engine_running:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Cannot activate watchlist while engine is running"
                    )
                
                success = self.repository.set_active_watchlist(watchlist_id)
                if not success:
                    raise HTTPException(status_code=404, detail="Watchlist not found")
                
                # Get active watchlist
                active_watchlist = self.repository.get_active_watchlist()
                
                # Broadcast update (fire and forget)
                # asyncio.create_task(
                #     self.broadcaster.broadcast_watchlist_update(active_watchlist)
                # )
                
                return {"message": "Watchlist activated successfully"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error activating watchlist {watchlist_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.put("/api/rules/{rule_id}/activate")
        def activate_rule(rule_id: int):
            """Activate a rule."""
            try:
                # Check if engine is running (MVP constraint)
                if self._engine_running:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Cannot activate rule while engine is running"
                    )
                
                rule = self.repository.get_rule(rule_id)
                if not rule:
                    raise HTTPException(status_code=404, detail="Rule not found")
                
                # Broadcast activation (fire and forget)
                # asyncio.create_task(
                #     self.broadcaster.broadcast_rule_activation(rule_id, True)
                # )
                
                return {"message": "Rule activated successfully"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error activating rule {rule_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        # Engine endpoints
        @self.app.get("/api/engine/status", response_model=EngineStatus)
        def get_engine_status():
            """Get current engine status."""
            try:
                # Get status from engine if available
                status = self.scalping_engine.get_engine_status_sync()
                return JSONResponse(content=status)
            except Exception as e:
                self.logger.error(f"Error getting engine status: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.post("/api/engine/start")
        async def start_engine(engine_config: EngineStart, background_tasks: BackgroundTasks):
            """Start the scalping engine."""
            with self._engine_lock:
                try:
                    # Check if engine is already running
                    if self._engine_running:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Engine is already running"
                        )
                    
                    # Get watchlist and rule
                    watchlist = self.repository.get_watchlist(engine_config.watchlist_id)
                    rule = self.repository.get_rule(engine_config.rule_id)
                    
                    if not watchlist:
                        raise HTTPException(status_code=404, detail="Watchlist not found")
                    if not rule:
                        raise HTTPException(status_code=404, detail="Rule not found")
                    
                    # Validate watchlist limits
                    if len(watchlist['symbols']) > 5:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Watchlist cannot exceed 5 symbols for MVP"
                        )
                    
                    # Start engine in separate thread with event loop
                    engine_thread = threading.Thread(
                        target=self._start_engine_in_thread,
                        args=(watchlist['symbols'], engine_config.rule_id),
                        daemon=True
                    )
                    engine_thread.start()
                    
                    # Broadcast will happen after engine fully starts
                    # We'll do it in a background task after a short delay
                    background_tasks.add_task(self._broadcast_engine_status_after_start)
                    
                    return {"message": "Engine start initiated"}
                except HTTPException:
                    raise
                except Exception as e:
                    self.logger.error(f"Error starting engine: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Internal server error"
                    )
        
        @self.app.post("/api/engine/stop")
        def stop_engine():
            """Stop the scalping engine."""
            try:
                if not self._engine_running:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Engine is not running"
                    )
                
                # Stop engine in background thread
                def stop_and_broadcast():
                    try:
                        self._stop_engine_in_thread()
                        time.sleep(0.5)
                        
                        # Build stopped status dict
                        stopped_status = {
                            'is_running': False,
                            'is_connected': False,
                            'ibkr_connected': False,
                            'state': {'state': 'stopped'},
                            'active_watchlist': [],
                            'active_rule': None,
                            'subscribed_symbols': [],
                            'reconnect_enabled': False,
                            'reconnect_attempts': 0,
                            'connection_details': {}
                        }
                        
                        self.broadcaster.broadcast_engine_status_sync(stopped_status)
                        self.logger.info("Broadcasted stopped status")
                    except Exception as e:
                        self.logger.error(f"Error in stop thread: {e}")
                
                threading.Thread(target=stop_and_broadcast, daemon=True).start()
                
                return {"message": "Engine stop initiated"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error stopping engine: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        # Signals endpoints
        @self.app.get("/api/signals", response_model=List[SignalResponse])
        def get_signals(limit: int = 100, symbol: Optional[str] = None):
            """Get recent signals."""
            try:
                signals = self.repository.get_signals(limit=limit, symbol=symbol)
                return JSONResponse(content=signals)
            except Exception as e:
                self.logger.error(f"Error getting signals: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.delete("/api/signals/{signal_id}")
        def delete_signal(signal_id: int):
            """Delete a signal."""
            try:
                success = self.repository.delete_signal(signal_id)
                if not success:
                    raise HTTPException(status_code=404, detail="Signal not found")
                
                return {"message": "Signal deleted successfully"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error deleting signal {signal_id}: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        # Settings endpoints
        @self.app.get("/api/settings/{key}", response_model=SettingsResponse)
        def get_setting(key: str):
            """Get a setting value."""
            try:
                value = self.repository.get_setting(key)
                return SettingsResponse(key=key, value=value)
            except Exception as e:
                self.logger.error(f"Error getting setting {key}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.get("/api/settings", response_model=Dict[str, Any])
        def get_all_settings():
            """Get all application settings."""
            try:
                # Get common settings
                settings = {}
                common_keys = [
                    'ib_host', 'ib_port', 'ib_client_id',
                    'max_watchlist_symbols', 'default_cooldown',
                    'bar_size', 'ui_theme', 'timeframe'
                ]
                
                for key in common_keys:
                    value = self.repository.get_setting(key)
                    if value is not None:
                        settings[key] = value
                
                return settings
            except Exception as e:
                self.logger.error(f"Error getting all settings: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.put("/api/settings/{key}")
        async def set_setting(key: str, setting_update: SettingsUpdate):
            """Set a setting value."""
            try:
                # Validate setting key
                valid_keys = [
                    'ib_host', 'ib_port', 'ib_client_id',
                    'max_watchlist_symbols', 'default_cooldown',
                    'bar_size', 'ui_theme', 'timeframe'
                ]
                
                if key not in valid_keys:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid setting key: {key}"
                    )
                
                # Special validation for timeframe
                if key == 'timeframe':
                    from .core.candle_builder import CandleBuilder
                    if not CandleBuilder.validate_timeframe(setting_update.value):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid timeframe: {setting_update.value}. Must be one of {CandleBuilder.get_supported_timeframes()}"
                        )
                
                self.repository.set_setting(key, setting_update.value)
                
                # Broadcast setting update
                asyncio.create_task(
                    self.broadcaster.broadcast_error({
                        'type': 'setting_update',
                        'message': f'Setting {key} updated',
                        'data': {'key': key, 'value': setting_update.value}
                    })
                )
                
                return {"message": "Setting updated successfully"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error setting {key}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        # Timeframe endpoints
        @self.app.get("/api/timeframes")
        def get_available_timeframes():
            """Get list of available timeframes."""
            try:
                from .core.candle_builder import CandleBuilder
                return {
                    "timeframes": CandleBuilder.get_supported_timeframes(),
                    "current": self.scalping_engine.get_timeframe()
                }
            except Exception as e:
                self.logger.error(f"Error getting timeframes: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.put("/api/timeframe")
        async def change_timeframe(setting_update: SettingsUpdate):
            """Change the active timeframe. Engine must be stopped."""
            try:
                from .core.candle_builder import CandleBuilder
                
                new_timeframe = setting_update.value
                
                # Validate timeframe
                if not CandleBuilder.validate_timeframe(new_timeframe):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid timeframe: {new_timeframe}. Must be one of {CandleBuilder.get_supported_timeframes()}"
                    )
                
                # Check if engine is running
                if self.scalping_engine.is_running:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot change timeframe while engine is running. Stop the engine first."
                    )
                
                # Change timeframe in engine
                self.scalping_engine.change_timeframe(new_timeframe)
                
                # Save to settings
                self.repository.set_setting('timeframe', new_timeframe)
                
                # Broadcast timeframe change
                asyncio.create_task(
                    self.broadcaster.broadcast_error({
                        'type': 'timeframe_change',
                        'message': f'Timeframe changed to {new_timeframe}',
                        'data': {'timeframe': new_timeframe}
                    })
                )
                
                return {
                    "message": "Timeframe changed successfully",
                    "timeframe": new_timeframe
                }
            except HTTPException:
                raise
            except RuntimeError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                self.logger.error(f"Error changing timeframe: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        # ============================================================
        # BACKTESTING API ENDPOINTS
        # ============================================================
        
        @self.app.post("/api/backtest/run")
        async def run_backtest(request: BacktestRequest):
            """
            Run a backtest with historical data.
            
            Request body:
                name: Backtest run name
                mode: 'scalping' or 'swing'
                rule_id: Rule ID to test
                symbols: List of symbols
                timeframe: Candle timeframe
                start_date: ISO date string
                end_date: ISO date string
                data_source: 'ibkr' or 'yahoo'
            """
            try:
                from datetime import datetime
                from .engines.backtesting_engine import BacktestingEngine
                from .data_sources import IBKRDataSource, YahooDataSource
                
                # Parse dates
                start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
                end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
                
                # Create data source
                if request.data_source == 'ibkr':
                    data_source = IBKRDataSource()
                else:
                    data_source = YahooDataSource()
                
                # Create engine
                engine = BacktestingEngine(
                    data_source=data_source,
                    timeframe=request.timeframe
                )
                
                # Run backtest
                self.logger.info(f"Starting backtest: {request.name}")
                results = await engine.run_backtest(
                    name=request.name,
                    mode=request.mode,
                    symbols=request.symbols,
                    rule_id=request.rule_id,
                    start_date=start_date,
                    end_date=end_date,
                    data_source_name=request.data_source
                )
                
                return {
                    "message": "Backtest completed successfully",
                    "backtest_run_id": results['backtest_run_id'],
                    "total_signals": results['metrics']['total_signals'],
                    "metrics": results['metrics']
                }
                
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                self.logger.error(f"Backtest error: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Backtest failed: {str(e)}"
                )
        
        @self.app.get("/api/backtest/runs")
        def get_backtest_runs():
            """Get all backtest runs."""
            try:
                runs = self.repository.get_all_backtest_runs()
                return {"runs": runs}
            except Exception as e:
                self.logger.error(f"Error getting backtest runs: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.get("/api/backtest/runs/{run_id}")
        def get_backtest_run(run_id: int):
            """Get specific backtest run with signals."""
            try:
                run = self.repository.get_backtest_run(run_id)
                if not run:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Backtest run {run_id} not found"
                    )
                
                signals = self.repository.get_backtest_signals(run_id)
                run['signals'] = signals
                
                return run
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error getting backtest run {run_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.delete("/api/backtest/runs/{run_id}")
        def delete_backtest_run(run_id: int):
            """Delete a backtest run."""
            try:
                success = self.repository.delete_backtest_run(run_id)
                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Backtest run {run_id} not found"
                    )
                
                return {"message": "Backtest run deleted successfully"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error deleting backtest run {run_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        # ============================================================
        # SWING TRADING API ENDPOINTS
        # ============================================================
        
        @self.app.post("/api/swing/screen")
        async def screen_swing_signals(request: SwingScreenRequest):
            """
            Run swing trading screening on a ticker universe.
            
            Request body:
                rule_id: Rule ID to use
                ticker_universe_id: Ticker universe ID
                timeframe: Candle timeframe (default: '1d')
                lookback_days: Days of historical data (default: 30)
            """
            try:
                from .engines.swing_screening_engine import SwingScreeningEngine
                
                # Create screening engine
                engine = SwingScreeningEngine(timeframe=request.timeframe)
                
                # Run screening
                self.logger.info(f"Starting swing screening on universe {request.ticker_universe_id}")
                results = await engine.screen_universe(
                    universe_id=request.ticker_universe_id,
                    rule_id=request.rule_id,
                    lookback_days=request.lookback_days
                )
                
                # Filter out errors for summary
                successful = [r for r in results if r['status'] == 'success']
                signals_found = [r for r in successful if r['signal'] is not None]
                
                return {
                    "message": "Screening completed successfully",
                    "results": results,
                    "summary": {
                        "total_tickers": len(results),
                        "successful": len(successful),
                        "signals_found": len(signals_found),
                        "errors": len(results) - len(successful)
                    }
                }
                
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                self.logger.error(f"Screening error: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Screening failed: {str(e)}"
                )
        
        @self.app.get("/api/swing/universes")
        def get_ticker_universes():
            """Get all ticker universes."""
            try:
                universes = self.repository.get_all_ticker_universes()
                return {"universes": universes}
            except Exception as e:
                self.logger.error(f"Error getting ticker universes: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.get("/api/swing/universes/{universe_id}")
        def get_ticker_universe(universe_id: int):
            """Get specific ticker universe."""
            try:
                universe = self.repository.get_ticker_universe(universe_id)
                if not universe:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Ticker universe {universe_id} not found"
                    )
                return universe
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error getting ticker universe {universe_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.post("/api/swing/universes")
        def create_ticker_universe(request: UniverseCreate):
            """Create new ticker universe."""
            try:
                universe_id = self.repository.create_ticker_universe(
                    name=request.name,
                    tickers=request.tickers,
                    description=request.description
                )
                
                return {
                    "message": "Ticker universe created successfully",
                    "universe_id": universe_id
                }
            except Exception as e:
                self.logger.error(f"Error creating ticker universe: {e}")
                if "UNIQUE constraint failed" in str(e):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Universe with name '{request.name}' already exists"
                    )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.put("/api/swing/universes/{universe_id}")
        def update_ticker_universe(universe_id: int, request: UniverseUpdate):
            """Update ticker universe."""
            try:
                success = self.repository.update_ticker_universe(
                    universe_id=universe_id,
                    name=request.name,
                    tickers=request.tickers,
                    description=request.description
                )
                
                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Ticker universe {universe_id} not found"
                    )
                
                return {"message": "Ticker universe updated successfully"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error updating ticker universe {universe_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.delete("/api/swing/universes/{universe_id}")
        def delete_ticker_universe(universe_id: int):
            """Delete ticker universe."""
            try:
                success = self.repository.delete_ticker_universe(universe_id)
                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Ticker universe {universe_id} not found"
                    )
                
                return {"message": "Ticker universe deleted successfully"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error deleting ticker universe {universe_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        # ============================================================
        # MODE MANAGEMENT API ENDPOINTS
        # ============================================================
        
        @self.app.get("/api/mode")
        def get_current_mode():
            """Get current operational mode."""
            try:
                # For MVP, mode is determined by engine state
                # In future, this could be stored in settings
                mode = "scalping"  # Default mode
                if not self.scalping_engine.is_running:
                    mode = "idle"
                
                return {
                    "mode": mode,
                    "available_modes": ["scalping", "backtesting", "swing", "swing_backtest"],
                    "engine_running": self.scalping_engine.is_running
                }
            except Exception as e:
                self.logger.error(f"Error getting mode: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.put("/api/mode")
        def set_mode(request: ModeChange):
            """
            Change operational mode.
            
            Note: Mode changes are currently UI-driven.
            Real-time scalping uses ScalpingEngine.
            Backtesting and swing use their respective engines on-demand.
            """
            try:
                # Validate that engine is not running
                if self.scalping_engine.is_running:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot change mode while scalping engine is running. Stop the engine first."
                    )
                
                # Store mode preference in settings (for future use)
                self.repository.set_setting('operational_mode', request.mode)
                
                return {
                    "message": f"Mode changed to {request.mode}",
                    "mode": request.mode
                }
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error setting mode: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
    
    def _start_engine_in_thread(self, symbols: List[str], rule_id: int) -> None:
        """
        Start engine in separate thread with its own event loop.
        This is needed for ib_insync which requires an event loop.
        
        Args:
            symbols: List of symbols to monitor
            rule_id: Rule ID to use
        """
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Store loop reference for stopping later
        self._engine_loop = loop
        
        try:
            # Start the engine
            loop.run_until_complete(self._start_engine_async(symbols, rule_id))
            
            # CRITICAL: Keep the loop running to process IBKR events
            # The loop must stay alive to receive real-time updates
            self.logger.info("Engine started, keeping event loop running for real-time updates...")
            loop.run_forever()
            
        except Exception as e:
            self.logger.error(f"Error in engine thread: {e}")
        finally:
            loop.close()
            self._engine_loop = None
    
    def _stop_engine_in_thread(self) -> None:
        """
        Stop engine in separate thread with event loop.
        This is needed for ib_insync which requires an event loop.
        """
        # If the engine loop is still running, stop it properly
        if hasattr(self, '_engine_loop') and self._engine_loop and self._engine_loop.is_running():
            # Schedule stop in the running loop and wait for completion
            future = asyncio.run_coroutine_threadsafe(self._stop_engine_async(), self._engine_loop)
            try:
                # Wait up to 5 seconds for stop to complete
                future.result(timeout=5.0)
            except Exception as e:
                self.logger.error(f"Error waiting for engine stop: {e}")
            
            # Now stop the event loop
            self._engine_loop.call_soon_threadsafe(self._engine_loop.stop)
            self.logger.info("Stopped engine event loop")
        else:
            # Fallback: create temporary loop for cleanup
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self._stop_engine_async())
            except Exception as e:
                self.logger.error(f"Error in stop engine thread: {e}")
            finally:
                loop.close()
    
    async def _stop_engine_async(self) -> None:
        """Async method to stop the engine."""
        try:
            await self.scalping_engine.stop_engine()
            
            with self._engine_lock:
                self._engine_running = False
                self._engine_start_time = None
            
            self.logger.info("Engine stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping engine: {e}")
    
    async def _start_engine_async(self, symbols: List[str], rule_id: int) -> None:
        """
        Async method to start the engine.
        
        Args:
            symbols: List of symbols to monitor
            rule_id: Rule ID to use
        """
        try:
            with self._engine_lock:
                self._engine_running = True
                self._engine_start_time = datetime.utcnow()
                
            success = await self.scalping_engine.start_engine(symbols, rule_id)
            self.logger.info(f"Engine start_engine returned: {success}")
            
            if success:
                self.logger.info(f"Engine started successfully with {len(symbols)} symbols")
                # Broadcast will be handled by background task, not here
            else:
                self.logger.warning("Engine start failed!")
                with self._engine_lock:
                    self._engine_running = False
                    self._engine_start_time = None
                
                # Broadcast error status to UI
                try:
                    error_status = {
                        'is_running': False,
                        'is_connected': False,
                        'ibkr_connected': False,
                        'state': {'state': 'stopped'},
                        'active_watchlist': [],
                        'active_rule': None,
                        'subscribed_symbols': [],
                        'reconnect_enabled': False,
                        'reconnect_attempts': 0,
                        'connection_details': {},
                        'error': 'Failed to connect to IBKR. Please ensure TWS or IB Gateway is running.'
                    }
                    self.broadcaster.broadcast_engine_status_sync(error_status)
                    self.logger.info("Broadcasted error status to UI")
                except Exception as e:
                    self.logger.error(f"Error broadcasting error status: {e}")
                
                # Stop the event loop so the thread can exit
                if self._engine_loop and self._engine_loop.is_running():
                    self._engine_loop.call_soon_threadsafe(self._engine_loop.stop)
                    self.logger.info("Stopped event loop after engine start failure")
                    
        except Exception as e:
            with self._engine_lock:
                self._engine_running = False
                self._engine_start_time = None
                
            self.logger.error(f"Error starting engine: {e}")
            try:
                error_status = {
                    'is_running': False,
                    'is_connected': False,
                    'ibkr_connected': False,
                    'state': {'state': 'stopped'},
                    'active_watchlist': [],
                    'active_rule': None,
                    'subscribed_symbols': [],
                    'reconnect_enabled': False,
                    'reconnect_attempts': 0,
                    'connection_details': {},
                    'error': str(e)
                }
                self.broadcaster.broadcast_engine_status_sync(error_status)
            except Exception:
                pass  # Ignore broadcast errors
            
            # Stop the event loop so the thread can exit
            if self._engine_loop and self._engine_loop.is_running():
                self._engine_loop.call_soon_threadsafe(self._engine_loop.stop)
                self.logger.info("Stopped event loop after exception")
    
    async def _broadcast_engine_status_after_start(self) -> None:
        """Background task to broadcast engine status after startup delay."""
        import asyncio
        # Wait for engine to fully initialize
        await asyncio.sleep(0.5)
        
        try:
            self.logger.info("Broadcasting engine status after start...")
            
            # Build status manually to avoid blocking calls
            status = {
                'is_running': self._engine_running,
                'is_connected': self.scalping_engine.is_connected,
                'ibkr_connected': self.scalping_engine.is_connected,
                'state': {'state': 'running' if self._engine_running else 'stopped'},
                'active_watchlist': self.scalping_engine.active_watchlist.copy() if hasattr(self.scalping_engine, 'active_watchlist') else [],
                'active_rule': self.scalping_engine.active_rule if hasattr(self.scalping_engine, 'active_rule') else None,
                'subscribed_symbols': list(self.scalping_engine.subscribed_contracts.keys()) if hasattr(self.scalping_engine, 'subscribed_contracts') else [],
                'reconnect_enabled': True,
                'reconnect_attempts': 0,
                'connection_details': {}
            }
            
            self.logger.info(f"Got status: running={status.get('is_running')}, connected={status.get('is_connected')}")
            self.broadcaster.broadcast_engine_status_sync(status)
            self.logger.info("Broadcast completed")
        except Exception as e:
            self.logger.error(f"Error broadcasting engine status: {e}", exc_info=True)
    
    async def _get_safe_engine_status(self) -> Dict[str, Any]:
        """
        Get engine status safely without raising exceptions.
        
        Returns:
            Dict with engine status information
        """
        try:
            status = await self.scalping_engine.get_engine_status()
            return status
        except Exception as e:
            self.logger.error(f"Error getting engine status: {e}")
            return {
                'is_running': False,
                'is_connected': False,
                'state': {'state': 'error'},
                'active_watchlist': [],
                'active_rule': None,
                'ibkr_connected': False,
                'reconnect_attempts': 0,
                'connection_details': {'error': str(e)}
            }
    
    def initialize_database(self) -> None:
        """
        Initialize the database.
        
        Note: Database is already initialized during __init__.
        This method is kept for backward compatibility.
        """
        self.logger.info("Database already initialized during app startup")
    
    def get_app(self) -> FastAPI:
        """
        Get the FastAPI application instance.
        
        Returns:
            FastAPI: The configured FastAPI app
        """
        return self.app
    
    def get_socketio_app(self):
        """
        Get the Socket.IO ASGI application for WebSocket support.
        
        Returns:
            ASGI app: The Socket.IO ASGI application
        """
        return self.broadcaster.create_asgi_app()

# Create global app instance
signalgen_app = SignalGenApp()
app = signalgen_app.get_app()
