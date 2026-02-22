import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ContentType
from aiogram.utils.keyboard import InlineKeyboardBuilder

# === НАСТРОЙКИ ===
BOT_TOKEN = "8082248663:AAHwLh-RI-SKJkf3b7e-WeUjzkT31tOjYec"
ADMIN_GROUP_ID = -1003893913068  # ID группы (отрицательное)
ADMIN_IDS = [8564427714]  # Твой Telegram ID (можно добавить ещё через запятую)

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
                  group_msg_id INTEGER,
                  user_msg_id INTEGER,
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
    c.execute("SELECT user_id, user_msg_id FROM messages WHERE group_msg_id=?", (group_msg_id,))
    row = c.fetchone()
    conn.close()
    return row if row else (None, None)

async def get_all_users(banned=False):
    conn = sqlite3.connect('support.db')
    c = conn.cursor()
    if banned:
        c.execute("SELECT user_id FROM users WHERE banned=1")
    else:
        c.execute("SELECT user_id FROM users WHERE banned=0")
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

# ========== КОМАНДЫ ДЛЯ АДМИНОВ (работают только в группе) ==========
# Эти хэндлеры должны быть первыми, чтобы перехватывать команды до общего обработчика

@dp.message(Command("ban"), F.chat.id == ADMIN_GROUP_ID)
async def cmd_ban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    args = message.text.split()
    if len(args) < 2:
        if message.reply_to_message:
            replied_id = message.reply_to_message.message_id
            user_id, _ = await get_user_by_group_msg(replied_id)
            if not user_id:
                await message.reply("❌ Не удалось определить пользователя.")
                return
        else:
            await message.reply("❌ Укажите ID или ответьте на сообщение.\nПример: /ban 123456789")
            return
    else:
        try:
            user_id = int(args[1])
        except ValueError:
            await message.reply("❌ Неверный ID.")
            return

    await set_banned(user_id, True)
    await message.reply(f"✅ Пользователь {user_id} забанен.")

@dp.message(Command("unban"), F.chat.id == ADMIN_GROUP_ID)
async def cmd_unban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    args = message.text.split()
    if len(args) < 2:
        if message.reply_to_message:
            replied_id = message.reply_to_message.message_id
            user_id, _ = await get_user_by_group_msg(replied_id)
            if not user_id:
                await message.reply("❌ Не удалось определить пользователя.")
                return
        else:
            await message.reply("❌ Укажите ID.")
            return
    else:
        try:
            user_id = int(args[1])
        except ValueError:
            await message.reply("❌ Неверный ID.")
            return

    await set_banned(user_id, False)
    await message.reply(f"✅ Пользователь {user_id} разбанен.")

@dp.message(Command("stats"), F.chat.id == ADMIN_GROUP_ID)
async def cmd_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    conn = sqlite3.connect('support.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE banned=1")
    banned = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM messages")
    msgs = c.fetchone()[0]
    conn.close()

    await message.reply(f"📊 Статистика:\nВсего: {total}\nЗабанено: {banned}\nСообщений: {msgs}")

@dp.message(Command("broadcast"), F.chat.id == ADMIN_GROUP_ID)
async def cmd_broadcast(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Укажите текст рассылки.\nПример: /broadcast Всем привет!")
        return

    text = args[1]
    users = await get_all_users(banned=False)
    if not users:
        await message.reply("❌ Нет активных пользователей для рассылки.")
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"broadcast_confirm|{message.message_id}")
    builder.button(text="❌ Отмена", callback_data="broadcast_cancel")
    await message.reply(
        f"📢 Будет отправлено **{len(users)}** пользователям.\n\nТекст:\n{text}",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith("broadcast_"))
async def broadcast_callback(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id not in ADMIN_IDS:
        return

    if callback.data == "broadcast_cancel":
        await callback.message.edit_text("❌ Рассылка отменена.")
        return

    if callback.data.startswith("broadcast_confirm|"):
        original_text = callback.message.text
        if "\n\nТекст:\n" in original_text:
            text = original_text.split("\n\nТекст:\n", 1)[1]
        else:
            await callback.message.edit_text("❌ Не удалось извлечь текст.")
            return

        users = await get_all_users(banned=False)
        if not users:
            await callback.message.edit_text("❌ Нет пользователей.")
            return

        await callback.message.edit_text(f"📢 Начинаю рассылку {len(users)} пользователям...")

        success = 0
        fail = 0
        for uid in users:
            try:
                await bot.send_message(uid, f"📢 Рассылка:\n\n{text}")
                success += 1
                await asyncio.sleep(0.05)
            except Exception:
                fail += 1

        await callback.message.edit_text(
            f"✅ Рассылка завершена.\n"
            f"Успешно: {success}\n"
            f"Не удалось: {fail}"
        )

# ========== ОБРАБОТЧИК ОТВЕТОВ АДМИНОВ В ГРУППЕ ==========
# Этот хэндлер сработает только на сообщения, которые не являются командами (потому что команды уже отловлены выше)
@dp.message(F.chat.id == ADMIN_GROUP_ID)
async def handle_group_reply(message: Message):
    # Проверяем, что это ответ на какое-то сообщение и автор - админ
    if not message.reply_to_message or message.from_user.id not in ADMIN_IDS:
        return

    replied_id = message.reply_to_message.message_id
    user_id, user_msg_id = await get_user_by_group_msg(replied_id)
    if not user_id:
        await message.reply("❌ Не удалось найти пользователя.")
        return

    user = await get_user(user_id)
    if user and user[3] == 1:
        await message.reply("❌ Пользователь заблокирован.")
        return

    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"💬 Ответ от поддержки:\n\n{message.text}",
            reply_to_message_id=user_msg_id
        )
        await message.reply("✅ Ответ отправлен (с реплаем).")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

# ========== ОБРАБОТЧИКИ ЛИЧНЫХ СООБЩЕНИЙ ==========
@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: Message):
    await add_or_update_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    text = ("👋 Привет! Я бот поддержки. Напиши мне сообщение, и оно будет передано нашим специалистам.\n"
            "Они ответят тебе в ближайшее время.")
    await message.reply(text)

@dp.message(F.chat.type == "private")
async def handle_private_message(message: Message):
    user_id = message.from_user.id
    await add_or_update_user(user_id, message.from_user.username, message.from_user.full_name)

    user = await get_user(user_id)
    if user and user[3] == 1:
        await message.reply("❌ Вы заблокированы и не можете писать в поддержку.")
        return

    caption = f"📩 Новое сообщение от @{message.from_user.username or 'NoUsername'} ({user_id})\n\n{message.text or ''}"

    if message.content_type != ContentType.TEXT:
        sent = await message.copy_to(chat_id=ADMIN_GROUP_ID, caption=caption)
    else:
        sent = await bot.send_message(chat_id=ADMIN_GROUP_ID, text=caption)

    await save_message_link(user_id, sent.message_id, message.message_id)

# ========== ЗАПУСК ==========
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
