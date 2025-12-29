"""
SQLite Repository Module

This module provides database operations for the SignalGen scalping system.
It handles all SQLite database operations for rules, watchlists, signals, and settings.

Database Schema:
- rules: Trading rules with JSON definitions
- watchlists: Symbol watchlists for monitoring
- watchlist_items: Individual symbols within watchlists
- signals: Generated trading signals
- settings: Application configuration settings

Key Features:
- Thread-safe database operations
- Automatic database initialization
- Connection pooling for performance
- Transaction management
- Data migration support

MVP Limitations:
- Single SQLite file (no client-server architecture)
- Maximum 5 symbols per watchlist
- One active watchlist at a time

Typical Usage:
    repo = SQLiteRepository()
    repo.initialize_database()
    rules = repo.get_all_rules()
    repo.save_signal(signal_data)
"""

import sqlite3
import json
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

class SQLiteRepository:
    """
    SQLite database repository for all data persistence operations.
    
    This class provides a clean interface for database operations with
    proper connection management and error handling.
    """
    
    def __init__(self, db_path: str = 'signalgen.db'):
        """
        Initialize repository with database path.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def initialize_database(self) -> None:
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create rules table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT CHECK(type IN ('system', 'custom')) NOT NULL,
                    definition TEXT NOT NULL,
                    is_system BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create watchlists table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS watchlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create watchlist_items table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS watchlist_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    watchlist_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (watchlist_id) REFERENCES watchlists(id) ON DELETE CASCADE
                )
            ''')
            
            # Create signals table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    time TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    rule_id INTEGER,
                    indicators TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (rule_id) REFERENCES rules(id) ON DELETE SET NULL
                )
            ''')
            
            # Check if indicators column exists, add it if not (migration)
            cursor.execute("PRAGMA table_info(signals)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'indicators' not in columns:
                cursor.execute('ALTER TABLE signals ADD COLUMN indicators TEXT')
                self.logger.info("Added indicators column to signals table")
            
            # Create settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_time ON signals(time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_watchlist_items_watchlist_id ON watchlist_items(watchlist_id)')
            
            # Create backtest_runs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    mode TEXT CHECK(mode IN ('scalping', 'swing')) NOT NULL,
                    rule_id INTEGER NOT NULL,
                    symbols TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    data_source TEXT CHECK(data_source IN ('ibkr', 'yahoo')) NOT NULL,
                    created_at TEXT NOT NULL,
                    total_signals INTEGER DEFAULT 0,
                    metadata TEXT,
                    FOREIGN KEY (rule_id) REFERENCES rules(id) ON DELETE CASCADE
                )
            ''')
            
            # Create backtest_signals table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backtest_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backtest_run_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    price REAL NOT NULL,
                    indicators TEXT,
                    FOREIGN KEY (backtest_run_id) REFERENCES backtest_runs(id) ON DELETE CASCADE
                )
            ''')
            
            # Create ticker_universes table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ticker_universes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    tickers TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            # Create indexes for backtesting tables
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backtest_runs_created_at ON backtest_runs(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backtest_signals_timestamp ON backtest_signals(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backtest_signals_run_id ON backtest_signals(backtest_run_id)')
            
            conn.commit()
            self.logger.info("Database initialized successfully")
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Get database connection with proper configuration.
        
        Returns:
            sqlite3.Connection: Database connection
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
    # Rules operations
    def create_rule(self, name: str, rule_type: str, definition: Dict, is_system: bool = False) -> int:
        """
        Create a new trading rule.
        
        Args:
            name: Rule name
            rule_type: Rule type ('system' or 'custom')
            definition: Rule definition as dictionary
            is_system: Whether this is a system rule
            
        Returns:
            int: ID of created rule
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO rules (name, type, definition, is_system)
                VALUES (?, ?, ?, ?)
            ''', (name, rule_type, json.dumps(definition), is_system))
            conn.commit()
            return cursor.lastrowid
    
    def get_rule(self, rule_id: int) -> Optional[Dict]:
        """
        Get rule by ID.
        
        Args:
            rule_id: Rule ID
            
        Returns:
            Optional[Dict]: Rule data or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM rules WHERE id = ?', (rule_id,))
            row = cursor.fetchone()
            
            if row:
                rule = dict(row)
                rule['definition'] = json.loads(rule['definition'])
                return rule
            return None
    
    def get_all_rules(self) -> List[Dict]:
        """
        Get all rules.
        
        Returns:
            List[Dict]: List of all rules
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM rules ORDER BY created_at')
            rows = cursor.fetchall()
            
            rules = []
            for row in rows:
                rule = dict(row)
                rule['definition'] = json.loads(rule['definition'])
                rules.append(rule)
            
            return rules
    
    def update_rule(self, rule_id: int, name: str = None, definition: Dict = None) -> bool:
        """
        Update rule.
        
        Args:
            rule_id: Rule ID
            name: New name (optional)
            definition: New definition (optional)
            
        Returns:
            bool: True if update successful, False otherwise
        """
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        
        if definition is not None:
            updates.append("definition = ?")
            params.append(json.dumps(definition))
        
        if not updates:
            return False
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(rule_id)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE rules SET {', '.join(updates)}
                WHERE id = ? AND is_system = FALSE
            ''', params)
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_rule(self, rule_id: int) -> bool:
        """
        Delete rule (only custom rules can be deleted).
        
        Args:
            rule_id: Rule ID
            
        Returns:
            bool: True if deletion successful, False otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # First, set rule_id to NULL for any signals using this rule
            # (for databases created before ON DELETE SET NULL was added)
            cursor.execute('UPDATE signals SET rule_id = NULL WHERE rule_id = ?', (rule_id,))
            
            # Then delete the rule (only custom rules)
            cursor.execute('DELETE FROM rules WHERE id = ? AND is_system = FALSE', (rule_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    # Watchlist operations
    def create_watchlist(self, name: str, symbols: List[str]) -> int:
        """
        Create a new watchlist.
        
        Args:
            name: Watchlist name
            symbols: List of symbols (max 5 for MVP)
            
        Returns:
            int: ID of created watchlist
        """
        if len(symbols) > 5:
            raise ValueError("Watchlist cannot exceed 5 symbols for MVP")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create watchlist
            cursor.execute('INSERT INTO watchlists (name) VALUES (?)', (name,))
            watchlist_id = cursor.lastrowid
            
            # Add symbols
            for symbol in symbols:
                cursor.execute('INSERT INTO watchlist_items (watchlist_id, symbol) VALUES (?, ?)', 
                           (watchlist_id, symbol))
            
            conn.commit()
            return watchlist_id
    
    def get_watchlist(self, watchlist_id: int) -> Optional[Dict]:
        """
        Get watchlist by ID with its symbols.
        
        Args:
            watchlist_id: Watchlist ID
            
        Returns:
            Optional[Dict]: Watchlist data or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM watchlists WHERE id = ?', (watchlist_id,))
            watchlist_row = cursor.fetchone()
            
            if not watchlist_row:
                return None
            
            watchlist = dict(watchlist_row)
            
            # Get symbols
            cursor.execute('SELECT symbol FROM watchlist_items WHERE watchlist_id = ?', (watchlist_id,))
            symbol_rows = cursor.fetchall()
            watchlist['symbols'] = [row['symbol'] for row in symbol_rows]
            
            return watchlist
    
    def get_all_watchlists(self) -> List[Dict]:
        """
        Get all watchlists with their symbols.
        
        Returns:
            List[Dict]: List of all watchlists
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM watchlists ORDER BY created_at')
            watchlist_rows = cursor.fetchall()
            
            watchlists = []
            for watchlist_row in watchlist_rows:
                watchlist = dict(watchlist_row)
                
                # Get symbols
                cursor.execute('SELECT symbol FROM watchlist_items WHERE watchlist_id = ?', 
                           (watchlist['id'],))
                symbol_rows = cursor.fetchall()
                watchlist['symbols'] = [row['symbol'] for row in symbol_rows]
                
                watchlists.append(watchlist)
            
            return watchlists
    
    def update_watchlist(self, watchlist_id: int, update_data: Dict[str, Any]) -> bool:
        """
        Update an existing watchlist.
        
        Args:
            watchlist_id: Watchlist ID to update
            update_data: Dictionary containing fields to update
            
        Returns:
            bool: True if update successful, False otherwise
        """
        updates = []
        params = []
        
        if 'name' in update_data:
            updates.append("name = ?")
            params.append(update_data['name'])
        
        if not updates:
            return False
        
        params.append(watchlist_id)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE watchlists
                SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', params)
            conn.commit()
            
            # Update symbols if provided
            if 'symbols' in update_data:
                # Delete existing symbols
                cursor.execute('DELETE FROM watchlist_items WHERE watchlist_id = ?', (watchlist_id,))
                
                # Insert new symbols
                for symbol in update_data['symbols']:
                    cursor.execute('INSERT INTO watchlist_items (watchlist_id, symbol) VALUES (?, ?)',
                               (watchlist_id, symbol))
                
                conn.commit()
            
            return cursor.rowcount > 0
    
    def delete_watchlist(self, watchlist_id: int) -> bool:
        """
        Delete a watchlist.
        
        Args:
            watchlist_id: Watchlist ID to delete
            
        Returns:
            bool: True if deletion successful, False otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM watchlists WHERE id = ?', (watchlist_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def set_active_watchlist(self, watchlist_id: int) -> bool:
        """
        Set active watchlist (only one can be active at a time).
        
        Args:
            watchlist_id: Watchlist ID to set as active
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Deactivate all watchlists
            cursor.execute('UPDATE watchlists SET is_active = FALSE')
            
            # Activate specified watchlist
            cursor.execute('UPDATE watchlists SET is_active = TRUE WHERE id = ?', (watchlist_id,))
            conn.commit()
            
            return cursor.rowcount > 0
    
    def get_active_watchlist(self) -> Optional[Dict]:
        """
        Get currently active watchlist.
        
        Returns:
            Optional[Dict]: Active watchlist or None if none active
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM watchlists WHERE is_active = TRUE')
            watchlist_row = cursor.fetchone()
            
            if not watchlist_row:
                return None
            
            return self.get_watchlist(watchlist_row['id'])
    
    # Signal operations
    def save_signal(self, signal_data: Dict) -> int:
        """
        Save trading signal to database.
        
        Args:
            signal_data: Signal data dictionary with optional indicators
            
        Returns:
            int: ID of saved signal
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Convert indicators dict to JSON string if present
            indicators_json = None
            if 'indicators' in signal_data and signal_data['indicators']:
                indicators_json = json.dumps(signal_data['indicators'])
            
            cursor.execute('''
                INSERT INTO signals (time, symbol, price, rule_id, indicators)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                signal_data['timestamp'],
                signal_data['symbol'],
                signal_data['price'],
                signal_data.get('rule_id'),
                indicators_json
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_signals(self, limit: int = 100, symbol: str = None) -> List[Dict]:
        """
        Get recent signals.
        
        Args:
            limit: Maximum number of signals to return
            symbol: Filter by symbol (optional)
            
        Returns:
            List[Dict]: List of signals with parsed indicators
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if symbol:
                cursor.execute('''
                    SELECT * FROM signals 
                    WHERE symbol = ? 
                    ORDER BY time DESC 
                    LIMIT ?
                ''', (symbol, limit))
            else:
                cursor.execute('''
                    SELECT * FROM signals 
                    ORDER BY time DESC 
                    LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            signals = []
            for row in rows:
                signal = dict(row)
                # Parse indicators JSON if present
                if signal.get('indicators'):
                    try:
                        signal['indicators'] = json.loads(signal['indicators'])
                    except json.JSONDecodeError:
                        signal['indicators'] = None
                signals.append(signal)
            return signals
    
    def delete_signal(self, signal_id: int) -> bool:
        """
        Delete a signal.
        
        Args:
            signal_id: Signal ID
            
        Returns:
            bool: True if deletion successful, False otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM signals WHERE id = ?', (signal_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    # Settings operations
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get setting value.
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Any: Setting value or default
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            row = cursor.fetchone()
            
            if row:
                try:
                    return json.loads(row['value'])
                except json.JSONDecodeError:
                    return row['value']
            
            return default
    
    def set_setting(self, key: str, value: Any) -> None:
        """
        Set setting value.
        
        Args:
            key: Setting key
            value: Setting value
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value)
            else:
                value_str = str(value)
            
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value)
                VALUES (?, ?)
            ''', (key, value_str))
            conn.commit()
    
    # MVP-specific methods
    def get_system_rules(self) -> List[Dict]:
        """
        Get all system rules (readonly rules that cannot be deleted).
        
        Returns:
            List[Dict]: List of system rules
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM rules WHERE is_system = TRUE ORDER BY created_at')
            rows = cursor.fetchall()
            
            rules = []
            for row in rows:
                rule = dict(row)
                rule['definition'] = json.loads(rule['definition'])
                rules.append(rule)
            
            return rules
    
    def get_custom_rules(self) -> List[Dict]:
        """
        Get all custom rules (user-created rules).
        
        Returns:
            List[Dict]: List of custom rules
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM rules WHERE is_system = FALSE ORDER BY created_at')
            rows = cursor.fetchall()
            
            rules = []
            for row in rows:
                rule = dict(row)
                rule['definition'] = json.loads(rule['definition'])
                rules.append(rule)
            
            return rules
    
    def get_active_symbols(self) -> List[str]:
        """
        Get symbols from the active watchlist.
        
        Returns:
            List[str]: List of symbols from active watchlist
        """
        active_watchlist = self.get_active_watchlist()
        if not active_watchlist:
            return []
        
        return active_watchlist.get('symbols', [])
    
    def get_signal_count_today(self, symbol: str = None) -> int:
        """
        Get count of signals generated today.
        
        Args:
            symbol: Filter by symbol (optional)
            
        Returns:
            int: Count of signals today
        """
        today = datetime.now().strftime('%Y-%m-%d')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if symbol:
                cursor.execute('''
                    SELECT COUNT(*) FROM signals
                    WHERE DATE(time) = ? AND symbol = ?
                ''', (today, symbol))
            else:
                cursor.execute('''
                    SELECT COUNT(*) FROM signals
                    WHERE DATE(time) = ?
                ''', (today,))
            
            result = cursor.fetchone()
            return result[0] if result else 0
    
    def cleanup_old_signals(self, days_to_keep: int = 30) -> int:
        """
        Clean up old signals to manage database size.
        
        Args:
            days_to_keep: Number of days to keep signals
            
        Returns:
            int: Number of signals deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM signals
                WHERE time < datetime('now', '-{} days')
            '''.format(days_to_keep))
            conn.commit()
            return cursor.rowcount
    
    def validate_watchlist_limits(self, watchlist_id: int) -> Dict[str, Any]:
        """
        Validate watchlist against MVP limits.
        
        Args:
            watchlist_id: Watchlist ID to validate
            
        Returns:
            Dict[str, Any]: Validation result with status and message
        """
        watchlist = self.get_watchlist(watchlist_id)
        if not watchlist:
            return {"valid": False, "message": "Watchlist not found"}
        
        symbol_count = len(watchlist.get('symbols', []))
        
        if symbol_count > 5:
            return {
                "valid": False,
                "message": f"Watchlist exceeds MVP limit of 5 symbols (has {symbol_count})"
            }
        
        if symbol_count == 0:
            return {
                "valid": False,
                "message": "Watchlist must have at least 1 symbol"
            }
        
        return {"valid": True, "message": "Watchlist is valid"}
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics for monitoring.
        
        Returns:
            Dict[str, Any]: Database statistics
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Count rules
            cursor.execute('SELECT COUNT(*) FROM rules')
            stats['total_rules'] = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM rules WHERE is_system = TRUE')
            stats['system_rules'] = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM rules WHERE is_system = FALSE')
            stats['custom_rules'] = cursor.fetchone()[0]
            
            # Count watchlists
            cursor.execute('SELECT COUNT(*) FROM watchlists')
            stats['total_watchlists'] = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM watchlists WHERE is_active = TRUE')
            stats['active_watchlists'] = cursor.fetchone()[0]
            
            # Count signals
            cursor.execute('SELECT COUNT(*) FROM signals')
            stats['total_signals'] = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM signals
                WHERE DATE(time) = DATE('now')
            ''')
            stats['signals_today'] = cursor.fetchone()[0]
            
            # Count settings
            cursor.execute('SELECT COUNT(*) FROM settings')
            stats['total_settings'] = cursor.fetchone()[0]
            
            # Count backtest runs
            cursor.execute('SELECT COUNT(*) FROM backtest_runs')
            stats['total_backtest_runs'] = cursor.fetchone()[0]
            
            # Count backtest signals
            cursor.execute('SELECT COUNT(*) FROM backtest_signals')
            stats['total_backtest_signals'] = cursor.fetchone()[0]
            
            # Count ticker universes
            cursor.execute('SELECT COUNT(*) FROM ticker_universes')
            stats['total_ticker_universes'] = cursor.fetchone()[0]
            
            return stats
    
    # Backtesting operations
    def create_backtest_run(
        self,
        name: str,
        mode: str,
        rule_id: int,
        symbols: List[str],
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        data_source: str,
        total_signals: int = 0,
        metadata: Optional[Dict] = None
    ) -> int:
        """
        Create a new backtest run.
        
        Args:
            name: Backtest run name
            mode: 'scalping' or 'swing'
            rule_id: Rule ID used
            symbols: List of symbols tested
            timeframe: Timeframe used
            start_date: Start date
            end_date: End date
            data_source: 'ibkr' or 'yahoo'
            total_signals: Total signals generated
            metadata: Additional metrics as dictionary
        
        Returns:
            int: ID of created backtest run
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO backtest_runs 
                (name, mode, rule_id, symbols, timeframe, start_date, end_date, 
                 data_source, created_at, total_signals, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                mode,
                rule_id,
                json.dumps(symbols),
                timeframe,
                start_date.isoformat(),
                end_date.isoformat(),
                data_source,
                datetime.now().isoformat(),
                total_signals,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()
            return cursor.lastrowid
    
    def create_backtest_signals(self, backtest_run_id: int, signals: List[Dict]) -> None:
        """
        Create backtest signals in batch.
        
        Args:
            backtest_run_id: Backtest run ID
            signals: List of signal dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for signal in signals:
                cursor.execute('''
                    INSERT INTO backtest_signals 
                    (backtest_run_id, symbol, timestamp, signal_type, price, indicators)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    backtest_run_id,
                    signal['symbol'],
                    signal['timestamp'].isoformat(),
                    signal['signal_type'],
                    signal['price'],
                    json.dumps(signal.get('indicators'))
                ))
            conn.commit()
    
    def get_backtest_run(self, run_id: int) -> Optional[Dict]:
        """
        Get backtest run by ID.
        
        Args:
            run_id: Backtest run ID
        
        Returns:
            Optional[Dict]: Backtest run data or None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM backtest_runs WHERE id = ?', (run_id,))
            row = cursor.fetchone()
            
            if row:
                run = dict(row)
                run['symbols'] = json.loads(run['symbols'])
                run['metadata'] = json.loads(run['metadata']) if run['metadata'] else {}
                return run
            return None
    
    def get_all_backtest_runs(self) -> List[Dict]:
        """
        Get all backtest runs.
        
        Returns:
            List[Dict]: List of all backtest runs
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM backtest_runs ORDER BY created_at DESC')
            rows = cursor.fetchall()
            
            runs = []
            for row in rows:
                run = dict(row)
                run['symbols'] = json.loads(run['symbols'])
                run['metadata'] = json.loads(run['metadata']) if run['metadata'] else {}
                runs.append(run)
            
            return runs
    
    def get_backtest_signals(self, run_id: int) -> List[Dict]:
        """
        Get all signals for a backtest run.
        
        Args:
            run_id: Backtest run ID
        
        Returns:
            List[Dict]: List of signals
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM backtest_signals 
                WHERE backtest_run_id = ? 
                ORDER BY timestamp
            ''', (run_id,))
            rows = cursor.fetchall()
            
            signals = []
            for row in rows:
                signal = dict(row)
                signal['indicators'] = json.loads(signal['indicators']) if signal['indicators'] else {}
                signals.append(signal)
            
            return signals
    
    def delete_backtest_run(self, run_id: int) -> bool:
        """
        Delete a backtest run and its signals.
        
        Args:
            run_id: Backtest run ID
        
        Returns:
            bool: True if deletion successful
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM backtest_runs WHERE id = ?', (run_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    # Ticker Universe operations
    def create_ticker_universe(
        self,
        name: str,
        tickers: List[str],
        description: Optional[str] = None
    ) -> int:
        """
        Create a new ticker universe.
        
        Args:
            name: Universe name
            tickers: List of ticker symbols
            description: Optional description
        
        Returns:
            int: ID of created universe
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO ticker_universes (name, tickers, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, json.dumps(tickers), description, now, now))
            conn.commit()
            return cursor.lastrowid
    
    def get_ticker_universe(self, universe_id: int) -> Optional[Dict]:
        """
        Get ticker universe by ID.
        
        Args:
            universe_id: Universe ID
        
        Returns:
            Optional[Dict]: Universe data or None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ticker_universes WHERE id = ?', (universe_id,))
            row = cursor.fetchone()
            
            if row:
                universe = dict(row)
                universe['tickers'] = json.loads(universe['tickers'])
                return universe
            return None
    
    def get_all_ticker_universes(self) -> List[Dict]:
        """
        Get all ticker universes.
        
        Returns:
            List[Dict]: List of all universes
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ticker_universes ORDER BY name')
            rows = cursor.fetchall()
            
            universes = []
            for row in rows:
                universe = dict(row)
                universe['tickers'] = json.loads(universe['tickers'])
                universes.append(universe)
            
            return universes
    
    def update_ticker_universe(
        self,
        universe_id: int,
        name: Optional[str] = None,
        tickers: Optional[List[str]] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        Update ticker universe.
        
        Args:
            universe_id: Universe ID
            name: New name (optional)
            tickers: New tickers list (optional)
            description: New description (optional)
        
        Returns:
            bool: True if update successful
        """
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        
        if tickers is not None:
            updates.append("tickers = ?")
            params.append(json.dumps(tickers))
        
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        
        if not updates:
            return False
        
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(universe_id)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE ticker_universes SET {', '.join(updates)}
                WHERE id = ?
            ''', params)
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_ticker_universe(self, universe_id: int) -> bool:
        """
        Delete a ticker universe.
        
        Args:
            universe_id: Universe ID
        
        Returns:
            bool: True if deletion successful
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ticker_universes WHERE id = ?', (universe_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_rule_by_id(self, rule_id: int) -> Optional[Dict]:
        """
        Get rule by ID (alias for get_rule for consistency).
        
        Args:
            rule_id: Rule ID
        
        Returns:
            Optional[Dict]: Rule data or None
        """
        return self.get_rule(rule_id)