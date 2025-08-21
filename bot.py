from __future__ import annotations

import os
import logging
from typing import Dict, List, Literal, Optional

from telegram import Update, ReplyKeyboardMarkup, Message
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    PicklePersistence,
)

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID_ENV = os.getenv("ADMIN_CHAT_ID")  # may be negative for supergroups
Lang = Literal["ru", "en", "uk"]

LANG_BTNS: List[List[str]] = [["Русский 🇷🇺", "English 🇬🇧", "Українська 🇺🇦"]]
LANG_TEXT2CODE: Dict[str, Lang] = {
    "Русский 🇷🇺": "ru",
    "English 🇬🇧": "en",
    "Українська 🇺🇦": "uk",
}

MENU_BTNS: Dict[Lang, List[List[str]]] = {
    "ru": [
        ["🏠 Нуждаюсь в посещении"],
        ["🙏 Личная молитва и поддержка"],
        ["📖 Встреча с пастором"],
    ],
    "en": [
        ["🏠 I need a visit"],
        ["🙏 Personal prayer & support"],
        ["📖 Meet the pastor"],
    ],
    "uk": [
        ["🏠 Потребую відвідування"],
        ["🙏 Особиста молитва та підтримка"],
        ["📖 Зустріч з пастором"],
    ],
}

PROMPTS = {
    "choose_lang": "Выберите язык / Choose language / Оберіть мову:",
    "ru": "Выберите категорию:",
    "en": "Choose a category:",
    "uk": "Оберіть категорію:",
}

# --------------- Helpers ----------------
def admin_chat_id() -> int:
    if not ADMIN_CHAT_ID_ENV:
        raise RuntimeError("Set ADMIN_CHAT_ID env var (admin/group chat id)")
    try:
        return int(ADMIN_CHAT_ID_ENV)
    except ValueError:
        raise RuntimeError("ADMIN_CHAT_ID must be an integer (can be negative for groups)")

def lang_prompt(lang: Optional[Lang]) -> str:
    return PROMPTS["choose_lang"] if not lang else PROMPTS[lang]

def kb(rows: List[List[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def menu_contains(text: str, lang: Optional[Lang]) -> bool:
    if not lang or not text:
        return False
    return any(text in row for row in MENU_BTNS[lang])

# --------------- Handlers ---------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.effective_message.reply_text(lang_prompt(None), reply_markup=kb(LANG_BTNS))

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg: Message = update.effective_message
    text = msg.text or ""
    lang: Optional[Lang] = context.user_data.get("lang")
    category: Optional[str] = context.user_data.get("category")

    # 1) Language selection
    if text in LANG_TEXT2CODE:
        lang = LANG_TEXT2CODE[text]
        context.user_data["lang"] = lang
        await msg.reply_text(lang_prompt(lang), reply_markup=kb(MENU_BTNS[lang]))
        return

    # 2) Category button press -> save only, DO NOT forward
    if menu_contains(text, lang):
        context.user_data["category"] = text
        logging.info("Category selected: %s by user %s", text, msg.from_user.id)
        return  # critical: do not send this message to admin

    # 3) After category chosen -> forward/copy ANY subsequent message to admin, silently
    if category:
        header = (
            f"📨 Новое обращение\n"
            f"• Пользователь: {msg.from_user.full_name} (id={msg.from_user.id})\n"
            f"• Язык: {lang or '—'}\n"
            f"• Категория: {category}\n"
            f"• Из чата: {update.effective_chat.id}"
        )
        try:
            await context.bot.send_message(chat_id=admin_chat_id(), text=header)
            await msg.copy(chat_id=admin_chat_id())
            logging.info("Copied message from %s to admin", msg.from_user.id)
        except Exception as e:
            logging.exception("Failed to copy message to admin: %s", e)
        return

    # 4) Gentle prompts before selection is complete
    if not lang:
        await msg.reply_text(lang_prompt(None), reply_markup=kb(LANG_BTNS))
        return

    await msg.reply_text(lang_prompt(lang), reply_markup=kb(MENU_BTNS[lang]))

# --------------- Entrypoint -------------
def main() -> None:
    logging.basicConfig(level=logging.INFO)

    if not BOT_TOKEN:
        raise RuntimeError("Set BOT_TOKEN env var")
    _ = admin_chat_id()  # validate early

    # keep simple state across restarts
    persistence = PicklePersistence(filepath="bot_state.pkl")

    app = ApplicationBuilder().token(BOT_TOKEN).persistence(persistence).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(~filters.COMMAND, on_message))
    app.run_polling()

if __name__ == "__main__":
    main()