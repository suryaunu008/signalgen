# Panduan Setup Notifikasi Telegram

Dokumen ini menjelaskan cara mengkonfigurasi dan menggunakan fitur notifikasi sinyal trading via Telegram Bot.

## Fitur

✅ Notifikasi sinyal trading real-time ke Telegram
✅ Format pesan yang informatif dengan emoji
✅ Mendukung multiple chat IDs
✅ Konfigurasi mudah via UI/API
✅ Test message untuk verifikasi
✅ Informasi indikator teknikal lengkap

## Langkah Setup

### 1. Buat Telegram Bot

1. Buka Telegram dan cari **@BotFather**
2. Kirim command `/newbot`
3. Ikuti instruksi untuk membuat bot baru
4. Simpan **Bot Token** yang diberikan (format: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### 2. Dapatkan Chat ID

**Untuk personal chat:**
1. Kirim pesan apapun ke bot yang baru dibuat
2. Buka browser dan akses:
   ```
   https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   ```
   (Ganti `<BOT_TOKEN>` dengan token bot Anda)
3. Cari field `"chat":{"id":123456789}`
4. Simpan Chat ID tersebut

**Untuk grup:**
1. Tambahkan bot ke grup
2. Kirim pesan apapun di grup
3. Akses URL yang sama seperti di atas
4. Chat ID untuk grup biasanya negatif (contoh: `-987654321`)

### 3. Konfigurasi di SignalGen

**Via UI (Recommended):**
1. Buka aplikasi SignalGen
2. Masuk ke **Settings** > **Telegram Notifications**
3. Masukkan **Bot Token**
4. Masukkan **Chat IDs** (pisahkan dengan koma jika lebih dari satu)
   - Contoh: `123456789` (single user)
   - Contoh: `123456789,-987654321` (multiple chats)
5. Centang **Enable Telegram Notifications**
6. Klik **Save**
7. Klik **Test** untuk mengirim pesan test

**Via API:**

```bash
# Update settings
curl -X PUT http://localhost:3456/api/telegram/settings \
  -H "Content-Type: application/json" \
  -d '{
    "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    "chat_ids": "123456789",
    "enabled": true
  }'

# Test notification
curl -X POST http://localhost:3456/api/telegram/test \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 4. Verifikasi Setup

Setelah konfigurasi:
1. Klik tombol **Test** di UI
2. Anda akan menerima pesan test di Telegram
3. Jika berhasil, notifikasi siap digunakan

## Format Notifikasi Sinyal

Ketika sinyal trading terdeteksi, Anda akan menerima pesan dengan format:

```
🚀 SIGNAL TRADING ALERT

Symbol: AAPL
Type: BUY
Price: $189.50
Time: 2026-01-21 14:30:15
Rule: Default Scalping

📊 Indicators:
  • RSI: 45.23
  • MACD: 1.25
  • SIGNAL: 0.85
  • BB UPPER: 190.50
  • BB LOWER: 188.00
  • ADX: 28.50

SignalGen Trading System
```

## Troubleshooting

### Bot tidak merespon
- ✅ Pastikan Bot Token benar
- ✅ Pastikan bot tidak diblokir oleh Telegram
- ✅ Coba buat bot baru

### Pesan test gagal
- ✅ Periksa koneksi internet
- ✅ Pastikan Chat ID benar (cek dengan `/getUpdates`)
- ✅ Pastikan Anda sudah mengirim pesan ke bot terlebih dahulu

### Notifikasi sinyal tidak masuk
- ✅ Pastikan **Telegram Enabled** dicentang
- ✅ Pastikan engine sedang berjalan
- ✅ Cek log aplikasi untuk error

### Error "Chat not found"
- ✅ Pastikan Anda sudah `/start` bot
- ✅ Untuk grup, pastikan bot sudah ditambahkan

## API Endpoints

### GET `/api/telegram/settings`
Mendapatkan konfigurasi Telegram saat ini (bot token dimask untuk keamanan)

### PUT `/api/telegram/settings`
Update konfigurasi Telegram

**Request body:**
```json
{
  "bot_token": "string",      // optional
  "chat_ids": "string",        // optional, comma-separated
  "enabled": true              // optional
}
```

### POST `/api/telegram/test`
Kirim pesan test

**Request body:**
```json
{
  "chat_id": "string"  // optional, test specific chat
}
```

## Keamanan

- 🔒 Bot token disimpan di database lokal
- 🔒 Token tidak pernah di-log atau ditampilkan penuh di UI
- 🔒 Hanya aplikasi Anda yang memiliki akses ke token
- 🔒 Gunakan bot pribadi, jangan bagikan token

## Tips Penggunaan

1. **Multiple Chats**: Anda bisa mengirim ke beberapa chat sekaligus
2. **Grup Trading**: Buat grup Telegram untuk team trading
3. **Backup**: Simpan bot token di tempat aman
4. **Test Reguler**: Test notifikasi setelah update konfigurasi
5. **Monitoring**: Periksa log jika notifikasi gagal

## Dependencies

Fitur ini menggunakan:
- `aiohttp` untuk HTTP requests ke Telegram API
- Tidak memerlukan library tambahan selain yang sudah ada di `requirements.txt`

## Update Konfigurasi

Jika ingin mengubah konfigurasi saat engine berjalan:
1. Stop engine terlebih dahulu
2. Update settings Telegram
3. Restart engine
4. Notifikasi akan menggunakan konfigurasi baru

---

**Dibuat oleh**: SignalGen Development Team  
**Tanggal**: 21 Januari 2026  
**Versi**: 1.0.0
