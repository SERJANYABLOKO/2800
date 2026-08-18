import sys
import subprocess
import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta

# Автоматическая проверка и доустановка зависимостей при старте
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

# ==========================================
# ⚙️ ВАШИ ДАННЫЕ И НАСТРОЙКИ
# ==========================================
BOT_TOKEN = "8313715983:AAGbi8TxcXuAgwDyFxiqj-0i7ze2CZvzl-w"
SUPPORT_USERNAME = "@your_support_username"  # Укажите ваш юзернейм техподдержки
TRIAL_DAYS = 3  # Бесплатный период (3 дня)

# Telethon API (получите на my.telegram.org)
API_ID = 12345678          # Вставьте ваш API ID (число)
API_HASH = "ВАШ_API_HASH"  # Вставьте ваш API Hash (строка)

AVAILABLE_CITIES = ["Москва", "Санкт-Петербург", "Краснодар"]

# 📍 СПИСОК ЧАТОВ ИЗ СКРИНШОТОВ
MONITORED_CHATS = [
    {"link": "https://t.me/gk_mtvpark", "city": "Москва", "title": "ЖК Матвеевский парк"},
    {"link": "https://t.me/ZK_Aerobus", "city": "Москва", "title": "ЖК Аэробус"},
    {"link": "https://t.me/vniissok", "city": "Москва", "title": "Дубки (ВНИИССОК)"},
    {"link": "https://t.me/zelallei", "city": "Москва", "title": "ЖК Зеленые аллеи"},
    {"link": "https://t.me/salarevoparkzhk", "city": "Москва", "title": "ЖК Саларьево парк"},
    {"link": "https://t.me/kupiprodaygkpk", "city": "Краснодар", "title": "Купи-продай / Объявления"},
    {"link": "https://t.me/fsk_zoom", "city": "Санкт-Петербург", "title": "ЖК Zoom на Неве"},
]

# 🔍 КАТЕГОРИИ И КЛЮЧЕВЫЕ СЛОВА ИЗ СКРИНШОТОВ
KEYWORDS = [
    "сантехника", "сантехник", "электрика", "электрик", "ремонт техники",
    "муж на час", "плиточник", "отделка", "полы", "стены", "окна", "двери",
    "плесень", "тараканы", "дезинфекция", "дератизация", "дезинсекция",
    "засор", "замыкание", "починить", "установить", "мастер"
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
            city TEXT DEFAULT 'Москва',
            registered_at TIMESTAMP,
            received_leads INTEGER DEFAULT 0,
            processed_leads INTEGER DEFAULT 0,
            is_subscribed INTEGER DEFAULT 0
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

def update_user_city(user_id: int, city: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET city = ? WHERE user_id = ?", (city, user_id))
    conn.commit()
    conn.close()

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

def get_active_users_by_city(city: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, registered_at, is_subscribed FROM users WHERE city = ?", (city,))
    rows = cursor.fetchall()
    conn.close()
    
    active_ids = []
    now = datetime.now()
    for uid, reg_time_str, is_sub in rows:
        if is_sub:
            active_ids.append(uid)
            continue
        try:
            reg_time = datetime.fromisoformat(reg_time_str)
            if now < reg_time + timedelta(days=TRIAL_DAYS):
                active_ids.append(uid)
        except Exception:
            pass
    return active_ids

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

def get_city_selection_keyboard():
    buttons = [
        [InlineKeyboardButton(text=f"📍 {c}", callback_data=f"set_city:{c}")] for c in AVAILABLE_CITIES
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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
    user = get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or ""
    )
    current_city = user[3]
    text = (
        "Привет - это бот в котором приходят запросы в режиме онлайн!\n\n"
        f"📍 Ваш текущий город: **{current_city}**\n"
        "Вы можете изменить город в любой момент, нажав кнопку ниже:"
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    await message.answer("Выберите город для получения заявок:", reply_markup=get_city_selection_keyboard())

@dp.callback_query(F.data.startswith("set_city:"))
async def callback_set_city(call: CallbackQuery):
    city = call.data.split(":")[1]
    update_user_city(call.from_user.id, city)
    await call.message.edit_text(f"✅ Город успешно изменен на: **{city}**", parse_mode="Markdown")
    await call.answer()

@dp.message(F.text == "Инструкция")
async def cmd_instruction(message: Message):
    text = (
        "📚 **Инструкция по использованию:**\n\n"
        "1. **Обработка запросов:**\n"
        "- Используйте кнопку «Написать сообщение», чтобы связаться с автором напрямую.\n"
        "- Используйте кнопку «Ссылка на сообщение», чтобы перейти к посту в ЖК-чате.\n\n"
        "2. **Статистика:**\n"
        "- В разделе «Моя статистика» отображается количество полученных и обработанных запросов.\n\n"
        "3. **Поддержка:**\n"
        "- При возникновении вопросов нажмите кнопку «Поддержка».\n\n"
        "4. **Перезапуск бота:**\n"
        "- Для смены города или обновления меню нажмите «Перезапустить бота».\n\n"
        "📌 **Важно:**\n"
        f"- Пробный период длится {TRIAL_DAYS} дня с момента первого запуска.\n"
        "- После окончания пробного периода необходимо активировать подписку."
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "Моя статистика")
async def cmd_stats(message: Message):
    user = get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or ""
    )
    city, received, processed = user[3], user[5], user[6]
    conversion = round((processed / received * 100), 1) if received > 0 else 0
    text = (
        "📊 **Ваша статистика:**\n\n"
        f"📍 **Выбранный город:** {city}\n"
        f"📥 **Получено запросов:** {received}\n"
        f"✅ **Обработано вами:** {processed}\n"
        f"🎯 **Конверсия:** {conversion}%"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_(["Проверить подписку", "Активировать подписку"]))
async def cmd_subscription(message: Message):
    user = get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or ""
    )
    try:
        reg_time = datetime.fromisoformat(user[4])
    except Exception:
        reg_time = datetime.now()

    is_paid = bool(user[7])
    trial_end = reg_time + timedelta(days=TRIAL_DAYS)
    now = datetime.now()

    if is_paid:
        sub_status = "🟢 **Платная подписка активна (Безлимит)**"
    elif now < trial_end:
        rem_sec = int((trial_end - now).total_seconds())
        days = rem_sec // 86400
        hours = (rem_sec % 86400) // 3600
        minutes = (rem_sec % 3600) // 60
        time_left_str = f"{days} дн. {hours} ч." if days > 0 else f"{hours} ч. {minutes} мин."
        sub_status = f"🟡 **Активен пробный период** (осталось {time_left_str})"
    else:
        sub_status = "🔴 **Пробный период завершен.** Заявки приостановлены."

    text = f"💳 **Статус доступа:**\n\n{sub_status}\n\nДля продления напишите: {SUPPORT_USERNAME}"
    await message.answer(text, parse_mode="Markdown")

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

@dp.message(Command("test_lead"))
async def cmd_test_lead(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name or "")
    city = user[3]
    lead_text = f"Соседи, подскажите хорошего сантехника пожалуйста 🙏\n\n🗣 **Чат:**\nЖК Матвеевский парк ({city})"
    kb = get_lead_keyboard("https://t.me/telegram", "https://t.me/telegram")
    increment_received(message.from_user.id)
    await message.answer(lead_text, reply_markup=kb, parse_mode="Markdown")

# ==========================================
# 📡 МОНИТОРИНГ ЧАТОВ TELETHON
# ==========================================
client = None
if API_ID != 12345678 and API_HASH != "ВАШ_API_HASH":
    client = TelegramClient("session_parser", API_ID, API_HASH)

async def start_parser():
    if not client:
        return
    await client.start()
    print("📡 Telethon клиент запущен и подключен.")

    target_dialog_ids = []
    chat_city_map = {}
    chat_title_map = {}

    for item in MONITORED_CHATS:
        try:
            entity = await client.get_entity(item["link"])
            target_dialog_ids.append(entity.id)
            chat_city_map[entity.id] = item["city"]
            chat_title_map[entity.id] = item.get("title") or getattr(entity, "title", "ЖК Чат")
        except Exception as e:
            logging.error(f"Не удалось подключить чат {item['link']}: {e}")

    @client.on(events.NewMessage(chats=target_dialog_ids))
    async def message_filter(event):
        text = event.message.message or ""
        text_lower = text.lower()

        if not any(k in text_lower for k in KEYWORDS):
            return

        chat_id = event.chat_id
        city = chat_city_map.get(chat_id, "Москва")
        chat_title = chat_title_map.get(chat_id, "ЖК Чат")

        sender = await event.get_sender()
        if getattr(sender, "username", None):
            user_link = f"https://t.me/{sender.username}"
        else:
            user_link = f"tg://user?id={event.sender_id}"

        chat_username = getattr(event.chat, "username", None)
        msg_link = f"https://t.me/{chat_username}/{event.message.id}" if chat_username else user_link
        lead_message = f"{text}\n\n🗣 **Чат:**\n{chat_title} ({city})"
        kb = get_lead_keyboard(user_link, msg_link)

        recipients = get_active_users_by_city(city)
        for uid in recipients:
            try:
                increment_received(uid)
                await bot.send_message(uid, lead_message, reply_markup=kb, parse_mode="Markdown")
            except Exception as err:
                logging.error(f"Ошибка отправки: {err}")

# ==========================================
# 🚀 ЗАПУСК
# ==========================================
async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    
    if client:
        asyncio.create_task(start_parser())
        
    print("🚀 Бот успешно запущен на Railway!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
