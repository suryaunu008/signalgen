# BAB 3.11.1 PENGUJIAN FUNGSIONAL SISTEM

Pengujian fungsional sistem dilakukan dengan metode **Black Box Testing** untuk memverifikasi bahwa setiap fungsi sistem menghasilkan output yang sesuai dengan input yang diberikan, tanpa mempertimbangkan logika internal (kode) sistem. Skenario di bawah ini disusun langsung berdasarkan elemen antarmuka (`app/ui/templates/index.html`), perilaku JavaScript (`app/ui/static/js/*.js`), dan kontrak REST API (`app/app.py`) yang benar-benar ada pada aplikasi SignalGen — bukan asumsi.

Aplikasi dijalankan sebagai desktop window (PyWebView) yang memuat `http://127.0.0.1:3456` (FastAPI, port default) dan berkomunikasi real-time melalui Socket.IO pada `ws://127.0.0.1:8765`. Jika PyWebView gagal start (mis. WebView2 Runtime tidak terpasang), sistem otomatis membuka URL yang sama di browser default (fallback).

Antarmuka terdiri dari 6 menu pada sidebar/tab: **Realtime Signal**, **Screener**, **Data**, **Backtesting**, **Rules**, **Settings**. Pemetaan pengujian terhadap rumusan masalah (RM):

- **RM1** — Sistem menghasilkan sinyal beli/jual saham AS berbasis indikator teknikal.
- **RM2** — Kombinasi indikator teknikal untuk strategi scalping dan swing trading.
- **RM3** — Mekanisme distribusi sinyal agar terintegrasi dengan platform lain.
- **RM4** — Evaluasi performa sinyal melalui backtesting pada data historis.

## Tabel 3.1 Rancangan Pengujian Fungsional Modul Startup & Navigasi Antarmuka

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-01 | Menjalankan aplikasi | Menjalankan `python -m app.main` | Perintah dijalankan pada terminal dari root project | Database `signalgen.db` diinisialisasi, FastAPI berjalan di `127.0.0.1:3456`, Socket.IO di `127.0.0.1:8765`, dan window PyWebView berjudul "SignalGen" terbuka menampilkan halaman utama |
| P-02 | Fallback ke browser | Menjalankan aplikasi pada environment tanpa WebView2 Runtime | PyWebView gagal start (`webview.start()` melempar exception) | Sistem mencatat log error dan otomatis membuka URL `http://127.0.0.1:3456` pada browser default |
| P-03 | Tampilan halaman utama | Mengakses window/browser setelah aplikasi start | Window terbuka pertama kali | Sidebar menampilkan 6 menu: Realtime Signal, Screener, Data, Backtesting, Rules, Settings, dengan tab "Realtime Signal" aktif secara default |
| P-04 | Navigasi antar tab | Berpindah menu melalui sidebar | Pengguna mengklik tab "Screener", lalu "Data", "Backtesting", "Rules", "Settings" secara berurutan | Konten `tab-content-*` yang sesuai ditampilkan dan tab sebelumnya disembunyikan, tanpa reload halaman |
| P-05 | Membuka panduan Help | Membuka modal bantuan | Pengguna mengklik tombol "Help" pada header | Modal `view-help-modal` terbuka menampilkan deskripsi menu, dengan pilihan bahasa English/Indonesia |

## Tabel 3.2 Rancangan Pengujian Fungsional Modul Watchlist Management (Realtime Signal)

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-06 | Membuat watchlist baru | Mengisi form "Create New Watchlist" | Nama `Tech Giants`, menambahkan simbol `AAPL`, `MSFT` melalui tombol tambah (+), lalu klik "Create Watchlist" | Toast "Watchlist created successfully" muncul, watchlist baru tampil pada daftar `watchlists-container` dengan label "2 symbols" |
| P-07 | Membuat watchlist tanpa nama | Submit form tanpa mengisi nama | Kolom simbol diisi `AAPL` tetapi kolom nama dikosongkan, lalu submit | Toast error "Please enter a watchlist name" muncul, request tidak dikirim ke API |
| P-08 | Membuat watchlist tanpa simbol | Submit form tanpa menambah simbol apa pun | Nama diisi `Empty List`, tidak ada simbol ditambahkan, lalu submit | Toast error "Please add at least one symbol" muncul |
| P-09 | Menambahkan simbol duplikat | Menambahkan simbol yang sama dua kali pada form | Simbol `AAPL` ditambahkan, lalu `AAPL` ditambahkan lagi sebelum submit | Toast error "Symbol already added" muncul, simbol tidak digandakan pada `symbols-list` |
| P-10 | Menghapus watchlist | Menghapus watchlist dari daftar | Pengguna mengklik tombol "Delete" pada salah satu watchlist | Muncul dialog konfirmasi browser; setelah dikonfirmasi, toast "Watchlist deleted successfully" muncul dan item hilang dari daftar |
| P-11 | Menghapus watchlist saat engine berjalan | Mencoba menghapus watchlist ketika engine sinyal aktif | Engine dalam status running, pengguna mengklik "Delete" pada watchlist manapun | API mengembalikan HTTP 409 "Cannot delete watchlist while engine is running"; toast error ditampilkan dan watchlist tidak terhapus |
| P-12 | Watchlist kosong | Menampilkan state ketika belum ada watchlist | Basis data belum memiliki watchlist selain default seed | Panel menampilkan "No watchlists found" pada `watchlists-container` |

## Tabel 3.3 Rancangan Pengujian Fungsional Modul Rule Builder (Rules) — mendukung RM1 & RM2

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-13 | Membuat rule dengan 1 kondisi | Mengisi Rule Builder dengan kondisi indikator tunggal | Nama `RSI Oversold`, Signal Type `BUY`, kondisi `RSI14 < 30`, cooldown `60`, lalu "Save Rule" | Toast "Rule created successfully" muncul, rule baru tampil di daftar "Rules" dengan keterangan "AND - 1 conditions" dan "Cooldown: 60s" |
| P-14 | Membuat rule kombinasi multi-indikator (scalping) | Menambahkan lebih dari satu kondisi dengan "Add Condition" | Kondisi 1: `EMA9 CROSS_UP EMA21`; Kondisi 2: `RSI14 > 50`; Kondisi 3: `MACD_HIST > 0`, Signal Type `BUY`, cooldown `30` detik | Rule tersimpan dengan `logic: AND` dan 3 kondisi; Rule Preview menampilkan `BUY WHEN EMA9 CROSS_UP EMA21 AND RSI14 > 50 AND MACD_HIST > 0` sebelum disimpan |
| P-15 | Membuat rule kombinasi indikator swing | Menyusun kondisi berbasis timeframe panjang (untuk dipakai di Screener) | Kondisi: `ICHIMOKU_CONVERSION CROSS_UP ICHIMOKU_BASE` dan `ADX5 > 25`, Signal Type `BUY` | Rule tersimpan dan dapat dipilih pada dropdown "Rule" di tab Screener maupun Backtesting |
| P-16 | Rule tanpa nama | Submit form tanpa mengisi nama rule | Kondisi diisi lengkap, kolom "Rule Name" dikosongkan, lalu submit | Toast error "Please enter a rule name" muncul |
| P-17 | Rule tanpa kondisi valid | Menghapus seluruh baris kondisi lalu submit | Seluruh `condition-row` dihapus menggunakan tombol trash, lalu submit | Toast error "Please add at least one valid condition" muncul |
| P-18 | Operator CROSS_UP/CROSS_DOWN pada operand tidak valid | Memilih operator cross dengan operand angka statis | Kondisi `PRICE CROSS_UP 150` (Right = Custom Number) | Toast validasi error `Condition 1 right side: CROSS_UP requires an indicator with previous values`, rule tidak tersimpan |
| P-19 | Custom numeric operand tidak valid | Mengisi nilai custom bukan angka | Left = "Custom Number...", nilai diisi `abc` | Toast validasi error memuat `Invalid number`, rule tidak tersimpan |
| P-20 | Melihat detail rule | Membuka detail salah satu rule | Pengguna mengklik "View Details" pada rule tertentu | Modal "Rule Details" terbuka menampilkan nama, tipe, logic, daftar kondisi, cooldown, tanggal dibuat/diubah |
| P-21 | Menghapus rule custom | Menghapus rule buatan pengguna | Pengguna mengklik "Delete" pada rule non-system | Toast "Rule deleted successfully" muncul, rule hilang dari daftar |
| P-22 | Melindungi rule sistem dari penghapusan | Memastikan rule default (`is_system=true`) tidak bisa dihapus dari UI | Rule sistem (mis. "Default Scalping") ditampilkan pada daftar | Tombol "Delete" tidak dirender untuk rule sistem (hanya "View Details" yang tersedia) |

## Tabel 3.4 Rancangan Pengujian Fungsional Modul Realtime Signal Engine — RM1 & RM2

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-23 | Start engine tanpa watchlist/rule | Mengklik "Start Engine" tanpa memilih dropdown | Dropdown "Active Watchlist" dan/atau "Active Rule" masih kosong, lalu klik "Start Engine" | Toast error "Please select both a watchlist and a rule" muncul, engine tidak start |
| P-24 | Start engine dengan konfigurasi valid | Memilih watchlist & rule lalu start | Watchlist `Default Watchlist`, Rule `RSI Oversold` dipilih, timeframe `5m`, klik "Start Engine" | Toast "Engine started successfully" muncul; indikator "Signal Engine" berubah hijau ("Engine: Running"); tombol "Start Engine" nonaktif dan "Stop Engine" aktif |
| P-25 | Start engine dua kali | Mengklik "Start Engine" saat engine sudah berjalan | Engine sudah running, request start dikirim ulang (mis. lewat API langsung) | API mengembalikan HTTP 409 "Engine is already running" |
| P-26 | Stop engine | Menghentikan engine yang berjalan | Pengguna mengklik "Stop Engine" | Toast "Engine stopped successfully" muncul; status berubah menjadi "Engine: Stopped", "IBKR: Disconnected" |
| P-27 | Ganti timeframe saat engine berjalan | Mengubah dropdown "Timeframe" ketika engine aktif | Engine running, pengguna memilih timeframe `1h` pada dropdown | Toast warning "Cannot change timeframe while engine is running. Stop the engine first." muncul, dropdown kembali ke nilai semula |
| P-28 | Ganti timeframe saat engine berhenti | Mengubah timeframe ketika engine idle | Engine stopped, pengguna memilih timeframe `15m` | Toast "Timeframe changed to 15m. Historical data will be re-aggregated when engine starts." muncul |
| P-29 | Update harga real-time | Memverifikasi tabel harga saat engine aktif | Engine running dengan watchlist berisi `AAPL, MSFT, GOOGL` | Tabel `price-table-container` menampilkan harga live tiap simbol yang diperbarui otomatis melalui Socket.IO tanpa refresh |
| P-30 | Sinyal baru muncul di panel Live Signals | Menunggu rule terpenuhi saat engine aktif | Kondisi rule aktif terpenuhi pada salah satu simbol watchlist | Item sinyal baru muncul di atas daftar `signals-container` beserta toast "New signal: {symbol} at {price}"; placeholder "No signals received yet" hilang |
| P-31 | Melihat detail sinyal | Membuka detail salah satu sinyal pada panel Live Signals | Pengguna mengklik ikon info pada salah satu sinyal | Modal "Signal Details" terbuka menampilkan symbol, price, date, time, nama rule, logic, kondisi, dan cooldown yang memicu sinyal |
| P-32 | Menghapus sinyal | Menghapus entry sinyal dari daftar & database | Pengguna mengklik ikon trash pada sinyal tertentu dan mengonfirmasi dialog | Toast "Signal deleted successfully" muncul, entry hilang dari `signals-container` dan dari tabel `signals` di database |
| P-33 | Status koneksi IBKR gagal | Memverifikasi status ketika TWS/Gateway tidak aktif | Engine start tanpa TWS/IB Gateway berjalan pada host/port yang dikonfigurasi | Panel "Broker Gateway" tetap menampilkan "IBKR: Disconnected"; engine tetap mencoba reconnect sesuai backoff tanpa membuat aplikasi crash |

## Tabel 3.5 Rancangan Pengujian Fungsional Modul Distribusi Sinyal — RM3

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-34 | Koneksi Socket.IO ke antarmuka | Memuat tab Realtime Signal | Halaman dimuat dan mencoba connect ke `ws://127.0.0.1:8765` | Indikator "Realtime Feed" berubah menjadi hijau/"Connected" pada panel Connections |
| P-35 | Distribusi sinyal real-time ke UI | Memverifikasi sinyal tersiar tanpa reload | Sinyal baru dihasilkan oleh engine | Sinyal diterima browser melalui event Socket.IO room `signals` dan langsung tampil di panel Live Signals tanpa refresh halaman |
| P-36 | Konfigurasi Telegram belum lengkap | Membuka tab Settings tanpa mengisi bot token | Bot token dan Chat ID kosong pada form Telegram Notifications | Status menampilkan "⚠️ Bot token not configured" |
| P-37 | Menyimpan konfigurasi Telegram | Mengisi dan menyimpan bot token & chat ID | Bot Token diisi token valid dari @BotFather, Chat IDs diisi `123456789`, centang "Enable Telegram Notifications", klik "Save" | Notifikasi "Settings saved successfully" muncul; status berubah menjadi "✅ Active"; token ditampilkan ter-mask setelah reload |
| P-38 | Mengirim pesan uji Telegram | Mengklik tombol "Test" pada panel Telegram | Konfigurasi Telegram valid dan aktif, pengguna klik "Test" | Tombol berubah teks "Sending..." lalu notifikasi "✅ Test message sent! Check your Telegram." muncul, dan pesan uji diterima pada chat Telegram terkait |
| P-39 | Test Telegram dengan konfigurasi tidak valid | Mengklik "Test" tanpa bot token valid | Bot token kosong/salah, klik "Test" | Notifikasi "❌ Test failed: {pesan error dari server}" muncul |
| P-40 | Distribusi sinyal ke Telegram otomatis | Memverifikasi notifikasi terkirim saat sinyal terbentuk | Telegram enabled & valid, engine running, rule terpenuhi | Pesan notifikasi sinyal (symbol, harga, tipe) terkirim otomatis ke Chat ID terdaftar bersamaan dengan broadcast Socket.IO |

## Tabel 3.6 Rancangan Pengujian Fungsional Modul Settings (Koneksi Broker) — RM3

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-41 | Menyimpan pengaturan IBKR | Mengubah Host/Port IBKR | IBKR Host diisi `127.0.0.1`, Port diisi `7497`, klik "Save Settings" | Toast "Settings saved successfully" muncul, nilai tersimpan pada tabel `settings` dan tetap muncul setelah reload halaman |
| P-42 | Client ID bersifat read-only | Memverifikasi field Client ID tidak dapat diubah manual | Pengguna mencoba mengklik/mengetik pada field "Client ID" | Field tetap menampilkan "Auto (random)", disabled, dan tidak dapat diedit (client ID dibuat otomatis 1000-9999 tiap koneksi) |
| P-43 | Menyimpan setting dengan port tidak valid | Mengisi port non-numerik pada form | Port diisi karakter non-angka melalui devtools/manipulasi input number | Input type="number" menolak karakter non-digit di level browser, atau API mengembalikan error validasi jika request tetap dikirim |

## Tabel 3.7 Rancangan Pengujian Fungsional Modul Backtesting — RM4

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-44 | Backtest mode Rule-based | Menjalankan backtesting berbasis rule tersimpan | Mode `Rule-based`, Timeframe `5m`, Rule `RSI Oversold`, Tickers `AAPL, MSFT`, Screening Start/End diisi rentang tanggal valid, Data Source `Yahoo Finance`, klik "Run Backtesting" | Toast "Completed. Rows: {n}" muncul; tabel hasil menampilkan kolom Ticker, Signal, Entry Time, Entry Price, dan T+1 s.d. T+5 (sesuai n-steps) berikut Win Rate & Total P/L |
| P-45 | Backtest mode Rule-based tanpa field wajib | Submit tanpa mengisi rule/tanggal | Mode `Rule-based` dipilih, tetapi Rule/Screening Start/Screening End dikosongkan, lalu "Run Backtesting" | Pesan error "Rule mode requires: rule, start, end" ditampilkan pada `backtest-message`, request tidak dikirim |
| P-46 | Backtest mode Manual-entry | Menjalankan backtest dari entri manual | Mode diganti ke `Manual-entry`, textarea diisi `AAPL,2026-05-01T09:35,BUY,192.50`, klik "Run Backtesting" | Sistem memproses entri manual tersebut melalui `RuleEngine`/`IndicatorEngine` yang sama dan menampilkan hasil P/L per langkah T+n |
| P-47 | Backtest manual tanpa entri | Submit mode manual dengan textarea kosong | Mode `Manual-entry`, textarea dikosongkan, lalu submit | Pesan error "Manual mode requires at least 1 entry" ditampilkan |
| P-48 | Variasi Entry/Exit Price Basis | Menguji kombinasi basis harga entry & exit | Entry Price Basis `Open`, Exit/P/L Basis `High`, sisanya default, jalankan backtest rule-based valid | Hasil P/L pada tiap kolom T+n dihitung menggunakan harga Open sebagai entry dan High sebagai exit sesuai pilihan, bukan default Close/Close |
| P-49 | Backtest tanpa hasil (data kosong) | Menjalankan backtest pada rentang tanpa data candle di cache/Yahoo | Rentang tanggal sangat lampau atau ticker tidak valid dipilih | Tabel hasil menampilkan `row_count: 0` / baris kosong, tanpa aplikasi crash |
| P-50 | Menyimpan riwayat backtest | Memverifikasi hasil backtest tersimpan | Backtest berhasil dijalankan | Entry baru tersimpan pada tabel `backtest_runs`/`backtest_signals` dan dapat diambil kembali melalui `GET /api/backtest/runs` |
| P-51 | Menghapus riwayat backtest | Menghapus salah satu run backtest | Pengguna memanggil aksi hapus pada salah satu run (via API `DELETE /api/backtest/runs/{run_id}`) | Run beserta detail sinyalnya terhapus dari database dan tidak lagi muncul pada daftar riwayat |

## Tabel 3.8 Rancangan Pengujian Fungsional Modul Swing Screening — RM1 & RM2

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-52 | Screening tanpa memilih rule | Mengklik "Run Screening" tanpa memilih rule | Dropdown "Rule" kosong, "Ticker Universe" sudah dipilih, klik "Run Screening" | Pesan error "Please select a rule" ditampilkan pada `swing-message` |
| P-53 | Screening tanpa memilih universe | Mengklik "Run Screening" tanpa memilih universe | Dropdown "Rule" dipilih, "Ticker Universe" kosong, klik "Run Screening" | Pesan error "Please select a ticker universe" ditampilkan |
| P-54 | Screening dengan hasil ditemukan | Menjalankan screening dengan rule yang menghasilkan sinyal | Universe berisi beberapa ticker AS, Rule `RSI Oversold`, Timeframe `1d`, Lookback `30` hari, klik "Run Screening" | Toast "Screening completed. {n} signals found." muncul; ringkasan menampilkan kartu Total Tickers, Signals Found, Successful, Errors, No Data, Duration (ms); tabel hasil menampilkan simbol yang memenuhi kriteria |
| P-55 | Screening tanpa hasil memenuhi kriteria | Menjalankan screening dengan kriteria ketat | Rule dengan kondisi ekstrem (mis. `RSI14 < 1`) dijalankan pada universe | Toast "Screening completed. 0 signals found." muncul, statistik "Signals Found" bernilai 0 tanpa error |
| P-56 | Membatalkan proses screening | Menghentikan screening yang sedang berjalan | Screening sedang berjalan (tombol berubah menjadi state loading), pengguna membatalkan request | Pesan info "Screening cancelled" ditampilkan, proses dihentikan tanpa menampilkan hasil parsial yang salah |
| P-57 | Melihat chart hasil screening | Membuka grafik candlestick salah satu hasil | Pengguna mengklik salah satu baris hasil untuk membuka chart | Modal `swing-chart-modal` terbuka menampilkan candlestick chart, ringkasan rule yang cocok, kontrol zoom (+/-), dan ruler pengukur harga/waktu |
| P-58 | Ekspor hasil screening ke CSV | Mengekspor hasil ke file | Hasil screening tersedia, pengguna memilih aksi export CSV | File CSV terunduh berisi kolom symbol, signal, price, timestamp, status, error_message |
| P-59 | Ekspor tanpa hasil | Mengekspor CSV ketika belum ada hasil screening | Belum menjalankan screening apa pun, langsung memicu export | Pesan error "No screening results to export" ditampilkan |

## Tabel 3.9 Rancangan Pengujian Fungsional Modul Data (Ticker Universe & Yahoo Cache) — mendukung RM1, RM2, RM4

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-60 | Membuat ticker universe | Mengisi form "Create Ticker Universe" | Nama `US Large Cap`, Tickers `AAPL, MSFT, GOOGL, AMZN, TSLA`, Description opsional diisi, klik "Save" | Notifikasi "Universe created successfully" muncul, universe baru tampil di `universe-list` dan tersedia pada dropdown Screener/Backtesting/Yahoo Cache |
| P-61 | Membuat universe tanpa nama | Submit form tanpa mengisi nama | Field Tickers diisi tetapi Name dikosongkan, lalu "Save" | Notifikasi error "Please enter a universe name" muncul, request tidak terkirim |
| P-62 | Mengedit ticker universe | Mengubah daftar ticker universe yang sudah ada | Universe `US Large Cap` dibuka untuk edit, ticker `NFLX` ditambahkan, klik "Save" | Notifikasi "Universe updated successfully" muncul, daftar ticker ter-update |
| P-63 | Menghapus ticker universe | Menghapus universe dari daftar | Pengguna mengklik hapus pada salah satu universe dan mengonfirmasi dialog | Universe terhapus dari `universe-list` dan tidak lagi muncul pada dropdown terkait |
| P-64 | Mengisi Yahoo cache tanpa memilih universe | Mengklik "Fill Data" tanpa universe dipilih | Dropdown "Ticker Universe" pada panel Yahoo Cache kosong, timeframe tercentang default, klik "Fill Data" | Status menampilkan error "Select a ticker universe before filling Yahoo cache." |
| P-65 | Mengisi Yahoo cache tanpa timeframe | Mengklik "Fill Data" tanpa mencentang timeframe | Universe dipilih, seluruh checkbox timeframe (1m/5m/15m/1h/4h/1d) tidak dicentang, klik "Fill Data" | Status menampilkan error "Select at least one timeframe before filling Yahoo cache." |
| P-66 | Mengisi Yahoo cache dengan konfigurasi valid | Menjalankan backfill data historis | Universe `US Large Cap` dipilih, timeframe `1h`, `4h`, `1d` tercentang (default), klik "Fill Data" | Status menampilkan progres "Filling Yahoo cache for US Large Cap: 5 tickers, 1h, 4h, 1d.", diikuti hasil akhir "Yahoo cache filled: {n} candles across {m} symbol/timeframe jobs." dan data OHLCV tersimpan pada tabel `price_candles` |
| P-67 | Cache hit pada permintaan berikutnya | Menjalankan screening/backtest pada rentang yang sudah di-cache | Data untuk simbol & timeframe yang sama diminta kembali dalam rentang yang sudah tersedia di `price_candles` | `CachedDataSource` menyajikan data dari cache tanpa memanggil ulang Yahoo Finance untuk seluruh rentang, hanya bagian yang belum tercakup yang di-fetch |

---

## Kesimpulan Rancangan Pengujian

Rancangan pengujian fungsional di atas mencakup **9 modul** sesuai struktur antarmuka nyata aplikasi SignalGen (Startup & Navigasi, Watchlist, Rule Builder, Realtime Signal Engine, Distribusi Sinyal, Settings/Koneksi Broker, Backtesting, Swing Screening, dan Data) dengan total **67 skenario pengujian**. Setiap skenario disusun dari elemen UI (ID tombol/form), pesan toast/error, dan endpoint REST yang benar-benar diimplementasikan pada `app/app.py` dan `app/ui/static/js/`, menggunakan pendekatan **Black Box Testing**.

Pengujian fungsional ini memastikan bahwa:

1. **Rule Builder dan Realtime Signal Engine** (Tabel 3.3–3.4) memverifikasi RM1 — kemampuan sistem menghasilkan sinyal BUY/SELL berbasis kondisi indikator teknikal pada watchlist saham AS.
2. **Kombinasi kondisi multi-indikator** pada Rule Builder, dipakai bersama di Realtime Signal (scalping) maupun Screener (swing) (Tabel 3.3 & 3.8), memverifikasi RM2.
3. **Distribusi Sinyal via WebSocket dan Telegram** (Tabel 3.5) serta **Settings koneksi broker** (Tabel 3.6) memverifikasi RM3 — integrasi sinyal keluar ke platform/channel lain.
4. **Modul Backtesting** (Tabel 3.7) memverifikasi RM4 — evaluasi performa sinyal (win rate, P/L per langkah T+n) terhadap data historis, dievaluasi melalui `RuleEngine`/`IndicatorEngine` yang sama dengan mode live.
5. **Modul Watchlist dan Data (Ticker Universe/Yahoo Cache)** (Tabel 3.2 & 3.9) memverifikasi kesiapan data pendukung (simbol, cache OHLCV) sebelum sinyal dapat dihasilkan atau dievaluasi.

Setiap skenario pengujian dirancang agar dapat dijalankan langsung pada aplikasi yang telah dibangun (window PyWebView atau browser fallback di `http://127.0.0.1:3456`) tanpa memerlukan akses ke kode sumber, sesuai prinsip Black Box Testing. Hasil pengujian aktual (kolom "Hasil Pengujian" dan "Kesimpulan") diisi pada saat eksekusi pengujian oleh penguji.
