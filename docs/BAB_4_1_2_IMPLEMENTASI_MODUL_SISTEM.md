# 4.1.2 Implementasi Modul Sistem

Subbab ini menjelaskan implementasi nyata dari modul-modul sistem yang telah dirancang sebelumnya. Setiap modul diimplementasikan dalam bentuk kode program Python yang saling terintegrasi untuk membentuk sistem *trading signal generator* yang utuh. Penjelasan berikut mengacu pada implementasi aktual dari kode program yang telah dikembangkan.

---

## 4.1.2.1 Implementasi Modul Web Interface

Modul *Web Interface* berfungsi sebagai antarmuka pengguna yang memungkinkan interaksi dengan sistem melalui tampilan grafis berbasis *web*. Modul ini diimplementasikan menggunakan HTML, CSS, dan JavaScript yang terintegrasi dengan kerangka kerja *Tailwind CSS* untuk tampilan responsif dan modern.

Implementasi modul ini direalisasikan dalam bentuk kode program yang berfungsi untuk menampilkan komponen-komponen antarmuka pengguna seperti panel kontrol *engine*, tabel sinyal *real-time*, manajemen *rule*, dan manajemen *watchlist*. Berikut adalah potongan kode representatif dari modul *Web Interface*:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>SignalGen - Multi-Mode Trading System</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.socket.io/4.7.4/socket.io.min.js"></script>
    <link rel="stylesheet" 
          href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <script src="/static/js/app.js"></script>
    <script src="/static/js/websocket.js"></script>
    <script src="/static/js/api.js"></script>
    <script src="/static/js/backtesting.js"></script>
    <script src="/static/js/swing.js"></script>
  </head>
  <body class="bg-gray-100 text-gray-800">
    <!-- Header -->
    <header class="bg-blue-600 text-white shadow-lg">
      <div class="container mx-auto px-4 py-4">
        <div class="flex justify-between items-center">
          <div class="flex items-center space-x-3">
            <i class="fas fa-chart-line text-2xl"></i>
            <h1 class="text-2xl font-bold">SignalGen</h1>
          </div>
        </div>
      </div>
    </header>
  </body>
</html>
```

Kode di atas menunjukkan struktur dasar halaman *web* yang memuat *library* eksternal seperti *Socket.IO* untuk komunikasi *real-time*, *Tailwind CSS* untuk tampilan, serta beberapa file JavaScript yang mengelola logika antarmuka. File-file JavaScript tersebut mencakup `app.js` untuk kontrol utama aplikasi, `websocket.js` untuk koneksi *WebSocket*, `api.js` untuk komunikasi dengan *REST API*, `backtesting.js` untuk fitur *backtesting*, dan `swing.js` untuk fitur *swing screening*. Dengan demikian, modul ini berperan sebagai lapisan presentasi yang menghubungkan pengguna dengan fungsi-fungsi internal sistem.

---

## 4.1.2.2 Implementasi Modul Main Application

Modul *Main Application* merupakan titik masuk utama (*entry point*) dari sistem. Modul ini bertanggung jawab untuk menginisialisasi seluruh komponen sistem, mengelola siklus hidup aplikasi, dan mengintegrasikan antara antarmuka pengguna dengan *backend* melalui *FastAPI* dan *PyWebView*.

Implementasi modul ini direalisasikan dalam bentuk kode program yang berfungsi untuk memulai *server* *FastAPI* dalam *thread* terpisah, membuat jendela aplikasi *desktop* menggunakan *PyWebView*, serta menginisialisasi basis data. Berikut adalah potongan kode representatif dari modul *Main Application*:

```python
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
    """Seed default data for MVP."""
    logger = logging.getLogger(__name__)
    
    try:
        existing_rules = repository.get_all_rules()
        default_rule_exists = any(
            rule.get('name') == 'Default Scalping' and rule.get('is_system')
            for rule in existing_rules
        )
        
        if not default_rule_exists:
            logger.warning("Default Scalping rule not found. Please run init_db")
        
        existing_watchlists = repository.get_all_watchlists()
        if not existing_watchlists:
            repository.create_watchlist(
                name="Default Watchlist",
                symbols=["AAPL", "MSFT", "GOOGL"]
            )
            watchlists = repository.get_all_watchlists()
            if watchlists:
                repository.set_active_watchlist(watchlists[0]['id'])
            logger.info("Default watchlist created and activated")
```

Kode di atas menunjukkan fungsi-fungsi yang digunakan untuk mengonfigurasi sistem *logging* dan melakukan inisialisasi data awal. Fungsi `setup_logging()` mengatur agar seluruh aktivitas sistem dicatat dalam file log dan ditampilkan di konsol. Fungsi `seed_default_data()` memeriksa apakah data default seperti *rule* dan *watchlist* sudah tersedia, jika belum maka akan dibuat secara otomatis. Modul ini memastikan bahwa sistem dapat berjalan langsung setelah instalasi tanpa memerlukan konfigurasi manual yang rumit.

---

## 4.1.2.3 Implementasi Modul REST API

Modul *REST API* menyediakan antarmuka komunikasi berbasis HTTP untuk mengelola data dan mengontrol *engine*. Modul ini diimplementasikan menggunakan kerangka kerja *FastAPI* yang menyediakan validasi data otomatis, dokumentasi API interaktif, dan performa tinggi.

Implementasi modul ini direalisasikan dalam bentuk kode program yang berfungsi untuk menyediakan *endpoint* API seperti manajemen *rule*, *watchlist*, kontrol *engine*, pengambilan sinyal, dan pengaturan sistem. Berikut adalah potongan kode representatif dari modul *REST API*:

```python
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

class WatchlistCreate(BaseModel):
    """Model for creating a new watchlist."""
    name: str = Field(..., min_length=1, max_length=100)
    symbols: List[str] = Field(..., min_items=1, max_items=5)
    
    @validator('symbols')
    def validate_symbols(cls, v):
        symbols = [s.upper().strip() for s in v if s.strip()]
        if len(set(symbols)) != len(symbols):
            raise ValueError("Duplicate symbols are not allowed")
        return symbols
```

Kode di atas menunjukkan model-model data yang digunakan untuk validasi *request* dari klien. Model `RuleCreate` memastikan bahwa setiap *rule* yang dibuat memiliki nama dan definisi yang valid dengan struktur yang benar. Model `WatchlistCreate` memvalidasi *watchlist* yang dibuat, memastikan simbol saham ditulis dalam huruf kapital, tidak ada duplikasi, dan jumlah maksimal 5 simbol. *FastAPI* menggunakan *Pydantic* untuk melakukan validasi otomatis sehingga data yang masuk ke sistem terjamin konsisten dan aman.

---

## 4.1.2.4 Implementasi Modul WebSocket Broadcaster

Modul *WebSocket Broadcaster* berfungsi untuk mengirimkan data secara *real-time* dari *server* ke klien menggunakan protokol *WebSocket*. Modul ini diimplementasikan dengan *Socket.IO* yang mendukung komunikasi dua arah, *room-based broadcasting*, dan manajemen koneksi klien secara otomatis.

Implementasi modul ini direalisasikan dalam bentuk kode program yang berfungsi untuk mengelola koneksi klien, mengirimkan berbagai jenis *event* seperti sinyal *trading*, status *engine*, dan notifikasi kesalahan kepada seluruh klien yang terhubung. Berikut adalah potongan kode representatif dari modul *WebSocket Broadcaster*:

```python
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import socketio
from socketio import AsyncServer
import json

class SocketIOBroadcaster:
    """WebSocket broadcaster using Socket.IO for real-time communication."""
    
    def __init__(self, cors_origins: List[str] = None):
        """Initialize the Socket.IO broadcaster."""
        self.logger = logging.getLogger(__name__)
        
        if cors_origins is None:
            cors_origins = ["http://localhost:3456", "http://127.0.0.1:3456"]
        
        self.sio = AsyncServer(
            async_mode='asgi',
            cors_allowed_origins=cors_origins,
            logger=False,
            engineio_logger=False
        )
        
        self.connected_clients: Dict[str, Dict[str, Any]] = {}
        
        self.ROOMS = {
            'signals': 'signals',
            'engine': 'engine_status',
            'rules': 'rules',
            'watchlists': 'watchlists',
            'ibkr': 'ibkr_status',
            'errors': 'errors',
        }
```

Kode di atas menunjukkan inisialisasi *server* *Socket.IO* dengan konfigurasi *CORS* (*Cross-Origin Resource Sharing*) untuk mengizinkan koneksi dari antarmuka *web* lokal. Atribut `connected_clients` menyimpan informasi klien yang sedang terhubung, sedangkan `ROOMS` mendefinisikan ruang-ruang (*room*) yang digunakan untuk mengelompokkan jenis *event* tertentu. Dengan mekanisme *room*, sistem dapat mengirimkan data hanya kepada klien yang berlangganan *event* tertentu, sehingga lebih efisien dalam penggunaan *bandwidth*.

---

## 4.1.2.5 Implementasi Modul Notifikasi

Modul Notifikasi tidak diimplementasikan sebagai modul terpisah, melainkan terintegrasi langsung dalam modul *WebSocket Broadcaster*. Fungsi notifikasi dilakukan melalui mekanisme *broadcasting* dengan berbagai jenis *event* seperti sinyal *trading*, status *engine*, perubahan *rule*, perubahan *watchlist*, koneksi ke *IBKR*, dan notifikasi kesalahan.

Implementasi modul ini direalisasikan dalam bentuk kode program yang berfungsi untuk mengirimkan notifikasi secara *real-time* kepada pengguna melalui *WebSocket*. Sistem notifikasi ini memungkinkan pengguna untuk segera mengetahui perubahan status atau munculnya sinyal baru tanpa perlu melakukan *refresh* secara manual.

Mekanisme notifikasi dalam sistem ini dirancang untuk mendukung berbagai tipe *event* yang masing-masing memiliki *room* tersendiri. Ketika sebuah *event* terjadi, *broadcaster* akan mengirimkan data ke semua klien yang terhubung dalam *room* yang sesuai. Pendekatan ini memastikan bahwa notifikasi terkirim dengan latensi rendah dan tidak membebani klien dengan data yang tidak relevan.

---

## 4.1.2.6 Implementasi Modul Scalping Engine

Modul *Scalping Engine* merupakan mesin utama untuk strategi *scalping* yang beroperasi dengan data *real-time* dari *Interactive Brokers* (*IBKR*). Modul ini mengorkestrasikan alur data dari *IBKR* hingga menghasilkan sinyal *trading* yang kemudian di-*broadcast* melalui *WebSocket*.

Implementasi modul ini direalisasikan dalam bentuk kode program yang berfungsi untuk mengelola koneksi ke *IBKR*, berlangganan data pasar secara *real-time*, memproses data melalui *Indicator Engine* dan *Rule Engine*, serta mengirimkan sinyal yang dihasilkan. Berikut adalah potongan kode representatif dari modul *Scalping Engine*:

```python
import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Callable
from ib_insync import IB, Stock, BarDataList, BarData, Contract
from datetime import datetime

from ..core.rule_engine import RuleEngine
from ..core.indicator_engine import IndicatorEngine
from ..core.state_machine import StateMachine, EngineState
from ..storage.sqlite_repo import SQLiteRepository
from ..ws.broadcaster import SocketIOBroadcaster

class ScalpingEngine:
    """Main scalping engine that orchestrates real-time signal generation."""
    
    def __init__(self, ib_host: str = '127.0.0.1', ib_port: int = 7497, 
                 ib_client_id: int = 1, timeframe: str = '1m'):
        """Initialize scalping engine with IBKR connection parameters."""
        self.ib = IB()
        self.ib_host = ib_host
        self.ib_port = ib_port
        self.ib_client_id = None
        
        self.timeframe = timeframe
        self.rule_engine = RuleEngine()
        self.indicator_engine = IndicatorEngine(timeframe=timeframe)
        self.state_machine = StateMachine()
        self.repository = SQLiteRepository()
        self.broadcaster = SocketIOBroadcaster()
        
        self.is_running = False
        self.is_connected = False
        self.active_watchlist: List[str] = []
        self.active_rule: Optional[Dict] = None
        
        self.subscribed_contracts: Dict[str, Contract] = {}
        self.contract_symbol_map: Dict[int, str] = {}
        self.real_time_bars: Dict[str, object] = {}
        self.symbol_cooldowns: Dict[str, float] = {}
        
        self.reconnect_enabled = True
        self.reconnect_interval = 5
        self.max_reconnect_attempts = 10
        self.reconnect_attempts = 0
        
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.logger = logging.getLogger(__name__)
```

Kode di atas menunjukkan inisialisasi *Scalping Engine* dengan berbagai komponen yang diperlukan. *Engine* ini menyimpan referensi ke *Rule Engine* untuk evaluasi aturan, *Indicator Engine* untuk perhitungan indikator teknikal, *State Machine* untuk manajemen status, *Repository* untuk akses basis data, dan *Broadcaster* untuk komunikasi *real-time*. Atribut-atribut seperti `subscribed_contracts` dan `symbol_cooldowns` digunakan untuk mengelola langganan data dan mencegah generasi sinyal yang terlalu sering untuk simbol yang sama. Mekanisme *reconnection* juga diimplementasikan untuk menangani gangguan koneksi dengan *IBKR* secara otomatis.

---

## 4.1.2.7 Implementasi Modul Swing Screening Engine

Modul *Swing Screening Engine* menyediakan fungsi penyaringan (*screening*) untuk strategi *swing trading*. Berbeda dengan *Scalping Engine* yang berjalan secara terus-menerus dengan data *real-time*, modul ini bekerja secara *batch* untuk menganalisis banyak saham sekaligus berdasarkan data historis.

Implementasi modul ini direalisasikan dalam bentuk kode program yang berfungsi untuk mengambil data dari *Yahoo Finance*, menerapkan *rule* yang dipilih pengguna pada setiap saham, dan mengembalikan daftar saham yang menghasilkan sinyal. Berikut adalah potongan kode representatif dari modul *Swing Screening Engine*:

```python
import asyncio
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from ..core.rule_engine import RuleEngine
from ..core.indicator_engine import IndicatorEngine
from ..storage.sqlite_repo import SQLiteRepository
from ..data_sources.yahoo_data_source import YahooDataSource

class SwingScreeningEngine:
    """Swing trading screening engine for batch analysis of multiple tickers."""
    
    def __init__(self, timeframe: str = '1d'):
        """Initialize swing screening engine."""
        self.data_source = YahooDataSource()
        self.timeframe = timeframe
        self.repository = SQLiteRepository()
        self.logger = logging.getLogger(__name__)
        
        if timeframe not in ['1h', '4h', '1d']:
            self.logger.warning(
                f"Timeframe '{timeframe}' is unusual for swing trading. "
                "Recommended: '1h', '4h', or '1d'"
            )
    
    async def screen_tickers(self, tickers: List[str], rule_id: int, 
                            lookback_days: int = 30) -> List[Dict[str, Any]]:
        """Screen multiple tickers for swing trading signals."""
        # Implementation continues...
```

Kode di atas menunjukkan bahwa *Swing Screening Engine* menggunakan *Yahoo Finance* sebagai sumber data dan mendukung *timeframe* seperti 1 jam, 4 jam, atau harian yang sesuai untuk strategi *swing trading*. Fungsi `screen_tickers()` menerima daftar simbol saham, ID *rule*, dan periode data historis yang akan dianalisis. *Engine* ini memberikan peringatan jika *timeframe* yang dipilih tidak umum untuk *swing trading*, membantu pengguna dalam memilih konfigurasi yang tepat.

---

## 4.1.2.8 Implementasi Modul Backtesting Engine

Modul *Backtesting Engine* menyediakan kemampuan untuk menguji strategi *trading* menggunakan data historis. Modul ini mendukung baik strategi *scalping* maupun *swing trading* dengan berbagai sumber data.

Implementasi modul ini direalisasikan dalam bentuk kode program yang berfungsi untuk melakukan simulasi *trading* secara historis dengan memproses data lilin (*candle*) secara berurutan, menghitung indikator, mengevaluasi *rule*, dan mencatat sinyal yang dihasilkan. Berikut adalah potongan kode representatif dari modul *Backtesting Engine*:

```python
import asyncio
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import json

from ..core.rule_engine import RuleEngine
from ..core.indicator_engine import IndicatorEngine
from ..storage.sqlite_repo import SQLiteRepository
from ..data_sources.base_data_source import BaseDataSource

class BacktestingEngine:
    """Unified backtesting engine for strategy validation."""
    
    def __init__(self, data_source: BaseDataSource, timeframe: str = '1d'):
        """Initialize backtesting engine."""
        self.data_source = data_source
        self.timeframe = timeframe
        self.indicator_engine = IndicatorEngine(timeframe=timeframe)
        self.rule_engine = RuleEngine()
        self.repository = SQLiteRepository()
        self.logger = logging.getLogger(__name__)
        
        self.signals = []
        self.current_rule = None
    
    async def run_backtest(self, name: str, mode: str, symbols: List[str], 
                          rule_id: int, start_date: datetime, end_date: datetime,
                          data_source_name: str) -> Dict[str, Any]:
        """Run backtest for given symbols and date range."""
        # Implementation continues...
```

Kode di atas menunjukkan bahwa *Backtesting Engine* dirancang secara modular dengan menerima objek `BaseDataSource` sebagai parameter, sehingga dapat bekerja dengan berbagai sumber data seperti *IBKR* atau *Yahoo Finance*. Fungsi `run_backtest()` menerima berbagai parameter termasuk nama *backtest*, mode (*scalping* atau *swing*), daftar simbol, *rule* yang digunakan, rentang tanggal, dan nama sumber data. Modul ini menggunakan *Indicator Engine* dan *Rule Engine* yang sama dengan *engine* lainnya untuk memastikan konsistensi evaluasi strategi.

---

## 4.1.2.9 Implementasi Modul Rule Engine

Modul *Rule Engine* bertugas untuk mengevaluasi aturan *trading* yang didefinisikan pengguna terhadap nilai-nilai indikator teknikal. Modul ini menggunakan pendekatan deterministik tanpa eksekusi kode dinamis untuk menjaga keamanan dan performa.

Implementasi modul ini direalisasikan dalam bentuk kode program yang berfungsi untuk memeriksa kondisi-kondisi dalam *rule* terhadap data indikator dan menghasilkan keputusan apakah sinyal *trading* harus dibangkitkan. Berikut adalah potongan kode representatif dari modul *Rule Engine*:

```python
import json
import logging
from typing import Dict, Any, List, Union

logger = logging.getLogger(__name__)

class RuleValidationError(Exception):
    """Exception raised when rule validation fails."""
    pass

class RuleEvaluationError(Exception):
    """Exception raised when rule evaluation fails."""
    pass

class RuleEngine:
    """Deterministic rule evaluation engine for trading signals."""
    
    SUPPORTED_OPERANDS = {
        "PRICE", "PREV_CLOSE", "PREV_OPEN",
        "MA20", "MA50", "MA100", "MA200",
        "MA20_PREV", "MA50_PREV", "MA100_PREV", "MA200_PREV",
        "EMA6", "EMA9", "EMA10", "EMA13", "EMA20", "EMA21", "EMA34", "EMA50",
        "EMA6_PREV", "EMA9_PREV", "EMA10_PREV", "EMA13_PREV",
        "MACD", "MACD_SIGNAL", "MACD_HIST", "MACD_HIST_PREV",
        "MACD_PREV", "MACD_SIGNAL_PREV",
        "BB_UPPER", "BB_MIDDLE", "BB_LOWER", "BB_WIDTH",
        "BB_UPPER_PREV", "BB_MIDDLE_PREV", "BB_LOWER_PREV",
        "ADX5", "ADX5_PREV",
        "RSI14", "RSI14_PREV",
        "VOLUME", "SMA_VOLUME_20", "REL_VOLUME_20",
        "PRICE_EMA20_DIFF_PCT",
    }
    
    SUPPORTED_OPERATORS = {
        ">", "<", ">=", "<=",
        "CROSS_UP", "CROSS_DOWN",
    }
```

Kode di atas menunjukkan definisi operand dan operator yang didukung oleh *Rule Engine*. Set `SUPPORTED_OPERANDS` mencakup berbagai indikator teknikal seperti harga, *moving average*, MACD, RSI, ADX, *Bollinger Bands*, dan indikator volume. Set `SUPPORTED_OPERATORS` mendefinisikan operator perbandingan standar serta operator khusus seperti `CROSS_UP` dan `CROSS_DOWN` untuk mendeteksi persilangan antara dua indikator. Pendekatan ini memastikan bahwa *rule* yang didefinisikan pengguna hanya dapat menggunakan operand dan operator yang telah divalidasi, sehingga menghindari injeksi kode berbahaya.

---

## 4.1.2.10 Implementasi Modul Indicator Engine

Modul *Indicator Engine* bertanggung jawab untuk menghitung indikator-indikator teknikal yang diperlukan dalam evaluasi *rule*. Modul ini menggunakan *library* `pandas-ta` dan `ta` untuk perhitungan yang efisien dan akurat.

Implementasi modul ini direalisasikan dalam bentuk kode program yang berfungsi untuk mengelola data lilin, menghitung berbagai indikator teknikal seperti *moving average*, MACD, RSI, ADX, dan *Bollinger Bands*, serta menyimpan nilai-nilai indikator untuk digunakan oleh *Rule Engine*. Berikut adalah potongan kode representatif dari modul *Indicator Engine*:

```python
import threading
import time
from collections import deque
from typing import Dict, List, Optional, Union
import logging

import pandas as pd
import numpy as np
import ta

from .candle_builder import CandleBuilder

class IndicatorEngine:
    """Technical indicator calculation engine for trading signals."""
    
    def __init__(self, max_history: int = 250, timeframe: str = '1m'):
        """Initialize the indicator engine."""
        self.max_history = max_history
        self.timeframe = timeframe
        self.candle_builder = CandleBuilder(timeframe=timeframe, max_candles=max_history)
        self.candle_data: Dict[str, deque] = {}
        self.indicators: Dict[str, Dict[str, float]] = {}
        self.prev_indicators: Dict[str, Dict[str, float]] = {}
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
        
        self.ma_periods = [20, 50, 100, 200]
        self.ema_periods = [6, 9, 10, 13, 20, 21, 34, 50]
        self.rsi_period = 14
        self.adx_period = 5
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.bb_period = 20
        self.bb_std_dev = 2
    
    def initialize_symbol(self, symbol: str) -> None:
        """Initialize data structures for a new symbol."""
        with self.lock:
            if symbol not in self.candle_data:
                self.candle_data[symbol] = deque(maxlen=self.max_history)
                self.indicators[symbol] = {}
                self.prev_indicators[symbol] = {}
                self.candle_builder.initialize_symbol(symbol)
```

Kode di atas menunjukkan bahwa *Indicator Engine* menggunakan `CandleBuilder` untuk agregasi data lilin sesuai *timeframe* yang dipilih. Struktur data `candle_data` menggunakan `deque` dengan batas maksimal untuk efisiensi memori, sementara `indicators` dan `prev_indicators` menyimpan nilai indikator saat ini dan sebelumnya untuk mendukung evaluasi kondisi seperti *crossover*. Atribut-atribut seperti `ma_periods` dan `ema_periods` mendefinisikan periode yang digunakan untuk perhitungan *moving average*. Penggunaan *lock* (`threading.RLock()`) memastikan bahwa modul ini aman digunakan dalam lingkungan multi-*thread*.

---

## 4.1.2.11 Implementasi Modul Candle Builder

Modul *Candle Builder* berfungsi untuk melakukan agregasi data *bar* mentah menjadi lilin (*candle*) sesuai dengan *timeframe* yang dipilih. Modul ini mendukung berbagai *timeframe* dari 1 menit hingga harian.

Implementasi modul ini direalisasikan dalam bentuk kode program yang berfungsi untuk mengelompokkan data *bar* berdasarkan *timestamp*, menghitung nilai OHLC (*Open*, *High*, *Low*, *Close*), dan mencegah duplikasi data. Berikut adalah potongan kode representatif dari modul *Candle Builder*:

```python
import threading
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import logging

class CandleBuilder:
    """Builds aggregated candles from raw bar data based on timeframe."""
    
    TIMEFRAMES = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '1h': 3600,
        '4h': 14400,
        '1d': 86400,
    }
    
    def __init__(self, timeframe: str = '1m', max_candles: int = 500):
        """Initialize candle builder."""
        if timeframe not in self.TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        
        self.timeframe = timeframe
        self.timeframe_seconds = self.TIMEFRAMES[timeframe]
        self.max_candles = max_candles
        
        self.completed_candles: Dict[str, deque] = {}
        self.current_candles: Dict[str, Optional[Dict]] = {}
        self.processed_timestamps: Dict[str, set] = {}
        self.last_candle_times: Dict[str, float] = {}
        
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
    
    def change_timeframe(self, new_timeframe: str) -> None:
        """Change the active timeframe and clear all candle data."""
        if new_timeframe not in self.TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {new_timeframe}")
        
        with self.lock:
            self.timeframe = new_timeframe
            self.timeframe_seconds = self.TIMEFRAMES[new_timeframe]
```

Kode di atas menunjukkan bahwa *Candle Builder* mendefinisikan mapping antara simbol *timeframe* dan durasinya dalam detik. Atribut `completed_candles` menyimpan lilin yang telah selesai dibentuk, sementara `current_candles` menyimpan lilin yang sedang dibentuk. Mekanisme `processed_timestamps` digunakan untuk mencegah pemrosesan data *bar* yang sama lebih dari satu kali. Fungsi `change_timeframe()` memungkinkan penggantian *timeframe* secara dinamis dengan membersihkan semua data lilin yang ada, memastikan bahwa data yang digunakan selalu konsisten dengan *timeframe* aktif.

---

## 4.1.2.12 Implementasi Modul Data Source

Modul *Data Source* menyediakan antarmuka abstrak untuk mengakses data pasar dari berbagai sumber. Implementasi modul ini menggunakan pola *Abstract Base Class* (ABC) untuk memastikan konsistensi antarmuka di seluruh implementasi konkret.

Implementasi modul ini direalisasikan dalam bentuk kode program yang berfungsi untuk mendefinisikan metode-metode yang wajib diimplementasikan oleh setiap sumber data, seperti pengambilan data historis, validasi simbol, dan informasi *timeframe* yang didukung. Berikut adalah potongan kode representatif dari modul *Data Source*:

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime

class BaseDataSource(ABC):
    """Abstract base class for all market data sources."""
    
    @abstractmethod
    async def fetch_historical_data(self, symbol: str, start_date: datetime, 
                                   end_date: datetime, timeframe: str) -> List[Dict]:
        """Fetch historical OHLCV data for a given symbol and time range."""
        pass
    
    @abstractmethod
    async def validate_symbol(self, symbol: str) -> bool:
        """Check if a symbol is valid and available from this data source."""
        pass
    
    @abstractmethod
    def get_supported_timeframes(self) -> List[str]:
        """Return list of timeframes supported by this data source."""
        pass
```

Kode di atas menunjukkan tiga metode abstrak yang wajib diimplementasikan oleh kelas turunan. Metode `fetch_historical_data()` bertanggung jawab untuk mengambil data historis dalam format OHLCV yang konsisten. Metode `validate_symbol()` memeriksa validitas simbol saham sebelum data diambil. Metode `get_supported_timeframes()` memberikan informasi *timeframe* yang didukung oleh sumber data tersebut. Pendekatan abstraksi ini memungkinkan sistem untuk bekerja dengan berbagai sumber data seperti *Interactive Brokers* dan *Yahoo Finance* tanpa perlu mengubah logika di modul-modul lain.

Implementasi konkret dari `BaseDataSource` salah satunya adalah `YahooDataSource` yang menggunakan *library* `yfinance` untuk mengakses data dari *Yahoo Finance*:

```python
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd

from .base_data_source import BaseDataSource

class YahooDataSource(BaseDataSource):
    """Yahoo Finance data source implementation using yfinance."""
    
    TIMEFRAME_MAP = {
        '1m': '1m',
        '5m': '5m',
        '15m': '15m',
        '1h': '1h',
        '1d': '1d',
    }
```

Implementasi `YahooDataSource` memetakan *timeframe* sistem ke format interval yang digunakan oleh *Yahoo Finance*, memastikan kompatibilitas antara kedua representasi.

---

## 4.1.2.13 Implementasi Modul Storage

Modul *Storage* menangani seluruh operasi basis data menggunakan SQLite. Modul ini menyediakan antarmuka untuk menyimpan dan mengambil data seperti *rule*, *watchlist*, sinyal, dan pengaturan sistem.

Implementasi modul ini direalisasikan dalam bentuk kode program yang berfungsi untuk mengelola koneksi basis data, menjalankan operasi CRUD (*Create*, *Read*, *Update*, *Delete*), dan memastikan integritas data melalui manajemen transaksi. Berikut adalah potongan kode representatif dari modul *Storage*:

```python
import sqlite3
import json
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

class SQLiteRepository:
    """SQLite database repository for all data persistence operations."""
    
    def __init__(self, db_path: str = 'signalgen.db'):
        """Initialize repository with database path."""
        self.db_path = db_path
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def initialize_database(self) -> None:
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
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
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS watchlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
```

Kode di atas menunjukkan implementasi fungsi `initialize_database()` yang membuat tabel-tabel basis data jika belum ada. Tabel `rules` menyimpan aturan *trading* dengan definisi dalam format JSON, tabel `watchlists` menyimpan daftar *watchlist* dengan status aktif. Penggunaan *lock* (`threading.Lock()`) memastikan bahwa operasi basis data aman terhadap kondisi *race condition* dalam lingkungan multi-*thread*. Modul ini juga menggunakan manajer konteks untuk koneksi basis data (`with self._get_connection()`) yang memastikan koneksi selalu ditutup dengan benar setelah operasi selesai, mencegah *resource leak*.

---

Dengan implementasi seluruh modul di atas, sistem *trading signal generator* dapat beroperasi secara terintegrasi, mulai dari antarmuka pengguna hingga pemrosesan data dan penyimpanan hasil. Setiap modul dirancang untuk memiliki tanggung jawab yang jelas dan berkomunikasi dengan modul lain melalui antarmuka yang terdefinisi dengan baik.
