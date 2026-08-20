import sys
import subprocess
import asyncio
import logging
import sqlite3
import re
from datetime import datetime

# Автоматическая проверка и установка зависимостей
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
# ⚙️ НАСТРОЙКИ И КЛЮЧИ
# ==========================================
BOT_TOKEN = "8313715983:AAGbi8TxcXuAgwDyFxiqj-0i7ze2CZvzl-w"
SUPPORT_USERNAME = "@serjantyabloko"

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

# Список отслеживаемых чатов
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
    "подскажите", "нужен мастер", "ищу мастера", "трубу", "протечка"
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

@dp.message(CommandStart())
@dp.message(F.text == "Перезапустить бота")
async def cmd_start(message: Message):
    get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or ""
    )
    text = (
        "Привет — это бот онлайн-запросов и заявок на услуги!\n\n"
        "🟢 **Статус:** Вечный доступ активен.\n"
        "Вы будете получать уведомления со всех подключенных ЖК-чатов."
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.message(F.text == "Инструкция")
async def cmd_instruction(message: Message):
    text = (
        "📚 **Инструкция:**\n\n"
        "1. Заявки приходят автоматически, как только кто-то пишет о проблеме в чате ЖК.\n"
        "2. Нажмите «Написать сообщение», чтобы написать клиенту в ЛС.\n"
        "3. Нажмите «Ссылка на сообщение», чтобы перейти к посту в группе."
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "Моя статистика")
async def cmd_stats(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name or "")
    received, processed = user[4], user[5]
    conversion = round((processed / received * 100), 1) if received > 0 else 0
    text = (
        "📊 **Ваша статистика:**\n\n"
        f"📥 **Получено запросов:** {received}\n"
        f"✅ **Обработано вами:** {processed}\n"
        f"🎯 **Конверсия:** {conversion}%\n"
        "♾ **Подписка:** Бессрочная (Безлимит)"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_(["Проверить подписку", "Активировать подписку"]))
async def cmd_subscription(message: Message):
    await message.answer("💳 **Статус доступа:**\n\n🟢 **Бессрочная подписка активна (Безлимит)**", parse_mode="Markdown")

@dp.message(F.text == "Поддержка")
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

# ==========================================
# 📡 МОНИТОРИНГ ЧАТОВ TELETHON
# ==========================================
client = TelegramClient("session_parser", API_ID, API_HASH)

async def start_parser():
    await client.start()
    me = await client.get_me()
    print(f"\n==========================================")
    print(f"✅ Telethon успешно вошел: {me.first_name} (@{me.username})")
    print(f"==========================================\n")

    monitored_ids = set()
    chat_titles = {}

    # Загружаем список всех диалогов аккаунта
    dialogs = await client.get_dialogs()
    for d in dialogs:
        username = getattr(d.entity, "username", None)
        title = getattr(d.entity, "title", str(d.id))
        real_id = get_peer_id(d.entity)

        # Проверяем совпадение по юзернейму или названию
        for target in MONITORED_CHATS:
            clean_target = target.replace("https://t.me/", "").replace("@", "").lower()
            if (username and username.lower() == clean_target) or (clean_target in title.lower()):
                monitored_ids.add(real_id)
                chat_titles[real_id] = title
                print(f"📡 Мониторинг активен для: {title} (ID: {real_id})")

    print(f"\nВсего подключено чатов для прослушивания: {len(monitored_ids)}\n")

    @client.on(events.NewMessage)
    async def incoming_message_handler(event):
        chat_id = get_peer_id(event.message.peer_id)

        # Если чат не из списка мониторинга, пропускаем
        if chat_id not in monitored_ids:
            return

        text = event.message.message or ""
        if not text:
            return

        text_lower = text.lower()
        matched = [k for k in KEYWORDS if k in text_lower]
        
        # Если ключевых слов нет, пропускаем
        if not matched:
            return

        chat_name = chat_titles.get(chat_id, "ЖК Чат")
        print(f"\n🎯 НАЙДЕНА ЗАЯВКА в [{chat_name}] (Ключи: {matched}):\n{text}\n")

        # Получаем данные автора
        sender = await event.get_sender()
        if getattr(sender, "username", None):
            user_link = f"https://t.me/{sender.username}"
        elif sender:
            user_link = f"tg://user?id={sender.id}"
        else:
            user_link = "https://t.me/telegram"

        chat_username = getattr(event.chat, "username", None)
        msg_link = f"https://t.me/{chat_username}/{event.message.id}" if chat_username else user_link

        lead_message = f"🔔 **Новая заявка:**\n\n{text}\n\n🗣 **Чат:** {chat_name}"
        kb = get_lead_keyboard(user_link, msg_link)

        recipients = get_all_users()
        if not recipients:
            print("⚠️ Нет пользователей в базе! Нажмите /start в боте.")

        for uid in recipients:
            try:
                increment_received(uid)
                await bot.send_message(uid, lead_message, reply_markup=kb, parse_mode="Markdown")
                print(f" Отправлено пользователю {uid}")
            except Exception as e:
                print(f"❌ Ошибка отправки пользователю {uid}: {e}")

# ==========================================
# 🚀 ЗАПУСК
# ==========================================
async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    asyncio.create_task(start_parser())
    print("🚀 Бот запущен! Ожидание сообщений...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
