
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

LANG_BTNS: List[List[tuple[str, str]]] = [[
    ("Русский 🇷🇺", "lang:ru"),
    ("English 🇬🇧", "lang:en"),
    ("Українська 🇺🇦", "lang:uk"),
]]

MENU_ITEMS: Dict[Lang, List[str]] = {
    "ru": [
        "💡 Есть идея",
        "🤝 Служение и волонтёрство",
        "🏠 Нуждаюсь в посещении",
        "🙏 Личная молитва и поддержка",
        "📖 Встреча с пастором",
    ],
    "en": [
        "💡 I have an idea",
        "🤝 Ministry & volunteering",
        "🏠 I need a visit",
        "🙏 Personal prayer & support",
        "📖 Meet the pastor",
    ],
    "uk": [
        "💡 Є ідея",
        "🤝 Служіння та волонтерство",
        "🏠 Потребую відвідування",
        "🙏 Особиста молитва та підтримка",
        "📖 Зустріч з пастором",
    ],
}

PROMPTS = {
    "ru": "Выберите категорию:",
    "en": "Choose a category:",
    "uk": "Оберіть категорію:",
}

CHANGE_LANG_BTN = {
    "ru": "🌐 Сменить язык",
    "en": "🌐 Change language",
    "uk": "🌐 Змінити мову",
}

FINISH_BTN = {
    "ru": "🔚 Завершить работу",
    "en": "🔚 Finish",
    "uk": "🔚 Завершити",
}

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

# --------------- Helpers ----------------
def admin_chat_id() -> int:
    if not ADMIN_CHAT_ID_ENV:
        raise RuntimeError("Set ADMIN_CHAT_ID env var (admin/group chat id)")
    try:
        return int(ADMIN_CHAT_ID_ENV)
    except ValueError:
        raise RuntimeError("ADMIN_CHAT_ID must be an integer (can be negative for groups)")

def lang_inline_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text, callback_data=data) for text, data in LANG_BTNS[0]]]
    return InlineKeyboardMarkup(rows)

def menu_inline_keyboard(lang: Lang) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(title, callback_data=f"cat:{title}")] for title in MENU_ITEMS[lang]]
    rows.append([InlineKeyboardButton(CHANGE_LANG_BTN[lang], callback_data="change_lang")])
    rows.append([InlineKeyboardButton(FINISH_BTN[lang], callback_data="finish")])
    return InlineKeyboardMarkup(rows)

def is_menu_item(text: str, lang: Optional[Lang]) -> bool:
    return bool(lang and text in MENU_ITEMS[lang])

async def show_menu(update_or_msg, lang: Lang) -> None:
    msg = update_or_msg.effective_message if isinstance(update_or_msg, Update) else update_or_msg
    await msg.reply_text(
        PROMPTS[lang],
        reply_markup=menu_inline_keyboard(lang)
    )

# --------------- Handlers ---------------
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
            ud.pop("category", None)
            await query.answer()
            await query.message.reply_text(
                PROMPTS[lang],
                reply_markup=menu_inline_keyboard(lang),
            )
            return

        if data == "change_lang":
            ud.pop("category", None)
            ud.pop("lang", None)
            await query.answer()
            # remove inline keyboard from the pressed message (visual cleanup)
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await query.message.reply_text(
                TRILINGUAL_GREETING,
                reply_markup=lang_inline_keyboard(),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return

        if data == "finish":
            lang = ud.get("lang", "ru")
            # clear session
            ud.clear()
            await query.answer()
            # remove inline keyboard from the pressed message
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            # send goodbye without any keyboard
            await query.message.reply_text(GOODBYE_TEXT.get(lang, GOODBYE_TEXT["en"]))
            return

        if data.startswith("cat:"):
            category = data.split(":", 1)[1]
            ud["category"] = category
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
    category: Optional[str] = context.user_data.get("category")

    if is_menu_item(text, lang):
        context.user_data["category"] = text
        return

    # After category chosen -> forward/copy ANY subsequent message to admin,
    # optional ack to the user, then reset category and show menu again.
    if category and lang:
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
        except Exception as e:
            logging.exception("Failed to copy message to admin: %s", e)

        if AUTO_REPLY:
            try:
                await msg.reply_text(ACK_TEXT[lang])
            except Exception:
                pass

        context.user_data.pop("category", None)
        await show_menu(update, lang)
        return

    if not lang:
        await msg.reply_text(
            TRILINGUAL_GREETING,
            reply_markup=lang_inline_keyboard(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    await show_menu(update, lang)

# --------------- Entrypoint -------------
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
