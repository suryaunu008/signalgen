
---

# 🛠️ RESOLUTION PLAN — FastAPI + PyWebView Infinite Loading

## 🎯 OBJECTIVE

* WebView load **tanpa infinite loading**
* API FastAPI **responsif**
* Add watchlist **langsung berhasil**
* UI bisa fetch & render data

---

## PHASE 0 — Safety & Context Lock (WAJIB)

**Tujuan:** pastikan agent nggak ngerusak scope MVP.

**Rules untuk agent:**

* ❌ Jangan refactor besar
* ❌ Jangan ubah arsitektur
* ❌ Jangan async-ify semua code
* ✅ Fokus ke orchestration & blocking issue

---

## PHASE 1 — Verify FastAPI Actually Running (Critical)

### Task 1.1 — Isolate backend

Agent harus:

1. **Jalankan FastAPI TANPA PyWebView**

   ```bash
   uvicorn app.main:app --reload
   ```

2. Akses:

   ```
   http://127.0.0.1:8000/docs
   ```

### Expected result

* Swagger UI muncul
* Endpoint bisa dipanggil

### If FAIL

👉 Bug **di FastAPI sendiri**, STOP PyWebView debugging.

---

## PHASE 2 — Fix Process Orchestration (Root Cause)

### Task 2.1 — Ensure FastAPI runs in background thread

Agent harus memastikan `main.py`:

**WAJIB pakai pattern ini**

```python
def start_api():
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )

threading.Thread(
    target=start_api,
    daemon=True
).start()
```

### Task 2.2 — Delay WebView startup

Tambahkan delay **1–2 detik** sebelum WebView load:

```python
time.sleep(1.5)
```

📌 Ini penting biar UI nggak load sebelum API siap.

---

## PHASE 3 — PyWebView Debug Visibility

### Task 3.1 — Enable debug mode

```python
webview.create_window(
    "SignalGen",
    "http://127.0.0.1:8000",
    debug=True
)
```

### Task 3.2 — Open DevTools

Agent harus:

* buka DevTools
* catat error JS pertama

### Expected errors (umum):

* `ERR_CONNECTION_REFUSED`
* `fetch failed`
* `404 endpoint`

---

## PHASE 4 — Endpoint Path Validation (Common Bug)

### Task 4.1 — Audit all fetch() calls

Agent cek semua frontend JS:

```js
fetch("/watchlists")
```

Bandingkan dengan router:

```python
app.include_router(watchlist_router, prefix="/watchlists")
```

### Fix rule:

* **Absolute path**
* **No assumption proxy**

Jika perlu:

```js
fetch("http://127.0.0.1:8000/watchlists")
```

---

## PHASE 5 — Async Trap Elimination (Very Common)

### Task 5.1 — Identify async routes with blocking code

Cari:

```python
@router.post(...)
async def ...
```

Yang di dalamnya:

* sqlite3
* file IO
* heavy logic

### Task 5.2 — Convert to sync temporarily

```python
@router.post(...)
def ...
```

📌 Untuk MVP: **sync > async**

---

## PHASE 6 — CORS & Preflight Safety

### Task 6.1 — Add CORSMiddleware

Agent pastikan ini ada di `app.main`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Walau local, ini sering silent-fail.

---

## PHASE 7 — Watchlist Endpoint Deep Test

### Task 7.1 — Test via Swagger

* POST `/watchlists`
* Payload minimal

### Task 7.2 — Add logging

```python
print("WATCHLIST CREATE HIT")
```

### Expected:

* log muncul
* response < 100ms

Jika Swagger loading → DB blocking.

---

## PHASE 8 — Final Validation Checklist

Agent baru boleh bilang “DONE” kalau:

* [ ] `/docs` load < 2 detik
* [ ] WebView load tanpa spinner
* [ ] Add watchlist sukses
* [ ] Tidak ada JS error di DevTools
* [ ] Tidak ada infinite request di Network tab

---

## 📌 DELIVERABLE DARI AGENT

Agent harus submit:

1. File yang diubah (biasanya `main.py`)
2. Screenshot DevTools (optional)
3. Root cause summary (1–2 kalimat)

---

## 🧠 MOST LIKELY ROOT CAUSE (FYI)

Dari pengalaman + gejala kamu:

> **FastAPI belum ready tapi WebView sudah load**, atau
> **async route + sqlite blocking event loop**

90% kasus di sini.

---

