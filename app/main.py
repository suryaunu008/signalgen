"""
Main Entry Point Module

This module provides the application entry point for the SignalGen desktop application.
It initializes PyWebView, FastAPI server, and coordinates the application lifecycle.

Key Features:
- PyWebView desktop window management
- FastAPI server startup and coordination
- Database initialization
- Default rule seeding
- Graceful shutdown handling
- Error handling and logging

Application Flow:
1. Initialize database and seed default data
2. Start FastAPI server in background thread
3. Start Socket.IO server in background thread
4. Create PyWebView window with local URL
5. Run application until window is closed

MVP Configuration:
- Single desktop window application
- Local FastAPI server on localhost:3456
- Local Socket.IO server on localhost:8765
- SQLite database in application directory

Typical Usage:
    if __name__ == "__main__":
        main()
"""

import asyncio
import logging
import sys
import threading
import webview
from typing import Optional
import uvicorn
from pathlib import Path

from .app import signalgen_app
from .storage.sqlite_repo import SQLiteRepository

def setup_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('signalgen.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def seed_default_data(repository: SQLiteRepository) -> None:
    """
    Seed default data for MVP.
    
    Args:
        repository: Database repository instance
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Default rule creation is now handled by init_db.py
        # Check for "Default Scalping" rule exists
        existing_rules = repository.get_all_rules()
        default_rule_exists = any(
            rule.get('name') == 'Default Scalping' and rule.get('is_system')
            for rule in existing_rules
        )
        
        if not default_rule_exists:
            logger.warning("Default Scalping rule not found. Please run: python -m app.storage.init_db")
        
        # Create default watchlist if none exists
        existing_watchlists = repository.get_all_watchlists()
        if not existing_watchlists:
            repository.create_watchlist(
                name="Default Watchlist",
                symbols=["AAPL", "MSFT", "GOOGL"]
            )
            
            # Set it as active
            watchlists = repository.get_all_watchlists()
            if watchlists:
                repository.set_active_watchlist(watchlists[0]['id'])
            
            logger.info("Default watchlist created and activated")
        
        # Set default application settings
        default_settings = {
            'ib_host': '127.0.0.1',
            'ib_port': 7497,
            'ib_client_id': 1,
            'max_watchlist_symbols': 5,
            'default_cooldown': 60,
            'bar_size': 5,  # 5-second bars
            'ui_theme': 'light'
        }
        
        for key, value in default_settings.items():
            if repository.get_setting(key) is None:
                repository.set_setting(key, value)
        
        logger.info("Default settings configured")
        
    except Exception as e:
        logger.error(f"Error seeding default data: {e}")

def start_fastapi_server(host: str = '127.0.0.1', port: int = 3456) -> threading.Thread:
    """
    Start FastAPI server in a separate thread.
    
    Args:
        host: Server host
        port: Server port
        
    Returns:
        threading.Thread: Server thread
    """
    logger = logging.getLogger(__name__)
    
    def run_server():
        try:
            uvicorn.run(
                "app.app:app",
                host=host,
                port=port,
                log_level="info",
                access_log=False
            )
        except Exception as e:
            logger.error(f"FastAPI server error: {e}")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    logger.info(f"FastAPI server started on http://{host}:{port}")
    
    return server_thread

def start_socketio_server(broadcaster, host: str = '127.0.0.1', port: int = 8765) -> threading.Thread:
    """
    Start Socket.IO server in a separate thread.
    
    Args:
        broadcaster: Socket.IO broadcaster instance
        host: Server host
        port: Server port
        
    Returns:
        threading.Thread: Server thread
    """
    logger = logging.getLogger(__name__)
    
    def run_server():
        try:
            # Create ASGI app from broadcaster
            socketio_app = broadcaster.create_asgi_app()
            
            # Run uvicorn server
            uvicorn.run(
                socketio_app,
                host=host,
                port=port,
                log_level="info",
                access_log=False
            )
        except Exception as e:
            logger.error(f"Socket.IO server error: {e}")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    logger.info(f"Socket.IO server started on ws://{host}:{port}")
    
    return server_thread

def create_pywebview_window(url: str = "http://127.0.0.1:3456", title: str = "SignalGen") -> webview.Window:
    """
    Create PyWebView window with specified URL.
    
    Args:
        url: URL to load in the webview
        title: Window title
        
    Returns:
        webview.Window: Configured webview window
    """
    logger = logging.getLogger(__name__)
    
    try:
        window = webview.create_window(
            title=title,
            url=url,
            width=1400,
            height=900,
            resizable=True,
            min_size=(1000, 700),
            confirm_close=True
        )
        
        logger.info(f"PyWebView window created with URL: {url}")
        return window
        
    except Exception as e:
        logger.error(f"Error creating PyWebView window: {e}")
        raise

def main() -> None:
    """Main application entry point."""
    logger = logging.getLogger(__name__)
    
    try:
        # Setup logging
        setup_logging()
        logger.info("SignalGen application starting")
        
        # Initialize database
        signalgen_app.initialize_database()
        
        # Seed default data
        seed_default_data(signalgen_app.repository)
        
        # Start FastAPI server
        fastapi_thread = start_fastapi_server()
        
        # Start Socket.IO server
        socketio_thread = start_socketio_server(signalgen_app.broadcaster)
        
        # Wait a moment for servers to start
        import time
        time.sleep(2)
        
        # Create PyWebView window
        window = create_pywebview_window()
        
        logger.info("All components started, running application")
        
        # Run the webview (this blocks until window is closed)
        webview.start(debug=True)
        
        logger.info("Application shutdown initiated")
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        sys.exit(1)
    finally:
        logger.info("SignalGen application stopped")

if __name__ == "__main__":
    main()