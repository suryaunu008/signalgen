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
from datetime import datetime, timedelta
from uuid import uuid4

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
from .core.rule_engine import RuleEngine, RuleValidationError

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
    symbols: List[str] = Field(..., min_items=1)
    
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
    symbols: Optional[List[str]] = Field(None, min_items=1)
    
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

class ManualBacktestEntry(BaseModel):
    """Manual backtest entry row."""
    symbol: str = Field(..., min_length=1, max_length=20)
    entry_time: str = Field(...)  # ISO datetime string
    signal_type: Optional[str] = Field(default='BUY', pattern='^(BUY|SELL)$')
    entry_price: Optional[float] = Field(None, gt=0)

class BacktestScreenRequest(BaseModel):
    """Model for new backtesting screen request (rule/manual)."""
    mode: str = Field(..., pattern='^(rule|manual)$')
    timeframe: str = Field(..., pattern='^(1m|5m|15m|1h|4h|1d)$')
    n_steps: int = Field(..., ge=1, le=100)
    data_source: str = Field(..., pattern='^(ibkr|yahoo)$')
    entry_price_basis: str = Field(default='close', pattern='^(open|high|low|close)$')
    exit_price_basis: str = Field(default='close', pattern='^(open|high|low|close)$')
    pl_basis: Optional[str] = Field(default=None, pattern='^(open|high|low|close)$')
    rule_id: Optional[int] = Field(None, gt=0)
    start_at: Optional[str] = Field(None)  # ISO datetime string
    end_at: Optional[str] = Field(None)    # ISO datetime string
    symbols: Optional[List[str]] = Field(None, max_items=200)
    manual_entries: Optional[List[ManualBacktestEntry]] = Field(None, max_items=2000)

class SwingScreenRequest(BaseModel):
    """Model for swing screening request."""
    rule_id: int = Field(..., gt=0)
    ticker_universe_id: int = Field(..., gt=0)
    timeframe: str = Field(default='1d', pattern='^(1h|4h|1d)$')
    lookback_days: int = Field(default=30, ge=1, le=365)
    start_date: Optional[str] = Field(None)  # ISO date/datetime string
    end_date: Optional[str] = Field(None)    # ISO date/datetime string

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

class TelegramSettings(BaseModel):
    """Model for Telegram settings."""
    bot_token: Optional[str] = Field(None, description="Telegram Bot Token from BotFather")
    chat_ids: Optional[str] = Field(None, description="Comma-separated list of Telegram chat IDs")
    enabled: Optional[bool] = Field(None, description="Enable/disable Telegram notifications")

class TelegramTestRequest(BaseModel):
    """Model for testing Telegram configuration."""
    chat_id: Optional[str] = Field(None, description="Specific chat ID to test (optional)")

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
        import sys
        if getattr(sys, 'frozen', False):
            # Running in PyInstaller bundle
            base_dir = Path(sys._MEIPASS)
        else:
            # Running in normal Python environment
            base_dir = Path(__file__).parent
        
        ui_dir = base_dir / "app" / "ui" if getattr(sys, 'frozen', False) else base_dir / "ui"
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
        self.rule_engine = RuleEngine()
        
        # Initialize database schema and default data
        # Must be done before accessing settings or creating engine
        self.repository.initialize_database()
        from .storage.init_db import initialize_database as init_db
        init_db(db_path)
        
        # Initialize broadcaster with repository for Telegram integration
        self.broadcaster = SocketIOBroadcaster(repository=self.repository)
        
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

    def _normalize_rule_for_validation(
        self,
        name: str,
        definition: Dict[str, Any],
        rule_id: int = 0,
        rule_type: str = "custom"
    ) -> Dict[str, Any]:
        """Build the full rule shape expected by RuleEngine validation."""
        return {
            "id": rule_id,
            "name": name,
            "type": rule_type,
            **definition
        }

    def _validate_rule_definition(
        self,
        name: str,
        definition: Dict[str, Any],
        rule_id: int = 0,
        rule_type: str = "custom"
    ) -> None:
        """Validate a stored rule definition before it reaches the database."""
        rule = self._normalize_rule_for_validation(name, definition, rule_id, rule_type)
        self.rule_engine.validate_rule(rule)
    
    def _register_routes(self) -> None:
        """Register all API routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def serve_ui(request: Request):
            """Serve the main UI dashboard."""
            if self.templates:
                return self.templates.TemplateResponse(
                    request=request,
                    name="index.html",
                    context={}
                )
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

        @self.app.get("/api/rules/schema", response_model=Dict)
        def get_rule_schema():
            """Get supported rule operands, operators, and logic values."""
            try:
                operand_groups = {
                    "Price & Candle": [
                        "PRICE", "OPEN", "HIGH", "LOW", "CLOSE",
                        "PREV_CLOSE", "PREV_OPEN",
                        "OPEN_PREV", "HIGH_PREV", "LOW_PREV", "CLOSE_PREV",
                    ],
                    "Simple Moving Averages": [
                        "MA20", "MA50", "MA100", "MA200",
                        "MA20_PREV", "MA50_PREV", "MA100_PREV", "MA200_PREV",
                    ],
                    "Exponential Moving Averages": [
                        "EMA6", "EMA9", "EMA10", "EMA13", "EMA20", "EMA21", "EMA34", "EMA50",
                        "EMA6_PREV", "EMA9_PREV", "EMA10_PREV", "EMA13_PREV",
                        "EMA20_PREV", "EMA21_PREV", "EMA34_PREV", "EMA50_PREV",
                    ],
                    "MACD": [
                        "MACD", "MACD_SIGNAL", "MACD_HIST",
                        "MACD_PREV", "MACD_SIGNAL_PREV", "MACD_HIST_PREV",
                    ],
                    "RSI": ["RSI14", "RSI14_PREV"],
                    "ADX": ["ADX5", "ADX5_PREV"],
                    "Bollinger Bands": [
                        "BB_UPPER", "BB_MIDDLE", "BB_LOWER", "BB_WIDTH",
                        "BB_UPPER_PREV", "BB_MIDDLE_PREV", "BB_LOWER_PREV",
                    ],
                    "Stochastic Oscillator": [
                        "STOCH_K", "STOCH_D", "STOCH_K_PREV", "STOCH_D_PREV",
                    ],
                    "Ichimoku Cloud": [
                        "ICHIMOKU_CONVERSION", "ICHIMOKU_BASE", "ICHIMOKU_A", "ICHIMOKU_B",
                        "ICHIMOKU_CONVERSION_PREV", "ICHIMOKU_BASE_PREV",
                        "ICHIMOKU_A_PREV", "ICHIMOKU_B_PREV",
                    ],
                    "Volume": ["VOLUME", "SMA_VOLUME_20"],
                    "Calculated Metrics": ["PRICE_EMA20_DIFF_PCT"],
                }
                supported = self.rule_engine.SUPPORTED_OPERANDS
                filtered_groups = {
                    group: [operand for operand in operands if operand in supported]
                    for group, operands in operand_groups.items()
                }
                quick_operand_groups = {
                    group: [
                        operand for operand in operands
                        if (
                            operand
                            and not operand.endswith("_PREV")
                            and not operand.startswith("PREV_")
                        )
                    ]
                    for group, operands in filtered_groups.items()
                }
                quick_operands = {
                    operand
                    for operands in quick_operand_groups.values()
                    for operand in operands
                }
                return JSONResponse(content={
                    "operand_groups": quick_operand_groups,
                    "prev_n_base_operand_groups": quick_operand_groups,
                    "legacy_operands": sorted(supported - quick_operands),
                    "operands": sorted(supported),
                    "dynamic_operand_templates": [
                        {
                            "value": "PRICE_PREV_{n}",
                            "label": "Historical Close Price (legacy)",
                            "parameter": "n",
                            "min": self.rule_engine.MIN_DYNAMIC_PERIOD,
                            "max": self.rule_engine.MAX_DYNAMIC_PERIOD,
                        },
                        {
                            "value": "{operand}_PREV_{n}",
                            "label": "Previous Value for Any Indicator",
                            "parameter": "n",
                            "min": self.rule_engine.MIN_DYNAMIC_PERIOD,
                            "max": self.rule_engine.MAX_DYNAMIC_PERIOD,
                        },
                        {
                            "value": "MA{period}",
                            "label": "Simple Moving Average",
                            "parameter": "period",
                            "min": self.rule_engine.MIN_DYNAMIC_PERIOD,
                            "max": self.rule_engine.MAX_DYNAMIC_PERIOD,
                        },
                        {
                            "value": "EMA{period}",
                            "label": "Exponential Moving Average",
                            "parameter": "period",
                            "min": self.rule_engine.MIN_DYNAMIC_PERIOD,
                            "max": self.rule_engine.MAX_DYNAMIC_PERIOD,
                        },
                        {
                            "value": "RSI{period}",
                            "label": "Relative Strength Index",
                            "parameter": "period",
                            "min": self.rule_engine.MIN_DYNAMIC_PERIOD,
                            "max": self.rule_engine.MAX_DYNAMIC_PERIOD,
                        },
                        {
                            "value": "ADX{period}",
                            "label": "Average Directional Index",
                            "parameter": "period",
                            "min": self.rule_engine.MIN_DYNAMIC_PERIOD,
                            "max": self.rule_engine.MAX_DYNAMIC_PERIOD,
                        },
                        {
                            "value": "SMA_VOLUME_{period}",
                            "label": "Volume SMA",
                            "parameter": "period",
                            "min": self.rule_engine.MIN_DYNAMIC_PERIOD,
                            "max": self.rule_engine.MAX_DYNAMIC_PERIOD,
                        },
                    ],
                    "dynamic_parameter_bounds": {
                        "min": self.rule_engine.MIN_DYNAMIC_PERIOD,
                        "max": self.rule_engine.MAX_DYNAMIC_PERIOD,
                    },
                    "operators": [
                        operator for operator in [">", "<", ">=", "<=", "CROSS_UP", "CROSS_DOWN"]
                        if operator in self.rule_engine.SUPPORTED_OPERATORS
                    ],
                    "logic": sorted(self.rule_engine.SUPPORTED_LOGIC),
                    "cross_operators": ["CROSS_UP", "CROSS_DOWN"],
                    "crossable_operands": self.rule_engine.get_crossable_operands(),
                })
            except Exception as e:
                self.logger.error(f"Error getting rule schema: {e}")
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
                self._validate_rule_definition(rule.name, rule.definition)
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
            except RuleValidationError as e:
                raise HTTPException(status_code=422, detail=str(e))
            except Exception as e:
                self.logger.error(f"Error creating rule: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.put("/api/rules/{rule_id}", response_model=Dict)
        def update_rule(rule_id: int, rule: RuleUpdate):
            """Update an existing rule."""
            try:
                existing_rule = self.repository.get_rule(rule_id)
                if not existing_rule or existing_rule.get('is_system'):
                    raise HTTPException(status_code=404, detail="Rule not found or is system rule")

                next_name = rule.name if rule.name is not None else existing_rule['name']
                next_definition = rule.definition if rule.definition is not None else existing_rule['definition']
                self._validate_rule_definition(
                    next_name,
                    next_definition,
                    rule_id=rule_id,
                    rule_type=existing_rule.get('type', 'custom')
                )

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
            except RuleValidationError as e:
                raise HTTPException(status_code=422, detail=str(e))
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
        # TELEGRAM NOTIFICATION API ENDPOINTS
        # ============================================================
        
        @self.app.get("/api/telegram/settings")
        def get_telegram_settings():
            """Get current Telegram notification settings."""
            try:
                def _as_bool(value: Any) -> bool:
                    if isinstance(value, bool):
                        return value
                    if isinstance(value, str):
                        return value.strip().lower() in {"1", "true", "yes", "on"}
                    return bool(value)

                bot_token = self.repository.get_setting('telegram_bot_token', '')
                chat_ids = self.repository.get_setting('telegram_chat_ids', '')
                settings = {
                    'bot_token': bot_token,
                    'chat_ids': chat_ids,
                    'enabled': _as_bool(self.repository.get_setting('telegram_enabled', False)),
                    'token_configured': bool(str(bot_token or '').strip()),
                    'chat_ids_configured': bool(str(chat_ids or '').strip())
                }
                
                # Mask bot token for security (show only last 4 characters)
                if settings['bot_token']:
                    token_str = str(settings['bot_token'])
                    if len(token_str) > 8:
                        settings['bot_token'] = '...' + token_str[-4:]
                    else:
                        settings['bot_token'] = '***'
                
                return settings
            except Exception as e:
                self.logger.error(f"Error getting Telegram settings: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.put("/api/telegram/settings")
        async def update_telegram_settings(telegram_settings: TelegramSettings):
            """
            Update Telegram notification settings.
            
            Request body:
                bot_token: Telegram Bot Token from BotFather (optional)
                chat_ids: Comma-separated chat IDs (optional)
                enabled: Enable/disable notifications (optional)
            """
            try:
                # Update bot token if provided
                if telegram_settings.bot_token is not None:
                    # Don't update if it's the masked value
                    if not telegram_settings.bot_token.startswith('...'):
                        self.repository.set_setting('telegram_bot_token', telegram_settings.bot_token)
                        self.logger.info("Telegram bot token updated")
                
                # Update chat IDs if provided
                if telegram_settings.chat_ids is not None:
                    self.repository.set_setting('telegram_chat_ids', telegram_settings.chat_ids)
                    self.logger.info("Telegram chat IDs updated")
                
                # Update enabled status if provided
                if telegram_settings.enabled is not None:
                    self.repository.set_setting('telegram_enabled', telegram_settings.enabled)
                    self.logger.info(f"Telegram notifications {'enabled' if telegram_settings.enabled else 'disabled'}")
                
                # Reinitialize broadcaster's Telegram notifier with new settings
                if hasattr(self.broadcaster, 'telegram_notifier') and self.broadcaster.telegram_notifier:
                    await self.broadcaster.telegram_notifier.initialize()
                    self.logger.info("Telegram notifier reinitialized with new settings")

                enabled_value = (
                    telegram_settings.enabled
                    if telegram_settings.enabled is not None
                    else self.repository.get_setting('telegram_enabled', False)
                )
                if isinstance(enabled_value, str):
                    enabled_value = enabled_value.strip().lower() in {"1", "true", "yes", "on"}
                
                return {
                    "message": "Telegram settings updated successfully",
                    "enabled": bool(enabled_value)
                }
            except Exception as e:
                self.logger.error(f"Error updating Telegram settings: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )
        
        @self.app.post("/api/telegram/test")
        async def test_telegram_notification(test_request: TelegramTestRequest):
            """
            Send a test message to verify Telegram configuration.
            
            Request body:
                chat_id: Optional specific chat ID to test
            """
            try:
                # Check if Telegram is configured
                bot_token = self.repository.get_setting('telegram_bot_token')
                if not bot_token:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Telegram bot token not configured"
                    )
                
                # Initialize temporary notifier if broadcaster doesn't have one
                if not hasattr(self.broadcaster, 'telegram_notifier') or not self.broadcaster.telegram_notifier:
                    from .notifications.telegram_notifier import TelegramNotifier
                    temp_notifier = TelegramNotifier(self.repository)
                else:
                    temp_notifier = self.broadcaster.telegram_notifier

                await temp_notifier.initialize()
                
                # Send test message
                success = await temp_notifier.send_test_message(test_request.chat_id)
                
                if success:
                    return {
                        "message": "Test message sent successfully",
                        "success": True
                    }
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to send test message. Check bot token and chat ID."
                    )
                    
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error testing Telegram notification: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Internal server error: {str(e)}"
                )
        
        # ============================================================
        # BACKTESTING API ENDPOINTS
        # ============================================================

        @self.app.post("/api/backtest/screen")
        async def run_backtest_screen(request: BacktestScreenRequest):
            """
            New backtesting screen endpoint with 2 modes:
            - rule: generate entries from rule signals within date range
            - manual: user-provided entry timestamps
            """
            try:
                from .data_sources import CachedDataSource, IBKRDataSource, YahooDataSource
                from .core.rule_engine import RuleEngine
                from .core.indicator_engine import IndicatorEngine
                from datetime import timezone

                def _parse_dt(value: str, field_name: str) -> datetime:
                    try:
                        return datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except Exception as ex:
                        raise ValueError(f"Invalid {field_name}: {value}") from ex

                def _normalize_dt(value: datetime) -> datetime:
                    if value.tzinfo is not None:
                        return value.astimezone(timezone.utc).replace(tzinfo=None)
                    return value

                def _utc_iso(value: datetime) -> str:
                    if value.tzinfo is not None:
                        value = value.astimezone(timezone.utc).replace(tzinfo=None)
                    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

                def _wall_clock_iso(value: datetime) -> str:
                    if value.tzinfo is not None:
                        value = value.replace(tzinfo=None)
                    return value.isoformat()

                def _is_numeric_operand(value: Any) -> bool:
                    if isinstance(value, (int, float)):
                        return True
                    if isinstance(value, str):
                        try:
                            float(value)
                            return True
                        except ValueError:
                            return False
                    return False

                def _required_rule_operands(rule_def: Dict[str, Any]) -> set:
                    return RuleEngine.extract_required_operands(rule_def)

                def _has_required_indicators(indicators: Dict[str, Any], required: set) -> bool:
                    return all(operand in indicators for operand in required)

                def _calculate_trade_pl(signal_type: str, entry_price: float, exit_price: float) -> Dict[str, float]:
                    direction = -1 if str(signal_type).upper() == "SELL" else 1
                    pl = (exit_price - entry_price) * direction
                    pl_pct = 0 if entry_price == 0 else (pl / entry_price) * 100
                    return {"pl": pl, "pl_pct": pl_pct}

                def _basis_price(candle: Dict[str, Any], basis: str) -> float:
                    if basis not in {"open", "high", "low", "close"}:
                        raise ValueError(f"Unsupported price basis: {basis}")
                    return float(candle[basis])

                def _empty_step_metrics(step: int) -> Dict[str, Any]:
                    return {
                        "step": step,
                        "label": f"T+{step}",
                        "evaluated": 0,
                        "missing": 0,
                        "wins": 0,
                        "losses": 0,
                        "flats": 0,
                        "win_rate": 0,
                        "total_pl": 0,
                        "avg_pl": 0,
                        "total_pl_pct": 0,
                        "avg_pl_pct": 0,
                        "best_pl": None,
                        "worst_pl": None,
                        "best_pl_pct": None,
                        "worst_pl_pct": None,
                        "avg_win": 0,
                        "avg_loss": 0,
                        "profit_factor": None
                    }

                exit_price_basis = request.pl_basis or request.exit_price_basis or 'close'
                entry_price_basis = request.entry_price_basis or 'close'

                def _calculate_metrics(rows: List[Dict[str, Any]], n_steps: int, exit_basis: str) -> Dict[str, Any]:
                    per_step = []
                    by_symbol: Dict[str, Dict[str, Any]] = {}

                    for step in range(1, n_steps + 1):
                        values = []
                        missing = 0
                        label = f"T+{step}"

                        for row in rows:
                            step_data = row.get("steps", {}).get(label)
                            if not step_data or step_data.get("pl") is None:
                                missing += 1
                                continue
                            values.append(step_data)

                        metrics = _empty_step_metrics(step)
                        metrics["missing"] = missing
                        if values:
                            pls = [float(v["pl"]) for v in values]
                            pl_pcts = [float(v["pl_pct"]) for v in values]
                            wins = [v for v in pls if v > 0]
                            losses = [v for v in pls if v < 0]
                            flats = [v for v in pls if v == 0]
                            gross_profit = sum(wins)
                            gross_loss = abs(sum(losses))

                            metrics.update({
                                "evaluated": len(values),
                                "wins": len(wins),
                                "losses": len(losses),
                                "flats": len(flats),
                                "win_rate": (len(wins) / len(values)) * 100,
                                "total_pl": sum(pls),
                                "avg_pl": sum(pls) / len(pls),
                                "total_pl_pct": sum(pl_pcts),
                                "avg_pl_pct": sum(pl_pcts) / len(pl_pcts),
                                "best_pl": max(pls),
                                "worst_pl": min(pls),
                                "best_pl_pct": max(pl_pcts),
                                "worst_pl_pct": min(pl_pcts),
                                "avg_win": (sum(wins) / len(wins)) if wins else 0,
                                "avg_loss": (sum(losses) / len(losses)) if losses else 0,
                                "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else (None if gross_profit == 0 else gross_profit)
                            })
                        per_step.append(metrics)

                    final_label = f"T+{n_steps}"
                    for row in rows:
                        symbol = row["symbol"]
                        if symbol not in by_symbol:
                            by_symbol[symbol] = {
                                "symbol": symbol,
                                "trades": 0,
                                "evaluated": 0,
                                "wins": 0,
                                "losses": 0,
                                "total_pl": 0,
                                "avg_pl": 0,
                                "avg_pl_pct": 0
                            }
                        by_symbol[symbol]["trades"] += 1
                        final_step = row.get("steps", {}).get(final_label)
                        if not final_step or final_step.get("pl") is None:
                            continue
                        by_symbol[symbol]["evaluated"] += 1
                        pl = float(final_step["pl"])
                        pl_pct = float(final_step["pl_pct"])
                        by_symbol[symbol]["wins"] += 1 if pl > 0 else 0
                        by_symbol[symbol]["losses"] += 1 if pl < 0 else 0
                        by_symbol[symbol]["total_pl"] += pl
                        by_symbol[symbol]["avg_pl_pct"] += pl_pct

                    for metrics in by_symbol.values():
                        evaluated = metrics["evaluated"]
                        if evaluated > 0:
                            metrics["avg_pl"] = metrics["total_pl"] / evaluated
                            metrics["avg_pl_pct"] = metrics["avg_pl_pct"] / evaluated
                            metrics["win_rate"] = (metrics["wins"] / evaluated) * 100
                        else:
                            metrics["win_rate"] = 0

                    final_step_metrics = per_step[-1] if per_step else _empty_step_metrics(n_steps)
                    return {
                        "pl_basis": exit_basis,
                        "exit_price_basis": exit_basis,
                        "final_horizon": final_label,
                        "total_entries": len(rows),
                        "final": final_step_metrics,
                        "per_step": per_step,
                        "by_symbol": sorted(by_symbol.values(), key=lambda item: item["total_pl"], reverse=True)
                    }

                def _rule_warmup_start(start_dt: datetime, rule_def: Dict[str, Any], timeframe: str) -> datetime:
                    warmup_bars = RuleEngine.estimate_rule_warmup(rule_def)

                    if timeframe == "1d":
                        warmup_days = (warmup_bars * 2) + 10
                    elif timeframe in {"1h", "4h"}:
                        warmup_days = max(14, warmup_bars // 4 + 7)
                    else:
                        warmup_days = max(7, warmup_bars // 20 + 3)

                    return start_dt - timedelta(days=warmup_days)

                # Create data source
                if request.data_source == 'ibkr':
                    data_source = IBKRDataSource()
                else:
                    data_source = CachedDataSource(
                        YahooDataSource(),
                        self.repository,
                        data_source_name='yahoo'
                    )

                # Resolve symbols
                symbols = [s.upper().strip() for s in (request.symbols or []) if s and s.strip()]
                if request.mode == "rule" and not symbols:
                    symbols = self.repository.get_active_symbols()
                if request.mode == "rule" and not symbols:
                    raise ValueError("No symbols provided and no active watchlist found")

                entries = []
                candle_cache: Dict[str, List[Dict[str, Any]]] = {}

                async def _fetch_candles(symbol: str, start_dt: datetime, end_dt: datetime) -> List[Dict[str, Any]]:
                    key = f"{symbol}|{start_dt.isoformat()}|{end_dt.isoformat()}|{request.timeframe}|{request.data_source}"
                    if key in candle_cache:
                        return candle_cache[key]
                    candles = await data_source.fetch_historical_data(
                        symbol=symbol,
                        start_date=start_dt,
                        end_date=end_dt,
                        timeframe=request.timeframe
                    )
                    candle_cache[key] = candles or []
                    return candle_cache[key]

                # Build entries from rule mode
                if request.mode == "rule":
                    if not request.rule_id:
                        raise ValueError("rule_id is required for rule mode")
                    if not request.start_at or not request.end_at:
                        raise ValueError("start_at and end_at are required for rule mode")

                    start_at = _normalize_dt(_parse_dt(request.start_at, "start_at"))
                    end_at = _normalize_dt(_parse_dt(request.end_at, "end_at"))
                    if end_at <= start_at:
                        raise ValueError("end_at must be later than start_at")

                    rule = self.repository.get_rule(request.rule_id)
                    if not rule:
                        raise ValueError(f"Rule with ID {request.rule_id} not found")
                    rule_to_evaluate = {**rule, **rule['definition']}
                    rule_engine = RuleEngine()
                    required_operands = _required_rule_operands(rule_to_evaluate)
                    warmup_start_at = _rule_warmup_start(start_at, rule_to_evaluate, request.timeframe)

                    for symbol in symbols:
                        candles = await _fetch_candles(symbol, warmup_start_at, end_at)
                        if not candles:
                            continue

                        indicator_engine = IndicatorEngine(timeframe=request.timeframe)
                        indicator_engine.set_required_operands(rule_to_evaluate)
                        cooldown_seconds = rule_to_evaluate.get('cooldown_sec', 60)
                        last_signal_ts = None

                        for candle in candles:
                            raw_ts = candle['timestamp']
                            ts = _normalize_dt(raw_ts)
                            ts_unix = ts.timestamp() if isinstance(ts, datetime) else float(ts)

                            candle_completed = indicator_engine.update_candle_data(
                                symbol=symbol,
                                open_price=candle['open'],
                                high=candle['high'],
                                low=candle['low'],
                                close=candle['close'],
                                timestamp=ts_unix,
                                volume=candle.get('volume', 0),
                                suppress_warnings=True
                            )
                            if not candle_completed:
                                continue
                            if not indicator_engine.is_symbol_ready(symbol):
                                continue
                            if ts < start_at:
                                continue
                            if last_signal_ts is not None and (ts_unix - last_signal_ts) < cooldown_seconds:
                                continue

                            indicators = indicator_engine.get_indicators(symbol)
                            if not indicators:
                                continue
                            if not _has_required_indicators(indicators, required_operands):
                                continue

                            if rule_engine.evaluate(rule_to_evaluate, indicators):
                                entries.append({
                                    "symbol": symbol,
                                    "entry_time": ts if isinstance(ts, datetime) else datetime.fromtimestamp(ts_unix),
                                    "display_time": _wall_clock_iso(raw_ts) if isinstance(raw_ts, datetime) else None,
                                    "entry_price": _basis_price(candle, entry_price_basis),
                                    "entry_price_basis": entry_price_basis,
                                    "signal_type": str(rule_to_evaluate.get('signal_type', 'BUY')).upper(),
                                    "source": "rule"
                                })
                                last_signal_ts = ts_unix

                # Build entries from manual mode
                else:
                    if not request.manual_entries or len(request.manual_entries) == 0:
                        raise ValueError("manual_entries is required for manual mode")

                    for item in request.manual_entries:
                        entry_time = _normalize_dt(_parse_dt(item.entry_time, "manual_entries.entry_time"))
                        entries.append({
                            "symbol": item.symbol.upper().strip(),
                            "entry_time": entry_time,
                            "display_time": None,
                            "entry_price": float(item.entry_price) if item.entry_price is not None else None,
                            "entry_price_basis": "manual" if item.entry_price is not None else entry_price_basis,
                            "signal_type": (item.signal_type or "BUY").upper(),
                            "source": "manual"
                        })

                # Enrich entries with T+1 ... T+n OHLC
                rows = []
                for entry in entries:
                    symbol = entry["symbol"]
                    entry_time = _normalize_dt(entry["entry_time"])

                    # pull wider range so we can include next n candles
                    lookahead_days = 365 if request.timeframe in ('1d',) else 90
                    candles = await _fetch_candles(
                        symbol,
                        entry_time.replace(hour=0, minute=0, second=0, microsecond=0),
                        entry_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=lookahead_days)
                    )
                    if not candles:
                        continue

                    # find first candle >= entry_time
                    idx = None
                    for i, c in enumerate(candles):
                        cts = _normalize_dt(c['timestamp'])
                        if cts >= entry_time:
                            idx = i
                            break
                    if idx is None:
                        continue

                    entry_candle = candles[idx]
                    entry_basis = entry.get("entry_price_basis") or entry_price_basis
                    entry_price = entry["entry_price"] if entry["entry_price"] is not None else _basis_price(entry_candle, entry_price_basis)

                    step_values = {}
                    signal_type = str(entry.get("signal_type", "BUY")).upper()
                    for step in range(1, request.n_steps + 1):
                        ci = idx + step
                        if ci >= len(candles):
                            step_values[f"T+{step}"] = None
                            continue
                        c = candles[ci]
                        basis_price = _basis_price(c, exit_price_basis)
                        trade_pl = _calculate_trade_pl(signal_type, float(entry_price), basis_price)
                        step_values[f"T+{step}"] = {
                            "time": _wall_clock_iso(c['timestamp']) if isinstance(c['timestamp'], datetime) else str(c['timestamp']),
                            "open": float(c['open']),
                            "high": float(c['high']),
                            "low": float(c['low']),
                            "close": float(c['close']),
                            "basis": exit_price_basis,
                            "exit_price_basis": exit_price_basis,
                            "basis_price": basis_price,
                            "exit_price": basis_price,
                            "pl": trade_pl["pl"],
                            "pl_pct": trade_pl["pl_pct"]
                        }

                    rows.append({
                        "symbol": symbol,
                        "signal_type": signal_type,
                        "entry_time": entry.get("display_time") or _utc_iso(entry_time),
                        "entry_price": float(entry_price),
                        "entry_price_basis": entry_basis,
                        "source": entry["source"],
                        "steps": step_values
                    })

                metrics = _calculate_metrics(rows, request.n_steps, exit_price_basis)

                return {
                    "mode": request.mode,
                    "timeframe": request.timeframe,
                    "n_steps": request.n_steps,
                    "entry_price_basis": entry_price_basis,
                    "exit_price_basis": exit_price_basis,
                    "pl_basis": exit_price_basis,
                    "row_count": len(rows),
                    "metrics": metrics,
                    "rows": rows
                }

            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                self.logger.error(f"Backtest screen error: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Backtest screen failed: {str(e)}"
                )
        
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
                from .data_sources import CachedDataSource, IBKRDataSource, YahooDataSource
                
                # Parse dates
                start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
                end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
                
                # Create data source
                if request.data_source == 'ibkr':
                    data_source = IBKRDataSource()
                else:
                    data_source = CachedDataSource(
                        YahooDataSource(),
                        self.repository,
                        data_source_name='yahoo'
                    )
                
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
        
        @self.app.get("/api/swing/chart")
        async def get_swing_chart(
            symbol: str,
            timeframe: str,
            timestamp: str,
            rule_id: int,
            before: int = 80,
            after: int = 40
        ):
            """Get candle and rule-indicator series for a screener result chart."""
            try:
                import math
                import pandas as pd
                import ta
                from datetime import timezone
                from .data_sources import CachedDataSource, YahooDataSource

                if timeframe not in {"1h", "4h", "1d"}:
                    raise ValueError("timeframe must be one of: 1h, 4h, 1d")
                before = min(250, max(10, before))
                after = min(120, max(0, after))
                symbol = symbol.upper().strip()
                if not symbol:
                    raise ValueError("symbol is required")

                rule = self.repository.get_rule(rule_id)
                if not rule:
                    raise ValueError(f"Rule with ID {rule_id} not found")

                signal_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if signal_dt.tzinfo is not None:
                    signal_dt = signal_dt.astimezone(timezone.utc).replace(tzinfo=None)

                rule_to_evaluate = {**rule, **rule['definition']}
                operands = RuleEngine.extract_required_operands(rule_to_evaluate)
                base_operands = set()
                for operand in operands:
                    if not isinstance(operand, str) or RuleEngine._is_numeric_literal(operand):
                        continue
                    prev_n = RuleEngine.parse_prev_n_operand(operand)
                    if prev_n:
                        base_operands.add(prev_n["base"])
                    elif operand.endswith("_PREV"):
                        base_operands.add(operand[:-5])
                    else:
                        base_operands.add(operand)
                base_operands = sorted(base_operands)

                total_bars = before + after + RuleEngine.estimate_rule_warmup(rule_to_evaluate, default=80)
                if timeframe == "1d":
                    fetch_days = (total_bars * 2) + 10
                elif timeframe == "4h":
                    fetch_days = max(60, total_bars // 2 + 20)
                else:
                    fetch_days = max(30, total_bars // 4 + 14)

                data_source = CachedDataSource(
                    YahooDataSource(),
                    self.repository,
                    data_source_name='yahoo'
                )
                candles = await data_source.fetch_historical_data(
                    symbol=symbol,
                    start_date=signal_dt - timedelta(days=fetch_days),
                    end_date=signal_dt + timedelta(days=fetch_days),
                    timeframe=timeframe
                )
                if not candles:
                    raise ValueError("No chart data available")

                def _normalize_dt(value: Any) -> datetime:
                    if isinstance(value, datetime):
                        if value.tzinfo is not None:
                            return value.astimezone(timezone.utc).replace(tzinfo=None)
                        return value
                    return datetime.fromtimestamp(float(value))

                indexed = [(idx, _normalize_dt(candle['timestamp']), candle) for idx, candle in enumerate(candles)]
                nearest_idx, _, _ = min(
                    indexed,
                    key=lambda item: abs((item[1] - signal_dt).total_seconds())
                )
                start_idx = max(0, nearest_idx - before)
                end_idx = min(len(candles), nearest_idx + after + 1)
                visible_candles = candles[start_idx:end_idx]

                df = pd.DataFrame({
                    'timestamp': [_normalize_dt(c['timestamp']) for c in candles],
                    'open': [float(c['open']) for c in candles],
                    'high': [float(c['high']) for c in candles],
                    'low': [float(c['low']) for c in candles],
                    'close': [float(c['close']) for c in candles],
                    'volume': [float(c.get('volume', 0) or 0) for c in candles],
                })

                def _chart_time(value: datetime) -> int:
                    return int(value.replace(tzinfo=timezone.utc).timestamp())

                def _series_points(values) -> List[Dict[str, Any]]:
                    points = []
                    for idx in range(start_idx, end_idx):
                        value = values.iloc[idx] if hasattr(values, "iloc") else values[idx]
                        if value is None or pd.isna(value):
                            continue
                        numeric = float(value)
                        if not math.isfinite(numeric):
                            continue
                        points.append({
                            "time": _chart_time(df['timestamp'].iloc[idx]),
                            "value": numeric
                        })
                    return points

                def _series_from_operand(operand: str) -> Optional[Dict[str, Any]]:
                    base = operand[:-5] if operand.endswith("_PREV") else operand
                    parsed = RuleEngine.parse_dynamic_operand(base)
                    panel = "overlay"
                    series_type = "line"
                    values = None

                    if base in {"PRICE", "PREV_CLOSE", "PREV_OPEN"} or base.startswith("PRICE_PREV_"):
                        return None
                    if parsed:
                        period = parsed["period"]
                        operand_type = parsed["type"]
                        if operand_type == "MA_N":
                            values = ta.trend.sma_indicator(df['close'], window=period)
                        elif operand_type == "EMA_N":
                            values = ta.trend.ema_indicator(df['close'], window=period)
                        elif operand_type == "RSI_N":
                            values = ta.momentum.rsi(df['close'], window=period)
                            panel = "oscillator"
                        elif operand_type == "ADX_N":
                            values = ta.trend.adx(df['high'], df['low'], df['close'], window=period)
                            panel = "oscillator"
                        elif operand_type == "SMA_VOLUME_N":
                            values = ta.trend.sma_indicator(df['volume'], window=period)
                            panel = "volume"
                        elif operand_type == "REL_VOLUME_N":
                            sma_volume = ta.trend.sma_indicator(df['volume'], window=period)
                            values = df['volume'] / sma_volume.where(sma_volume != 0)
                            panel = "volume"
                        else:
                            return None
                    elif base.startswith("MA") and base[2:].isdigit():
                        values = ta.trend.sma_indicator(df['close'], window=int(base[2:]))
                    elif base.startswith("EMA") and base[3:].isdigit():
                        values = ta.trend.ema_indicator(df['close'], window=int(base[3:]))
                    elif base.startswith("RSI") and base[3:].isdigit():
                        values = ta.momentum.rsi(df['close'], window=int(base[3:]))
                        panel = "oscillator"
                    elif base.startswith("ADX") and base[3:].isdigit():
                        values = ta.trend.adx(df['high'], df['low'], df['close'], window=int(base[3:]))
                        panel = "oscillator"
                    elif base == "MACD":
                        values = ta.trend.macd(df['close'])
                        panel = "macd"
                    elif base == "MACD_SIGNAL":
                        values = ta.trend.macd_signal(df['close'])
                        panel = "macd"
                    elif base == "MACD_HIST":
                        values = ta.trend.macd_diff(df['close'])
                        panel = "macd"
                        series_type = "histogram"
                    elif base in {"BB_UPPER", "BB_MIDDLE", "BB_LOWER"}:
                        if base == "BB_UPPER":
                            values = ta.volatility.bollinger_hband(df['close'])
                        elif base == "BB_MIDDLE":
                            values = ta.volatility.bollinger_mavg(df['close'])
                        else:
                            values = ta.volatility.bollinger_lband(df['close'])
                    elif base == "STOCH_K":
                        values = ta.momentum.stoch(df['high'], df['low'], df['close'])
                        panel = "oscillator"
                    elif base == "STOCH_D":
                        values = ta.momentum.stoch_signal(df['high'], df['low'], df['close'])
                        panel = "oscillator"
                    elif base == "VOLUME":
                        values = df['volume']
                        panel = "volume"
                        series_type = "histogram"
                    elif base == "SMA_VOLUME_20":
                        values = ta.trend.sma_indicator(df['volume'], window=20)
                        panel = "volume"
                    elif base == "REL_VOLUME_20":
                        sma_volume = ta.trend.sma_indicator(df['volume'], window=20)
                        values = df['volume'] / sma_volume.where(sma_volume != 0)
                        panel = "volume"
                    else:
                        return None

                    points = _series_points(values)
                    if not points:
                        return None
                    return {
                        "id": base,
                        "label": base,
                        "panel": panel,
                        "type": series_type,
                        "enabled": True,
                        "points": points
                    }

                indicator_series = []
                seen = set()
                for operand in base_operands:
                    try:
                        series = _series_from_operand(operand)
                    except Exception as ex:
                        self.logger.debug(f"Skipping chart indicator {operand}: {ex}")
                        series = None
                    if series and series["id"] not in seen:
                        indicator_series.append(series)
                        seen.add(series["id"])

                response_candles = []
                for candle in visible_candles:
                    candle_dt = _normalize_dt(candle['timestamp'])
                    response_candles.append({
                        "time": _chart_time(candle_dt),
                        "timestamp": candle_dt.isoformat(),
                        "open": float(candle['open']),
                        "high": float(candle['high']),
                        "low": float(candle['low']),
                        "close": float(candle['close']),
                        "volume": int(candle.get('volume', 0) or 0)
                    })

                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "rule_id": rule_id,
                    "rule_name": rule.get("name"),
                    "signal_timestamp": signal_dt.isoformat(),
                    "signal_time": _chart_time(signal_dt),
                    "before": before,
                    "after": after,
                    "candles": response_candles,
                    "indicators": indicator_series,
                    "rule_operands": base_operands,
                    "rule": {
                        "id": rule_id,
                        "name": rule.get("name"),
                        "type": rule.get("type"),
                        "is_system": bool(rule.get("is_system")),
                        "logic": rule_to_evaluate.get("logic", "AND"),
                        "signal_type": rule_to_evaluate.get("signal_type", "BUY"),
                        "conditions": rule_to_evaluate.get("conditions", []),
                        "cooldown_sec": rule_to_evaluate.get("cooldown_sec")
                    }
                }
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                self.logger.error(f"Swing chart error: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Swing chart failed: {str(e)}"
                )

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
                request_id = str(uuid4())
                start_time = time.perf_counter()

                def _parse_screen_date(value: Optional[str], field_name: str) -> Optional[datetime]:
                    if not value:
                        return None
                    try:
                        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except Exception as ex:
                        raise ValueError(f"Invalid {field_name}: {value}") from ex

                    if parsed.tzinfo is not None:
                        parsed = parsed.astimezone().replace(tzinfo=None)
                    return parsed

                start_date = _parse_screen_date(request.start_date, "start_date")
                end_date = _parse_screen_date(request.end_date, "end_date")

                if bool(start_date) != bool(end_date):
                    raise ValueError("start_date and end_date must be provided together")

                if start_date and end_date:
                    if end_date <= start_date:
                        raise ValueError("end_date must be later than start_date")
                
                # Create screening engine
                engine = SwingScreeningEngine(timeframe=request.timeframe)
                
                # Run screening
                self.logger.info(f"Starting swing screening on universe {request.ticker_universe_id}")
                results = await engine.screen_universe(
                    universe_id=request.ticker_universe_id,
                    rule_id=request.rule_id,
                    lookback_days=request.lookback_days,
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Filter out errors for summary
                successful = [r for r in results if r['status'] == 'success']
                signals_found = [r for r in successful if r['signal'] is not None]
                no_data = [
                    r for r in results
                    if 'no data available' in (r.get('error_message') or '').lower()
                ]
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                return {
                    "message": "Screening completed successfully",
                    "request_id": request_id,
                    "results": results,
                    "summary": {
                        "total_tickers": len(results),
                        "successful": len(successful),
                        "signals_found": len(signals_found),
                        "errors": len(results) - len(successful),
                        "no_data": len(no_data),
                        "duration_ms": duration_ms,
                        "screening_start": start_date.isoformat() if start_date else None,
                        "screening_end": end_date.isoformat() if end_date else None,
                        "lookback_days": request.lookback_days if not start_date else None
                    }
                }
                
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                request_id = str(uuid4())
                self.logger.exception(f"Screening error (request_id={request_id}): {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Screening failed due to an internal error. request_id={request_id}"
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
