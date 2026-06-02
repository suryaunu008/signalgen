"""
Database Initialization Script

This script initializes the SQLite database with default data for the SignalGen system.
It creates the database schema and seeds it with the default scalping rule and initial settings.

Default Rules:
- NAME: "Default Scalping"
- TYPE: "system"
- LOGIC: "AND" with 4 conditions
- CONDITIONS:
  * EMA9 > EMA20 (short-term trend)
  * PRICE > EMA9 (momentum continuation)
  * 45 < RSI14 < 75 (healthy momentum)
- IS_SYSTEM: true (readonly, cannot be deleted)

Initial Settings:
- app_version: Current app version
- default_cooldown_sec: 60 (default cooldown between signals)
"""

import json
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
        
        # Seed ticker universes if none exist
        _seed_ticker_universes(repo)
        
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
    system_rules = [
        {
            "id": 1,
            "name": "Default Scalping",
            "conditions": [
                {"left": "EMA9", "op": ">", "right": "EMA20"},
                {"left": "PRICE", "op": ">", "right": "EMA9"},
                {"left": "RSI14", "op": ">", "right": 45},
                {"left": "RSI14", "op": "<", "right": 75},
            ],
            "cooldown_sec": 60,
        },
        {
            "id": 2,
            "name": "EMA Momentum Scalping",
            "conditions": [
                {"left": "EMA9", "op": ">", "right": "EMA20"},
                {"left": "MACD", "op": ">", "right": "MACD_SIGNAL"},
                {"left": "RSI14", "op": ">", "right": 50},
                {"left": "RSI14", "op": "<", "right": 80},
            ],
            "cooldown_sec": 60,
        },
        {
            "id": 3,
            "name": "BB Pullback Scalping",
            "conditions": [
                {"left": "PRICE", "op": "<", "right": "BB_MIDDLE"},
                {"left": "RSI14", "op": ">", "right": 25},
                {"left": "RSI14", "op": "<", "right": 45},
            ],
            "cooldown_sec": 90,
        },
        {
            "id": 4,
            "name": "Trend Continuation Scalping",
            "conditions": [
                {"left": "PRICE", "op": ">", "right": "EMA20"},
                {"left": "EMA20", "op": ">", "right": "EMA50"},
                {"left": "RSI14", "op": ">", "right": 50},
                {"left": "RSI14", "op": "<", "right": 78},
            ],
            "cooldown_sec": 60,
        },
    ]

    for rule in system_rules:
        definition = {
            "id": rule["id"],
            "name": rule["name"],
            "type": "system",
            "logic": "AND",
            "signal_type": "BUY",
            "conditions": rule["conditions"],
            "cooldown_sec": rule["cooldown_sec"],
        }
        _upsert_system_rule(repo, rule["name"], definition)


def _upsert_system_rule(repo: SQLiteRepository, name: str, definition: dict) -> None:
    existing = next(
        (rule for rule in repo.get_all_rules() if rule.get('is_system') and rule.get('name') == name),
        None
    )
    if not existing:
        rule_id = repo.create_rule(
            name=name,
            rule_type="system",
            definition=definition,
            is_system=True
        )
        logger.info(f"Created system rule '{name}' with ID: {rule_id}")
        return

    with repo._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE rules
            SET definition = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_system = TRUE
        ''', (json.dumps(definition), existing['id']))
        conn.commit()
    logger.info(f"Updated system rule '{name}'")

def _seed_initial_settings(repo: SQLiteRepository) -> None:
    """
    Set initial application settings.
    
    Args:
        repo: SQLiteRepository instance
    """
    initial_settings = {
        "app_version": "1.0.0",
        "default_cooldown_sec": 60,
        "ibkr_host": "127.0.0.1",
        "ibkr_port": 7497,
        "ibkr_client_id": 1,
        "data_feed_type": "live",
        "bar_size": "5 secs",
        "websocket_port": 8765,
        "timeframe": "1m"  # Default timeframe: 1 minute
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

def _seed_ticker_universes(repo: SQLiteRepository) -> None:
    """
    Seed default ticker universes for swing trading.
    
    Args:
        repo: SQLiteRepository instance
    """
    existing_universes = repo.get_all_ticker_universes()
    if existing_universes:
        logger.info("Ticker universes already exist, skipping seeding")
        return
    
    # Tech Giants
    repo.create_ticker_universe(
        name="Tech Giants",
        tickers=["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
        description="Major technology stocks"
    )
    
    # S&P 100 Top Holdings
    repo.create_ticker_universe(
        name="S&P 100 Top 20",
        tickers=[
            "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK.B",
            "LLY", "AVGO", "JPM", "WMT", "V", "UNH", "XOM", "ORCL", "MA", "HD",
            "PG", "COST"
        ],
        description="Top 20 holdings in S&P 100 index"
    )
    
    # Popular Trading Stocks
    repo.create_ticker_universe(
        name="Popular Traders",
        tickers=["SPY", "QQQ", "TSLA", "AAPL", "NVDA", "AMD", "AMZN", "MSFT", "META", "GOOGL"],
        description="Most actively traded stocks and ETFs"
    )
    
    # Custom (empty for user to fill)
    repo.create_ticker_universe(
        name="Custom",
        tickers=[],
        description="User-defined ticker universe"
    )
    
    logger.info("Seeded default ticker universes")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize database
    initialize_database()
