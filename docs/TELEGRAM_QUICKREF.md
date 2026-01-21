# Telegram Notifier - Quick Reference

## 🚀 Setup Cepat (5 Menit)

### 1. Buat Bot
```
1. Buka Telegram → Cari @BotFather
2. Ketik: /newbot
3. Beri nama bot Anda
4. Copy token yang diberikan
```

### 2. Dapatkan Chat ID
```
1. Kirim pesan ke bot Anda
2. Buka: https://api.telegram.org/bot<TOKEN>/getUpdates
3. Cari: "chat":{"id":12345678}
4. Copy angka ID tersebut
```

### 3. Konfigurasi
```bash
# Via UI:
Settings → Telegram → Paste Token & Chat ID → Enable → Test

# Via API:
curl -X PUT http://localhost:3456/api/telegram/settings \
  -H "Content-Type: application/json" \
  -d '{
    "bot_token": "123456:ABC-DEF...",
    "chat_ids": "12345678",
    "enabled": true
  }'
```

## 📡 API Endpoints

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/telegram/settings` | Get current settings |
| PUT | `/api/telegram/settings` | Update settings |
| POST | `/api/telegram/test` | Send test message |

## 🔧 Konfigurasi Settings

| Setting | Type | Example | Required |
|---------|------|---------|----------|
| `bot_token` | string | `123456:ABC-DEF...` | ✅ Yes |
| `chat_ids` | string | `123,456,-789` | ✅ Yes |
| `enabled` | boolean | `true` | ✅ Yes |

## 💾 Database Schema

```sql
-- Stored in settings table
key: telegram_bot_token
value: "123456:ABC-DEF..."

key: telegram_chat_ids  
value: "123456789,-987654321"

key: telegram_enabled
value: true/false
```

## 📱 Format Pesan

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

SignalGen Trading System
```

## 🐛 Common Issues & Fixes

| Error | Fix |
|-------|-----|
| "Chat not found" | Send /start ke bot dulu |
| "Invalid token" | Check token dari BotFather |
| "Timeout" | Check internet connection |
| "Not enabled" | Set `enabled: true` |

## 📂 File Structure

```
app/
├── notifications/
│   ├── __init__.py
│   └── telegram_notifier.py     ← Core logic
├── ws/
│   └── broadcaster.py            ← Integration
├── app.py                        ← API endpoints
├── main.py                       ← Initialization
└── ui/
    ├── static/js/telegram.js     ← Frontend
    └── templates/
        └── telegram_settings.html ← UI
```

## 🔍 Debugging

```python
# Check settings
import sqlite3
conn = sqlite3.connect('signalgen.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM settings WHERE key LIKE 'telegram%'")
print(cursor.fetchall())

# Test directly
from app.notifications.telegram_notifier import TelegramNotifier
from app.storage.sqlite_repo import SQLiteRepository

repo = SQLiteRepository()
notifier = TelegramNotifier(repo)
await notifier.initialize()
await notifier.send_test_message()
```

## 🎯 Tips

✅ **DO:**
- Test setelah konfigurasi
- Monitor logs untuk errors
- Backup bot token
- Gunakan grup untuk team

❌ **DON'T:**
- Share bot token publicly
- Spam test messages
- Ignore error logs
- Hardcode credentials

## 📞 Support

- 📖 Full Guide: `docs/TELEGRAM_SETUP.md`
- 🏗️ Implementation: `docs/TELEGRAM_IMPLEMENTATION.md`
- 💻 Code: `app/notifications/telegram_notifier.py`

---
Made with ❤️ for SignalGen v1.0.0
