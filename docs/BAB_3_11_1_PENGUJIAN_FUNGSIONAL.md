# BAB 3.11.1 PENGUJIAN FUNGSIONAL SISTEM

Pengujian fungsional sistem dilakukan dengan metode **Black Box Testing** untuk memverifikasi bahwa setiap fungsi sistem menghasilkan output yang sesuai dengan input yang diberikan, tanpa mempertimbangkan logika internal sistem. Pengujian ini berfokus pada validasi fungsionalitas sistem berdasarkan spesifikasi yang telah dirancang pada tahap perancangan.

## Tabel 3.1 Rancangan Pengujian Fungsional Modul Antarmuka Pengguna

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-01 | Menjalankan aplikasi | Menjalankan server aplikasi | Pengguna menjalankan perintah `python app/main.py` pada terminal | Aplikasi web berjalan pada `http://localhost:5000` dan dapat diakses melalui browser |
| P-02 | Akses halaman utama | Mengakses antarmuka web sistem | Pengguna membuka URL `http://localhost:5000` pada browser | Halaman utama ditampilkan dengan menu navigasi Scalping, Swing Screening, dan Backtesting |
| P-03 | Navigasi menu Scalping | Memilih menu Scalping | Pengguna mengklik menu Scalping pada navigation bar | Halaman Scalping ditampilkan dengan form input simbol dan rule |
| P-04 | Navigasi menu Swing Screening | Memilih menu Swing Screening | Pengguna mengklik menu Swing Screening | Halaman Swing Screening ditampilkan dengan form input daftar simbol |
| P-05 | Navigasi menu Backtesting | Memilih menu Backtesting | Pengguna mengklik menu Backtesting | Halaman Backtesting ditampilkan dengan form input simbol, periode, dan rule |

## Tabel 3.2 Rancangan Pengujian Fungsional Modul Input Data

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-06 | Input simbol saham valid | Mengisi form input dengan simbol saham | Pengguna memasukkan simbol `AAPL` pada form input | Sistem menerima input dan menampilkan indikator loading atau proses |
| P-07 | Input simbol saham tidak valid | Memproses input simbol yang tidak terdaftar | Pengguna memasukkan simbol `INVALIDXYZ` | Sistem menampilkan pesan error "Simbol tidak ditemukan" atau "Data tidak tersedia" |
| P-08 | Input multiple simbol untuk screening | Mengisi daftar simbol untuk swing screening | Pengguna memasukkan `AAPL, MSFT, GOOGL, TSLA` | Sistem menerima daftar simbol dan memproses permintaan screening |
| P-09 | Input periode backtesting | Mengisi rentang tanggal untuk backtesting | Pengguna memilih tanggal mulai `2024-01-01` dan tanggal akhir `2024-12-31` | Sistem menerima input periode dan siap memproses backtesting |
| P-10 | Input periode tidak valid | Mengisi periode dengan tanggal akhir sebelum tanggal mulai | Pengguna memilih tanggal mulai `2024-12-31` dan tanggal akhir `2024-01-01` | Sistem menampilkan pesan error "Tanggal akhir harus setelah tanggal mulai" |

## Tabel 3.3 Rancangan Pengujian Fungsional Modul Pengambilan Data

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-11 | Pengambilan data historis | Mengambil data pasar dari sumber data eksternal | Sistem memproses permintaan dengan simbol `AAPL` | Data historis OHLCV (Open, High, Low, Close, Volume) berhasil diambil dan ditampilkan |
| P-12 | Validasi koneksi data source | Memastikan koneksi ke sumber data aktif | Sistem melakukan request data pada kondisi koneksi internet normal | Data berhasil diambil dari sumber data tanpa error koneksi |
| P-13 | Penanganan error data source | Mengambil data pada kondisi sumber tidak tersedia | Sistem mencoba mengambil data saat koneksi gagal atau API down | Sistem menampilkan pesan error "Gagal mengambil data" atau "Sumber data tidak tersedia" |
| P-14 | Caching data historis | Mengambil data yang sudah pernah diminta sebelumnya | Pengguna meminta data simbol yang sama dalam waktu singkat | Sistem menggunakan data cache untuk mempercepat response time |

## Tabel 3.4 Rancangan Pengujian Fungsional Modul Perhitungan Indikator

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-15 | Perhitungan indikator teknikal | Menghitung nilai indikator dari data historis | Sistem memproses data OHLCV untuk simbol `AAPL` | Nilai indikator MA, RSI, MACD, Bollinger Bands, dan ADX berhasil dihitung dan ditampilkan |
| P-16 | Validasi perhitungan Moving Average | Menghitung Simple Moving Average (SMA) | Data historis 50 candle diproses dengan periode MA-20 | Nilai MA-20 ditampilkan dengan nilai yang valid (tidak kosong atau error) |
| P-17 | Validasi perhitungan RSI | Menghitung Relative Strength Index | Data historis diproses dengan parameter RSI periode 14 | Nilai RSI ditampilkan dalam rentang 0-100 |
| P-18 | Validasi perhitungan MACD | Menghitung MACD dan Signal Line | Data historis diproses dengan parameter MACD standar (12,26,9) | Nilai MACD Line, Signal Line, dan Histogram ditampilkan |
| P-19 | Perhitungan dengan data minimal | Menghitung indikator dengan jumlah data terbatas | Sistem memproses data kurang dari periode indikator yang diperlukan | Sistem menampilkan pesan "Data tidak cukup untuk menghitung indikator" atau menampilkan nilai parsial |

## Tabel 3.5 Rancangan Pengujian Fungsional Modul Evaluasi Rule Trading

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-20 | Evaluasi rule sinyal beli | Mengevaluasi kondisi rule untuk sinyal BUY | Kondisi rule `RSI < 30` terpenuhi dengan nilai RSI = 25 | Sistem menghasilkan sinyal BUY dengan timestamp dan harga saat itu |
| P-21 | Evaluasi rule sinyal jual | Mengevaluasi kondisi rule untuk sinyal SELL | Kondisi rule `RSI > 70` terpenuhi dengan nilai RSI = 75 | Sistem menghasilkan sinyal SELL dengan timestamp dan harga saat itu |
| P-22 | Evaluasi rule tidak terpenuhi | Mengevaluasi kondisi yang tidak memenuhi kriteria | Kondisi rule `RSI < 30` dengan nilai RSI = 50 | Sistem tidak menghasilkan sinyal atau menampilkan status NEUTRAL |
| P-23 | Evaluasi rule kompleks | Mengevaluasi rule dengan multiple kondisi | Rule `RSI < 30 AND MACD_CROSS_ABOVE_SIGNAL` dengan kedua kondisi terpenuhi | Sistem menghasilkan sinyal BUY hanya jika semua kondisi terpenuhi |
| P-24 | Validasi rule tidak valid | Memproses rule dengan sintaks tidak valid | Pengguna memasukkan rule dengan indikator tidak dikenali | Sistem menampilkan pesan error "Rule tidak valid" atau "Indikator tidak dikenali" |
| P-25 | Deteksi cross pattern | Mengevaluasi kondisi crossover indikator | MA periode pendek melintasi MA periode panjang dari bawah ke atas | Sistem mendeteksi crossover dan menghasilkan sinyal BUY |

## Tabel 3.6 Rancangan Pengujian Fungsional Modul Scalping Real-Time

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-26 | Memulai monitoring scalping | Memulai pemantauan sinyal real-time | Pengguna mengklik tombol "Start Monitoring" dengan simbol `AAPL` dan rule yang valid | Sistem mulai memantau data real-time dan menampilkan status "Monitoring Active" |
| P-27 | Deteksi sinyal scalping | Mendeteksi sinyal pada timeframe intraday | Kondisi rule scalping terpenuhi pada interval 5 menit | Sistem menghasilkan sinyal dan menampilkan notifikasi real-time pada antarmuka |
| P-28 | Menghentikan monitoring | Menghentikan pemantauan real-time | Pengguna mengklik tombol "Stop Monitoring" | Sistem menghentikan pemantauan dan menampilkan status "Monitoring Stopped" |
| P-29 | Update data real-time | Memperbarui data candle secara berkala | Sistem berjalan dalam mode monitoring | Data candle terbaru ditampilkan dan diperbarui setiap interval waktu yang ditentukan |

## Tabel 3.7 Rancangan Pengujian Fungsional Modul Swing Screening

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-30 | Proses swing screening | Melakukan screening terhadap daftar saham | Pengguna memasukkan daftar simbol `AAPL, MSFT, GOOGL, TSLA` dengan rule `RSI < 35` | Sistem memproses semua simbol dan menampilkan daftar saham yang memenuhi kriteria |
| P-31 | Filter hasil screening | Menampilkan saham yang memenuhi kriteria | Dari daftar 10 simbol, 3 simbol memenuhi kondisi rule | Sistem menampilkan 3 simbol yang memenuhi kriteria beserta nilai indikatornya |
| P-32 | Screening tanpa hasil | Memproses screening tanpa ada yang memenuhi | Semua simbol dalam daftar tidak memenuhi kondisi rule | Sistem menampilkan pesan "Tidak ada saham yang memenuhi kriteria" |
| P-33 | Screening dengan multiple kriteria | Mengevaluasi beberapa kondisi sekaligus | Rule screening menggunakan kondisi `RSI < 35 AND ADX > 25` | Sistem menampilkan hanya saham yang memenuhi kedua kondisi |

## Tabel 3.8 Rancangan Pengujian Fungsional Modul Backtesting

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-34 | Menjalankan backtesting | Melakukan simulasi strategi pada data historis | Pengguna memasukkan simbol `AAPL`, periode `2024-01-01` hingga `2024-12-31`, dan rule trading | Sistem memproses backtesting dan menampilkan progres |
| P-35 | Menampilkan hasil backtesting | Menampilkan laporan hasil simulasi | Proses backtesting selesai | Sistem menampilkan daftar sinyal historis dengan timestamp, tipe sinyal, dan harga |
| P-36 | Statistik backtesting | Menghitung statistik performa strategi | Backtesting menghasilkan beberapa sinyal | Sistem menampilkan statistik: total sinyal, jumlah sinyal beli, jumlah sinyal jual |
| P-37 | Backtesting tanpa sinyal | Memproses periode tanpa sinyal terpenuhi | Periode atau rule tidak menghasilkan sinyal | Sistem menampilkan pesan "Tidak ada sinyal ditemukan pada periode ini" |
| P-38 | Visualisasi hasil backtesting | Menampilkan grafik atau tabel sinyal | Hasil backtesting tersedia | Sistem menampilkan visualisasi sinyal pada timeline atau tabel rinci |

## Tabel 3.9 Rancangan Pengujian Fungsional Modul Distribusi Sinyal

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-39 | Distribusi sinyal real-time | Mengirim sinyal ke antarmuka pengguna | Sistem menghasilkan sinyal BUY pada scalping monitoring | Sinyal ditampilkan pada antarmuka web secara real-time tanpa perlu refresh halaman |
| P-40 | Notifikasi sinyal baru | Menampilkan notifikasi visual untuk sinyal | Sinyal baru terdeteksi oleh sistem | Notifikasi muncul di antarmuka dengan informasi simbol, tipe sinyal, dan harga |
| P-41 | Koneksi WebSocket | Membangun koneksi untuk komunikasi real-time | Halaman scalping dibuka oleh pengguna | Koneksi WebSocket berhasil dibuat dan status ditampilkan di console browser |
| P-42 | Update data streaming | Memperbarui data secara berkelanjutan | Monitoring aktif dengan koneksi WebSocket | Data candle dan indikator diperbarui secara otomatis setiap interval waktu |

## Tabel 3.10 Rancangan Pengujian Fungsional Modul Penyimpanan Data

| Kode | Pengujian | Aktivitas Pengujian | Skenario Pengujian | Hasil yang Diharapkan |
|------|-----------|---------------------|--------------------|-----------------------|
| P-43 | Penyimpanan sinyal | Menyimpan data sinyal ke basis data | Sistem menghasilkan sinyal BUY untuk simbol `AAPL` | Data sinyal tersimpan di basis data SQLite dengan informasi lengkap (simbol, timestamp, tipe, harga) |
| P-44 | Penyimpanan hasil backtesting | Menyimpan laporan hasil backtesting | Backtesting selesai dijalankan | Hasil backtesting tersimpan di database dengan detail periode, rule, dan statistik |
| P-45 | Query riwayat sinyal | Mengambil data sinyal historis dari database | Pengguna meminta riwayat sinyal untuk simbol `AAPL` | Sistem menampilkan daftar sinyal historis yang tersimpan untuk simbol tersebut |
| P-46 | Inisialisasi database | Membuat struktur database saat pertama kali | Aplikasi dijalankan pertama kali atau database belum ada | File database SQLite terbuat dengan tabel-tabel yang diperlukan (signals, backtests, watchlist) |
| P-47 | Validasi integritas data | Memastikan data tersimpan dengan benar | Data sinyal disimpan dan kemudian di-query kembali | Data yang di-query sama dengan data yang disimpan tanpa kehilangan informasi |

---

## Kesimpulan Rancangan Pengujian

Rancangan pengujian fungsional di atas mencakup **10 modul utama** sistem sinyal trading dengan total **47 skenario pengujian** yang komprehensif. Setiap skenario dirancang untuk memverifikasi bahwa sistem menghasilkan output yang sesuai dengan spesifikasi berdasarkan input yang diberikan, menggunakan pendekatan **Black Box Testing**.

Pengujian fungsional ini memastikan bahwa:

1. **Antarmuka pengguna** dapat diakses dan navigasi berjalan dengan baik
2. **Input data** divalidasi dan diproses sesuai ketentuan
3. **Pengambilan data historis** berhasil dari sumber data eksternal
4. **Perhitungan indikator teknikal** menghasilkan nilai yang valid
5. **Evaluasi rule trading** menghasilkan sinyal sesuai kondisi yang ditentukan
6. **Monitoring real-time** (scalping) berfungsi dengan responsif
7. **Screening saham** memfilter simbol berdasarkan kriteria yang ditetapkan
8. **Backtesting** menghasilkan analisis historis yang akurat
9. **Distribusi sinyal** berjalan secara real-time ke antarmuka pengguna
10. **Penyimpanan data** menjaga persistensi dan integritas informasi

Setiap skenario pengujian dirancang agar dapat dijalankan pada aplikasi yang telah dibangun tanpa memerlukan akses ke kode sumber atau logika internal, sesuai dengan prinsip pengujian Black Box. Hasil pengujian ini akan menjadi acuan untuk memverifikasi bahwa sistem telah memenuhi persyaratan fungsional yang ditetapkan pada tahap analisis dan perancangan.
