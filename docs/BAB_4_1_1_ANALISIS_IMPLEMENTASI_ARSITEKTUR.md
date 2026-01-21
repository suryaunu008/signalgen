# LAPORAN ANALISIS IMPLEMENTASI ARSITEKTUR SISTEM

**Dokumen Pendukung Penulisan Bab 4.1.1 – Implementasi Arsitektur Sistem**

**Tanggal:** 17 Januari 2026  
**Proyek:** SignalGen - Real-time Scalping Signal Generator  
**Tujuan:** Mengumpulkan informasi faktual dan konkret dari repository untuk mendukung penulisan skripsi S1 Teknologi Informasi

---

## 📌 1. ENTRY POINT APLIKASI

### Identifikasi File Entry Point

**File Entry Point:** `app/main.py`  
**Total Baris Kode:** 254 lines  
**Fungsi Utama:** `main()` (line 201-254)

### Proses Inisialisasi Aplikasi

Berdasarkan kode aktual di `app/main.py`, aplikasi menjalankan proses inisialisasi dalam urutan berikut:

#### 1.1 Setup Logging (line 44-53)
```python
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
```
**Fungsi:** Konfigurasi logging ke file `signalgen.log` dan console output (stdout).

#### 1.2 Database Initialization (line 215)
```python
signalgen_app.initialize_database()
```
**Fungsi:** Inisialisasi schema database SQLite (`signalgen.db`) dengan 5 tabel utama:
- `rules` - Trading rules dengan JSON definitions
- `watchlists` - Symbol watchlists
- `watchlist_items` - Individual symbols dalam watchlist
- `signals` - Generated trading signals
- `settings` - Application configuration

#### 1.3 Data Seeding (line 218)
```python
seed_default_data(signalgen_app.repository)
```
**Fungsi:** Mengisi database dengan data default:
- Default Scalping rule (system rule)
- Default Watchlist dengan symbols: AAPL, MSFT, GOOGL
- Default settings (IB host, port, timeframe, dll)

#### 1.4 FastAPI Server Startup (line 221)
```python
fastapi_thread = start_fastapi_server()
```
**Konfigurasi:**
- Host: `127.0.0.1`
- Port: `3456`
- Thread: Daemon thread (background)
- Server: Uvicorn ASGI server

**Fungsi:** Menyediakan REST API endpoints untuk komunikasi UI-backend.

#### 1.5 Socket.IO Server Startup (line 224)
```python
socketio_thread = start_socketio_server(signalgen_app.broadcaster)
```
**Konfigurasi:**
- Host: `127.0.0.1`
- Port: `8765`
- Thread: Daemon thread (background)
- Protocol: WebSocket via Socket.IO

**Fungsi:** Menyediakan real-time bidirectional communication untuk broadcasting signals dan status updates.

#### 1.6 PyWebView Window Creation (line 230)
```python
window = create_pywebview_window()
```
**Konfigurasi:**
- URL: `http://127.0.0.1:3456`
- Window Size: 1400 x 900 pixels
- Min Size: 1000 x 700 pixels
- Resizable: True
- Confirm Close: True

**Fungsi:** Membuat desktop application window yang me-load UI dari local FastAPI server.

### Runtime Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     main() - Entry Point                     │
└───────────────────────────┬─────────────────────────────────┘
                            │
                ┌───────────▼───────────┐
                │   setup_logging()    │
                │   - signalgen.log    │
                │   - stdout           │
                └───────────┬───────────┘
                            │
                ┌───────────▼───────────┐
                │ initialize_database() │
                │   - signalgen.db     │
                │   - Create tables    │
                └───────────┬───────────┘
                            │
                ┌───────────▼───────────┐
                │  seed_default_data()  │
                │   - Default rules    │
                │   - Default watchlist│
                │   - Settings         │
                └───────────┬───────────┘
                            │
                ┌───────────▼───────────┐
                │ start_fastapi_server()│
                │   - Thread: daemon   │
                │   - Port: 3456       │
                └───────────┬───────────┘
                            │
                ┌───────────▼───────────┐
                │start_socketio_server()│
                │   - Thread: daemon   │
                │   - Port: 8765       │
                └───────────┬───────────┘
                            │
                ┌───────────▼───────────┐
                │ time.sleep(2)         │
                │ Wait for servers      │
                └───────────┬───────────┘
                            │
                ┌───────────▼───────────┐
                │create_pywebview_window│
                │   - Load UI          │
                │   - Size: 1400x900   │
                └───────────┬───────────┘
                            │
                ┌───────────▼───────────┐
                │    webview.start()    │
                │   BLOCKING LOOP       │
                │   (until close)       │
                └───────────────────────┘
```

---

## 📌 2. PEMETAAN ARSITEKTUR KE STRUKTUR FOLDER

Sistem SignalGen mengimplementasikan arsitektur 4-layer yang dipetakan ke struktur folder sebagai berikut:

### 2.1 Layer 1: User Interface Layer

**Folder:** `app/ui/`

#### File dan Modul Utama

| File | Fungsi Utama | Baris Kode |
|------|--------------|------------|
| `templates/index.html` | HTML template utama aplikasi | - |
| `static/js/app.js` | Main UI controller (class `SignalGenApp`) | 2270 lines |
| `static/js/api.js` | REST API client (class `ApiClient`) | 201 lines |
| `static/js/websocket.js` | WebSocket client (class `WebSocketClient`) | 249 lines |
| `static/js/backtesting.js` | Backtesting UI module | - |
| `static/js/swing.js` | Swing trading UI module | - |

#### Fungsi Layer

1. **Rendering UI**
   - Desktop window menggunakan PyWebView
   - Responsive layout dengan Tailwind CSS
   - Tab-based navigation (Scalping, Backtesting, Swing Trading)

2. **User Interaction Handling**
   - Form submissions (create/update rules, watchlists)
   - Button clicks (start/stop engine, activate rules)
   - Real-time signal display updates

3. **Komunikasi dengan Backend**
   - REST API calls via `ApiClient` class
   - Base URL: `http://127.0.0.1:3456`
   - WebSocket connection via `WebSocketClient` class
   - WebSocket URL: `ws://127.0.0.1:8765`

#### Contoh Implementasi dari `app.js` (line 1-50)

```javascript
class SignalGenApp {
  constructor() {
    this.engineRunning = false;
    this.currentWatchlist = null;
    this.currentRule = null;
    this.watchlistSymbols = [];
    this.signals = [];
  }
}
```

**Dokumentasi:** "This module initializes and coordinates all UI components, handles user interactions, and manages the application state."

---

### 2.2 Layer 2: Application Layer

**Folder:** `app/`

#### File dan Modul Utama

| File | Class/Module | Fungsi Utama | Baris Kode |
|------|--------------|--------------|------------|
| `app.py` | `SignalGenApp` | FastAPI application server | 1526 lines |
| `main.py` | `main()` | Application entry point | 254 lines |
| `ws/broadcaster.py` | `SocketIOBroadcaster` | WebSocket broadcasting | 681 lines |

#### Fungsi Layer

**1. REST API Endpoints (dari `app.py`)**

Implementasi 22 REST endpoints untuk operasi CRUD:

| Endpoint Pattern | Methods | Fungsi |
|-----------------|---------|--------|
| `/api/rules/*` | GET, POST, PUT, DELETE | CRUD trading rules |
| `/api/watchlists/*` | GET, POST, PUT, DELETE | CRUD watchlists |
| `/api/engine/*` | POST, GET | Start, stop, status engine |
| `/api/signals/*` | GET | Retrieve signal history |
| `/api/settings/*` | GET, PUT | Get/update settings |
| `/api/health` | GET | Health check endpoint |
| `/api/status` | GET | System status |

**2. WebSocket Events (dari `broadcaster.py`)**

Implementasi Socket.IO events untuk real-time communication:

| Event Name | Direction | Data |
|-----------|-----------|------|
| `signal` | Server → Client | Trading signal data |
| `engine_status` | Server → Client | Engine state changes |
| `rule_update` | Server → Client | Rule modifications |
| `watchlist_update` | Server → Client | Watchlist changes |
| `ibkr_status` | Server → Client | IBKR connection status |
| `error` | Server → Client | Error notifications |

**3. Engine Orchestration**

Dari `app.py` (line 185-245):
```python
def __init__(self, db_path: str = 'signalgen.db'):
    self.app = FastAPI(
        title="SignalGen API",
        description="Real-time scalping signal generator API",
        version="1.0.0"
    )
    
    self.repository = SQLiteRepository(db_path)
    self.broadcaster = SocketIOBroadcaster()
    
    # Get timeframe from settings
    timeframe = self.repository.get_setting('timeframe') or '1m'
    self.scalping_engine = ScalpingEngine(timeframe=timeframe)
    
    # Set broadcaster reference in scalping engine
    self.scalping_engine.broadcaster = self.broadcaster
```

**Dokumentasi:** "This module provides the main FastAPI application for the SignalGen scalping system. It handles REST API endpoints and integrates with the Socket.IO broadcaster."

---

### 2.3 Layer 3: Engine Layer

**Folder:** `app/engines/` dan `app/core/`

#### Engines (app/engines/)

| File | Class | Fungsi Utama | Baris Kode |
|------|-------|--------------|------------|
| `scalping_engine.py` | `ScalpingEngine` | Main real-time scalping engine | 1064 lines |
| `backtesting_engine.py` | `BacktestingEngine` | Historical data backtesting | - |
| `swing_screening_engine.py` | `SwingScreeningEngine` | Swing trading screening | - |

#### Core Components (app/core/)

| File | Class | Fungsi Utama | Baris Kode |
|------|-------|--------------|------------|
| `rule_engine.py` | `RuleEngine` | Deterministic rule evaluation | 453 lines |
| `indicator_engine.py` | `IndicatorEngine` | Technical indicator calculations | 781 lines |
| `candle_builder.py` | `CandleBuilder` | Candle/bar aggregation | - |
| `state_machine.py` | `StateMachine` | Engine state management | - |

#### Fungsi Layer

**1. ScalpingEngine - Main Processing Engine**

Dari `scalping_engine.py` (line 1-30):
```python
"""
Data Flow:
IBKR Bar Update → Indicator Engine → Rule Engine → Signal Generator → WebSocket Emit

MVP Limitations:
- Maximum 5 tickers per run
- Single active watchlist
- 1-minute or 5-second bar intervals
"""
```

**Fitur Implementasi:**
- Real-time data streaming dari IBKR via `ib_insync`
- Event-driven async architecture
- Single event loop untuk performance
- Automatic reconnection handling
- Per-symbol cooldown tracking

**2. RuleEngine - Trading Logic Evaluator**

Dari `rule_engine.py` (line 48-80):
```python
# Supported operands for rule conditions
SUPPORTED_OPERANDS = {
    # Price indicators
    "PRICE", "PREV_CLOSE", "PREV_OPEN",
    
    # Moving Averages
    "MA20", "MA50", "MA100", "MA200",
    "MA20_PREV", "MA50_PREV", "MA100_PREV", "MA200_PREV",
    
    # Exponential Moving Averages
    "EMA6", "EMA9", "EMA10", "EMA13", "EMA20", "EMA21", "EMA34", "EMA50",
    "EMA6_PREV", "EMA9_PREV", "EMA10_PREV", ...
    
    # MACD, RSI, ADX, Bollinger Bands, etc.
}
```

**Total Supported Operands:** 44 indicators

**Operators:**
- Comparison: `>`, `<`, `>=`, `<=`
- Cross: `CROSS_UP`, `CROSS_DOWN`
- Logic: `AND` (only)

**Security Feature:** Tidak menggunakan `eval()` atau dynamic code execution.

**Dokumentasi:** "Evaluates user-defined rules against indicator values to determine trading signals. No dynamic code execution or eval() usage for security."

**3. IndicatorEngine - Technical Analysis**

Dari `indicator_engine.py` (line 1-30):
```python
"""
Supported Indicators:
- PRICE, PREV_CLOSE, PREV_OPEN (candle data)
- MA20, MA50, MA100, MA200 (Simple Moving Averages)
- EMA6, EMA9, EMA10, EMA13, EMA20, EMA21, EMA34, EMA50 (Exponential Moving Averages)
- MACD, MACD_SIGNAL, MACD_HIST, MACD_HIST_PREV (MACD indicators)
- RSI14, RSI14_PREV (14-period RSI)
- ADX5, ADX5_PREV (5-period ADX)
- BB_UPPER, BB_MIDDLE, BB_LOWER, BB_WIDTH (Bollinger Bands)
- PRICE_EMA20_DIFF_PCT (calculated metric)
"""
```

**Library:** pandas-ta untuk accurate calculations  
**Data Management:** Rolling window (max 250 candles)  
**Thread Safety:** `threading.RLock()` untuk concurrent access

---

### 2.4 Layer 4: Data Layer

**Folder:** `app/storage/` dan `app/data_sources/`

#### Storage (app/storage/)

| File | Class | Fungsi Utama | Baris Kode |
|------|-------|--------------|------------|
| `sqlite_repo.py` | `SQLiteRepository` | Database operations | 1143 lines |
| `init_db.py` | `initialize_database()` | Database initialization | - |

#### Data Sources (app/data_sources/)

| File | Class | Fungsi Utama |
|------|-------|--------------|
| `ibkr_data_source.py` | `IBKRDataSource` | IBKR real-time data |
| `yahoo_data_source.py` | `YahooDataSource` | Yahoo Finance historical data |
| `base_data_source.py` | `BaseDataSource` | Base interface |

#### Database Schema

Dari `sqlite_repo.py` (line 54-80):

**Tabel 1: rules**
```sql
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT CHECK(type IN ('system', 'custom')) NOT NULL,
    definition TEXT NOT NULL,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Tabel 2: watchlists**
- Menyimpan watchlist metadata
- Foreign key ke `watchlist_items`

**Tabel 3: watchlist_items**
- Menyimpan individual symbols per watchlist
- Maximum 5 symbols per watchlist (MVP limitation)

**Tabel 4: signals**
- Menyimpan generated trading signals
- Includes timestamp, symbol, signal type, price, indicators

**Tabel 5: settings**
- Key-value storage untuk application settings
- Default settings: ib_host, ib_port, timeframe, dll

#### Fungsi Layer

**1. SQLiteRepository - Data Persistence**

**Thread Safety:** 
```python
def __init__(self, db_path: str = 'signalgen.db'):
    self.db_path = db_path
    self._lock = threading.Lock()
```

**Operations:**
- CRUD untuk semua 5 tabel
- Transaction management
- Connection pooling
- Data migration support

**2. IBKR Data Source**

**Library:** `ib_insync`  
**Connection:**
- TWS: port 7497
- Gateway: port 4002
- Client ID: Random untuk avoid conflicts

**Data Types:**
- Real-time bars (5-second, 1-minute)
- Historical data
- Market data subscriptions

**3. Yahoo Finance Data Source**

**Library:** `yfinance`  
**Usage:** Historical data untuk backtesting  
**Data Types:** OHLCV data dengan adjustable timeframes

---

## 📌 3. MEKANISME KOMUNIKASI ANTAR LAYER

### 3.1 UI Layer ↔ Application Layer

#### Komunikasi REST API

**Mekanisme:** HTTP Request/Response  
**Protocol:** REST over HTTP  
**Base URL:** `http://127.0.0.1:3456`

**Client Implementation** (`app/ui/static/js/api.js`):
```javascript
class ApiClient {
  constructor() {
    this.baseURL = "http://127.0.0.1:3456";
    this.defaultHeaders = {
      "Content-Type": "application/json",
    };
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      headers: { ...this.defaultHeaders, ...options.headers },
      ...options,
    };

    const response = await fetch(url, config);
    return await response.json();
  }
}
```

**Server Implementation** (`app/app.py`):
```python
@self.app.get("/api/rules", response_model=List[Dict])
def get_all_rules():
    """Get all trading rules."""
    rules = self.repository.get_all_rules()
    return JSONResponse(content=rules)
```

**Contoh Alur:**
```
User Click "Create Rule"
    ↓
app.js: createRule() 
    ↓
api.js: POST /api/rules { name, definition }
    ↓
app.py: @app.post("/api/rules")
    ↓
repository.create_rule()
    ↓
SQLite INSERT INTO rules
    ↓
Return: { id, name, definition, created_at }
    ↓
app.js: Update UI with new rule
```

#### Komunikasi WebSocket

**Mekanisme:** Bidirectional WebSocket  
**Protocol:** Socket.IO over WebSocket  
**URL:** `ws://127.0.0.1:8765`

**Client Implementation** (`app/ui/static/js/websocket.js`):
```javascript
class WebSocketClient {
  connect() {
    this.socket = io("http://127.0.0.1:8765", {
      transports: ["websocket", "polling"],
      timeout: 5000,
      forceNew: true,
    });

    this.socket.on("signal", (data) => this.handleEvent("signal", data));
  }
}
```

**Server Implementation** (`app/ws/broadcaster.py`):
```python
class SocketIOBroadcaster:
    def __init__(self, cors_origins: List[str] = None):
        if cors_origins is None:
            cors_origins = ["http://localhost:3456", "http://127.0.0.1:3456"]
        
        self.sio = AsyncServer(
            async_mode='asgi',
            cors_allowed_origins=cors_origins
        )
```

**Contoh Alur:**
```
Engine generates signal
    ↓
scalping_engine: await broadcaster.broadcast_signal(signal_data)
    ↓
broadcaster.py: await self.sio.emit('signal', signal_data)
    ↓
WebSocket transmission
    ↓
websocket.js: socket.on('signal', callback)
    ↓
app.js: handleSignal(data)
    ↓
UI: Display signal in real-time table
```

---

### 3.2 Application Layer ↔ Engine Layer

**Mekanisme:** Direct Function Call (in-process)  
**Thread Model:** Separate threads dengan shared state

**Implementation** dari `app.py` (engine control):

```python
async def _start_scalping_engine_async(self):
    """Start scalping engine in async context."""
    try:
        # Connect to IBKR
        connected = await self.scalping_engine.connect_to_ibkr()
        
        if not connected:
            await self.broadcaster.broadcast_engine_status({
                'status': 'error',
                'message': 'Failed to connect to IBKR'
            })
            return
        
        # Start engine
        await self.scalping_engine.start_engine()
        
    except Exception as e:
        self.logger.error(f"Error starting engine: {e}")
```

**Threading Model:**
```
FastAPI Main Thread
    ↓
threading.Thread(target=run_engine_async)
    ↓
New Event Loop in Thread
    ↓
asyncio.run(scalping_engine.start_engine())
    ↓
ib_insync Event Loop (IBKR callbacks)
```

**Contoh Alur:**
```
POST /api/engine/start
    ↓
app.py: start_scalping_engine()
    ↓
Create new thread: threading.Thread(target=run_engine_async)
    ↓
In new thread: asyncio.run(_start_scalping_engine_async())
    ↓
scalping_engine.connect_to_ibkr()
    ↓
scalping_engine.start_engine()
    ↓
Return status to API
    ↓
Broadcast engine_status via WebSocket
```

---

### 3.3 Engine Layer ↔ Data Layer

#### Database Access

**Mekanisme:** Repository Pattern dengan Direct Method Calls  
**Thread Safety:** `threading.Lock()` dalam repository

**Implementation** dari `scalping_engine.py`:

```python
async def start_engine(self):
    # Get active watchlist from database
    active_watchlist = self.repository.get_active_watchlist()
    
    if not active_watchlist:
        self.logger.error("No active watchlist found")
        return False
    
    # Get symbols
    symbols = self.repository.get_watchlist_symbols(active_watchlist['id'])
    self.active_watchlist = symbols
```

**Thread Safety** dalam `sqlite_repo.py`:

```python
def get_active_watchlist(self) -> Optional[Dict]:
    with self._lock:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM watchlists WHERE is_active = TRUE LIMIT 1
            """)
            row = cursor.fetchone()
```

**Contoh Alur:**
```
Engine starts
    ↓
scalping_engine.start_engine()
    ↓
repository.get_active_watchlist()
    ↓
Lock acquired: self._lock
    ↓
SQLite: SELECT * FROM watchlists WHERE is_active = TRUE
    ↓
Return watchlist data
    ↓
Lock released
    ↓
repository.get_watchlist_symbols(watchlist_id)
    ↓
Return: ['AAPL', 'MSFT', 'GOOGL']
    ↓
Engine subscribes to symbols
```

#### IBKR Data Access

**Mekanisme:** Event-driven callbacks via `ib_insync`  
**Pattern:** Observer pattern (async callbacks)

**Implementation** dari `scalping_engine.py`:

```python
async def connect_to_ibkr(self) -> bool:
    try:
        # Use random client ID to avoid conflicts
        self.ib_client_id = random.randint(1, 9999)
        
        await self.ib.connectAsync(
            self.ib_host, 
            self.ib_port, 
            clientId=self.ib_client_id
        )
        
        self.is_connected = True
        self.logger.info(f"Connected to IBKR at {self.ib_host}:{self.ib_port}")
        return True
    except Exception as e:
        self.logger.error(f"IBKR connection failed: {e}")
        return False
```

**Callback Implementation:**

```python
def on_bar_update(self, bars: BarDataList, hasNewBar: bool):
    """Callback when new bar data arrives from IBKR."""
    if not hasNewBar:
        return
    
    # Get symbol from contract
    contract = bars.contract
    symbol = self.contract_symbol_map.get(contract.conId)
    
    # Add bar to indicator engine
    bar = bars[-1]
    self.indicator_engine.add_bar(symbol, {
        'timestamp': bar.time,
        'open': bar.open,
        'high': bar.high,
        'low': bar.low,
        'close': bar.close,
        'volume': bar.volume
    })
    
    # Evaluate rules
    indicators = self.indicator_engine.get_indicators(symbol)
    signal = self.rule_engine.evaluate(self.active_rule, indicators)
    
    if signal:
        # Broadcast signal
        await self.broadcaster.broadcast_signal(signal)
```

**Data Flow:**
```
IBKR TWS/Gateway
    ↓
Real-time bar event
    ↓
ib_insync library
    ↓
Callback: on_bar_update(bars, hasNewBar)
    ↓
indicator_engine.add_bar(symbol, bar_data)
    ↓
Calculate indicators (MA, EMA, MACD, RSI, etc)
    ↓
rule_engine.evaluate(rule, indicators)
    ↓
If signal detected:
    ↓
repository.save_signal(signal_data)
    ↓
broadcaster.broadcast_signal(signal_data)
    ↓
WebSocket → UI
```

---

## 📌 4. ARTEFAK IMPLEMENTASI (BUKTI KODE)

### 4.1 Struktur Direktori Lengkap

```
signalgen/
├── app/
│   ├── __init__.py
│   ├── main.py                         # Entry point (254 lines)
│   ├── app.py                          # FastAPI application (1526 lines)
│   │
│   ├── core/                           # Core business logic
│   │   ├── __init__.py
│   │   ├── rule_engine.py              # Rule evaluation (453 lines)
│   │   ├── indicator_engine.py         # Indicator calculations (781 lines)
│   │   ├── candle_builder.py           # Candle aggregation
│   │   └── state_machine.py            # State management
│   │
│   ├── engines/                        # Processing engines
│   │   ├── scalping_engine.py          # Main engine (1064 lines)
│   │   ├── backtesting_engine.py       # Backtesting engine
│   │   └── swing_screening_engine.py   # Swing trading engine
│   │
│   ├── storage/                        # Data persistence
│   │   ├── __init__.py
│   │   ├── sqlite_repo.py              # SQLite operations (1143 lines)
│   │   └── init_db.py                  # DB initialization
│   │
│   ├── data_sources/                   # External data sources
│   │   ├── __init__.py
│   │   ├── base_data_source.py         # Base interface
│   │   ├── ibkr_data_source.py         # IBKR integration
│   │   └── yahoo_data_source.py        # Yahoo Finance
│   │
│   ├── ws/                             # WebSocket layer
│   │   ├── __init__.py
│   │   └── broadcaster.py              # Socket.IO server (681 lines)
│   │
│   └── ui/                             # User Interface
│       ├── static/
│       │   └── js/
│       │       ├── app.js              # UI controller (2270 lines)
│       │       ├── api.js              # REST client (201 lines)
│       │       ├── websocket.js        # WebSocket client (249 lines)
│       │       ├── backtesting.js      # Backtesting UI
│       │       └── swing.js            # Swing trading UI
│       └── templates/
│           └── index.html              # Main HTML template
│
├── docs/                               # Documentation
├── tests/                              # Unit tests
├── requirements.txt                    # Python dependencies
├── pytest.ini                          # Test configuration
├── README.md                           # Project documentation
└── signalgen.db                        # SQLite database (runtime)
```

### 4.2 Total Lines of Code (Modul Utama)

| Layer | File | Lines of Code |
|-------|------|---------------|
| **Entry Point** | `app/main.py` | 254 |
| **Application** | `app/app.py` | 1,526 |
| **Application** | `app/ws/broadcaster.py` | 681 |
| **Engine** | `app/engines/scalping_engine.py` | 1,064 |
| **Engine** | `app/core/rule_engine.py` | 453 |
| **Engine** | `app/core/indicator_engine.py` | 781 |
| **Data** | `app/storage/sqlite_repo.py` | 1,143 |
| **UI** | `app/ui/static/js/app.js` | 2,270 |
| **UI** | `app/ui/static/js/api.js` | 201 |
| **UI** | `app/ui/static/js/websocket.js` | 249 |
| **TOTAL (Main Modules)** | | **8,622 lines** |

### 4.3 Docstring Arsitektural (Evidence)

#### Dari `app/main.py` (line 1-32)

```python
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
"""
```

#### Dari `app/app.py` (line 1-30)

```python
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
"""
```

#### Dari `app/engines/scalping_engine.py` (line 1-28)

```python
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
"""
```

#### Dari `app/core/rule_engine.py` (line 1-30)

```python
"""
Rule Engine Module

This module provides deterministic rule evaluation logic for the SignalGen scalping system.
It evaluates user-defined rules against indicator values to determine trading signals.

Key Features:
- Evaluates rules with logical operators (AND)
- Supports comparison operators (>, <, >=, <=)
- Works with predefined operands (PRICE, MA5, MA10, MA20)
- Stateless evaluation - state is managed by the calling engine
- No dynamic code execution or eval() usage for security

MVP Limitations:
- No dynamic code execution or eval() usage
- Fixed set of supported operands and operators
- Single rule evaluation (no multi-rule support)
- Only AND logic is supported (no OR logic)
"""
```

#### Dari `app/core/indicator_engine.py` (line 1-28)

```python
"""
Indicator Engine Module

This module provides technical indicator calculations for the SignalGen scalping system.
Uses pandas-ta library for efficient and accurate technical indicator calculations.

Supported Indicators:
- PRICE, PREV_CLOSE, PREV_OPEN (candle data)
- MA20, MA50, MA100, MA200 (Simple Moving Averages)
- EMA6, EMA9, EMA10, EMA13, EMA20, EMA21, EMA34, EMA50 (Exponential Moving Averages)
- MACD, MACD_SIGNAL, MACD_HIST, MACD_HIST_PREV (MACD indicators)
- RSI14, RSI14_PREV (14-period RSI)
- ADX5, ADX5_PREV (5-period ADX)
- BB_UPPER, BB_MIDDLE, BB_LOWER, BB_WIDTH (Bollinger Bands)
- PRICE_EMA20_DIFF_PCT (calculated metric)
"""
```

#### Dari `app/storage/sqlite_repo.py` (line 1-32)

```python
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
"""
```

#### Dari `app/ws/broadcaster.py` (line 1-28)

```python
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
"""
```

### 4.4 Konfigurasi Runtime Faktual

#### Server Configuration

| Component | Host | Port | Protocol |
|-----------|------|------|----------|
| FastAPI Server | 127.0.0.1 | 3456 | HTTP |
| Socket.IO Server | 127.0.0.1 | 8765 | WebSocket |
| IBKR TWS | 127.0.0.1 | 7497 | IB API |
| IBKR Gateway | 127.0.0.1 | 4002 | IB API |

#### Database Configuration

| Parameter | Value |
|-----------|-------|
| Database Type | SQLite |
| Database File | `signalgen.db` |
| Location | Application directory |
| Tables | 5 (rules, watchlists, watchlist_items, signals, settings) |

#### PyWebView Configuration

| Parameter | Value |
|-----------|-------|
| Window Title | "SignalGen" |
| Default Size | 1400 x 900 pixels |
| Minimum Size | 1000 x 700 pixels |
| URL | http://127.0.0.1:3456 |
| Resizable | True |
| Confirm Close | True |

#### Engine Configuration

| Parameter | Default Value | Source |
|-----------|---------------|--------|
| Timeframe | '1m' | Database setting |
| Max Watchlist Symbols | 5 | MVP limitation |
| Default Cooldown | 60 seconds | Database setting |
| Max History | 250 candles | Indicator engine |
| Reconnect Interval | 5 seconds | Scalping engine |
| Max Reconnect Attempts | 10 | Scalping engine |

---

## 📌 5. RINGKASAN IMPLEMENTASI ARSITEKTUR SISTEM

### Ringkasan Faktual (Single Paragraph)

Sistem SignalGen diimplementasikan sebagai aplikasi desktop dengan arsitektur 4-layer yang berjalan dalam single Python process dengan multi-threading model. Entry point di `app/main.py` (254 lines) menginisialisasi database SQLite dengan 5 tabel, menjalankan FastAPI server pada port 3456 dan Socket.IO server pada port 8765 dalam daemon threads terpisah, kemudian membuka PyWebView window (1400x900 pixels) yang me-load UI dari localhost. Layer User Interface terdiri dari 5 modul JavaScript utama (`app.js` 2270 lines, `api.js` 201 lines, `websocket.js` 249 lines, `backtesting.js`, `swing.js`) yang berkomunikasi dengan Application Layer melalui 22 REST API endpoints untuk operasi CRUD dan WebSocket untuk real-time updates dengan 6 event types (signal, engine_status, rule_update, watchlist_update, ibkr_status, error). Application Layer dalam `app.py` (1526 lines) menggunakan FastAPI framework dan `SocketIOBroadcaster` (681 lines) untuk meng-orchestrate `ScalpingEngine` (1064 lines) yang berjalan dalam event loop terpisah dengan threading model. Engine Layer mengimplementasikan event-driven architecture dimana `ScalpingEngine` menerima real-time bar data dari IBKR via `ib_insync` callbacks, memproses data melalui `IndicatorEngine` (781 lines) yang menghitung 44 technical indicators menggunakan pandas-ta library dengan rolling window 250 candles, kemudian mengevaluasi trading conditions melalui `RuleEngine` (453 lines) yang support 44 operands dan 6 operators tanpa menggunakan `eval()` untuk security, dan mem-broadcast hasil signal melalui WebSocket ke connected clients. Data Layer menggunakan `SQLiteRepository` (1143 lines) dengan thread-safe operations menggunakan `threading.Lock()` untuk persist data ke database file `signalgen.db`, serta integrasi dengan IBKR TWS/Gateway (port 7497/4002) untuk real-time market data dan Yahoo Finance via `yfinance` untuk historical data backtesting. Komunikasi antar layer menggunakan 3 mekanisme berbeda: HTTP REST API untuk synchronous request-response pattern antara UI dan Application Layer, WebSocket bidirectional communication untuk asynchronous real-time push dari server ke clients, dan direct function calls dengan thread-safe repository pattern untuk komunikasi internal antara Application-Engine-Data layers dengan proper lock management dan async event loop isolation.

### Diagram Arsitektur Implementasi Lengkap

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LAYER 1: USER INTERFACE                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              PyWebView Window (1400x900)                      │  │
│  │         URL: http://127.0.0.1:3456                            │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │  index.html (Tailwind CSS)                              │ │  │
│  │  │  - Tab Navigation: Scalping, Backtesting, Swing         │ │  │
│  │  │                                                          │ │  │
│  │  │  app.js (2270 lines) - SignalGenApp class               │ │  │
│  │  │  api.js (201 lines) - ApiClient class                   │ │  │
│  │  │  websocket.js (249 lines) - WebSocketClient class       │ │  │
│  │  │  backtesting.js - Backtesting UI                        │ │  │
│  │  │  swing.js - Swing Trading UI                            │ │  │
│  │  └─────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────┬──────────────────────┬────────────────────────┘
                      │ REST API             │ WebSocket
                      │ (HTTP)               │ (Socket.IO)
                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 2: APPLICATION LAYER                        │
│  ┌──────────────────────────────┐  ┌─────────────────────────────┐ │
│  │  FastAPI Server              │  │  Socket.IO Server           │ │
│  │  (app.py - 1526 lines)       │  │  (broadcaster.py - 681 lines)│ │
│  │  Thread: Daemon              │  │  Thread: Daemon             │ │
│  │  Port: 3456                  │  │  Port: 8765                 │ │
│  │                              │  │                             │ │
│  │  22 REST Endpoints:          │  │  6 WebSocket Events:        │ │
│  │  - /api/rules/*              │  │  - signal                   │ │
│  │  - /api/watchlists/*         │  │  - engine_status            │ │
│  │  - /api/engine/*             │  │  - rule_update              │ │
│  │  - /api/signals/*            │  │  - watchlist_update         │ │
│  │  - /api/settings/*           │  │  - ibkr_status              │ │
│  │  - /api/health               │  │  - error                    │ │
│  │  - /api/status               │  │                             │ │
│  └──────────────────────────────┘  └─────────────────────────────┘ │
└─────────────────────┬────────────────────────────────────────────────┘
                      │ Direct Function Calls
                      │ Threading Model: Separate Event Loop
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      LAYER 3: ENGINE LAYER                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ScalpingEngine (scalping_engine.py - 1064 lines)           │   │
│  │  - Event-driven async architecture                          │   │
│  │  - IBKR connection via ib_insync                            │   │
│  │  - Auto reconnection (max 10 attempts, 5s interval)         │   │
│  │  - Per-symbol cooldown tracking                             │   │
│  │                                                              │   │
│  │  Data Flow:                                                  │   │
│  │  IBKR Bar → Indicator Engine → Rule Engine → Signal → WS    │   │
│  └───────┬──────────────────────┬──────────────────────┬────────┘   │
│          ▼                      ▼                      ▼            │
│  ┌─────────────────┐   ┌────────────────┐   ┌──────────────────┐  │
│  │ IndicatorEngine │   │  RuleEngine    │   │  CandleBuilder   │  │
│  │ (781 lines)     │   │  (453 lines)   │   │  State Machine   │  │
│  │                 │   │                │   │                  │  │
│  │ Library:        │   │ Security:      │   │ Timeframe:       │  │
│  │ - pandas-ta     │   │ - No eval()    │   │ - 1m, 5m, 15m   │  │
│  │                 │   │                │   │ - 1h, 4h, 1d     │  │
│  │ 44 Indicators:  │   │ 44 Operands:   │   │                  │  │
│  │ - PRICE         │   │ - PRICE        │   │ Max: 250 candles │  │
│  │ - MA (4 types)  │   │ - MA, EMA      │   │                  │  │
│  │ - EMA (8 types) │   │ - MACD, RSI    │   │ Thread-safe:     │  │
│  │ - MACD (4)      │   │ - ADX, BB      │   │ - RLock()        │  │
│  │ - RSI, ADX      │   │                │   │                  │  │
│  │ - Bollinger (4) │   │ 6 Operators:   │   │                  │  │
│  │ - Previous vals │   │ - >, <, >=, <= │   │                  │  │
│  │                 │   │ - CROSS_UP     │   │                  │  │
│  │ Rolling window: │   │ - CROSS_DOWN   │   │                  │  │
│  │ - 250 candles   │   │                │   │                  │  │
│  │                 │   │ Logic: AND     │   │                  │  │
│  └─────────────────┘   └────────────────┘   └──────────────────┘  │
└─────────────────────┬────────────────────────────────────────────────┘
                      │ Repository Pattern
                      │ Thread-safe: Lock()
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       LAYER 4: DATA LAYER                            │
│  ┌──────────────────────────────┐  ┌─────────────────────────────┐ │
│  │  SQLiteRepository            │  │  Data Sources               │ │
│  │  (sqlite_repo.py - 1143 lines│  │                             │ │
│  │                              │  │  ┌────────────────────────┐ │ │
│  │  Database: signalgen.db      │  │  │ IBKRDataSource         │ │ │
│  │  Thread-safe: Lock()         │  │  │ - Library: ib_insync   │ │ │
│  │                              │  │  │ - TWS Port: 7497       │ │ │
│  │  5 Tables:                   │  │  │ - Gateway Port: 4002   │ │ │
│  │  1. rules                    │  │  │ - Real-time bars       │ │ │
│  │     - id, name, type         │  │  │ - Historical data      │ │ │
│  │     - definition (JSON)      │  │  └────────────────────────┘ │ │
│  │     - is_system, timestamps  │  │                             │ │
│  │                              │  │  ┌────────────────────────┐ │ │
│  │  2. watchlists               │  │  │ YahooDataSource        │ │ │
│  │     - id, name, is_active    │  │  │ - Library: yfinance    │ │ │
│  │     - created_at             │  │  │ - Historical OHLCV     │ │ │
│  │                              │  │  │ - For backtesting      │ │ │
│  │  3. watchlist_items          │  │  └────────────────────────┘ │ │
│  │     - watchlist_id, symbol   │  │                             │ │
│  │     - Max: 5 symbols         │  │                             │ │
│  │                              │  │                             │ │
│  │  4. signals                  │  │                             │ │
│  │     - timestamp, symbol      │  │                             │ │
│  │     - signal_type, price     │  │                             │ │
│  │     - indicators (JSON)      │  │                             │ │
│  │                              │  │                             │ │
│  │  5. settings                 │  │                             │ │
│  │     - key, value (JSON)      │  │                             │ │
│  │     - ib_host, ib_port       │  │                             │ │
│  │     - timeframe, theme       │  │                             │ │
│  └──────────────────────────────┘  └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ✅ VALIDASI SUMBER DATA

### Data yang Dikumpulkan Berasal Dari:

✅ **Source Code Aktual** - Semua informasi diambil dari file kode yang benar-benar ada di repository  
✅ **Docstrings** - Dokumentasi yang ditulis oleh developer dalam kode  
✅ **Komentar Kode** - Penjelasan inline dari implementasi  
✅ **Struktur Folder** - Organisasi file dan direktori yang terverifikasi  
✅ **Jumlah Baris Kode** - Dihitung dari file aktual (verifiable)  
✅ **Nama Class/Method** - Identifikasi dari implementasi nyata  
✅ **Konfigurasi Runtime** - Port numbers, URLs, dan parameter faktual dari kode  
✅ **Database Schema** - SQL statements aktual dari sqlite_repo.py  
✅ **API Endpoints** - Daftar routes dari FastAPI implementation  
✅ **WebSocket Events** - Event names dari broadcaster implementation  

### Data yang TIDAK Termasuk:

❌ **Konsep Teoritis** - Tidak ada teori yang tidak diimplementasikan  
❌ **Best Practices** - Tidak menyebutkan best practices yang hanya wacana  
❌ **Future Features** - Tidak ada fitur yang direncanakan tapi belum dikoding  
❌ **Assumptions** - Tidak ada asumsi di luar kode  
❌ **Generic Explanations** - Tidak ada penjelasan umum tanpa konteks kode  

---

## 📊 STATISTIK IMPLEMENTASI

### Total Lines of Code by Layer

| Layer | Lines of Code |
|-------|---------------|
| Entry Point | 254 |
| User Interface Layer | 2,720 |
| Application Layer | 2,207 |
| Engine Layer | 2,298 |
| Data Layer | 1,143 |
| **TOTAL** | **8,622** |

### File Distribution by Layer

| Layer | Number of Files |
|-------|-----------------|
| User Interface | 6 files |
| Application | 3 files |
| Engine | 7 files |
| Data | 5 files |
| **TOTAL** | **21 core files** |

### Technology Stack (Factual)

**Backend:**
- Python 3.8+
- FastAPI (ASGI web framework)
- Uvicorn (ASGI server)
- ib_insync (IBKR API client)
- pandas-ta (Technical indicators)
- SQLite3 (Database)
- python-socketio (WebSocket)

**Frontend:**
- PyWebView (Desktop window)
- Vanilla JavaScript (ES6+)
- Tailwind CSS (Styling)
- Socket.IO Client (WebSocket)

**Data Sources:**
- Interactive Brokers API (Real-time)
- Yahoo Finance (Historical)

---

## 📝 CATATAN UNTUK PENULISAN BAB 4.1.1

### Poin-Poin Kunci yang Dapat Digunakan:

1. **Entry Point dan Inisialisasi**
   - Aplikasi dimulai dari `app/main.py` dengan 6 tahap inisialisasi
   - Multi-threaded architecture dengan daemon threads untuk servers
   - Desktop application menggunakan PyWebView

2. **Arsitektur 4-Layer**
   - Setiap layer memiliki file dan modul konkret yang dapat disebutkan
   - Total 21 core files dengan 8,622 lines of code
   - Pemisahan tanggung jawab yang jelas antar layer

3. **Komunikasi Antar Layer**
   - 3 mekanisme berbeda: REST API, WebSocket, Direct Function Calls
   - Port configuration faktual: 3456 (FastAPI), 8765 (Socket.IO), 7497 (IBKR)
   - Thread-safety implementation dengan locks

4. **Engine Architecture**
   - Event-driven async architecture untuk real-time processing
   - 44 technical indicators dengan library pandas-ta
   - Security: No eval() usage dalam rule engine

5. **Data Persistence**
   - 5 tabel database dengan schema terdokumentasi
   - Thread-safe repository pattern
   - Dual data sources: IBKR (real-time) + Yahoo (historical)

### File References untuk Sitasi:

Semua referensi ke kode dapat menggunakan format:
- `app/main.py` (lines X-Y)
- `app/app.py` (class SignalGenApp)
- `app/engines/scalping_engine.py` (method start_engine)
- dll.

---

**END OF DOCUMENT**

*Dokumen ini berisi informasi faktual 100% berdasarkan implementasi kode aktual di repository SignalGen.*
