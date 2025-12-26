
---

# 🧠 TUJUAN SISTEM

Desktop app lokal untuk **realtime scalping signal generator** dengan:

* rule bisa dikustomisasi user
* data realtime dari **IBKR**
* output signal via **WebSocket** (untuk sistem eksekusi terpisah)
* UI ringan (PyWebView + Tailwind)
* tanpa DB server (SQLite)

---

# 🧱 HIGH-LEVEL ARCHITECTURE

```
┌──────────────────────────────┐
│        PyWebView UI          │
│   (Tailwind + JS + WS)       │
└───────────────┬──────────────┘
                │ REST / WS
                ▼
┌──────────────────────────────┐
│       App Controller         │
│     (Flask / FastAPI)        │
│  - REST API                  │
│  - WebSocket Server          │
│  - Engine Orchestrator       │
└───────────────┬──────────────┘
                │
        ┌───────┴────────┐
        │                │
        ▼                ▼
┌──────────────┐  ┌─────────────────┐
│ Rule Engine  │  │ Scalping Engine │
│ (determin.) │  │  (ib_insync)    │
└───────┬──────┘  └───────┬─────────┘
        │                │
        └───────┬────────┘
                ▼
          SQLite Storage
```

---

# 🧩 KOMPONEN INTI

## 1️⃣ UI LAYER (PyWebView + Tailwind)

### Modul UI:

* **Rule Builder**
* **Rule List**
* **Watchlist Manager**
* **Scalping Control Panel**
* **Live Signal Panel**
* **Engine Status Indicator**

UI **TIDAK**:

* hitung indikator
* akses IBKR langsung
* generate signal

UI hanya:

* kirim config
* terima signal via WS

---

## 2️⃣ RULE SYSTEM (CORE DESIGN)

### Rule sebagai CONFIG (bukan code)

Contoh rule user:

```
PRICE > MA5 AND MA5 > MA10
```

### Representasi internal (JSON)

```json
{
  "id": 2,
  "name": "MA Momentum",
  "type": "custom",
  "logic": "AND",
  "conditions": [
    { "left": "PRICE", "op": ">", "right": "MA5" },
    { "left": "MA5", "op": ">", "right": "MA10" }
  ],
  "cooldown_sec": 60
}
```

### Supported operands (MVP):

* PRICE
* MA5
* MA10
* MA20

### Supported operator:

* `>`
* `<`
* `>=`
* `<=`

➡️ **NO eval**, **NO script**, **NO dynamic code**

---

## 3️⃣ DEFAULT RULE (TIDAK BISA DIHAPUS)

### Tujuan:

* contoh buat user
* fallback
* validasi UI

### Karakteristik:

* `is_system = true`
* readonly di UI
* bisa di-*clone*

Contoh default rule:

```
PRICE > MA5 AND MA5 > MA10
```

### Storage:

* di-seed saat app pertama jalan
* disimpan di SQLite
* UI disable delete/edit

---

## 4️⃣ RULE ENGINE (DETERMINISTIC)

### Tugas:

* menerima snapshot indikator
* evaluasi rule
* return TRUE / FALSE
* stateless (state di engine)

### Flow:

```python
if rule_engine.evaluate(rule, indicators):
    emit_signal()
```

### Contoh evaluator:

```python
def eval_condition(cond, values):
    return OPERATORS[cond.op](
        values[cond.left],
        values[cond.right]
    )
```

➡️ Rule engine **dipakai oleh**:

* scalping engine
* (future) backtester

---

## 5️⃣ SCALPING ENGINE (IBKR – ib_insync)

### Data Source:

* IBKR TWS / Gateway
* realtime bars (1m / 5s)

### Karakteristik:

* async, event-driven
* single event loop
* isolate dari UI thread

### Flow realtime:

```
IBKR Bar Update
   ↓
Indicator Engine
   ↓
Rule Engine
   ↓
Signal Generator
   ↓
WebSocket Emit
```

### State Machine (anti noise):

```
WAIT → SIGNAL → COOLDOWN
```

---

## 6️⃣ WATCHLIST SYSTEM

### Fungsi:

* menentukan symbol yang di-subscribe ke IBKR
* dibatasi untuk menjaga stabilitas

### Aturan keras (MVP):

* **MAX 5 ticker per run**
* satu watchlist aktif
* tidak bisa diubah saat engine running

Alasan:

* limit IBKR market data
* latency
* kestabilan

### Storage:

```sql
watchlists
watchlist_items
```

---

## 7️⃣ WEBSOCKET LAYER (INTEGRATION-READY)

### Tujuan:

* realtime UI update
* integrasi ke **external execution system**

### Event yang dipublish:

```json
{
  "event": "signal",
  "symbol": "AAPL",
  "price": 189.20,
  "rule_id": 2,
  "timestamp": "2025-12-16T09:31:00Z"
}
```

### Karakteristik:

* broadcast
* stateless
* bisa dikonsumsi:

  * UI
  * trading executor (beda sistem)

➡️ Ini **design decision yang sangat bagus**.

---

## 8️⃣ STORAGE (SQLite – FILE BASED)

### Tables inti:

```
rules
watchlists
signals
settings
```

### Rules table:

```sql
rules (
  id INTEGER PK,
  name TEXT,
  type TEXT,        -- system | custom
  definition JSON,
  is_system BOOLEAN
)
```

### Signals table:

```sql
signals (
  id INTEGER,
  time TEXT,
  symbol TEXT,
  price REAL,
  rule_id INTEGER
)
```

---

## 9️⃣ APP CONTROLLER (ORCHESTRATOR)

### Tugas:

* start / stop scalping engine
* load active rule
* lock rule & watchlist saat running
* expose REST + WS
* handle error & reconnect IBKR

➡️ Ini **otak sistem**, bukan UI.

---

## 10️⃣ FOLDER STRUCTURE (FINAL & REALISTIS)

```
app/
 ├─ ui/
 │   ├─ templates/
 │   └─ static/
 ├─ core/
 │   ├─ rule_engine.py
 │   ├─ indicator_engine.py
 │   └─ state_machine.py
 ├─ engines/
 │   └─ scalping_engine.py
 ├─ storage/
 │   └─ sqlite_repo.py
 ├─ ws/
 │   └─ broadcaster.py
 ├─ app.py
 └─ main.py
```

---

# 🚧 BATASAN SENGAJA (MVP)

❌ Multi-rule aktif
❌ Multi-timeframe
❌ Auto execution
❌ Risk management kompleks
❌ Backtest

Ini **disengaja** supaya **1 minggu feasible**.

---

# ✅ BOTTOM LINE (TEGAS)

Arsitektur ini:

* **BISA DIBANGUN**
* **CLEAN**
* **EXTENSIBLE**
* **READY FOR EXECUTION SYSTEM**
* **NGGAK OVERENGINEER**
