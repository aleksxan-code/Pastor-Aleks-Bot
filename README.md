# Simple Forward Bot

- `/start` → язык → меню
- После выбора **категории** пользователь отправляет сообщение **любого типа**
- **На нажатие категории админ-чат не уведомляется**
- Любое **последующее** сообщение копируется в `ADMIN_CHAT_ID`

## Env
```
BOT_TOKEN=...
ADMIN_CHAT_ID=...
```

## Local run
```bash
pip install -r requirements.txt
export BOT_TOKEN=123:ABC...
export ADMIN_CHAT_ID=-1001234567890
python bot.py
```

## Railway
- Variables: `BOT_TOKEN`, `ADMIN_CHAT_ID`
- Start Command:
```
python bot.py
```