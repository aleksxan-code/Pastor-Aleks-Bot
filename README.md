
# Forward Bot — Category Buttons Fixed & Greeting Only at Start

Что изменилось:
- **Надёжные категории:** callback_data теперь короткие (ASCII IDs), поэтому кнопки категорий работают стабильно.
- **Приветствие только при /start:** большое триязычное приветствие показывается ТОЛЬКО в самом начале (и после "Finish" → пользователь нажимает /start). 
- **Смена языка без приветствия:** при "🌐 Change language" показывается выбор языка без большого приветствия; после выбора языка сразу выводится меню категорий.
- **Finish/Change language** остаются в меню категорий.
- **Опциональный автоответ** после отправки сообщения админу (включается переменной `AUTO_REPLY`).

Переменные окружения:
```
BOT_TOKEN=...
ADMIN_CHAT_ID=...
AUTO_REPLY=1   # 1/true/yes — включить автоответ; 0/false/no — отключить
```

Запуск:
```bash
pip install -r requirements.txt
export BOT_TOKEN=123:ABC...
export ADMIN_CHAT_ID=-1001234567890
export AUTO_REPLY=1
python bot.py
```
