# Build SignalGen Desktop Application ke .exe

## Cara Build

### Method 1: Menggunakan Script Build (Recommended)
```bash
python build_exe.py
```

### Method 2: Manual dengan PyInstaller
```bash
python -m PyInstaller --clean signalgen.spec
```

## Lokasi File Hasil Build

Setelah build selesai, executable akan berada di:
```
dist\SignalGen\SignalGen.exe
```

## Cara Menjalankan Aplikasi

1. Buka folder `dist\SignalGen\`
2. Double-click `SignalGen.exe`
3. Aplikasi akan terbuka dalam window desktop

## Distribusi Aplikasi

Untuk mendistribusikan aplikasi ke pengguna lain:

1. **Copy seluruh folder** `dist\SignalGen\` (bukan hanya file .exe)
2. Zip folder tersebut untuk memudahkan transfer
3. Pengguna cukup extract dan jalankan `SignalGen.exe`

**PENTING**: Jangan hanya copy file .exe saja, karena aplikasi membutuhkan semua file dependencies yang ada di folder `dist\SignalGen\`.

## File yang Di-bundle

- ✅ Icon aplikasi dari `static/favicon.ico`
- ✅ Templates HTML dari `app/ui/templates/`
- ✅ Static files (JS, CSS) dari `app/ui/static/`
- ✅ Semua dependencies Python
- ✅ SQLite database engine
- ✅ WebView engine untuk GUI

## Troubleshooting

### Aplikasi tidak bisa dibuka
- Pastikan seluruh folder `dist\SignalGen\` ter-copy lengkap
- Check apakah antivirus memblokir file .exe
- Jalankan sebagai Administrator jika perlu

### Database error
- Aplikasi akan otomatis membuat database baru di folder yang sama dengan .exe
- Pastikan folder memiliki write permission

### Port sudah digunakan
- Aplikasi menggunakan port 3456 (FastAPI) dan 8765 (WebSocket)
- Pastikan port tersebut tidak digunakan aplikasi lain

## Build Configuration

File `signalgen.spec` berisi konfigurasi build:
- **console=False**: Tidak menampilkan console window (GUI only)
- **icon**: Menggunakan `static/favicon.ico`
- **upx=True**: Kompresi untuk ukuran file lebih kecil
- **hiddenimports**: Dependencies yang di-import secara dinamis

## Rebuild Aplikasi

Jika ada perubahan code, jalankan lagi:
```bash
python build_exe.py
```

Build script akan otomatis:
1. Clean folder `build/` dan `dist/`
2. Rebuild dengan PyInstaller
3. Generate executable baru
