import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import CommandStart

TOKEN = "ВАШ_ТОКЕН_ОТ_BOTFATHER"
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Главное меню клавиатуры (как на скриншоте) ---
def get_main_keyboard():
    keyboard = [
        [KeyboardButton(text="Моя статистика")],
        [KeyboardButton(text="Инструкция"), KeyboardButton(text="Проверить подписку")],
        [KeyboardButton(text="Активировать подписку")],
        [KeyboardButton(text="Поддержка"), KeyboardButton(text="Перезапустить бота")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# --- Инлайн-кнопки под пересылаемыми заявками ---
def get_order_inline_keyboard(user_link: str, message_link: str):
    buttons = [
        [InlineKeyboardButton(text="Написать сообщение ↗", url=user_link)],
        [InlineKeyboardButton(text="Ссылка на сообщение ↗", url=message_link)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Команда /start и кнопка перезапуска
@dp.message(CommandStart())
@dp.message(F.text == "Перезапустить бота")
async def start_handler(message: Message):
    text = "Привет - это бот в котором приходят запросы в режиме онлайн!"
    await message.answer(text, reply_markup=get_main_keyboard())

# Раздел "Инструкция"
@dp.message(F.text == "Инструкция")
async def instruction_handler(message: Message):
    text = (
        "📚 **Инструкция по использованию:**\n\n"
        "1. **Обработка запросов:**\n"
        "- Используйте кнопку «Написать сообщение», чтобы связаться с автором запроса.\n"
        "- Используйте кнопку «Ссылка на сообщение», чтобы связаться с автором запроса через чат.\n\n"
        "2. **Статистика:**\n"
        "- Вы можете посмотреть свою статистику, нажав кнопку «Моя статистика».\n"
        "- Там отображается количество полученных и обработанных запросов.\n\n"
        "3. **Поддержка:**\n"
        "- Если у вас возникли вопросы, нажмите кнопку «Поддержка».\n\n"
        "4. **Перезапуск бота:**\n"
        "- Если бот работает некорректно, нажмите кнопку «Перезапустить бота».\n\n"
        "📌 **Важно:**\n"
        "- Пробный период длится 1 час.\n"
        "- После окончания потребуется оплатить подписку."
    )
    await message.answer(text, parse_mode="Markdown")

# Раздел "Моя статистика"
@dp.message(F.text == "Моя статистика")
async def stats_handler(message: Message):
    await message.answer(
        "📊 **Ваша статистика:**\n\n"
        "• Города мониторинга: Москва, Санкт-Петербург, Краснодар\n"
        "• Получено заявок: 14\n"
        "• Обработано: 3",
        parse_mode="Markdown"
    )

# Раздел "Проверить подписку" / "Активировать подписку"
@dp.message(F.text == "Проверить подписку")
@dp.message(F.text == "Активировать подписку")
async def sub_handler(message: Message):
    await message.answer(
        "💳 **Статус подписки:**\n\n"
        "Активен пробный период.\n"
        "Для продления выберите тариф или свяжитесь с поддержкой."
    )

# Раздел "Поддержка"
@dp.message(F.text == "Поддержка")
async def support_handler(message: Message):
    await message.answer("По всем вопросам обращайтесь к администратору: @username_admin")

# Пример отправки карточки заказа (эту функцию можно вызывать из парсера чатов)
async def send_lead_example(chat_id: int):
    post_text = (
        "Соседи, поделитесь контактом сантехника, пожалуйста 🙏\n\n"
        "🗣 **Чат:**\n"
        "Соседи ЖК Большое Путилково (Москва)"
    )
    kb = get_order_inline_keyboard(
        user_link="https://t.me/telegram", 
        message_link="https://t.me/telegram"
    )
    await bot.send_message(chat_id, post_text, reply_markup=kb, parse_mode="Markdown")

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
