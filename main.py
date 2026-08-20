import sys
import subprocess
import asyncio
import logging
import sqlite3
from datetime import datetime

# Автоматическая установка aiogram при необходимости
try:
    import aiogram
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiogram>=3.10.0"])

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ==========================================
# ⚙️ НАСТРОЙКИ
# ==========================================
BOT_TOKEN = "8313715983:AAGbi8TxcXuAgwDyFxiqj-0i7ze2CZvzl-w"
SUPPORT_USERNAME = "@your_support_username"

# Ключевые слова для поиска заявок
KEYWORDS = [
    "сантехника", "сантехник", "электрика", "электрик", "ремонт техники",
    "муж на час", "плиточник", "отделка", "полы", "стены", "окна", "двери",
    "плесень", "тараканы", "дезинфекция", "дератизация", "дезинсекция",
    "засор", "замыкание", "починить", "установить", "мастер", "посоветуйте мастера",
    "подскажите мастера", "нужен мастер", "подскажите сантехника", "нужен электрик"
]

# ==========================================
# 🗄 БАЗА ДАННЫХ SQLite
# ==========================================
DB_NAME = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            registered_at TIMESTAMP,
            received_leads INTEGER DEFAULT 0,
            processed_leads INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_or_create_user(user_id: int, username: str, full_name: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        now = datetime.now()
        cursor.execute(
            "INSERT INTO users (user_id, username, full_name, registered_at) VALUES (?, ?, ?, ?)",
            (user_id, username, full_name, now)
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return user

def increment_processed(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET processed_leads = processed_leads + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def increment_received(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET received_leads = received_leads + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

# ==========================================
# ⌨️ КЛАВИАТУРЫ
# ==========================================
def get_main_keyboard():
    keyboard = [
        [KeyboardButton(text="Моя статистика")],
        [KeyboardButton(text="Инструкция"), KeyboardButton(text="Проверить подписку")],
        [KeyboardButton(text="Активировать подписку")],
        [KeyboardButton(text="Поддержка"), KeyboardButton(text="Перезапустить бота")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_lead_keyboard(user_link: str, message_link: str):
    buttons = [
        [InlineKeyboardButton(text="Написать сообщение ↗", url=user_link)],
        [InlineKeyboardButton(text="Ссылка на сообщение ↗", url=message_link)],
        [InlineKeyboardButton(text="✅ Отметить как обработанное", callback_data="process_lead_action")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ==========================================
# 🤖 ЛОГИКА TELEGRAM БОТА
# ==========================================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработка личных сообщений бота
@dp.message(F.chat.type == "private", CommandStart())
@dp.message(F.chat.type == "private", F.text == "Перезапустить бота")
async def cmd_start(message: Message):
    get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or ""
    )
    text = (
        "Привет — это бот онлайн-запросов и заявок на услуги!\n\n"
        "🟢 **Статус:** Вечный неограниченный доступ активен.\n"
        "Добавьте бота в ваши группы/чаты, и он будет фильтровать сообщения и присылать заявки сюда."
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.message(F.chat.type == "private", F.text == "Инструкция")
async def cmd_instruction(message: Message):
    text = (
        "📚 **Инструкция:**\n\n"
        "1. Добавьте бота в чаты или группы, откуда нужно собирать заявки.\n"
        "2. Бот автоматически отслеживает ключевые слова мастеров и услуг.\n"
        "3. Найденные запросы моментально отправляются вам в личные сообщения.\n\n"
        "📌 **Доступ:** Бессрочный безлимит."
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.chat.type == "private", F.text == "Моя статистика")
async def cmd_stats(message: Message):
    user = get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or ""
    )
    received, processed = user[4], user[5]
    conversion = round((processed / received * 100), 1) if received > 0 else 0
    text = (
        "📊 **Ваша статистика:**\n\n"
        f"📥 **Получено запросов:** {received}\n"
        f"✅ **Обработано вами:** {processed}\n"
        f"🎯 **Конверсия:** {conversion}%\n"
        "♾ **Подписка:** Бессрочная"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.chat.type == "private", F.text.in_(["Проверить подписку", "Активировать подписку"]))
async def cmd_subscription(message: Message):
    text = (
        "💳 **Статус доступа:**\n\n"
        "🟢 **Бессрочная подписка активна (Безлимит)**"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.chat.type == "private", F.text == "Поддержка")
async def cmd_support(message: Message):
    await message.answer(f"🛠 **Служба поддержки:**\n👉 {SUPPORT_USERNAME}")

@dp.callback_query(F.data == "process_lead_action")
async def callback_process_lead(call: CallbackQuery):
    increment_processed(call.from_user.id)
    await call.answer("✅ Отмечено в вашей статистике!")
    new_kb = InlineKeyboardMarkup(
        inline_keyboard=[row for row in call.message.reply_markup.inline_keyboard if not any("process_lead_action" in b.callback_data for b in row)] + [
            [InlineKeyboardButton(text="✅ Заявка обработана", callback_data="none")]
        ]
    )
    await call.message.edit_reply_markup(reply_markup=new_kb)

@dp.callback_query(F.data == "none")
async def callback_none(call: CallbackQuery):
    await call.answer("Вы уже отметили эту заявку.")

@dp.message(Command("test_lead"))
async def cmd_test_lead(message: Message):
    get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name or "")
    lead_text = "Соседи, подскажите проверенного сантехника пожалуйста 🙏\n\n🗣 **Чат:** ЖК Центральный"
    kb = get_lead_keyboard("https://t.me/telegram", "https://t.me/telegram")
    increment_received(message.from_user.id)
    await message.answer(lead_text, reply_markup=kb, parse_mode="Markdown")

# ==========================================
# 📡 ОБРАБОТЧИК СООБЩЕНИЙ ИЗ ГРУПП
# ==========================================
@dp.message(F.chat.type.in_(["group", "supergroup"]))
async def handle_group_messages(message: Message):
    text = message.text or message.caption or ""
    if not text:
        return

    text_lower = text.lower()
    if not any(k in text_lower for k in KEYWORDS):
        return

    chat_title = message.chat.title or "Группа"
    sender = message.from_user

    # Формируем ссылки
    user_link = f"https://t.me/{sender.username}" if sender and sender.username else f"tg://user?id={sender.id}" if sender else "https://t.me/telegram"
    msg_link = f"https://t.me/{message.chat.username}/{message.message_id}" if message.chat.username else user_link

    lead_message = f"{text}\n\n🗣 **Чат:**\n{chat_title}"
    kb = get_lead_keyboard(user_link, msg_link)

    # Отправляем всем пользователям бота
    recipients = get_all_users()
    for uid in recipients:
        try:
            increment_received(uid)
            await bot.send_message(uid, lead_message, reply_markup=kb, parse_mode="Markdown")
        except Exception as err:
            logging.error(f"Ошибка отправки пользователю {uid}: {err}")

# ==========================================
# 🚀 ЗАПУСК
# ==========================================
async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("🚀 Бот запущен! Добавьте его в группы для сбора сообщений.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
