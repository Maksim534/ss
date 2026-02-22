import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType
import asyncio


# === НАСТРОЙКИ ===
BOT_TOKEN = "8082248663:AAHwLh-RI-SKJkf3b7e-WeUjzkT31tOjYec"
ADMIN_GROUP_ID = -1003893913068  # ID группы, куда пересылать сообщения (должен быть отрицательным)
ADMIN_IDS = [8564427714, 222222222]  # Telegram ID админов, которые могут банить

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === БАЗА ДАННЫХ ===
def init_db():
    conn = sqlite3.connect('support.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  full_name TEXT,
                  banned INTEGER DEFAULT 0,
                  first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  group_msg_id INTEGER,   -- ID сообщения в админ-группе
                  user_msg_id INTEGER,    -- ID сообщения в личке с ботом
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
async def get_user(user_id):
    conn = sqlite3.connect('support.db')
    c = conn.cursor()
    c.execute("SELECT user_id, username, full_name, banned FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

async def add_or_update_user(user_id, username, full_name):
    conn = sqlite3.connect('support.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO users (user_id, username, full_name, banned)
                 VALUES (?, ?, ?, COALESCE((SELECT banned FROM users WHERE user_id=?), 0))''',
              (user_id, username, full_name, user_id))
    conn.commit()
    conn.close()

async def set_banned(user_id, banned):
    conn = sqlite3.connect('support.db')
    c = conn.cursor()
    c.execute("UPDATE users SET banned=? WHERE user_id=?", (1 if banned else 0, user_id))
    conn.commit()
    conn.close()

async def save_message_link(user_id, group_msg_id, user_msg_id):
    conn = sqlite3.connect('support.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages (user_id, group_msg_id, user_msg_id) VALUES (?, ?, ?)",
              (user_id, group_msg_id, user_msg_id))
    conn.commit()
    conn.close()

async def get_user_by_group_msg(group_msg_id):
    conn = sqlite3.connect('support.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM messages WHERE group_msg_id=?", (group_msg_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# === КОМАНДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ (личка) ===
@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: Message):
    await add_or_update_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    text = ("👋 Привет! Я бот поддержки. Напиши мне сообщение, и оно будет передано нашим специалистам.\n"
            "Они ответят тебе в ближайшее время.")
    await message.reply(text)

# === ОБРАБОТКА ЛИЧНЫХ СООБЩЕНИЙ ===
@dp.message(F.chat.type == "private")
async def handle_private_message(message: Message):
    user_id = message.from_user.id
    await add_or_update_user(user_id, message.from_user.username, message.from_user.full_name)

    # Проверка бана
    user = await get_user(user_id)
    if user and user[3] == 1:  # banned = 1
        await message.reply("❌ Вы заблокированы и не можете писать в поддержку.")
        return

    # Формируем подпись
    caption = f"📩 Новое сообщение от @{message.from_user.username or 'NoUsername'} ({user_id})\n\n{message.text or ''}"

    # Пересылаем в админ-группу с учётом типа контента
    if message.content_type != ContentType.TEXT:
        # Это медиа (фото, видео, документ и т.д.) – копируем с подписью
        sent = await message.copy_to(chat_id=ADMIN_GROUP_ID, caption=caption)
    else:
        # Текстовое сообщение – отправляем как есть с подписью
        sent = await bot.send_message(chat_id=ADMIN_GROUP_ID, text=caption)

    # Сохраняем связь
    await save_message_link(user_id, sent.message_id, message.message_id)

    # Подтверждение пользователю
    await message.reply("✅ Ваше сообщение отправлено администратору. Ожидайте ответа.")

# === ОБРАБОТКА СООБЩЕНИЙ В ГРУППЕ (ответы админов) ===
@dp.message(F.chat.id == ADMIN_GROUP_ID)
async def handle_group_reply(message: Message):
    if not message.reply_to_message:
        return  # отвечаем только на пересланные сообщения

    # Проверяем, что автор ответа - админ
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("❌ Только админ может отвечать.")
        return

    # Ищем, какому пользователю принадлежит исходное сообщение
    replied_msg_id = message.reply_to_message.message_id
    user_id = await get_user_by_group_msg(replied_msg_id)
    if not user_id:
        await message.reply("❌ Не удалось найти пользователя для этого сообщения.")
        return

    # Проверяем, не забанен ли пользователь
    user = await get_user(user_id)
    if user and user[3] == 1:
        await message.reply("❌ Этот пользователь заблокирован, ответ не будет отправлен.")
        return

    # Отправляем ответ пользователю
    try:
        await bot.send_message(chat_id=user_id, text=f"💬 Ответ от поддержки:\n\n{message.text}")
        await message.reply("✅ Ответ отправлен пользователю.")
    except Exception as e:
        await message.reply(f"❌ Ошибка при отправке: {e}")

# === КОМАНДЫ ДЛЯ АДМИНОВ В ГРУППЕ ===
@dp.message(Command("ban"), F.chat.id == ADMIN_GROUP_ID)
async def cmd_ban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    args = message.text.split()
    if len(args) < 2:
        # Пытаемся взять user_id из ответа
        if message.reply_to_message:
            replied_id = message.reply_to_message.message_id
            user_id = await get_user_by_group_msg(replied_id)
            if not user_id:
                await message.reply("❌ Не удалось определить пользователя.")
                return
        else:
            await message.reply("❌ Укажите ID пользователя или ответьте на его сообщение.\nПример: /ban 123456789")
            return
    else:
        try:
            user_id = int(args[1])
        except ValueError:
            await message.reply("❌ Неверный формат ID.")
            return

    await set_banned(user_id, True)
    await message.reply(f"✅ Пользователь {user_id} заблокирован.")

@dp.message(Command("unban"), F.chat.id == ADMIN_GROUP_ID)
async def cmd_unban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    args = message.text.split()
    if len(args) < 2:
        if message.reply_to_message:
            replied_id = message.reply_to_message.message_id
            user_id = await get_user_by_group_msg(replied_id)
            if not user_id:
                await message.reply("❌ Не удалось определить пользователя.")
                return
        else:
            await message.reply("❌ Укажите ID пользователя.")
            return
    else:
        try:
            user_id = int(args[1])
        except ValueError:
            await message.reply("❌ Неверный формат ID.")
            return

    await set_banned(user_id, False)
    await message.reply(f"✅ Пользователь {user_id} разблокирован.")

@dp.message(Command("stats"), F.chat.id == ADMIN_GROUP_ID)
async def cmd_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    conn = sqlite3.connect('support.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE banned=1")
    banned_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM messages")
    total_msgs = c.fetchone()[0]
    conn.close()

    await message.reply(f"📊 Статистика:\n"
                        f"Всего пользователей: {total_users}\n"
                        f"Заблокировано: {banned_users}\n"
                        f"Переслано сообщений: {total_msgs}")

# === ЗАПУСК ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
