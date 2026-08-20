import sys
import subprocess
import asyncio
import logging
import sqlite3
from datetime import datetime

# Установка зависимостей
def ensure_dependencies():
    packages = ["aiogram>=3.10.0", "telethon>=1.36.0"]
    for pkg in packages:
        pkg_name = pkg.split(">=")[0]
        try:
            __import__(pkg_name)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

ensure_dependencies()

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
from telethon import TelegramClient, events
from telethon.utils import get_peer_id

# ==========================================
# ⚙️ НАСТРОЙКИ
# ==========================================
BOT_TOKEN = "8313715983:AAGbi8TxcXuAgwDyFxiqj-0i7ze2CZvzl-w"
SUPPORT_USERNAME = "@serjantyabloko"

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

# 🔑 СПИСОК ID, КОМУ ВСЕГДА ПРИХОДЯТ ЗАЯВКИ (Ваш ID резервируется здесь)
# Если знаете свой точный числовой ID, можете вписать его: HARDCODED_ADMINS = [123456789]
HARDCODED_ADMINS = []

MONITORED_CHATS = [
    "zveni_chat", "zhk_zarechye_park", "ogni_jk", "krasnogorsk_Moscow",
    "perviyuzniy", "zelallei", "talisman_rokoss", "ChatPerovo",
    "yartsevskaya24", "pro_prokshino_chat", "zkliner", "yubitca12",
    "novoe_vidnoejk", "zagoryanka", "jkbuninskiekvartali", "Lermontovsky_54",
    "stal_online", "pervi_donskoy", "krasnogorskiy_nahabino", "michurpark",
    "jksimvol", "jkrimskiychatsobstvennikov", "pirogovskayariviera", "s_Les",
    "JkBrigantina", "yujnoe_bunino", "pb17faza", "ilpik", "Lybpark"
]

KEYWORDS = [
    "сантехника", "сантехник", "электрика", "электрик", "ремонт техники",
    "муж на час", "плиточник", "отделка", "полы", "стены", "окна", "двери",
    "плесень", "тараканы", "дезинфекция", "дератизация", "дезинсекция",
    "засор", "замыкание", "починить", "установить", "мастер", "посоветуйте",
    "подскажите", "нужен мастер", "ищу мастера", "тест"
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

def increment_received(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET received_leads = received_leads + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def increment_processed(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET processed_leads = processed_leads + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    db_users = [r[0] for r in rows]
    # Объединяем пользователей базы и встроенный список
    all_recipients = list(set(db_users + HARDCODED_ADMINS))
    return all_recipients

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

@dp.message(CommandStart())
@dp.message(F.text == "Перезапустить бота")
async def cmd_start(message: Message):
    get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or ""
    )
    if message.from_user.id not in HARDCODED_ADMINS:
        HARDCODED_ADMINS.append(message.from_user.id)

    print(f"👤 Новый активный пользователь: {message.from_user.full_name} (ID: {message.from_user.id})")

    text = (
        "Привет — это бот онлайн-запросов и заявок на услуги!\n\n"
        f"🟢 **Статус:** Вечный доступ активен.\n"
        f"🆔 Ваш ID: `{message.from_user.id}` (подключен к рассылке)\n\n"
        "Ожидайте заявок из чатов."
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.message(F.text == "Инструкция")
async def cmd_instruction(message: Message):
    await message.answer("📚 Бот автоматически находит сообщения по ключевым словам и пересылает их сюда.", parse_mode="Markdown")

@dp.message(F.text == "Моя статистика")
async def cmd_stats(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name or "")
    text = f"📊 **Статистика:**\n📥 Получено: {user[4]}\n✅ Обработано: {user[5]}"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_(["Проверить подписку", "Активировать подписку"]))
async def cmd_sub(message: Message):
    await message.answer("💳 **Статус:** 🟢 Бессрочный безлимитный доступ.", parse_mode="Markdown")

@dp.message(F.text == "Поддержка")
async def cmd_support(message: Message):
    await message.answer(f"🛠 Поддержка: {SUPPORT_USERNAME}")

@dp.callback_query(F.data == "process_lead_action")
async def callback_process_lead(call: CallbackQuery):
    increment_processed(call.from_user.id)
    await call.answer("✅ Отмечено!")

# ==========================================
# 📡 TELETHON ПАРСЕР
# ==========================================
client = TelegramClient("session_parser", API_ID, API_HASH)

async def start_parser():
    await client.start()
    me = await client.get_me()
    print(f"✅ Telethon вошел в аккаунт: {me.first_name} (@{me.username})")

    target_dialog_ids = set()
    chat_titles = {}

    dialogs = await client.get_dialogs()
    for d in dialogs:
        username = getattr(d.entity, "username", None)
        title = getattr(d.entity, "title", str(d.id))
        real_id = get_peer_id(d.entity)

        for target in MONITORED_CHATS:
            clean_target = target.replace("https://t.me/", "").replace("@", "").lower()
            if (username and username.lower() == clean_target) or (clean_target in title.lower()):
                target_dialog_ids.add(real_id)
                chat_titles[real_id] = title
                print(f"📡 Прослушивается чат: {title} [ID: {real_id}]")

    print(f"\n📊 Всего подключено чатов: {len(target_dialog_ids)}\n")

    # Обработка входящих сообщений (включая свои собственные для тестов)
    @client.on(events.NewMessage(incoming=None))
    async def parser_handler(event):
        try:
            chat_id = get_peer_id(event.message.peer_id)
            text = event.message.message or ""

            if not text or chat_id not in target_dialog_ids:
                return

            text_lower = text.lower()
            matched = [k for k in KEYWORDS if k in text_lower]

            if not matched:
                return

            chat_title = chat_titles.get(chat_id, "ЖК Чат")
            print(f"\n🔥 [НАЙДЕНА ЗАЯВКА] Чат: {chat_title} | Ключи: {matched}")
            print(f"Текст: {text}\n")

            sender = await event.get_sender()
            user_link = f"https://t.me/{sender.username}" if sender and getattr(sender, "username", None) else f"tg://user?id={event.sender_id}"
            chat_username = getattr(event.chat, "username", None)
            msg_link = f"https://t.me/{chat_username}/{event.message.id}" if chat_username else user_link

            lead_message = f"🔔 **Новая заявка:**\n\n{text}\n\n🗣 **Чат:** {chat_title}"
            kb = get_lead_keyboard(user_link, msg_link)

            recipients = get_all_users()
            print(f"👥 Отправка {len(recipients)} получателям...")

            for uid in recipients:
                try:
                    increment_received(uid)
                    await bot.send_message(uid, lead_message, reply_markup=kb, parse_mode="Markdown")
                    print(f"✅ Успешно доставлено на ID: {uid}")
                except Exception as send_err:
                    print(f"❌ Ошибка отправки пользователю {uid}: {send_err}")

        except Exception as e:
            print(f"❌ Ошибка внутри парсера: {e}")

# ==========================================
# 🚀 ЗАПУСК
# ==========================================
async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    asyncio.create_task(start_parser())
    print("🚀 Бот запущен в режиме ожидания!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
