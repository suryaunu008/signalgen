# INFORMASI TEKNIS MODUL NOTIFIKASI - SignalGen

**Tanggal:** 22 Januari 2026  
**Sistem:** SignalGen Trading System  
**Tujuan:** Dokumentasi teknis modul notifikasi untuk keperluan skripsi

---

## 1️⃣ IDENTIFIKASI MODUL NOTIFIKASI

### A. Modul Notifikasi Utama

**File:** `app/notifications/telegram_notifier.py`  
**Class:** `TelegramNotifier`  
**Fungsi:** Mengirim notifikasi sinyal trading melalui Telegram Bot API

**Fitur:**
- Async message delivery via Telegram Bot API
- Rich formatted messages dengan signal details
- Configurable via application settings
- Error handling dan retry logic
- Support untuk multiple chat IDs
- Signal formatting dengan emoji dan markdown

### B. Modul Broadcaster (Komunikasi Real-time)

**File:** `app/ws/broadcaster.py`  
**Class:** `SocketIOBroadcaster`  
**Fungsi:** Mengirim event real-time ke antarmuka pengguna melalui WebSocket (Socket.IO)

**Fitur:**
- Real-time bidirectional communication
- Broadcasting untuk multiple clients
- Room-based broadcasting untuk event types berbeda
- Client connection management
- Event validation dan formatting
- Error handling untuk failed broadcasts
- Comprehensive logging

### C. File Inisialisasi

**File:** `app/notifications/__init__.py`  
**Export:** `TelegramNotifier`

---

## 2️⃣ JENIS INFORMASI YANG DIKIRIM KE PENGGUNA

### A. Event dari WebSocket Broadcaster

| Event | Deskripsi | Data |
|-------|-----------|------|
| `signal` | Sinyal trading (BUY/SELL) | symbol, price, rule_id, timestamp |
| `engine_status` | Status engine | state (running/stopped/error), is_running, ibkr_connected |
| `price_update` | Update harga real-time | symbol, price, timestamp |
| `watchlist_update` | Perubahan watchlist | name, symbols, watchlist data |
| `rule_update` | Perubahan rule trading | name, definition, rule data |
| `rule_activation` | Aktivasi/deaktivasi rule | rule_id, activated (true/false) |
| `ibkr_status` | Status koneksi ke IBKR | connected, connection details |
| `error` | Notifikasi error sistem | type, message, data |
| `connected` | Konfirmasi koneksi WebSocket | sid, available_rooms, timestamp |
| `room_joined` / `room_left` | Konfirmasi join/leave room | room name |

### B. Event dari Telegram Notifier

| Jenis Notifikasi | Deskripsi | Format |
|------------------|-----------|--------|
| **Signal Trading** | Notifikasi lengkap sinyal BUY/SELL | Emoji, Symbol, Type, Price, Time, Rule, Indicators |
| **Engine Status** | Status engine | started (▶️), stopped (⏹️), error (❌), warning (⚠️) |
| **Test Message** | Pesan test verifikasi | Konfirmasi konfigurasi bot |

---

## 3️⃣ MEKANISME PENGIRIMAN NOTIFIKASI

### A. WebSocket (Socket.IO)

#### Fungsi Pengiriman Async

| Fungsi | Tujuan | Room |
|--------|--------|------|
| `broadcast_signal()` | Broadcast sinyal trading | signals |
| `broadcast_engine_status()` | Broadcast status engine | engine_status |
| `broadcast_price_update()` | Broadcast update harga | prices |
| `broadcast_watchlist_update()` | Broadcast update watchlist | watchlists |
| `broadcast_rule_update()` | Broadcast update rule | rules |
| `broadcast_ibkr_status()` | Broadcast status IBKR | ibkr_status |
| `broadcast_error()` | Broadcast error | errors |
| `broadcast_rule_activation()` | Broadcast aktivasi rule | rules |

#### Method Sinkron (Thread-safe)

- `broadcast_engine_status_sync()` - Wrapper sinkron untuk broadcast status engine
- `broadcast_price_update_sync()` - Wrapper sinkron untuk broadcast update harga

#### Mekanisme Teknis

1. **Socket.IO AsyncServer** dengan mode ASGI
2. **Room-based broadcasting** untuk efisiensi
   - signals, engine_status, rules, watchlists, ibkr_status, errors, prices
3. **Thread-safe emission** menggunakan `asyncio.run_coroutine_threadsafe()`
4. **Event loop capture** untuk menghindari race conditions
5. **CORS support** untuk PyWebView frontend

### B. Telegram Bot API

#### Fungsi Pengiriman

| Fungsi | Tujuan | Return |
|--------|--------|--------|
| `send_signal()` | Kirim notifikasi sinyal trading | bool (success/fail) |
| `send_engine_status()` | Kirim notifikasi status engine | bool |
| `send_test_message()` | Kirim pesan test | bool |
| `_send_message()` | Helper untuk mengirim ke chat ID | bool |

#### Mekanisme Teknis

1. **HTTP POST** ke `https://api.telegram.org/bot{token}/sendMessage`
2. **Async HTTP** menggunakan `aiohttp.ClientSession`
3. **Format pesan:** Markdown dengan emoji support
4. **Multiple chat IDs:** Parallel sending dengan `asyncio.gather()`
5. **Timeout:** 10 detik per request
6. **Error handling:** Continue on individual chat failures

#### Konfigurasi

Settings disimpan di database SQLite:
- `telegram_bot_token` - Token dari BotFather
- `telegram_chat_ids` - Comma-separated list chat IDs
- `telegram_enabled` - Enable/disable notifications

---

## 4️⃣ INTEGRASI DENGAN MODUL LAIN

### A. Scalping Engine (`app/engines/scalping_engine.py`)

#### Pemanggilan Notifikasi

**1. Sinyal Trading:**
- **Lokasi:** Method `_generate_signal()` line 838
- **Waktu:** Setelah sinyal terbentuk dan disimpan ke database
- **Call:** `self.broadcaster.broadcast_signal(signal_data)`
- **Mekanisme:** `asyncio.run_coroutine_threadsafe()` untuk thread safety

**2. Status Engine:**
- **Saat Engine Start:** Line 277
  ```python
  self.broadcaster.broadcast_engine_status_sync(status)
  ```
- **Saat Engine Stop:** Line 318
  ```python
  self.broadcaster.broadcast_engine_status_sync(status)
  ```
- **Saat IBKR Disconnect:** Line 230
  ```python
  self.broadcaster.broadcast_engine_status_sync(status)
  ```

**3. Update Harga:**
- **Setiap Bar Update:** Line 398
- **Setiap Ticker Update:** Line 739
- **Call:** `self.broadcaster.broadcast_price_update(symbol, price, timestamp)`

### B. WebSocket Broadcaster Integration

**Inisialisasi Telegram di Broadcaster:**
- **Method:** `initialize()` (line 683-695)
- **Proses:**
  1. Membuat instance `TelegramNotifier(repository)`
  2. Call `telegram_notifier.initialize()` untuk load settings
  3. Set sebagai property `self.telegram_notifier`
- **Pemanggilan:** Saat signal broadcast (line 266)
  ```python
  if self.telegram_notifier:
      await self.telegram_notifier.send_signal(signal_data)
  ```

### C. FastAPI Application (`app/app.py`)

**Setup di Aplikasi:**
- **Line 241:** Membuat instance broadcaster
  ```python
  self.broadcaster = SocketIOBroadcaster(repository=self.repository)
  ```
- **Line 255:** Set reference di scalping engine
  ```python
  self.scalping_engine.broadcaster = self.broadcaster
  ```

### D. Backtesting Engine (`app/engines/backtesting_engine.py`)

**Catatan:** Backtesting engine **TIDAK** menggunakan notifikasi real-time karena:
- Berjalan di historical data simulation
- Tidak memerlukan WebSocket broadcast
- Results dikembalikan sebagai response API

### E. Swing Screening Engine (`app/engines/swing_screening_engine.py`)

**Catatan:** Swing screening engine **TIDAK** menggunakan notifikasi karena:
- On-demand screening, bukan real-time monitoring
- Results dikembalikan langsung via API response

---

## 5️⃣ CONTOH POTONGAN KODE

### A. Pengiriman Sinyal via WebSocket + Telegram

**File:** `app/ws/broadcaster.py` (Line 240-275)

```python
async def broadcast_signal(self, signal_data: Dict[str, Any]) -> None:
    """
    Broadcast signal events to all connected clients and Telegram.
    
    Args:
        signal_data: Signal data with format:
            {
                "symbol": "AAPL",
                "price": 189.20,
                "rule_id": 2,
                "timestamp": "2025-12-16T09:31:00Z"
            }
    """
    try:
        # Validate signal data
        if not self._validate_signal_data(signal_data):
            raise ValueError("Invalid signal data format")
        
        # Format signal event according to PROJECT_MVP.md specification
        signal_event = {
            "event": "signal",
            "symbol": signal_data['symbol'],
            "price": signal_data['price'],
            "rule_id": signal_data['rule_id'],
            "timestamp": signal_data.get('timestamp', datetime.utcnow().isoformat())
        }
        
        # Broadcast to signals room (WebSocket)
        await self.sio.emit('signal', signal_event, room=self.ROOMS['signals'])
        
        # Send to Telegram if configured
        if self.telegram_notifier:
            try:
                await self.telegram_notifier.send_signal(signal_data)
            except Exception as telegram_error:
                self.logger.warning(f"Failed to send Telegram notification: {telegram_error}")
        
        self.logger.info(f"Signal broadcasted: {signal_data.get('symbol')} @ {signal_data.get('price')}")
        
    except Exception as e:
        self.logger.error(f"Error broadcasting signal: {e}")
        await self.broadcast_error({
            'type': 'broadcast_error',
            'message': f'Failed to broadcast signal: {str(e)}',
            'data': signal_data
        })
```

### B. Pemanggilan dari Scalping Engine

**File:** `app/engines/scalping_engine.py` (Line 826-843)

```python
# Store signal in database
signal_id = self.repository.save_signal(signal_data)

# Add signal ID to data for broadcasting
signal_data['id'] = signal_id

# Broadcast signal via WebSocket
if self.event_loop and self.broadcaster:
    try:
        asyncio.run_coroutine_threadsafe(
            self.broadcaster.broadcast_signal(signal_data),
            self.event_loop
        )
    except Exception as e:
        self.logger.error(f"Failed to schedule signal broadcast: {e}")

# Start cooldown period for this symbol
cooldown_sec = self.active_rule.get('cooldown_sec', 60)
self._start_symbol_cooldown(symbol, cooldown_sec)

self.logger.info(f"Signal generated for {symbol} at {price} (ID: {signal_id}), cooldown: {cooldown_sec}s")
```

### C. Format Pesan Telegram

**File:** `app/notifications/telegram_notifier.py` (Line 151-213)

```python
def _format_signal_message(self, signal_data: Dict[str, Any]) -> str:
    """
    Format signal data into a readable Telegram message.
    
    Args:
        signal_data: Signal data dictionary
        
    Returns:
        str: Formatted message with markdown
    """
    try:
        symbol = signal_data.get('symbol', 'UNKNOWN')
        signal_type = signal_data.get('signal_type', signal_data.get('type', 'UNKNOWN'))
        timestamp = signal_data.get('timestamp', datetime.now().isoformat())
        
        # Get rule info from repository if rule_id is available
        rule_name = signal_data.get('rule_name', 'N/A')
        rule_id = signal_data.get('rule_id')
        if rule_id and self.repository:
            try:
                rule = self.repository.get_rule(rule_id)
                if rule:
                    rule_name = rule.get('name', 'N/A')
            except:
                pass
        
        # Get indicator values
        indicators = signal_data.get('indicators', signal_data.get('indicator_values', {}))
        price = signal_data.get('price', indicators.get('PRICE', indicators.get('close', 'N/A')))
        
        # Signal emoji
        emoji = "🚀" if signal_type.upper() == "BUY" else "🔻" if signal_type.upper() == "SELL" else "⚠️"
        
        # Build message
        message_lines = [
            f"{emoji} *SIGNAL TRADING ALERT*",
            "",
            f"*Symbol:* `{symbol}`",
            f"*Type:* *{signal_type.upper()}*",
            f"*Price:* {self._format_price(price)}",
            f"*Time:* {self._format_timestamp(timestamp)}",
            f"*Rule:* {rule_name}",
        ]
        
        # Add ALL indicators if available
        if indicators:
            message_lines.append("")
            message_lines.append("*📊 Indicators:*")
            
            # Sort indicators alphabetically for consistent display
            sorted_indicators = sorted(indicators.items())
            
            for key, value in sorted_indicators:
                if value is not None:
                    # Format value based on type
                    if isinstance(value, (int, float)):
                        formatted_value = f"{float(value):.4f}"
                    else:
                        formatted_value = str(value)
                    
                    # Format display name (convert snake_case to readable format)
                    display_name = key.replace('_', ' ').upper()
                    message_lines.append(f"  • {display_name}: `{formatted_value}`")
        
        # Add footer
        message_lines.append("")
        message_lines.append("_SignalGen Trading System_")
        
        return "\n".join(message_lines)
        
    except Exception as e:
        self.logger.error(f"Error formatting signal message: {e}")
        return f"⚠️ Signal Alert: {signal_data.get('symbol', 'UNKNOWN')} - {signal_data.get('signal_type', signal_data.get('type', 'UNKNOWN'))}"
```

### D. Thread-safe Broadcast dari Non-async Context

**File:** `app/ws/broadcaster.py` (Line 401-445)

```python
def broadcast_engine_status_sync(self, status: Dict[str, Any]) -> None:
    """
    Thread-safe synchronous version of broadcast_engine_status.
    Can be called from any thread.
    
    Args:
        status: Engine status data
    """
    try:
        self.logger.info(f"broadcast_engine_status_sync called with: {status.get('is_running', 'N/A')}")
        
        # Use threading to call emit in a thread-safe way
        import threading
        def do_emit():
            try:
                # Get the Socket.IO async server's loop
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            self._emit_engine_status(status),
                            loop
                        )
                        self.logger.info("Scheduled emit in running loop")
                    else:
                        # Create a new loop and run the coroutine
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self._emit_engine_status(status))
                        loop.close()
                        self.logger.info("Emitted in new loop")
                except RuntimeError:
                    # No event loop in current thread, create one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self._emit_engine_status(status))
                    loop.close()
                    self.logger.info("Emitted in new loop (no existing loop)")
            except Exception as e:
                self.logger.error(f"Error emitting in thread: {e}", exc_info=True)
        
        threading.Thread(target=do_emit, daemon=True).start()
        
    except Exception as e:
        self.logger.error(f"Error in sync broadcast: {e}", exc_info=True)
```

---

## 6️⃣ BATASAN IMPLEMENTASI

### A. Notifikasi Bersifat INFORMATIF

✅ **Modul notifikasi TIDAK memengaruhi logika pembentukan sinyal**

**Bukti dari Kode:**

File: `app/engines/scalping_engine.py` (Line 826-843)

```python
# Store signal in database (LOGIC UTAMA)
signal_id = self.repository.save_signal(signal_data)

# Add signal ID to data for broadcasting
signal_data['id'] = signal_id

# Broadcast signal via WebSocket (NOTIFIKASI - tidak blocking)
if self.event_loop and self.broadcaster:
    try:
        asyncio.run_coroutine_threadsafe(
            self.broadcaster.broadcast_signal(signal_data),
            self.event_loop
        )
    except Exception as e:
        self.logger.error(f"Failed to schedule signal broadcast: {e}")
        # Signal tetap tersimpan, hanya broadcast yang gagal
```

**Kesimpulan:**
1. Signal **SUDAH disimpan ke database** sebelum broadcast
2. Error pada broadcast **TIDAK menghentikan** proses signal generation
3. Menggunakan try-except untuk **isolasi error**

### B. Decoupling dari Logika Bisnis

✅ **Broadcaster dan Telegram Notifier terpisah dari Rule Engine/Indicator Engine**

**Struktur Dependency:**

```
Rule Engine + Indicator Engine
        ↓
    Signal Data
        ↓
    Repository (save)
        ↓
    Broadcaster ← Telegram Notifier
        ↓
    WebSocket + Telegram
```

**Karakteristik:**
- Rule Engine tidak mengetahui keberadaan broadcaster
- Indicator Engine tidak mengetahui keberadaan notifikasi
- Scalping Engine yang melakukan orchestration
- Notifikasi adalah layer terakhir, tidak mempengaruhi core logic

### C. Async dan Non-blocking

✅ **WebSocket broadcast tidak blocking event loop engine**

**Mekanisme:**

1. **Thread-safe Coroutine Scheduling:**
   ```python
   asyncio.run_coroutine_threadsafe(
       self.broadcaster.broadcast_signal(signal_data),
       self.event_loop
   )
   ```

2. **Parallel Telegram Sending:**
   ```python
   tasks = [
       self._send_message(chat_id, message) 
       for chat_id in self.chat_ids
   ]
   results = await asyncio.gather(*tasks, return_exceptions=True)
   ```

3. **Error Handling:**
   - Continue on individual chat failures
   - Tidak menunggu response dari Telegram
   - Timeout 10 detik per request

### D. Limitasi Telegram

**Konfigurasi:**
- Maximum retry: Tidak ada automatic retry (fire-and-forget)
- Timeout: 10 detik per chat
- Multiple chats: Parallel sending, minimal 1 success untuk return True

**Error Scenarios:**
1. Bot token invalid → Notifikasi disabled
2. Chat ID tidak valid → Log warning, continue ke chat lain
3. Network timeout → Log error, return False
4. Telegram API down → Log error, WebSocket tetap berfungsi

---

## 7️⃣ DAFTAR FILE DAN FUNGSI TERKAIT

### Tabel Komprehensif

| **File** | **Class/Function** | **Line** | **Fungsi** |
|----------|-------------------|----------|------------|
| `app/ws/broadcaster.py` | `SocketIOBroadcaster` | 1-706 | Broadcaster utama WebSocket |
| `app/ws/broadcaster.py` | `broadcast_signal()` | 237-275 | Broadcast sinyal trading |
| `app/ws/broadcaster.py` | `broadcast_engine_status()` | 385-400 | Broadcast status engine (async) |
| `app/ws/broadcaster.py` | `broadcast_engine_status_sync()` | 401-445 | Broadcast status engine (sync) |
| `app/ws/broadcaster.py` | `broadcast_price_update()` | 281-310 | Broadcast update harga |
| `app/ws/broadcaster.py` | `broadcast_price_update_sync()` | 313-383 | Broadcast update harga (sync) |
| `app/ws/broadcaster.py` | `broadcast_watchlist_update()` | 447-471 | Broadcast update watchlist |
| `app/ws/broadcaster.py` | `broadcast_rule_update()` | 473-497 | Broadcast update rule |
| `app/ws/broadcaster.py` | `broadcast_ibkr_status()` | 499-523 | Broadcast status IBKR |
| `app/ws/broadcaster.py` | `broadcast_error()` | 525-548 | Broadcast error |
| `app/ws/broadcaster.py` | `broadcast_rule_activation()` | 683-706 | Broadcast aktivasi rule |
| `app/ws/broadcaster.py` | `initialize()` | 660-681 | Inisialisasi broadcaster + Telegram |
| `app/ws/broadcaster.py` | `_validate_signal_data()` | 570-603 | Validasi data sinyal |
| `app/notifications/telegram_notifier.py` | `TelegramNotifier` | 1-358 | Notifier Telegram |
| `app/notifications/telegram_notifier.py` | `initialize()` | 54-99 | Load settings dari database |
| `app/notifications/telegram_notifier.py` | `send_signal()` | 109-148 | Kirim notifikasi sinyal |
| `app/notifications/telegram_notifier.py` | `_format_signal_message()` | 151-213 | Format pesan sinyal |
| `app/notifications/telegram_notifier.py` | `_send_message()` | 249-288 | Kirim message ke chat ID |
| `app/notifications/telegram_notifier.py` | `send_test_message()` | 290-318 | Kirim test message |
| `app/notifications/telegram_notifier.py` | `send_engine_status()` | 320-358 | Kirim status engine |
| `app/engines/scalping_engine.py` | `_generate_signal()` | 774-846 | Generate signal + broadcast |
| `app/engines/scalping_engine.py` | `start_engine()` | 241-281 | Start engine + broadcast status |
| `app/engines/scalping_engine.py` | `stop_engine()` | 283-321 | Stop engine + broadcast status |
| `app/engines/scalping_engine.py` | `_on_disconnected()` | 214-232 | Handle disconnect + broadcast |
| `app/engines/scalping_engine.py` | `_on_bar_update()` | 370-405 | Handle bar + broadcast price |
| `app/engines/scalping_engine.py` | `_on_ticker_update()` | 848-902 | Handle ticker + broadcast price |
| `app/app.py` | `SignalGenApp.__init__()` | 235-260 | Setup broadcaster di aplikasi |
| `app/app.py` | `TelegramSettings` | 179-183 | Model settings Telegram |
| `app/notifications/__init__.py` | - | 1-11 | Export TelegramNotifier |

---

## 8️⃣ DIAGRAM ALUR NOTIFIKASI

### A. Alur Sinyal Trading

```
┌─────────────────────────────────────────────────────────────┐
│  IBKR Bar Update / Ticker Update                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Indicator Engine: Calculate Indicators                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Rule Engine: Evaluate Conditions                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
                ┌────────┐
                │ Signal? │
                └───┬────┘
                    │ YES
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Repository: Save Signal to Database                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Broadcaster: broadcast_signal()                            │
└─────────┬───────────────────────────────────────┬───────────┘
          │                                       │
          ▼                                       ▼
┌──────────────────────────┐        ┌─────────────────────────┐
│  WebSocket (Socket.IO)   │        │  Telegram Notifier      │
│  - Emit to 'signals'     │        │  - send_signal()        │
│    room                  │        │  - Format message       │
│  - All connected clients │        │  - Send to all chats    │
└──────────┬───────────────┘        └───────────┬─────────────┘
           │                                    │
           ▼                                    ▼
┌──────────────────────────┐        ┌─────────────────────────┐
│  Web UI (Frontend)       │        │  Telegram User's Device │
│  - Display signal alert  │        │  - Push notification    │
└──────────────────────────┘        └─────────────────────────┘
```

### B. Alur Status Engine

```
┌─────────────────────────────────────────────────────────────┐
│  Scalping Engine Event                                      │
│  - start_engine()                                           │
│  - stop_engine()                                            │
│  - IBKR disconnect                                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Broadcaster: broadcast_engine_status_sync()                │
│  (Thread-safe wrapper)                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Create new thread + event loop                             │
│  asyncio.run_coroutine_threadsafe()                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  WebSocket Emit                                             │
│  sio.emit('engine_status', status, room='engine_status')    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Web UI (Frontend)                                          │
│  - Update engine status display                             │
│  - Show start/stop button state                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 9️⃣ KESIMPULAN

### Ringkasan Karakteristik Modul Notifikasi

1. **Dual-channel Notification System:**
   - WebSocket (Socket.IO) untuk real-time UI updates
   - Telegram Bot untuk external notifications

2. **Event-driven Architecture:**
   - 10+ jenis event di-broadcast via WebSocket
   - 3 jenis notification via Telegram

3. **Decoupled Design:**
   - Tidak mempengaruhi logika trading
   - Error pada notifikasi tidak menghentikan signal generation
   - Terpisah dari Rule Engine dan Indicator Engine

4. **Thread-safe Implementation:**
   - Async/await untuk I/O operations
   - `asyncio.run_coroutine_threadsafe()` untuk thread safety
   - Parallel sending untuk multiple Telegram chats

5. **Reliability Features:**
   - Error handling dan logging komprehensif
   - Continue on partial failures
   - Validation sebelum broadcast

6. **Configurability:**
   - Telegram dapat di-enable/disable via settings
   - Support multiple chat IDs
   - Customizable message format

### Batasan yang Jelas

✅ Notifikasi **HANYA bersifat informatif**  
✅ **TIDAK memengaruhi** logika pembentukan sinyal  
✅ **TIDAK blocking** proses core trading  
✅ Error pada notifikasi **TIDAK fatal** untuk sistem  

---

**Dokumentasi ini dibuat berdasarkan analisis kode aktual dari repository SignalGen tanpa asumsi atau penambahan fitur yang tidak ada.**
