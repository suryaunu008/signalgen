"""
Database Initialization Script

This script initializes the SQLite database with default data for the SignalGen system.
It creates the database schema and seeds it with the default scalping rule and initial settings.

Default Rule (as specified in PROJECT_SPRINT_PHASE1.md):
- NAME: "Default Scalping"
- TYPE: "system"
- LOGIC: "AND" with 13 conditions (EMA crossovers, MACD, RSI, ADX momentum)
- IS_SYSTEM: true (readonly, cannot be deleted)

Initial Settings:
- app_version: Current app version
- max_symbols_per_watchlist: 5 (MVP limitation)
- default_cooldown_sec: 60 (default cooldown between signals)
"""

import logging
from datetime import datetime
from .sqlite_repo import SQLiteRepository

logger = logging.getLogger(__name__)

def initialize_database(db_path: str = 'signalgen.db') -> None:
    """
    Initialize the database with schema and default data.
    
    Args:
        db_path: Path to SQLite database file
    """
    repo = SQLiteRepository(db_path)
    
    try:
        # Initialize database schema
        repo.initialize_database()
        logger.info("Database schema initialized")
        
        # Seed default rule if it doesn't exist
        _seed_default_rule(repo)
        
        # Set initial settings
        _seed_initial_settings(repo)
        
        # Create default watchlist if none exists
        _create_default_watchlist(repo)
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

def _seed_default_rule(repo: SQLiteRepository) -> None:
    """
    Seed the default system rule if it doesn't exist.
    
    Args:
        repo: SQLiteRepository instance
    """
    # Check if default rule already exists
    existing_rules = repo.get_all_rules()
    for rule in existing_rules:
        if rule.get('is_system') and rule['name'] == "Default Scalping":
            logger.info("Default rule already exists, skipping seeding")
            return
    
    # Create default scalping rule as specified in PROJECT_SPRINT_PHASE1.md
    default_rule_definition = {
        "id": 1,
        "name": "Default Scalping",
        "type": "system",
        "logic": "AND",
        "conditions": [
            {"left": "PREV_CLOSE", "op": ">", "right": "PREV_OPEN"},
            
            {"left": "EMA6", "op": "CROSS_UP", "right": "EMA10"},
            {"left": "EMA6", "op": "CROSS_UP", "right": "EMA20"},
            
            {"left": "PRICE", "op": ">=", "right": "EMA20"},
            {"left": "PRICE_EMA20_DIFF_PCT", "op": "<=", "right": 0.01},
            
            {"left": "MACD_HIST", "op": ">", "right": "MACD_HIST_PREV"},
            {"left": "MACD_HIST", "op": ">", "right": 0},
            {"left": "MACD_HIST_PREV", "op": ">", "right": 0},
            
            {"left": "ADX5", "op": ">", "right": "ADX5_PREV"},
            {"left": "ADX5", "op": ">", "right": 0},
            
            {"left": "RSI14", "op": ">", "right": "RSI14_PREV"},
            {"left": "RSI14_PREV", "op": "<", "right": 40},
            {"left": "RSI14", "op": ">", "right": 40}
        ],
        "cooldown_sec": 60
    }
    
    rule_id = repo.create_rule(
        name="Default Scalping",
        rule_type="system",
        definition=default_rule_definition,
        is_system=True
    )
    
    logger.info(f"Created default rule with ID: {rule_id}")

def _seed_initial_settings(repo: SQLiteRepository) -> None:
    """
    Set initial application settings.
    
    Args:
        repo: SQLiteRepository instance
    """
    initial_settings = {
        "app_version": "1.0.0",
        "max_symbols_per_watchlist": 5,
        "default_cooldown_sec": 60,
        "ibkr_host": "127.0.0.1",
        "ibkr_port": 7497,
        "ibkr_client_id": 1,
        "data_feed_type": "live",
        "bar_size": "5 secs",
        "websocket_port": 8765
    }
    
    for key, value in initial_settings.items():
        # Only set if not already exists
        if repo.get_setting(key) is None:
            repo.set_setting(key, value)
            logger.info(f"Set initial setting: {key} = {value}")

def _create_default_watchlist(repo: SQLiteRepository) -> None:
    """
    Create a default watchlist if none exists.
    
    Args:
        repo: SQLiteRepository instance
    """
    existing_watchlists = repo.get_all_watchlists()
    if existing_watchlists:
        logger.info("Watchlists already exist, skipping default creation")
        return
    
    # Create default watchlist with common tech stocks
    default_symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]
    
    watchlist_id = repo.create_watchlist(
        name="Default Tech Stocks",
        symbols=default_symbols
    )
    
    # Set it as active
    repo.set_active_watchlist(watchlist_id)
    
    logger.info(f"Created default watchlist with ID: {watchlist_id}")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize database
    initialize_database()