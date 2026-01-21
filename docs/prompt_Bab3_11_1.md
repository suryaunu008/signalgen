

## 🎯 Prompt untuk AI Agent – Rancangan Pengujian Fungsional Sistem (Black Box)

**Prompt:**

> Kamu berperan sebagai **asisten akademik** yang membantu penyusunan **Bab 3.11.1 Pengujian Fungsional Sistem** pada tugas akhir berjudul
> **“Rancang Bangun Sistem Sinyal Trading Berbasis Indikator Teknikal untuk Saham Amerika Serikat”**.
>
> Tugas kamu adalah **menyusun Rancangan Pengujian Black Box** dalam **bentuk tabel**, dengan **gaya, struktur, dan detail setara dengan Rancangan Pengujian Black Box pada Tugas Akhir Dean Agnia**, tetapi **konteks sistem disesuaikan sepenuhnya dengan sistem sinyal trading**.
>
> ### Ketentuan Umum:
>
> 1. **Metode pengujian: Black Box Testing**
> 2. Fokus hanya pada:
>
>    * Kesesuaian **input** dan **output**
>    * Tidak membahas logika internal atau implementasi kode
> 3. Bahasa formal akademik skripsi (Bahasa Indonesia)
> 4. Jangan menggunakan sudut pandang orang pertama
> 5. Setiap tabel **merepresentasikan satu skenario pengujian**
> 6. Gunakan istilah teknis konsisten dengan Bab II dan Bab III (indikator teknikal, rule, sinyal trading, backtesting, dll.)
>
> ---
>
> ### Struktur Tabel (WAJIB SAMA KONSISTEN):
>
> Setiap tabel pengujian harus memiliki kolom berikut:
>
> | No | Modul yang Diuji | Skenario Pengujian | Data Masukan | Langkah Pengujian | Hasil yang Diharapkan | Kriteria Keberhasilan |
>
> ---
>
> ### Cakupan Modul yang Wajib Diuji:
>
> Buat skenario pengujian fungsional untuk modul-modul berikut:
>
> 1. Modul Web Interface
> 2. Modul REST API
> 3. Modul Data Source (pengambilan data historis)
> 4. Modul Indicator Engine
> 5. Modul Rule Engine
> 6. Modul Scalping Engine
> 7. Modul Swing Screening Engine
> 8. Modul Backtesting Engine
> 9. Modul WebSocket Broadcaster
> 10. Modul Storage (SQLite)
>
> ---
>
> ### Contoh Penyesuaian Konteks (WAJIB DIIKUTI):
>
> * Jika modul adalah **Indicator Engine**, maka skenario harus menguji:
>
>   * Input data OHLC
>   * Output indikator (MA, RSI, MACD, Bollinger Bands, ADX)
> * Jika modul adalah **Rule Engine**, maka skenario menguji:
>
>   * Rule valid
>   * Rule tidak valid
>   * Rule menghasilkan sinyal beli/jual
> * Jika modul adalah **Backtesting Engine**, maka skenario menguji:
>
>   * Input rentang tanggal dan simbol
>   * Output sinyal historis dan status backtesting
>
> ---
>
> ### Hasil Akhir yang Diharapkan:
>
> * Tabel-tabel **siap langsung dimasukkan ke Bab 3.11.1**
> * Konsisten dengan pendekatan **black-box testing**
> * Bahasa rapi, akademik, dan tidak bertele-tele
> * Tidak menyebut nama penyedia data atau broker secara eksplisit
>
> Mulai dengan judul tabel seperti:
> **“Tabel X. Rancangan Pengujian Fungsional Modul …”**

---
