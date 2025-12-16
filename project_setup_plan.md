# SignalGen MVP Project Setup Plan

## Project Overview
SignalGen is a desktop application for real-time scalping signal generation with customizable rules, real-time data from IBKR, and WebSocket output for external execution systems.

## Directory Structure
```
signalgen/
├── app/
│   ├── ui/
│   │   ├── templates/          # HTML templates for PyWebView
│   │   └── static/             # CSS, JS, images
│   ├── core/
│   │   ├── rule_engine.py      # Rule evaluation logic
│   │   ├── indicator_engine.py # Technical indicator calculations
│   │   └── state_machine.py    # Engine state management
│   ├── engines/
│   │   └── scalping_engine.py  # Main scalping engine with IBKR integration
│   ├── storage/
│   │   └── sqlite_repo.py      # SQLite database operations
│   ├── ws/
│   │   └── broadcaster.py      # WebSocket broadcasting
│   ├── app.py                  # Flask/FastAPI application
│   └── main.py                 # Application entry point
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
├── .gitignore                  # Git ignore file
└── PROJECT_MVP.md             # Project specification
```

## Dependencies (requirements.txt)
```
# Web Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0

# Desktop UI
pywebview==4.4.1

# IBKR Integration
ib_insync==0.9.86

# WebSocket Support with Socket.IO
python-socketio==5.10.0
python-engineio==4.7.1

# Technical Analysis Libraries
pandas==2.1.4
numpy==1.25.2
ta-lib==0.4.28
talib-binary==0.4.24

# Database
sqlite3  # Built-in with Python

# Additional utilities
python-multipart==0.0.6
jinja2==3.1.2
pydantic==2.5.0
```

## Component Details

### 1. Core Components

#### rule_engine.py
- Purpose: Evaluates user-defined rules against indicator values
- Key functions: evaluate_rule(), evaluate_condition()
- Supports operators: >, <, >=, <=
- Supports operands: PRICE, MA5, MA10, MA20

#### indicator_engine.py
- Purpose: Calculates technical indicators from price data using pandas, numpy, and TA-Lib
- Key functions: calculate_ma(), update_indicators(), calculate_rsi(), calculate_macd()
- Supports: Moving averages (5, 10, 20 periods), RSI, MACD, Bollinger Bands, and more
- Libraries: pandas for data manipulation, numpy for numerical operations, TA-Lib for technical indicators

#### state_machine.py
- Purpose: Manages engine states (WAIT → SIGNAL → COOLDOWN)
- Key functions: transition_to(), get_current_state()
- Prevents signal noise and spam

### 2. Engine Components

#### scalping_engine.py
- Purpose: Main engine orchestrating data flow from IBKR to signals
- Integrates with: IBKR TWS/Gateway via ib_insync
- Handles: Real-time bar updates, indicator calculations, rule evaluation

### 3. Storage Components

#### sqlite_repo.py
- Purpose: Database operations for rules, watchlists, signals, settings
- Tables: rules, watchlists, watchlist_items, signals, settings
- Functions: CRUD operations for all entities

### 4. WebSocket Components

#### broadcaster.py
- Purpose: Broadcasts signals to connected clients
- Events: signal events with symbol, price, rule_id, timestamp
- Supports: UI updates and external execution systems

### 5. Application Components

#### app.py
- Purpose: FastAPI application with REST API and WebSocket endpoints
- Endpoints: Rule management, watchlist management, engine control
- WebSocket: Real-time signal broadcasting

#### main.py
- Purpose: Application entry point
- Initializes: PyWebView window, FastAPI server, database
- Handles: Application lifecycle

## Database Schema

### Rules Table
```sql
CREATE TABLE rules (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT CHECK(type IN ('system', 'custom')) NOT NULL,
    definition TEXT NOT NULL,  -- JSON
    is_system BOOLEAN DEFAULT FALSE
);
```

### Watchlists Table
```sql
CREATE TABLE watchlists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT FALSE
);

CREATE TABLE watchlist_items (
    id INTEGER PRIMARY KEY,
    watchlist_id INTEGER,
    symbol TEXT NOT NULL,
    FOREIGN KEY (watchlist_id) REFERENCES watchlists(id)
);
```

### Signals Table
```sql
CREATE TABLE signals (
    id INTEGER PRIMARY KEY,
    time TEXT NOT NULL,
    symbol TEXT NOT NULL,
    price REAL NOT NULL,
    rule_id INTEGER,
    FOREIGN KEY (rule_id) REFERENCES rules(id)
);
```

### Settings Table
```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

## Default Rule
The system includes a non-deletable default rule:
- Name: "MA Momentum"
- Logic: "PRICE > MA5 AND MA5 > MA10"
- Type: system
- is_system: true

## Implementation Notes

1. **Thread Safety**: The scalping engine runs in a separate thread from the UI
2. **State Management**: Engine state is managed to prevent signal noise
3. **Error Handling**: Robust error handling for IBKR disconnections
4. **Performance**: Optimized for real-time processing with minimal latency
5. **Extensibility**: Clean architecture allows for future enhancements

## Next Steps

1. Create directory structure
2. Set up Python files with basic docstrings
3. Create requirements.txt
4. Create README.md with setup instructions
5. Create .gitignore
6. Initialize each component with basic structure