import sys
import subprocess
import asyncio
import logging
import sqlite3
import re
from datetime import datetime

def ensure_dependencies():
    packages = ["aiogram>=3.10.0", "telethon>=1.36.0", "nltk>=3.8.1"]
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
from telethon.tl.functions.channels import JoinChannelRequest
from nltk.stem.snowball import SnowballStemmer

# Инициализация стеммера для русского языка
stemmer = SnowballStemmer("russian")

# ==========================================
# ⚙️ НАСТРОЙКИ
# ==========================================
BOT_TOKEN = "8313715983:AAGbi8TxcXuAgwDyFxiqj-0i7ze2CZvzl-w"
SUPPORT_USERNAME = "@serjantyabloko"

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

MONITORED_CHATS = [
    # Предыдущие чаты
    "zveni_chat", "zhk_zarechye_park", "ogni_jk", "krasnogorsk_Moscow",
    "perviyuzniy", "zelallei", "talisman_rokoss", "ChatPerovo",
    "yartsevskaya24", "pro_prokshino_chat", "zkliner", "yubitca12",
    "novoe_vidnoejk", "zagoryanka", "jkbuninskiekvartali", "Lermontovsky_54",
    "stal_online", "pervi_donskoy", "krasnogorskiy_nahabino", "michurpark",
    "jksimvol", "jkrimskiychatsobstvennikov", "pirogovskayariviera", "s_Les",
    "JkBrigantina", "yujnoe_bunino", "pb17faza", "ilpik", "Lybpark",
    "Ladozhsky_AVENIR", "jkkosmos", "Remont_T2", "Yamburg_citi",
    "jk_grafika", "svetlana_park_zhk", "civilization10house", "SevDolChat",
    "GarageSaleCivi", "domterra", "manufactura_james_beck", "jkyugtaun",
    "jkgrafikanavode", "aeronaut_home", "ZHKParadnyjansambl", "Pulse_Premier",
    "gkcolnetnii55", "jk_dubrovsky", "Gorodpervyh", "enfildnew",
    "zk_ehndfild", "zk_statusuparkapobedy", "rozhdestvenskijkvartal", "pleset10",
    "avtograf_centre", "dom_aviator", "aleksandrovskiykaskad", "yslugisuuny",
    "morskaja_naberezhnaja", "pikspbGK", "fsk_zoom", "jk_lybograd_kvs",
    "zk_schastie", "mv_home", "jkjivoyruchei", "chat_group_tandem",
    "zhk_galaktika", "PragmaCity_OD_3_20", "newohtachat", "byron_gk",
    "prim41", "nebo10sosedi", "akvilon_stories_akvilon", "Jk_UltraCity",
    "jk_forestakvilon", "jk_kan", "chatvolok", "alia_chat",
    "sakramentodobroe", "salpark56", "klenovie_allei", "GB1_GB2",
    "bluga", "Barakholka_Odintsovo", "bd_park","KvartalOnly", "zk_zilart", "rodnikimoskva", "oblaka20k2",
    "rasskazovo_sosedi", "Shagal_city", "remont_tp", "perviy_sheremetevskiy",
    "perovotg", "ostafievo", "UpSkolkovoRemont", "MyBasmanny",
    "poboltaem_ZV", "bigputilkovo", "pervyy_dubrovskiy", "chat_tinao_novaya_moskva",
    "jkmoskvichka77", "gkmoskvichka3", "simvol_26", "novie_kotelniki_chat",
    "sosedegorovo", "rasskazovo2", "onemay_chat", "mamochki_rama",
    "lovebalance", "Majdulin1991", "pyatnitskie_luga", "jk_geroev",
    "tp_park", "otrada_lesnaya_sosedi", "vniissok", "matveypark",
    "jk_michurinsky_park", "pulkovskiy2", "akvilonleaves", "devyatkinososedi",
    "GRAFORLOVSPB", "zhk_univercity", "respectpsk", "Parkolovocds",
    "czarscapital", "jk_morskaya_milya", "colorciti_10_26", "therechka",
    "paruschat", "mama_lyublino", "odi_v13", "samolet2021all",
    "uznaabitca", "kuntsevo_online", "gkleningradski", "Skandi_Klubb",
    "chekvartal", "pehra_bez_spama"
]
]

# Базовые корни/слова (стеммер сам найдет все формы: починить -> починил, чинит и т.д.)
KEYWORDS = [
    # 1. Холодильное оборудование
    "холодильник", "холодос", "морозилк", "морозильник", "ларь",
    
    # 2. Стиральные и сушильные машины
    "стиралк", "стиральн", "сушилк", "сушильн",
    
    # 3. Посудомоечные машины
    "посудомойк", "посудомоечн", "пмм",
    
    # 4. Плиты, панели и духовки
    "электроплит", "варочн", "индукцион", "индукц", "духовк", "плит",
    
    # 5. Сантехника и коммуникации
    "сантехник", "кран", "смесител", "сифон", "протечк", "протек", 
    "засор", "слив", "труб", "прочистк", "ванн", "унитаз", "раковин", "мусоропровод",
    
    # 6. Электрика
    "электрик", "проводк", "розетк", "автомат", "щиток", "замыкани",
    
    # 7. Специалисты и услуги
    "мастер", "специалист", "сборщик", "подключен", "установк", "диагностик", "ремонт", "работник",
    
    # 8. Действия и поломки
    "починить", "отремонтировать", "сломаться", "морозить", "течь", "намораживать", 
    "греть", "крутить", "включаться", "выбивать", "шуметь", "гудеть", "греметь", "гарь", "ошибк"
]

# Заранее стеммим ключевые слова для максимальной скорости
STEMMED_KEYWORDS = {stemmer.stem(kw) for kw in KEYWORDS}

def check_match(text: str) -> list[str]:
    """Проверяет совпадение текста по корням слов."""
    words = re.findall(r'\b[а-яёa-z0-9]+\b', text.lower())
    matched_stems = []
    
    for word in words:
        st = stemmer.stem(word)
        if st in STEMMED_KEYWORDS:
            matched_stems.append(word)
            
    return list(set(matched_stems))

# ==========================================
# 🗄 БАЗА ДАННЫХ
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
        f"🟢 **Статус:** Вечный доступ активен.\n"
        f"🆔 Ваш ID: `{message.from_user.id}` сохранён в базе рассылки.\n\n"
        "Заявки из подключенных чатов будут поступать сюда автоматически."
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.message(Command("test_broadcast"))
async def cmd_test(message: Message):
    users = get_all_users()
    await message.answer(f"🛠 Тест связи: в базе зарегистрировано {len(users)} получателей.")

@dp.message(F.text == "Инструкция")
async def cmd_instruction(message: Message):
    await message.answer("📚 Бот в реальном времени находит запросы по однокоренным словам и пересылает их сюда.", parse_mode="Markdown")

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
    print(f"\n==========================================")
    print(f"✅ Telethon успешно вошел: {me.first_name} (@{me.username})")
    print(f"==========================================\n")

    target_entities = []
    chat_titles = {}

    for chat_name in MONITORED_CHATS:
        clean_name = chat_name.replace("https://t.me/", "").replace("@", "").strip()
        try:
            entity = await client.get_entity(clean_name)
            try:
                await client(JoinChannelRequest(entity))
            except Exception:
                pass
            target_entities.append(entity)
            chat_titles[entity.id] = getattr(entity, "title", clean_name)
            print(f"📡 Активен мониторинг: {chat_titles[entity.id]}")
        except Exception as e:
            print(f"⚠️ Ошибка подключения @{clean_name}: {e}")

    print(f"\n Всего успешно подключено чатов: {len(target_entities)}\n")

    @client.on(events.NewMessage(chats=target_entities))
    async def lead_handler(event):
        try:
            text = event.message.message or ""
            if not text:
                return

            matched = check_match(text)
            if not matched:
                return

            chat_title = getattr(event.chat, "title", "ЖК Чат")
            print(f"\n🔥 [НАЙДЕНА ЗАЯВКА] Чат: {chat_title} | Найденные слова: {matched}")

            sender = await event.get_sender()
            if sender and getattr(sender, "username", None):
                user_link = f"https://t.me/{sender.username}"
            elif sender:
                user_link = f"tg://user?id={event.sender_id}"
            else:
                user_link = "https://t.me/telegram"

            chat_username = getattr(event.chat, "username", None)
            msg_link = f"https://t.me/{chat_username}/{event.message.id}" if chat_username else user_link

            lead_message = (
                f"🔔 **Новая заявка:**\n\n"
                f"{text}\n\n"
                f"🏷 **Ключевые слова:** {', '.join(matched)}\n"
                f"🗣 **Чат:** {chat_title}"
            )
            kb = get_lead_keyboard(user_link, msg_link)

            recipients = get_all_users()
            for uid in recipients:
                try:
                    increment_received(uid)
                    await bot.send_message(uid, lead_message, reply_markup=kb, parse_mode="Markdown")
                    print(f"✅ Доставлено получателю: {uid}")
                except Exception as err:
                    print(f"❌ Ошибка отправки пользователю {uid}: {err}")

        except Exception as ex:
            print(f"❌ Ошибка внутри обработчика: {ex}")

# ==========================================
# 🚀 ЗАПУСК
# ==========================================
async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    asyncio.create_task(start_parser())
    print("🚀 Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
