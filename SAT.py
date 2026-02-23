import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import google.generativeai as genai

# === НАСТРОЙКИ ===
# Сюда вставь свои ключи (лучше использовать переменные окружения)
BOT_TOKEN = "твой_токен_бота"
GEMINI_API_KEY = "AIzaSyB158tLvLJJ4S8vSm6pcTIJzuOryinun2A"  # Твой ключ

# Настраиваем Gemini
genai.configure(api_key=GEMINI_API_KEY)
# Используем модель gemini-pro (для текста)
model = genai.GenerativeModel('gemini-pro')

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.reply(
        "👋 Привет! Я бот на базе Google Gemini.\n"
        "Просто напиши мне что-нибудь, и я отвечу."
    )

# Обработчик всех текстовых сообщений
@dp.message()
async def handle_message(message: types.Message):
    # Показываем, что бот печатает
    await bot.send_chat_action(message.chat.id, action="typing")
    
    try:
        # Отправляем запрос в Gemini
        response = model.generate_content(message.text)
        
        # Получаем текст ответа
        reply_text = response.text
        
        # Если ответ слишком длинный, Telegram может ругаться, но обычно ок
        await message.reply(reply_text)
        
    except Exception as e:
        logging.error(f"Ошибка при обращении к Gemini: {e}")
        await message.reply("❌ Произошла ошибка при обработке запроса. Попробуй позже.")

# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
