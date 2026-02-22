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
ADMIN_IDS = [8564427714]  # Твой Telegram ID

# Включаем логирование
logging.basicConfig(level=logging.INFO)

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
    c.execute('''CREATE TABLE IF NOT EXISTS admin_replies
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  admin_id INTEGER,
                  user_id INTEGER,
                  group_confirm_msg_id INTEGER UNIQUE,
                  user_reply_msg_id INTEGER,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    logging.info("Database initialized")

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
    logging.info(f"Saved message link: user {user_id}, group_msg {group_msg_id}, user_msg {user_msg_id}")

async def get_user_by_group_msg(group_msg_id):
    conn = sqlite3.connect('support.db')
    c = conn.cursor()
    c.execute("SELECT user_id, user_msg_id FROM messages WHERE group_msg_id=?", (group_msg_id,))
    row = c.fetchone()
    conn.close()
    logging.info(f"Looking for user by group msg {group_msg_id}: found {row}")
    return row if row else (None, None)

async def save_admin_reply(admin_id, user_id, group_confirm_msg_id, user_reply_msg_id):
    conn = sqlite3.connect('support.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO admin_replies (admin_id, user_id, group_confirm_msg_id, user_reply_msg_id) VALUES (?, ?, ?, ?)",
                  (admin_id, user_id, group_confirm_msg_id, user_reply_msg_id))
        conn.commit()
        logging.info(f"Saved admin reply: admin {admin_id}, user {user_id}, confirm {group_confirm_msg_id}, reply {user_reply_msg_id}")
    except Exception as e:
        logging.error(f"Error saving admin reply: {e}")
    finally:
        conn.close()

async def get_admin_reply_by_confirm(group_confirm_msg_id):
    conn = sqlite3.connect('support.db')
    c = conn.cursor()
    c.execute("SELECT admin_id, user_id, user_reply_msg_id FROM admin_replies WHERE group_confirm_msg_id=?", (group_confirm_msg_id,))
    row = c.fetchone()
    conn.close()
    logging.info(f"Looking for admin reply by confirm {group_confirm_msg_id}: found {row}")
    return row if row else (None, None, None)

async def delete_admin_reply_by_confirm(group_confirm_msg_id):
    conn = sqlite3.connect('support.db')
    c = conn.cursor()
    c.execute("DELETE FROM admin_replies WHERE group_confirm_msg_id=?", (group_confirm_msg_id,))
    conn.commit()
    conn.close()
    logging.info(f"Deleted admin reply for confirm {group_confirm_msg_id}")

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
@dp.message(Command("ban"), F.chat.id == ADMIN_GROUP_ID)
async def cmd_ban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    # ... (код без изменений, как в предыдущей версии)
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
    c.execute("SELECT COUNT(*) FROM admin_replies")
    replies = c.fetchone()[0]
    conn.close()
    await message.reply(f"📊 Статистика:\nВсего пользователей: {total}\nЗабанено: {banned}\nПереслано сообщений: {msgs}\nОтветов админов: {replies}")

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

# ========== КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ ОТВЕТАМИ (удаление/редактирование) ==========
@dp.message(Command("del"), F.chat.id == ADMIN_GROUP_ID)
async def cmd_del_reply(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение с подтверждением, которое хотите удалить.")
        return

    replied_id = message.reply_to_message.message_id
    admin_id, user_id, user_reply_msg_id = await get_admin_reply_by_confirm(replied_id)
    if not admin_id:
        await message.reply("❌ Это не подтверждение ответа или оно не найдено.")
        return

    try:
        await bot.delete_message(chat_id=user_id, message_id=user_reply_msg_id)
        user_delete_success = True
    except Exception:
        user_delete_success = False

    try:
        await message.reply_to_message.delete()
    except Exception:
        pass

    await delete_admin_reply_by_confirm(replied_id)

    if user_delete_success:
        await message.reply("✅ Сообщение удалено у пользователя и в группе.")
    else:
        await message.reply("⚠️ Сообщение в группе удалено, но у пользователя не удалось (возможно, слишком старое).")

@dp.message(Command("edit"), F.chat.id == ADMIN_GROUP_ID)
async def cmd_edit_reply(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение с подтверждением, которое хотите отредактировать.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Укажите новый текст после команды.\nПример: /edit Новый текст ответа")
        return
    new_text = args[1]

    replied_id = message.reply_to_message.message_id
    admin_id, user_id, user_reply_msg_id = await get_admin_reply_by_confirm(replied_id)
    if not admin_id:
        await message.reply("❌ Это не подтверждение ответа или оно не найдено.")
        return

    try:
        await bot.edit_message_text(chat_id=user_id, message_id=user_reply_msg_id, text=f"💬 Ответ от поддержки:\n\n{new_text}")
        user_edit_success = True
    except Exception as e:
        user_edit_success = False
        edit_error = str(e)

    try:
        await message.reply_to_message.edit_text(f"✅ Ответ отредактирован (новый текст отправлен).\n\nНовый текст: {new_text}")
    except Exception:
        pass

    if user_edit_success:
        await message.reply("✅ Сообщение отредактировано у пользователя и в группе.")
    else:
        await message.reply(f"❌ Не удалось отредактировать у пользователя: {edit_error}")

# ========== ОБРАБОТЧИК ОТВЕТОВ АДМИНОВ В ГРУППЕ (новые ответы) ==========
@dp.message(F.chat.id == ADMIN_GROUP_ID)
async def handle_group_reply(message: Message):
    if not message.reply_to_message or message.from_user.id not in ADMIN_IDS:
        return
    # Если это команда (уже проверили, но на всякий случай)
    if message.text and message.text.startswith('/'):
        return

    replied_id = message.reply_to_message.message_id
    user_id, user_msg_id = await get_user_by_group_msg(replied_id)
    if not user_id:
        await message.reply("❌ Не удалось найти пользователя. Возможно, это не входящее сообщение.")
        return

    user = await get_user(user_id)
    if user and user[3] == 1:
        await message.reply("❌ Пользователь заблокирован.")
        return

    try:
        # Отправляем ответ пользователю
        sent = await bot.send_message(
            chat_id=user_id,
            text=f"💬 Ответ от поддержки:\n\n{message.text}",
            reply_to_message_id=user_msg_id
        )
        # Отправляем подтверждение в группу
        confirm = await message.reply("✅ Ответ отправлен (с реплаем).")
        # Сохраняем связь между подтверждением и отправленным сообщением
        await save_admin_reply(message.from_user.id, user_id, confirm.message_id, sent.message_id)
    except Exception as e:
        await message.reply(f"❌ Ошибка при отправке: {e}")

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

    # 🔥 ЖЕСТКАЯ ПРОВЕРКА НА КОМАНДЫ
    # Проверяем текст или подпись на наличие слеша в начале
    text_to_check = message.text or message.caption or ''
    if text_to_check.startswith('/'):
        await message.reply("❌ Эта команда не поддерживается. Просто напишите сообщение, и администратор ответит вам.")
        return

    # Формируем подпись для админ-группы
    caption = f"📩 Новое сообщение от @{message.from_user.username or 'NoUsername'} ({user_id})"
    if message.caption:
        caption += f"\n\n{message.caption}"
    elif message.text:
        caption += f"\n\n{message.text}"

    # Пересылаем в группу
    try:
        if message.content_type != ContentType.TEXT:
            sent = await message.copy_to(chat_id=ADMIN_GROUP_ID, caption=caption)
        else:
            sent = await bot.send_message(chat_id=ADMIN_GROUP_ID, text=caption)

        await save_message_link(user_id, sent.message_id, message.message_id)
    except Exception as e:
        logging.error(f"Error forwarding message: {e}")
        await message.reply("❌ Произошла ошибка при отправке сообщения.")

# ========== ЗАПУСК ==========
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
