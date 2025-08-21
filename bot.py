
from __future__ import annotations

import os
import logging
from typing import Dict, List, Literal, Optional

from telegram import (
    Update, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters, PicklePersistence
)

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID_ENV = os.getenv("ADMIN_CHAT_ID")  # may be negative for supergroups
AUTO_REPLY = os.getenv("AUTO_REPLY", "1") in {"1", "true", "True", "yes", "YES"}

Lang = Literal["ru", "en", "uk"]

# Category IDs are short & ASCII to avoid Telegram's 64-byte callback_data limit
CATEGORY_DEFS = [
    {"id": "idea",     "ru": "💡 Есть идея",                 "en": "💡 I have an idea",            "uk": "💡 Є ідея"},
    {"id": "volunteer","ru": "🤝 Служение и волонтёрство",   "en": "🤝 Ministry & volunteering",    "uk": "🤝 Служіння та волонтерство"},
    {"id": "visit",    "ru": "🏠 Нуждаюсь в посещении",       "en": "🏠 I need a visit",             "uk": "🏠 Потребую відвідування"},
    {"id": "prayer",   "ru": "🙏 Личная молитва и поддержка", "en": "🙏 Personal prayer & support",  "uk": "🙏 Особиста молитва та підтримка"},
    {"id": "pastor",   "ru": "📖 Встреча с пастором",         "en": "📖 Meet the pastor",            "uk": "📖 Зустріч з пастором"},
]

# Precompute per-language label lookup by id
LABEL_BY_ID: Dict[Lang, Dict[str, str]] = {
    "ru": {c["id"]: c["ru"] for c in CATEGORY_DEFS},
    "en": {c["id"]: c["en"] for c in CATEGORY_DEFS},
    "uk": {c["id"]: c["uk"] for c in CATEGORY_DEFS},
}

PROMPTS = {
    "ru": "Выберите категорию:",
    "en": "Choose a category:",
    "uk": "Оберіть категорію:",
}

CHANGE_LANG_BTN = {"ru": "🌐 Сменить язык", "en": "🌐 Change language", "uk": "🌐 Змінити мову"}
FINISH_BTN      = {"ru": "🔚 Завершить работу", "en": "🔚 Finish", "uk": "🔚 Завершити"}

ACK_TEXT = {
    "ru": "✅ Спасибо! Мы свяжемся с вами.",
    "en": "✅ Thank you! We will get back to you.",
    "uk": "✅ Дякуємо! Ми зв'яжемося з вами.",
}

GOODBYE_TEXT = {
    "ru": "✅ Спасибо за общение! Чтобы вернуться, нажмите /start",
    "en": "✅ Thank you for chatting! To return, just type /start",
    "uk": "✅ Дякуємо за спілкування! Щоб повернутися, натисніть /start",
}

TRILINGUAL_GREETING = (
    "<b>Привет!</b> Пастор Александр Ханчевский рад с тобой пообщаться.\n"
    "Выбери удобный для тебя язык общения из меню ниже.\n\n"
    "<b>Hello!</b> Pastor Aleksandr Khanchevskii is glad to chat with you.\n"
    "Please choose the language you prefer.\n\n"
    "<b>Вітаю!</b> Пастор Олександр Ханчевський радий поспілкуватися.\n"
    "Оберіть зручну для вас мову спілкування нижче."
)

def admin_chat_id() -> int:
    if not ADMIN_CHAT_ID_ENV:
        raise RuntimeError("Set ADMIN_CHAT_ID env var (admin/group chat id)")
    try:
        return int(ADMIN_CHAT_ID_ENV)
    except ValueError:
        raise RuntimeError("ADMIN_CHAT_ID must be an integer (can be negative for groups)")

def lang_inline_keyboard() -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton("Русский 🇷🇺",  callback_data="lang:ru"),
        InlineKeyboardButton("English 🇬🇧",  callback_data="lang:en"),
        InlineKeyboardButton("Українська 🇺🇦", callback_data="lang:uk"),
    ]]
    return InlineKeyboardMarkup(rows)

def menu_inline_keyboard(lang: Lang) -> InlineKeyboardMarkup:
    rows = []
    for c in CATEGORY_DEFS:
        rows.append([InlineKeyboardButton(LABEL_BY_ID[lang][c["id"]], callback_data=f"cat:{c['id']}")])
    rows.append([InlineKeyboardButton(CHANGE_LANG_BTN[lang], callback_data="change_lang")])
    rows.append([InlineKeyboardButton(FINISH_BTN[lang],      callback_data="finish")])
    return InlineKeyboardMarkup(rows)

def is_menu_label(text: str, lang: Optional[Lang]) -> Optional[str]:
    """Return category_id if the text equals a menu label (fallback for typed labels)."""
    if not lang or not text:
        return None
    for cid, label in LABEL_BY_ID[lang].items():
        if text == label:
            return cid
    return None

async def show_menu(update_or_msg, lang: Lang) -> None:
    msg = update_or_msg.effective_message if isinstance(update_or_msg, Update) else update_or_msg
    await msg.reply_text(PROMPTS[lang], reply_markup=menu_inline_keyboard(lang))

# ---------------- Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.effective_message.reply_text(
        TRILINGUAL_GREETING,
        reply_markup=lang_inline_keyboard(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

async def on_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    ud = context.user_data
    try:
        if data.startswith("lang:"):
            lang: Lang = data.split(":", 1)[1]
            ud["lang"] = lang
            ud.pop("category_id", None)
            await query.answer()
            # No greeting here (per request). Go straight to category menu.
            await query.message.reply_text(PROMPTS[lang], reply_markup=menu_inline_keyboard(lang))
            return

        if data == "change_lang":
            # Switch language flow WITHOUT greeting (mid-session)
            ud.pop("category_id", None)
            # Do not clear lang so that language buttons show, selection will set a new lang
            await query.answer()
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await query.message.reply_text("Choose language / Выберите язык / Оберіть мову:", reply_markup=lang_inline_keyboard())
            return

        if data == "finish":
            lang = ud.get("lang", "ru")
            ud.clear()
            await query.answer()
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await query.message.reply_text(GOODBYE_TEXT.get(lang, GOODBYE_TEXT["en"]))
            return

        if data.startswith("cat:"):
            cid = data.split(":", 1)[1]
            ud["category_id"] = cid
            await query.answer()
            return
    except Exception as e:
        logging.exception("Callback error: %s", e)
        try:
            await query.answer()
        except Exception:
            pass

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg: Message = update.effective_message
    text = msg.text or ""
    lang: Optional[Lang] = context.user_data.get("lang")
    category_id: Optional[str] = context.user_data.get("category_id")

    # Fallback: if user typed a category label as plain text
    typed_cid = is_menu_label(text, lang)
    if typed_cid:
        context.user_data["category_id"] = typed_cid
        return

    # If category chosen, forward next message to admin, then reset category and show menu
    if category_id and lang:
        label = LABEL_BY_ID[lang].get(category_id, category_id)
        header = (
            f"📨 Новое обращение\n"
            f"• Пользователь: {msg.from_user.full_name} (id={msg.from_user.id})\n"
            f"• Язык: {lang}\n"
            f"• Категория: {label}\n"
            f"• Из чата: {update.effective_chat.id}"
        )
        try:
            await context.bot.send_message(chat_id=admin_chat_id(), text=header)
            await msg.copy(chat_id=admin_chat_id())
        except Exception as e:
            logging.exception("Failed to copy message to admin: %s", e)

        if AUTO_REPLY and lang in ("ru", "en", "uk"):
            try:
                await msg.reply_text(ACK_TEXT[lang])
            except Exception:
                pass

        context.user_data.pop("category_id", None)
        await show_menu(update, lang)
        return

    # No language yet -> show ONLY language picker (not full greeting)
    if not lang:
        await msg.reply_text("Choose language / Выберите язык / Оберіть мову:", reply_markup=lang_inline_keyboard())
        return

    # Language set but no category yet -> show category menu
    await show_menu(update, lang)

# ---------------- Entrypoint ----------------
def main() -> None:
    logging.basicConfig(level=logging.INFO)

    if not BOT_TOKEN:
        raise RuntimeError("Set BOT_TOKEN env var")
    _ = admin_chat_id()

    persistence = PicklePersistence(filepath="bot_state.pkl")

    app = ApplicationBuilder().token(BOT_TOKEN).persistence(persistence).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_cb))
    app.add_handler(MessageHandler(~filters.COMMAND, on_message))
    app.run_polling()

if __name__ == "__main__":
    main()
