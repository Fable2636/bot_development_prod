import os
import sqlite3

import openpyxl
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramAPIError
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
from datetime import datetime

# Укажите токен вашего бота
API_TOKEN = '7546483359:AAFpga1WZ4qeZSChTi3eU4yP1vXNqsf6bj0'

# Список администраторов по username
ADMIN_USERNAME = ['rrrrr30', 'pdgrn', 'Kolesnikov15','Fable2636']
ADMIN_IDS = [83851741, 1381162664, 157648462, 787676749]
DATABASE = "drone_alert_data.db"

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Настройка базы данных
def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        # Если колонки 'subscribed' нет, добавляем её
        if 'subscribed' not in columns:
            cursor.execute('''
                        ALTER TABLE users ADD COLUMN subscribed BOOLEAN DEFAULT 0
                    ''')
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        # Если колонки 'timestamp' нет, добавляем её
        if 'timestamp' not in columns:
            cursor.execute('''
                        ALTER TABLE users ADD COLUMN timestamp TEXT
                    ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                username TEXT,
                message TEXT,
                timestamp TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE,
                username TEXT,
                subscribed BOOLEAN,
                timestamp TEXT
            )
        ''')
        conn.commit()

async def save_alert(user_id, username, message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO alerts (user_id, username, message, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, message, timestamp))
        conn.commit()

async def save_user(user_id, username):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, subscribed, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, False, timestamp))  # Default subscription status is False
        conn.commit()

# Состояния для FSM
class UserStates(StatesGroup):
    waiting_for_subscription = State()
    waiting_for_report = State()
    waiting_for_broadcast_message = State()

# Команда /start
@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    # Сохраняем пользователя в базе данных
    await save_user(message.from_user.id, message.from_user.username)
    channel_link = "https://t.me/astra_ban"
    markup = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Я подписался")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "Добро пожаловать в чат-бот «ТРЕВОГА АСТРАХАНЬ».\n"
        "Бот создан для оперативного информирования жителей Астраханской области о чрезвычайных ситуациях.\n\n"
        "Для продолжения работы с ботом и получения более подробной информации "
        f"просим вас подписаться на телеграмм-канал «БАН - Бюро Астраханских Новостей»: {channel_link} и нажать «Я подписался».",
        reply_markup=markup
    )
    # Устанавливаем состояние ожидания подписки
    await state.set_state(UserStates.waiting_for_subscription)

# Импортируем sleep для паузы

async def update_subscription(user_id, status=True):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users
            SET subscribed = ?
            WHERE user_id = ?
        ''', (status, user_id))
        conn.commit()

# Обработка "Я подписался"
@dp.message(lambda message: message.text.lower() == "я подписался", UserStates.waiting_for_subscription)
async def check_subscription(message: Message, state: FSMContext):
    try:
        member = await bot.get_chat_member(chat_id="@invest_captain", user_id=message.from_user.id)
        if member.status in ['creator', 'administrator', 'member']:
            await update_subscription(message.from_user.id, status=True)
            await message.answer("Подписка проверяется... Пожалуйста, подождите ⏳")

            # Добавляем паузу в 2 секунды
            await asyncio.sleep(2)

            # Создаем inline-клавиатуру для сообщения
            inline_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚨 Сообщить о беспилотнике 🚨", callback_data="report_alert")]
            ])

            # Создаем reply-клавиатуру для нижнего меню
            reply_markup = types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="🚨 Сообщить о беспилотнике 🚨")]
                ],
                resize_keyboard=True
            )

            # Отправляем сообщение с inline-кнопкой
            await message.answer(
                "Подписка подтверждена! Теперь у вас есть возможность сообщить о беспилотнике.\n"
                "Вы можете использовать кнопку ниже или в нижнем меню:",
                reply_markup=inline_markup
            )

            # Меняем нижнюю клавиатуру на "Сообщить о беспилотнике"
            await message.answer(
                "Нажмите на кнопку ниже для отправки сообщения.",
                reply_markup=reply_markup
            )
            # Завершаем состояние
            await state.clear()
        else:
            await message.answer("Сначала необходимо подписаться на канал!")
    except Exception as e:
        await message.answer("Не удалось проверить подписку. Убедитесь, что вы подписаны на канал.")
        print(f"Ошибка проверки подписки: {e}")

# Обработка callback-запроса от кнопки
@dp.callback_query(lambda call: call.data == "report_alert")
async def report_alert_callback(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer(
        "Опишите ситуацию с беспилотником:\n"
        "- Местоположение (населенный пункт, район).\n"
        "- Время и обстоятельства.\n"
        "- Ваш номер телефона.\n"
        "- Любые дополнительные детали."
    )
    await state.set_state(UserStates.waiting_for_report)
    await call.answer()

@dp.message(lambda message: message.text == "🚨 Сообщить о беспилотнике 🚨")
async def report_button(message: Message, state: FSMContext):
    await message.answer(
        "Опишите ситуацию с беспилотником:\n"
        "- Местоположение (населенный пункт, район).\n"
        "- Время и обстоятельства.\n"
        "- Ваш номер телефона.\n"
        "- Любые дополнительные детали."
    )
    # Переводим пользователя в состояние ожидания репорта
    await state.set_state(UserStates.waiting_for_report)

# Команда /report
@dp.message(Command("report"))
async def report(message: Message, state: FSMContext):
    await message.answer(
        "Опишите ситуацию с беспилотником:\n"
        "- Местоположение (населенный пункт, район).\n"
        "- Время и обстоятельства.\n"
        "- Ваш номер телефона.\n"
        "- Любые дополнительные детали."
    )
    # Переводим пользователя в состояние ожидания репорта
    await state.set_state(UserStates.waiting_for_report)


# Обработка репорта
@dp.message(UserStates.waiting_for_report)
async def handle_report(message: Message, state: FSMContext):
    if message.text:
        # Сохраняем сообщение в базе данных
        await save_alert(
            user_id=message.from_user.id,
            username=message.from_user.username or "Не указано",
            message=message.text
        )

        # Уведомляем администраторов
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⚠️ Новое сообщение о беспилотнике от пользователя @{message.from_user.username or 'Не указано'}:\n"
                    f"{message.text}\n\n"
                    f"ID пользователя: {message.from_user.id}\n"
                    f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            except TelegramBadRequest as e:
                print(f"Ошибка отправки сообщения админу {admin_id}: {e}")

        # Создаем inline-кнопку для отправки нового сообщения
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚨 Сообщить о беспилотнике 🚨", callback_data="report_alert")]
        ])

        # Отправляем благодарность с кнопкой
        await message.answer(
            "Спасибо! Ваше сообщение передано администрации.\n"
            "Для передачи дальнейших сообщений о беспилотниках используйте команду: /report "
            "или воспользуйтесь кнопкой ниже.",
            reply_markup=markup
        )

        # Завершаем состояние
        await state.clear()

# Обработка рассылки сообщений с фильтрацией недоступных user_id
@dp.message(UserStates.waiting_for_broadcast_message)
async def process_broadcast(message: Message, state: FSMContext):
    text = message.text
    success, fail = 0, 0

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT user_id FROM users')  # Получаем всех пользователей
        user_ids = cursor.fetchall()

    for user_id in user_ids:
        try:
            # Проверяем подписку пользователя на канал
            member = await bot.get_chat_member(chat_id="@invest_captain", user_id=user_id[0])

            # Если пользователь не подписан, отправляем ему ссылку на канал с кнопкой для подписки
            if member.status not in ['creator', 'administrator', 'member']:
                channel_link = "https://t.me/astra_ban"
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Я подписался", callback_data="subscribe")]
                ])
                await bot.send_message(
                    user_id[0],
                    f"Вы не подписаны на наш канал. Чтобы не пропустить важные уведомления, "
                    f"подпишитесь на канал: {channel_link}",
                    reply_markup=markup
                )
                fail += 1  # Отметим как неудачную рассылку, так как пользователь не подписан
            else:
                # Если подписан, отправляем основное сообщение
                await bot.send_message(user_id[0], text)
                success += 1

        except TelegramAPIError as e:
            print(f"Ошибка при отправке сообщения пользователю {user_id[0]}: {e}")
            fail += 1

    await message.answer(f"Рассылка завершена. Успешно: {success}, Не подписанных людей: {fail}.")
    await state.clear()


@dp.callback_query(lambda call: call.data == "subscribe")
async def subscribe_button_callback(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    message = call.message  # Получаем сообщение для ответа

    try:
        # Проверяем подписку пользователя
        member = await bot.get_chat_member(chat_id="@invest_captain", user_id=user_id)

        if member.status in ['creator', 'administrator', 'member']:
            # Если подписка подтверждена
            await update_subscription(user_id, status=True)
            await call.message.answer(
                "Подписка проверена! Теперь вы можете получать уведомления.",
                reply_markup=None  # Убираем кнопку после успешной проверки
            )
        else:
            # Если пользователь не подписан
            channel_link = "https://t.me/astra_ban"
            await call.message.answer(
                f"Пожалуйста, подписывайтесь на канал:{channel_link} и нажмите «Я подписался».",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Я подписался", callback_data="subscribe")]
                ])
            )
    except TelegramAPIError:
        await call.message.answer("Не удалось проверить подписку. Попробуйте снова.")

    await call.answer()

# Команда /getdata для отправки Excel-файла
@dp.message(Command("getdata"))
async def get_data(message: Message):
    if message.from_user.username not in ADMIN_USERNAME:
        await message.answer("У вас нет прав на выполнение этой команды.")
        return

    await message.answer("Формирую файл с данными...")

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, user_id, username, message, timestamp FROM alerts')
        data = cursor.fetchall()

    if not data:
        await message.answer("Нет данных для отображения.")
        return

    temp_file = f"alerts_{message.chat.id}.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Reports"

    sheet.append(["ID", "User ID", "Username", "Message", "Timestamp"])
    for row in data:
        sheet.append(row)

    workbook.save(temp_file)

    try:
        await message.answer_document(types.FSInputFile(temp_file), caption="Вот все сообщения о беспилотниках.")
    finally:
        os.remove(temp_file)

# Команда /broadcast для рассылки сообщений
@dp.message(Command("broadcast"))
async def broadcast(message: Message, state: FSMContext):
    if message.from_user.username not in ADMIN_USERNAME:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    await message.answer("Введите сообщение для рассылки всем пользователям:")
    await state.set_state(UserStates.waiting_for_broadcast_message)

# Обработка рассылки сообщений
@dp.message(UserStates.waiting_for_broadcast_message)
async def process_broadcast(message: Message, state: FSMContext):
    text = message.text
    success, fail = 0, 0

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT user_id FROM alerts')
        user_ids = cursor.fetchall()

    for user_id in user_ids:
        try:
            await bot.send_message(user_id[0], text)
            success += 1
        except TelegramAPIError:
            fail += 1

    await message.answer(f"Рассылка завершена. Успешно: {success}, Ошибок: {fail}.")
    await state.clear()

# Инициализация базы данных
init_db()

# Главная функция
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())