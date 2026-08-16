import asyncio
import logging
import sqlite3
import re
from datetime import datetime, timedelta

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
# ⚙️ НАСТРОЙКИ (КОНФИГУРАЦИЯ)
# ==========================================
BOT_TOKEN = "8313715983:AAGbi8TxcXuAgwDyFxiqj-0i7ze2CZvzl-w"
SUPPORT_USERNAME = "@your_support_username"  # Юзернейм поддержки
TRIAL_DAYS = 3  # Длительность пробного периода в днях

# Данные от my.telegram.org для чтения чатов
API_ID = 12345678  # Вставьте ваш API_ID (число)
API_HASH = "ВАШ_API_HASH"  # Вставьте ваш API_HASH (строка)

AVAILABLE_CITIES = ["Москва", "Санкт-Петербург", "Краснодар"]

# 📌 СПИСОК ЧАТОВ ДЛЯ МОНИТОРИНГА
# Можно указывать: @username чата, ссылку t.me/joinchat/... или публичную ссылку https://t.me/...
MONITORED_CHATS = [
    {"link": "https://t.me/chat_msk_example", "city": "Москва", "title": "ЖК Пригород Лесное"},
    {"link": "https://t.me/chat_spb_example", "city": "Санкт-Петербург", "title": "ЖК Шуваловский"},
    {"link": "https://t.me/chat_krd_example", "city": "Краснодар", "title": "ЖК Панорама"},
]

# 🔍 Ключевые слова для поиска заявок
KEYWORDS = [
    "сантехник", "электрик", "плиточник", "мастер", "ремонт", "починить",
    "уборка", "клининг", "сборка", "установить", "протек", "замок",
    "кондиционер", "подскажите мастера", "нужен мастер", "посоветуйте мастера"
]

# ==========================================
# 🗄 РАБОТА С БАЗОЙ ДАННЫХ (SQLite)
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
    """Возвращает пользователей города, у которых действует подписка или триал"""
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
# 🤖 AIOGRAM (ОСНОВНОЙ БОТ)
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
        "- Используйте кнопку «Написать сообщение», чтобы связаться с автором запроса напрямую.\n"
        "- Используйте кнопку «Ссылка на сообщение», чтобы перейти к исходному посту в ЖК-чате.\n\n"
        "2. **Статистика:**\n"
        "- В разделе «Моя статистика» отображается количество полученных и обработанных вами запросов.\n\n"
        "3. **Поддержка:**\n"
        "- Если у вас возникли вопросы или ошибки, воспользуйтесь кнопкой «Поддержка».\n\n"
        "4. **Перезапуск бота:**\n"
        "- Для обновления меню или смены города нажмите «Перезапустить бота».\n\n"
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
        days, hours = rem_sec // 86400, (rem_sec % 86400) // 3600
        sub_status = f"🟡 **Активен пробный период** (осталось {days} дн. {hours} ч.)"
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
    await call.answer("✅ Отмечено в статистике!", show_alert=False)
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
# 📡 TELETHON (ПАРСЕР И ПЕРЕСЫЛЬЩИК СООБЩЕНИЙ)
# ==========================================
client = TelegramClient("session_parser", API_ID, API_HASH)

async def start_parser():
    # Автоматически вступаем во все указанные чаты
    await client.start()
    print("📡 Подключение парсера к чатам...")
    
    target_dialog_ids = []
    chat_city_map = {}
    chat_title_map = {}

    for item in MONITORED_CHATS:
        try:
            entity = await client.get_entity(item["link"])
            target_dialog_ids.append(entity.id)
            chat_city_map[entity.id] = item["city"]
            chat_title_map[entity.id] = item.get("title") or getattr(entity, "title", "ЖК Чат")
            print(f"✅ Мониторинг подключен: {chat_title_map[entity.id]} ({item['city']})")
        except Exception as e:
            print(f"⚠️ Не удалось подключиться к {item['link']}: {e}")

    @client.on(events.NewMessage(chats=target_dialog_ids))
    async def handler(event):
        text = event.message.message or ""
        text_lower = text.lower()

        # Проверяем наличие ключевых слов
        if not any(k in text_lower for k in KEYWORDS):
            return

        chat_id = event.chat_id
        city = chat_city_map.get(chat_id, "Москва")
        chat_title = chat_title_map.get(chat_id, "ЖК Чат")

        # Формируем ссылку на автора
        sender = await event.get_sender()
        if getattr(sender, "username", None):
            user_link = f"https://t.me/{sender.username}"
        else:
            user_link = f"tg://user?id={event.sender_id}"

        # Формируем ссылку на сообщение
        chat_username = getattr(event.chat, "username", None)
        if chat_username:
            msg_link = f"https://t.me/{chat_username}/{event.message.id}"
        else:
            msg_link = user_link

        lead_message = (
            f"{text}\n\n"
            f"🗣 **Чат:**\n"
            f"{chat_title} ({city})"
        )
        kb = get_lead_keyboard(user_link, msg_link)

        # Рассылаем всем активным пользователям этого города
        recipients = get_active_users_by_city(city)
        for uid in recipients:
            try:
                increment_received(uid)
                await bot.send_message(uid, lead_message, reply_markup=kb, parse_mode="Markdown")
            except Exception as err:
                logging.error(f"Ошибка отправки {uid}: {err}")

# ==========================================
# 🚀 ЗАПУСК СИСТЕМЫ
# ==========================================
async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    
    # Запускаем парсер чатов параллельно с ботом
    await start_parser()
    print("🚀 Бот и Парсер успешно запущены!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
