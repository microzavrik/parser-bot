import sqlite3
import asyncio
import random
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Создание объекта MemoryStorage
storage = MemoryStorage()

class States(StatesGroup):
    AddUser = State()
    EditWelcomeText = State()
    SendNotification = State()
    RemoveUser = State()

# Initialize Telegram bot
bot = Bot(token="6111072997:AAHmDAZopomqrJHp1XTPFyDkUHaiZO3zyAc")
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Connect to SQLite database
conn = sqlite3.connect('user_data.db')
cur = conn.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER, username TEXT, access_type TEXT)')
conn.commit()

last_pos = 0
admins = [5934596933, 421579111, 709325748]  # Place your admin user ID here

def load_welcome_text():
    with open("welcome_text.txt", "r") as file:
        return file.read()

# Сохранение нового текста приветствия в файл welcome_text.txt
def save_welcome_text(new_welcome_text):
    with open("welcome_text.txt", "w") as file:
        file.write(new_welcome_text)

async def notify_users(new_lines):
    for user_id, access_type in cur.execute('SELECT telegram_id, access_type FROM users WHERE access_type = ?', ("True",)):
        try:
            for line in new_lines:
                tokens, protocol, times, wallets, supply = line.split(' | ')

                if int(times) >= 2000:
                    message = f"🔹 Tokens: {tokens}\n🔸 Protocol: {protocol}\n⏰ Times: {times}\n💼 Wallets: {wallets}\n💰 Supply: {supply}\n⚠️ High activity detected!"
                elif int(times) >= 500:
                    message = f"🔹 Tokens: {tokens}\n🔸 Protocol: {protocol}\n⏰ Times: {times}\n💼 Wallets: {wallets}\n💰 Supply: {supply}"
                else:
                    continue

                inline_btn = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(text='Link to BtcTool ⚡️', url='https://www.btctool.pro/hot-mint'))
                await bot.send_message(user_id, message, disable_web_page_preview=True, reply_markup=inline_btn)
        except Exception as e:
            print(f"Error sending message to user {user_id}: {e}")

async def main():
    global last_pos
    while True:
        with open('times.txt', 'r') as file:
            file.seek(last_pos)
            new_lines = file.readlines()
            if new_lines:
                await notify_users(new_lines)
                last_pos = file.tell()

        await asyncio.sleep(1)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username

    cur.execute('SELECT * FROM users WHERE telegram_id = ?', (user_id,))
    existing_user = cur.fetchone()

    if not existing_user:
        cur.execute('INSERT INTO users (telegram_id, username, access_type) VALUES (?, ?, ?)', (user_id, username, "False"))  # Set default access_type to "False"
        conn.commit()

    # Отправка приветственного сообщения из файла
    welcome_text = load_welcome_text()
    await message.answer(welcome_text)

@dp.callback_query_handler(lambda query: query.from_user.id in admins, text='view_all_users')
async def view_all_users_handler(callback_query: types.CallbackQuery):
    access_types = {"True": "✅", "False": "❌"}  # Символы для обозначения доступа
    user_list = []

    for row in cur.execute('SELECT username, access_type FROM users ORDER BY access_type DESC'):
        user_id, access_type = row
        access_symbol = access_types.get(access_type, "❓")
        user_list.append(f"Username: {user_id} | Access:  {access_symbol}")

    total_users = len(user_list)
    users_with_access = sum(1 for row in cur.execute('SELECT 1 FROM users WHERE access_type = "True"'))

    text = f"Total Users: {total_users}\nUsers with Access: {users_with_access}\n\n" + "\n".join(user_list)
    
    await bot.send_message(callback_query.from_user.id, text)

# Добавляем кнопку в админ-панель для удаления пользователя
@dp.message_handler(lambda message: message.from_user.id in admins, commands=['admin'])
async def admin_panel(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Add User 👤", callback_data="add_user"),
         InlineKeyboardButton("Remove User ❌", callback_data="remove_user"),
        InlineKeyboardButton("Set Welcome Text ✏️", callback_data="edit_welcome_text"),
        InlineKeyboardButton("Send Notification 🔔", callback_data="send_notification"),
        InlineKeyboardButton("View All Users 👥", callback_data="view_all_users")
    )
    await message.answer("🕵️‍♂️ You are logged into the admin panel", reply_markup=keyboard)

@dp.callback_query_handler(lambda query: query.from_user.id in admins, text='remove_user')
async def remove_user_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await States.RemoveUser.set()
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.answer("Please provide the Telegram username of the user to remove.")

# Обработчик для удаления пользователя
@dp.message_handler(lambda message: message.from_user.id in admins, state=States.RemoveUser)
async def remove_user_input(message: types.Message, state: FSMContext):
    username = message.text

    cur.execute('SELECT telegram_id FROM users WHERE username = ?', (username,))
    row = cur.fetchone()

    if row:
        user_id = row[0]
        
        cur.execute('UPDATE users SET access_type = ? WHERE telegram_id = ?', ("False", user_id))
        conn.commit()

        await message.reply(f"User with username {username} has been removed.")
    
    else:
        await message.reply(f"User with username {username} not found in the database.")

    await state.finish()


@dp.callback_query_handler(lambda query: query.from_user.id in admins, text='send_notification')
async def send_notification_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.answer("Please enter the notification message to send to all users.")

    await States.SendNotification.set()

@dp.message_handler(state=States.SendNotification)
async def send_notification_to_users(message: types.Message, state: FSMContext):
    notification_message = message.text

    for user_id, _ in cur.execute('SELECT telegram_id, access_type FROM users'):
        try:
            await bot.send_message(user_id, notification_message)
        except Exception as e:
            print(f"Error sending notification to user {user_id}: {e}")

    await message.reply("Notification sent to all users.")

    await state.finish()

# Обработчик "Edit Welcome Text"
@dp.callback_query_handler(lambda query: query.from_user.id in admins, text='edit_welcome_text')
async def edit_welcome_text_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await States.EditWelcomeText.set()
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.answer("Please enter the new welcome text.")

# Обработчик ввода текста для редактирования приветственного сообщения
@dp.message_handler(state=States.EditWelcomeText)
async def edit_welcome_text_input(message: types.Message, state: FSMContext):
    save_welcome_text(message.text)
    
    await message.reply("Welcome text updated successfully.")

    await state.finish()

# Обновленный обработчик "Add User"
@dp.callback_query_handler(lambda query: query.from_user.id in admins, text='add_user')
async def add_user_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await States.AddUser.set()
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.answer("Please provide the Telegram username of the user to add.")

# Обработчик ввода текста
@dp.message_handler(state=States.AddUser)
async def add_user_input(message: types.Message, state: FSMContext):
    username = message.text

    # Поиск telegram_id по username в базе данных
    cur.execute('SELECT telegram_id FROM users WHERE username = ?', (username,))
    row = cur.fetchone()
    
    if row:
        user_id = row[0]
        
        # Обновляем данные пользователя в базе данных
        cur.execute('UPDATE users SET access_type = ? WHERE telegram_id = ?', ("True", user_id))
        conn.commit()

        await message.reply(f"User with username {username} has been granted access.")
    
    else:
        await message.reply(f"User with username {username} not found in the database.")

    # Завершаем состояние
    await state.finish()

# Запуск скрипта scrape_script.py при запуске бота
subprocess.Popen(["python", "scrape_script.py"])

if __name__ == '__main__':
    with open('times.txt', 'w') as file:
        pass  # Clear the file before starting

    loop = asyncio.get_event_loop()
    loop.create_task(dp.start_polling())
    loop.create_task(main())

    try:
        loop.run_forever()
    finally:
        loop.close()