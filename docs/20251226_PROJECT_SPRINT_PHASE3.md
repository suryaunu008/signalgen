# PROJECT SPRINT PHASE 3 - MULTI-MODE TRADING SYSTEM

## Specification Document - December 29, 2025

---

## 🎯 OBJECTIVE

Expand the current scalping-only system into a **multi-mode trading platform** with 4 distinct operational modes:

1. **Real-time Scalping** (existing - uses IBKR live data)
2. **Scalping Backtesting** (new - uses IBKR historical data)
3. **Swing Screening** (new - uses Yahoo Finance batch data)
4. **Swing Backtesting** (new - uses Yahoo Finance historical data)

**Core Design Principle:**

- All modes share the **same Rule Engine and Indicator Engine**
- Difference is only in **data source** and **execution workflow**
- Modular architecture for code reusability

---

## 📊 CURRENT PROJECT STATUS

### ✅ Completed (Sprint 1 & 2)

- **Rule Engine**: Full support for custom conditions, AND/OR logic, CROSS_UP/CROSS_DOWN operators
- **Indicator Engine**: MA, EMA, MACD, RSI, ADX with previous value tracking
- **Candle Builder**: Multi-timeframe aggregation (1m, 5m, 15m, 1h, 4h, 1d)
- **Scalping Engine**: IBKR integration with real-time 5-second bars
- **WebSocket Broadcasting**: Real-time signal delivery to UI
- **Database**: SQLite with rules, watchlists, settings, signals storage
- **UI**: Single-page scalping interface with PyWebView + Tailwind

### 📦 Technology Stack

- FastAPI (REST API)
- Socket.IO (WebSocket for real-time updates)
- ib_insync (IBKR data feed)
- PyWebView (Desktop UI)
- SQLite (Storage)
- pandas, numpy, ta (Technical analysis)

### 🔧 Available Components to Reuse

- **Rule Engine** ([app/core/rule_engine.py](app/core/rule_engine.py)) - Ready for all modes
- **Indicator Engine** ([app/core/indicator_engine.py](app/core/indicator_engine.py)) - Ready for all modes
- **Candle Builder** ([app/core/candle_builder.py](app/core/candle_builder.py)) - Ready for all modes
- **SQLite Repository** ([app/storage/sqlite_repo.py](app/storage/sqlite_repo.py)) - Needs extension
- **Broadcaster** ([app/ws/broadcaster.py](app/ws/broadcaster.py)) - Ready for all modes

---

## 🏗️ SYSTEM ARCHITECTURE CHANGES

### New Directory Structure

```
app/
  engines/
    scalping_engine.py          # Existing - real-time IBKR scalping
    backtesting_engine.py       # NEW - backtesting for both scalping & swing
    swing_screening_engine.py   # NEW - Yahoo Finance batch screening
  data_sources/
    ibkr_data_source.py         # NEW - abstraction for IBKR data
    yahoo_data_source.py        # NEW - abstraction for Yahoo Finance data
  ui/
    templates/
      index.html                # MODIFY - add mode selector and tabs
    static/
      js/
        app.js                  # MODIFY - multi-mode UI logic
        backtesting.js          # NEW - backtesting UI
        swing.js                # NEW - swing trading UI
```

### New Dependencies to Add

```requirements.txt
yfinance>=0.2.33              # Yahoo Finance data
```

---

## 🔀 IMPLEMENTATION PLAN

### Phase 3.1: Data Source Abstraction Layer

**Goal**: Create generic data source interface for both IBKR and Yahoo Finance

#### 3.1.1: Base Data Source Interface

**File**: `app/data_sources/base_data_source.py`

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime

class BaseDataSource(ABC):
    """Abstract base class for all data sources."""

    @abstractmethod
    async def fetch_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str
    ) -> List[Dict]:
        """
        Fetch historical OHLCV data.

        Returns:
            List of candles: [
                {
                    'timestamp': datetime,
                    'open': float,
                    'high': float,
                    'low': float,
                    'close': float,
                    'volume': int
                },
                ...
            ]
        """
        pass

    @abstractmethod
    async def validate_symbol(self, symbol: str) -> bool:
        """Check if symbol is valid for this data source."""
        pass

    @abstractmethod
    def get_supported_timeframes(self) -> List[str]:
        """Return list of supported timeframes."""
        pass
```

#### 3.1.2: IBKR Data Source

**File**: `app/data_sources/ibkr_data_source.py`

```python
from ib_insync import IB, Stock, util
from .base_data_source import BaseDataSource

class IBKRDataSource(BaseDataSource):
    """IBKR data source using ib_insync."""

    def __init__(self, host='127.0.0.1', port=7497):
        self.ib = IB()
        self.host = host
        self.port = port

    async def fetch_historical_data(self, symbol, start_date, end_date, timeframe):
        # Connect to IBKR
        # Request historical bars
        # Convert to standard format
        # Return list of candles
        pass

    async def validate_symbol(self, symbol):
        # Check if symbol exists on IBKR
        pass

    def get_supported_timeframes(self):
        return ['1m', '5m', '15m', '1h', '4h', '1d']
```

#### 3.1.3: Yahoo Finance Data Source

**File**: `app/data_sources/yahoo_data_source.py`

```python
import yfinance as yf
from .base_data_source import BaseDataSource

class YahooDataSource(BaseDataSource):
    """Yahoo Finance data source using yfinance."""

    async def fetch_historical_data(self, symbol, start_date, end_date, timeframe):
        # Convert timeframe to yfinance interval
        interval_map = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '1h': '1h',
            '4h': None,  # Not supported, need aggregation
            '1d': '1d'
        }

        # Download data from yfinance
        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start_date,
            end=end_date,
            interval=interval_map[timeframe]
        )

        # Convert DataFrame to list of dicts
        # Return standardized format
        pass

    async def validate_symbol(self, symbol):
        # Try to fetch ticker info
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return 'regularMarketPrice' in info

    def get_supported_timeframes(self):
        return ['1m', '5m', '15m', '1h', '1d']  # 4h requires aggregation
```

---

### Phase 3.2: Backtesting Engine

**Goal**: Create unified backtesting engine for both scalping and swing strategies

#### 3.2.1: Backtesting Engine Core

**File**: `app/engines/backtesting_engine.py`

**Features**:

- Accepts data source (IBKR or Yahoo)
- Iterates through historical candles sequentially
- Feeds candles to Indicator Engine → Rule Engine
- Generates signals with timestamps
- Calculates performance metrics
- No order execution (signal generation only)

**Key Methods**:

```python
class BacktestingEngine:
    def __init__(self, data_source: BaseDataSource, timeframe: str):
        self.data_source = data_source
        self.timeframe = timeframe
        self.indicator_engine = IndicatorEngine(timeframe=timeframe)
        self.rule_engine = RuleEngine()
        self.signals = []

    async def run_backtest(
        self,
        symbols: List[str],
        rule_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Run backtest for given symbols and date range.

        Returns:
            {
                'signals': [...],
                'metrics': {
                    'total_signals': int,
                    'signals_per_symbol': Dict[str, int],
                    'date_range': {'start': str, 'end': str}
                }
            }
        """
        # Load rule from database
        # For each symbol:
        #   Fetch historical data
        #   Feed to indicator engine
        #   Check rule conditions
        #   Record signals
        # Calculate metrics
        # Return results
        pass
```

#### 3.2.2: Backtest Results Storage

**Database Schema Extension** in `app/storage/init_db.py`:

```sql
CREATE TABLE IF NOT EXISTS backtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    mode TEXT NOT NULL,  -- 'scalping' or 'swing'
    rule_id INTEGER NOT NULL,
    symbols TEXT NOT NULL,  -- JSON array
    timeframe TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    data_source TEXT NOT NULL,  -- 'ibkr' or 'yahoo'
    created_at TEXT NOT NULL,
    total_signals INTEGER DEFAULT 0,
    metadata TEXT,  -- JSON for additional metrics
    FOREIGN KEY (rule_id) REFERENCES rules(id)
);

CREATE TABLE IF NOT EXISTS backtest_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_run_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    price REAL NOT NULL,
    indicators TEXT,  -- JSON snapshot
    FOREIGN KEY (backtest_run_id) REFERENCES backtest_runs(id)
);
```

---

### Phase 3.3: Swing Screening Engine

**Goal**: Batch screening for swing trading signals using Yahoo Finance

#### 3.3.1: Swing Screening Engine

**File**: `app/engines/swing_screening_engine.py`

**Features**:

- Uses Yahoo Finance data source
- Screens multiple tickers against a rule
- Runs on-demand (not real-time)
- Returns current signals for all tickers
- Supports daily, 4h, 1h timeframes (typical for swing)

**Key Methods**:

```python
class SwingScreeningEngine:
    def __init__(self, timeframe: str = '1d'):
        self.data_source = YahooDataSource()
        self.timeframe = timeframe
        self.indicator_engine = IndicatorEngine(timeframe=timeframe)
        self.rule_engine = RuleEngine()

    async def screen_tickers(
        self,
        tickers: List[str],
        rule_id: int,
        lookback_days: int = 30
    ) -> List[Dict]:
        """
        Screen multiple tickers for swing signals.

        Returns:
            [
                {
                    'symbol': 'AAPL',
                    'signal': 'BUY' or None,
                    'price': 150.25,
                    'timestamp': '2025-12-29 16:00:00',
                    'indicators': {...}
                },
                ...
            ]
        """
        # For each ticker:
        #   Fetch recent data (lookback_days)
        #   Feed to indicator engine
        #   Check rule conditions
        #   Return current status
        pass
```

#### 3.3.2: Ticker Universe Management

**Database Schema Extension**:

```sql
CREATE TABLE IF NOT EXISTS ticker_universes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    tickers TEXT NOT NULL,  -- JSON array of ticker symbols
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Seed default universes
INSERT INTO ticker_universes (name, tickers, description, created_at, updated_at)
VALUES
    ('S&P 100', '["AAPL","MSFT","GOOGL","AMZN","TSLA",...]',
     'Top 100 S&P stocks', datetime('now'), datetime('now')),
    ('Tech Giants', '["AAPL","MSFT","GOOGL","AMZN","META","NVDA","TSLA"]',
     'Major tech stocks', datetime('now'), datetime('now')),
    ('Custom', '[]', 'User-defined tickers', datetime('now'), datetime('now'));
```

---

### Phase 3.4: REST API Extensions

**File**: `app/app.py` - Add new endpoints

#### Backtesting Endpoints

```python
@app.post('/api/backtest/run')
async def run_backtest(request: BacktestRequest):
    """
    Run a backtest.

    Request Body:
    {
        "name": "My Backtest",
        "mode": "scalping" | "swing",
        "rule_id": 1,
        "symbols": ["AAPL", "MSFT"],
        "timeframe": "5m",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "data_source": "ibkr" | "yahoo"
    }
    """
    pass

@app.get('/api/backtest/runs')
async def get_backtest_runs():
    """Get all backtest runs."""
    pass

@app.get('/api/backtest/runs/{run_id}')
async def get_backtest_run(run_id: int):
    """Get specific backtest run with signals."""
    pass

@app.delete('/api/backtest/runs/{run_id}')
async def delete_backtest_run(run_id: int):
    """Delete a backtest run."""
    pass
```

#### Swing Trading Endpoints

```python
@app.post('/api/swing/screen')
async def screen_swing_signals(request: SwingScreenRequest):
    """
    Run swing screening.

    Request Body:
    {
        "rule_id": 1,
        "ticker_universe_id": 1,
        "timeframe": "1d",
        "lookback_days": 30
    }
    """
    pass

@app.get('/api/swing/universes')
async def get_ticker_universes():
    """Get all ticker universes."""
    pass

@app.post('/api/swing/universes')
async def create_ticker_universe(request: UniverseCreate):
    """Create new ticker universe."""
    pass

@app.put('/api/swing/universes/{universe_id}')
async def update_ticker_universe(universe_id: int, request: UniverseUpdate):
    """Update ticker universe."""
    pass

@app.delete('/api/swing/universes/{universe_id}')
async def delete_ticker_universe(universe_id: int):
    """Delete ticker universe."""
    pass
```

#### Mode Management Endpoint

```python
@app.get('/api/mode')
async def get_current_mode():
    """
    Get current operational mode.

    Returns:
    {
        "mode": "scalping" | "backtesting" | "swing" | "swing_backtest",
        "available_modes": [...]
    }
    """
    pass

@app.put('/api/mode')
async def set_mode(request: ModeChange):
    """
    Change operational mode.

    Request Body:
    {
        "mode": "scalping" | "backtesting" | "swing" | "swing_backtest"
    }
    """
    pass
```

---

### Phase 3.5: UI Redesign

**Goal**: Multi-tab interface for different modes

#### 3.5.1: Main UI Structure

**File**: `app/ui/templates/index.html` - Major restructuring

**New Layout**:

```html
<header>
	<!-- Existing header with mode indicator -->
	<div id="mode-selector">
		<select id="operational-mode">
			<option value="scalping">Real-time Scalping</option>
			<option value="backtesting">Scalping Backtest</option>
			<option value="swing">Swing Screening</option>
			<option value="swing_backtest">Swing Backtest</option>
		</select>
	</div>
</header>

<main>
	<!-- Tab Navigation -->
	<nav class="tab-navigation">
		<button data-tab="scalping">Scalping</button>
		<button data-tab="backtesting">Backtesting</button>
		<button data-tab="swing">Swing Trading</button>
	</nav>

	<!-- Tab: Real-time Scalping (existing UI) -->
	<div id="tab-scalping" class="tab-content">
		<!-- Current scalping UI -->
	</div>

	<!-- Tab: Backtesting -->
	<div id="tab-backtesting" class="tab-content hidden">
		<section class="backtest-setup">
			<!-- Mode selector: Scalping vs Swing -->
			<!-- Date range picker -->
			<!-- Symbol selection -->
			<!-- Rule selection -->
			<!-- Timeframe selection -->
			<!-- Data source selection (IBKR/Yahoo) -->
			<button id="run-backtest">Run Backtest</button>
		</section>

		<section class="backtest-results">
			<!-- Results table -->
			<!-- Signal list -->
			<!-- Performance metrics -->
		</section>

		<section class="backtest-history">
			<!-- List of previous backtest runs -->
		</section>
	</div>

	<!-- Tab: Swing Trading -->
	<div id="tab-swing" class="tab-content hidden">
		<section class="swing-setup">
			<!-- Ticker universe selector -->
			<!-- Rule selection -->
			<!-- Timeframe selection (1d, 4h, 1h) -->
			<!-- Lookback period -->
			<button id="run-screening">Run Screening</button>
		</section>

		<section class="swing-results">
			<!-- Current signals table -->
			<!-- Ticker details -->
		</section>

		<section class="universe-management">
			<!-- Create/Edit/Delete ticker universes -->
		</section>
	</div>
</main>
```

#### 3.5.2: New JavaScript Files

**File**: `app/ui/static/js/backtesting.js`

- Handle backtest configuration
- Submit backtest runs
- Display results and charts
- Manage backtest history

**File**: `app/ui/static/js/swing.js`

- Handle ticker universe selection
- Submit screening requests
- Display screening results
- Manage ticker universes (CRUD)

**File**: `app/ui/static/js/app.js` - Modifications

- Add mode switching logic
- Tab navigation
- Coordinate between different modules

---

## 🎯 IMPLEMENTATION CHECKLIST

### Phase 3.1: Data Abstraction ✅

- [ ] Create `app/data_sources/base_data_source.py`
- [ ] Create `app/data_sources/ibkr_data_source.py`
- [ ] Create `app/data_sources/yahoo_data_source.py`
- [ ] Add `yfinance>=0.2.33` to requirements.txt
- [ ] Write unit tests for data sources

### Phase 3.2: Backtesting ✅

- [ ] Create `app/engines/backtesting_engine.py`
- [ ] Extend database schema (backtest_runs, backtest_signals)
- [ ] Add backtesting methods to SQLiteRepository
- [ ] Add REST API endpoints for backtesting
- [ ] Write unit tests for backtesting engine

### Phase 3.3: Swing Screening ✅

- [ ] Create `app/engines/swing_screening_engine.py`
- [ ] Extend database schema (ticker_universes)
- [ ] Seed default ticker universes
- [ ] Add ticker universe CRUD to SQLiteRepository
- [ ] Add REST API endpoints for swing screening
- [ ] Write unit tests for swing screening

### Phase 3.4: UI Development ✅

- [ ] Redesign `index.html` with tab navigation
- [ ] Create `backtesting.js`
- [ ] Create `swing.js`
- [ ] Update `app.js` for mode switching
- [ ] Add CSS for new UI components
- [ ] Test all UI flows

### Phase 3.5: Integration & Testing ✅

- [ ] Integration testing for all modes
- [ ] End-to-end testing
- [ ] Performance testing (Yahoo Finance API rate limits)
- [ ] Documentation updates
- [ ] User guide for each mode

---

## 📝 TECHNICAL NOTES

### Yahoo Finance Limitations

- **Rate limits**: ~2000 requests/hour (use caching)
- **Intraday data**: Limited to last 60 days for 1m/5m intervals
- **4h timeframe**: Not natively supported, need to aggregate 1h bars
- **Weekend/holiday data**: No data for market closed days

### Data Source Selection Guidelines

- **IBKR**: Use for intraday scalping backtests (<60 days, high frequency)
- **Yahoo Finance**: Use for swing trading (daily/weekly, longer periods)

### Performance Considerations

- **Batch processing**: Screen 50-100 tickers in parallel (asyncio)
- **Caching**: Cache Yahoo Finance data (1h TTL for intraday, 1d for daily)
- **Database indexing**: Add indexes on backtest_signals(timestamp), backtest_runs(created_at)

### State Management

- Cannot run real-time scalping + backtesting simultaneously
- Mode switching requires engine shutdown
- Backtest runs are fire-and-forget (no real-time updates during backtest)
- Swing screening can run concurrently with backtesting

---

## 🚀 SUCCESS CRITERIA

1. ✅ User can switch between 4 operational modes via UI
2. ✅ Scalping backtesting works with IBKR historical data
3. ✅ Swing screening works with Yahoo Finance data
4. ✅ Backtests can be saved, viewed, and deleted
5. ✅ Ticker universes can be created and managed
6. ✅ All modes share the same rule engine and indicators
7. ✅ UI is intuitive with clear mode separation
8. ✅ No regression in existing real-time scalping functionality

---

## 📅 ESTIMATED TIMELINE

- **Phase 3.1 (Data Abstraction)**: 2-3 days
- **Phase 3.2 (Backtesting)**: 3-4 days
- **Phase 3.3 (Swing Screening)**: 3-4 days
- **Phase 3.4 (UI Development)**: 3-4 days
- **Phase 3.5 (Integration & Testing)**: 2-3 days

**Total**: ~13-18 days (2.5-3.5 weeks)

---

## 🔄 FUTURE ENHANCEMENTS (Post-Phase 3)

- Backtest performance analytics (Sharpe ratio, max drawdown, win rate)
- Export backtest results to CSV/Excel
- Advanced charting with TradingView integration
- Multiple rule backtesting (compare strategies)
- Portfolio-level swing screening (correlations, sector analysis)
- Alert system for swing signals (email/Telegram notifications)
