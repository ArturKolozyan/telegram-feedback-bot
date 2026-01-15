import asyncio
import json
import os
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID')

# Валидация времени
def validate_time_format(time_str, default_time):
    """Валидирует формат времени HH:MM"""
    try:
        datetime.strptime(time_str, '%H:%M')
        return time_str
    except ValueError:
        logger.warning(f"Неверный формат времени: {time_str}. Используется значение по умолчанию: {default_time}")
        return default_time

SURVEY_TIME = validate_time_format(os.getenv('SURVEY_TIME', '17:00'), '17:00')
REPORT_TIME = validate_time_format(os.getenv('REPORT_TIME', '21:00'), '21:00')

# Московский часовой пояс
MSK_TZ = timezone(timedelta(hours=3))

# Пути к файлам данных
DATA_DIR = Path.cwd() / 'data'
REPORTS_DIR = Path.cwd() / 'reports'
USER_DATA_FILE = DATA_DIR / 'users.json'
RESPONSES_FILE = DATA_DIR / 'responses.json'

# Создаем директории если не существуют
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# Смайлики для оценки дня
MOOD_OPTIONS = {
    'excellent': {'emoji': '👍', 'text': 'Отлично'},
    'good': {'emoji': '👌', 'text': 'Нормально'},
    'bad': {'emoji': '😔', 'text': 'Не очень'},
    'hard': {'emoji': '😓', 'text': 'Тяжело'},
    'critical': {'emoji': '😭', 'text': 'Критично'}
}

# Глобальные переменные
bot = None

# FSM состояния
class FeedbackStates(StatesGroup):
    waiting_for_project = State()


class FeedbackBot:
    def __init__(self):
        self.users = self.load_users()
        self.responses = self.load_responses()
    
    def load_users(self):
        try:
            if USER_DATA_FILE.exists():
                with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Ошибка загрузки пользователей: {e}")
            return {}
    
    def save_users(self):
        try:
            with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователей: {e}")
    
    def load_responses(self):
        try:
            if RESPONSES_FILE.exists():
                with open(RESPONSES_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Ошибка загрузки ответов: {e}")
            return {}
    
    def save_responses(self):
        try:
            with open(RESPONSES_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.responses, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения ответов: {e}")

# Создаем экземпляр бота
feedback_bot = FeedbackBot()

# Клавиатура для администратора
admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Меню")]
    ],
    resize_keyboard=True,
    persistent=True
)


async def send_daily_survey_async(bot_instance):
    """Отправляет ежедневный опрос всем пользователям"""
    
    if not bot_instance:
        logger.error("Бот не инициализирован")
        return
    
    try:
        today = datetime.now(MSK_TZ).strftime('%Y-%m-%d')
        feedback_bot.responses[today] = {}
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{MOOD_OPTIONS['excellent']['emoji']} {MOOD_OPTIONS['excellent']['text']}", callback_data='mood_excellent'),
                InlineKeyboardButton(text=f"{MOOD_OPTIONS['good']['emoji']} {MOOD_OPTIONS['good']['text']}", callback_data='mood_good')
            ],
            [
                InlineKeyboardButton(text=f"{MOOD_OPTIONS['bad']['emoji']} {MOOD_OPTIONS['bad']['text']}", callback_data='mood_bad'),
                InlineKeyboardButton(text=f"{MOOD_OPTIONS['hard']['emoji']} {MOOD_OPTIONS['hard']['text']}", callback_data='mood_hard')
            ],
            [
                InlineKeyboardButton(text=f"{MOOD_OPTIONS['critical']['emoji']} {MOOD_OPTIONS['critical']['text']}", callback_data='mood_critical')
            ]
        ])
        
        sent_count = 0
        error_count = 0
        
        for chat_id in feedback_bot.users:
            try:
                await bot_instance.send_message(
                    chat_id=int(chat_id),
                    text="Как прошел твой день? 🤔",
                    reply_markup=keyboard
                )
                sent_count += 1
                logger.info(f"Опрос отправлен пользователю {chat_id}")
            except Exception as e:
                error_count += 1
                logger.error(f"Ошибка отправки опроса пользователю {chat_id}: {e}")
        
        logger.info(f"Опрос завершен. Отправлено: {sent_count}, ошибок: {error_count}")
        feedback_bot.save_responses()
        
    except Exception as e:
        logger.error(f"Ошибка в отправке опроса: {e}")

async def generate_daily_report_async(bot_instance):
    """Генерирует и отправляет ежедневный отчет менеджеру"""
    
    if not MANAGER_CHAT_ID:
        logger.error("MANAGER_CHAT_ID не настроен")
        return
    
    if not bot_instance:
        logger.error("Бот не инициализирован")
        return
    
    try:
        today = datetime.now(MSK_TZ).strftime('%Y-%m-%d')
        today_formatted = datetime.now(MSK_TZ).strftime('%A, %d %B %Y')
        
        # Переводим на русский
        days_ru = {
            'Monday': 'Понедельник', 'Tuesday': 'Вторник', 'Wednesday': 'Среда',
            'Thursday': 'Четверг', 'Friday': 'Пятница', 'Saturday': 'Суббота', 'Sunday': 'Воскресенье'
        }
        
        months_ru = {
            'January': 'января', 'February': 'февраля', 'March': 'марта',
            'April': 'апреля', 'May': 'мая', 'June': 'июня',
            'July': 'июля', 'August': 'августа', 'September': 'сентября',
            'October': 'октября', 'November': 'ноября', 'December': 'декабря'
        }
        
        for eng, ru in days_ru.items():
            today_formatted = today_formatted.replace(eng, ru)
        for eng, ru in months_ru.items():
            today_formatted = today_formatted.replace(eng, ru)
        
        responses = feedback_bot.responses.get(today, {})
        
        if not responses:
            report = f"📊 Отчет за {today_formatted}\n\n❌ Сегодня никто не ответил на опрос."
        else:
            report = f"📊 Отчет за {today_formatted}\n\n"
            total_users = len(feedback_bot.users)
            responded_users = len(responses)
            
            report += f"👥 Ответили: {responded_users} из {total_users}\n\n"
            
            # Группируем по настроению
            mood_groups = {}
            for response in responses.values():
                mood = response['mood']
                if mood not in mood_groups:
                    mood_groups[mood] = []
                mood_groups[mood].append(response)
            
            # Сортируем по настроениям
            mood_order = ['excellent', 'good', 'bad', 'hard', 'critical']
            
            for mood in mood_order:
                if mood in mood_groups:
                    mood_data = MOOD_OPTIONS[mood]
                    count = len(mood_groups[mood])
                    report += f"{mood_data['emoji']} {mood_data['text']} ({count}):\n"
                    
                    for response in mood_groups[mood]:
                        project = response.get('project', 'Не указан')
                        username = response['username']
                        report += f"  • @{username}: {project}\n"
                    report += "\n"
            
            # Кто не ответил
            responded_user_ids = set(responses.keys())
            not_responded = [user_id for user_id in feedback_bot.users if user_id not in responded_user_ids]
            
            if not_responded:
                report += f"❌ Не ответили ({len(not_responded)}):\n"
                for user_id in not_responded:
                    user = feedback_bot.users[user_id]
                    username = user['username']
                    report += f"  • @{username}\n"
        
        # Отправляем текстовый отчет
        await bot_instance.send_message(chat_id=int(MANAGER_CHAT_ID), text=report)
        logger.info("Отчет отправлен менеджеру")
        
        # Сохраняем в CSV и отправляем файл
        if today in feedback_bot.responses:
            csv_path = await save_report_to_csv(today, feedback_bot.responses[today])
            if csv_path and csv_path.exists():
                await send_csv_file(bot_instance, int(MANAGER_CHAT_ID), csv_path, today)
            
    except Exception as e:
        logger.error(f"Ошибка отправки отчета: {e}")

async def save_report_to_csv(date, responses):
    """Сохраняет отчет в CSV формате для Excel"""
    try:
        csv_file = REPORTS_DIR / f"report_{date}.csv"
        
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Дата', 'Пользователь', 'Настроение', 'Проект', 'Время ответа'])
            
            for response in responses.values():
                writer.writerow([
                    date,
                    response['username'],
                    f"{response['mood_emoji']} {MOOD_OPTIONS[response['mood']]['text']}",
                    response.get('project', 'Не указан'),
                    response.get('completed_at', response['timestamp'])
                ])
        
        logger.info(f"Отчет сохранен в CSV: {csv_file}")
        return csv_file
        
    except Exception as e:
        logger.error(f"Ошибка сохранения CSV: {e}")
        return None

async def send_csv_file(bot_instance, chat_id, csv_path, date):
    """Отправляет CSV файл в Telegram"""
    try:
        file = FSInputFile(csv_path)
        await bot_instance.send_document(
            chat_id=chat_id,
            document=file,
            caption=f"📎 Отчет за {date} в формате CSV\n\nОткройте в Excel для удобного просмотра."
        )
        logger.info(f"CSV файл отправлен: {csv_path}")
    except Exception as e:
        logger.error(f"Ошибка отправки CSV файла: {e}")

async def download_command(message: Message):
    """Команда для скачивания отчета (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    # Парсим аргументы команды
    args = message.text.split(maxsplit=1)
    
    if len(args) == 1:
        # Без аргументов - отчет за сегодня
        date = datetime.now(MSK_TZ).strftime('%Y-%m-%d')
    else:
        # С датой
        date = args[1].strip()
        # Валидация формата даты
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            await message.answer(
                "❌ Неверный формат даты. Используйте:\n"
                "• `/download` - отчет за сегодня\n"
                "• `/download 2026-01-15` - отчет за конкретную дату"
            )
            return
    
    csv_file = REPORTS_DIR / f"report_{date}.csv"
    
    if not csv_file.exists():
        await message.answer(
            f"❌ Отчет за {date} не найден.\n\n"
            "Возможные причины:\n"
            "• Отчет еще не был создан\n"
            "• Никто не ответил на опрос в этот день\n"
            "• Неверная дата\n\n"
            "💡 Используйте `/reports` для просмотра доступных отчетов"
        )
        return
    
    await message.answer("📎 Отправляю файл...")
    await send_csv_file(bot, message.chat.id, csv_file, date)

async def reports_list_command(message: Message):
    """Команда для просмотра списка всех отчетов (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    # Получаем все CSV файлы
    csv_files = sorted(REPORTS_DIR.glob("report_*.csv"), reverse=True)
    
    if not csv_files:
        await message.answer("📁 Отчеты пока не созданы.\n\nОтчеты создаются автоматически после опроса.")
        return
    
    # Формируем список
    report_list = "📁 **Доступные отчеты:**\n\n"
    
    for i, csv_file in enumerate(csv_files[:10], 1):  # Показываем последние 10
        # Извлекаем дату из имени файла
        date_str = csv_file.stem.replace('report_', '')
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d.%m.%Y')
            
            # Получаем размер файла
            file_size = csv_file.stat().st_size
            size_kb = file_size / 1024
            
            report_list += f"{i}. `{date_str}` ({formatted_date}) - {size_kb:.1f} KB\n"
        except:
            continue
    
    if len(csv_files) > 10:
        report_list += f"\n... и еще {len(csv_files) - 10} отчетов\n"
    
    report_list += (
        f"\n📊 Всего отчетов: {len(csv_files)}\n\n"
        "💡 **Как скачать:**\n"
        "• `/download` - отчет за сегодня\n"
        "• `/download 2026-01-15` - отчет за конкретную дату"
    )
    
    await message.answer(report_list, parse_mode='Markdown')

async def scheduler_task(bot_instance):
    logger.info(f"Планировщик запущен. Опрос: {SURVEY_TIME} МСК, Отчет: {REPORT_TIME} МСК")
    
    while True:
        try:
            # Ждём до начала следующей минуты
            now = datetime.now(MSK_TZ)
            next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
            sleep_seconds = (next_minute - now).total_seconds()
            
            if sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds)
            
            # Теперь мы точно в начале новой минуты
            current_time = next_minute.strftime('%H:%M')
            today_str = next_minute.strftime('%Y-%m-%d')
            
            logger.debug(f"Текущее время МСК: {current_time}")
            
            if current_time == SURVEY_TIME:
                logger.info("Запуск ежедневного опроса...")
                await send_daily_survey_async(bot_instance)
            
            elif current_time == REPORT_TIME:
                logger.info("Запуск формирования отчета...")
                await generate_daily_report_async(bot_instance)
            
            # Логирование каждые 10 минут
            if next_minute.minute % 10 == 0:
                logger.info(f"Планировщик активен. Время МСК: {current_time}")
                
        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
            await asyncio.sleep(60)


# Обработчики команд
async def start_command(message: Message):
    """Обработчик команды /start"""
    user = message.from_user
    chat_id = str(user.id)
    
    logger.info(f"Пользователь {user.username} ({chat_id}) запустил бота")
    
    feedback_bot.users[chat_id] = {
        'username': user.username or 'Пользователь',
        'first_name': user.first_name,
        'last_name': user.last_name,
        'registered_at': datetime.now(MSK_TZ).isoformat(),
        'is_admin': chat_id == MANAGER_CHAT_ID
    }
    
    feedback_bot.save_users()
    
    if chat_id == MANAGER_CHAT_ID:
        welcome_message = (
            f"👑 Добро пожаловать, {user.first_name}!\n\n"
            "Вы вошли как *администратор*\n\n"
            "🔧 **Доступные команды:**\n"
            "• `/report` - получить отчет за сегодня\n"
            "• `/createreport` - принудительно создать отчет (перезапишет старый)\n"
            "• `/download` - скачать CSV файл за сегодня\n"
            "• `/download YYYY-MM-DD` - скачать за конкретную дату\n"
            "• `/reports` - список всех отчетов\n"
            "• `/stats` - статистика по боту\n"
            "• `/test` - тестовый опрос\n"
            "• `/schedule` - текущее расписание\n"
            "• `/help` - помощь по командам\n\n"
            "📊 **Автоматическое расписание:**\n"
            f"• {SURVEY_TIME} МСК - опрос сотрудников\n"
            f"• {REPORT_TIME} МСК - отчет + CSV файл вам в личные сообщения\n\n"
            f"🆔 Ваш Chat ID: `{chat_id}`"
        )
    else:
        welcome_message = (
            f"👋 Привет, {user.first_name}!\n\n"
            f"Я буду каждый день в {SURVEY_TIME} спрашивать, как прошел твой рабочий день.\n"
            "Это займет всего пару секунд и поможет улучшить рабочие процессы!\n\n"
            "📝 **Как это работает:**\n"
            f"1. В {SURVEY_TIME} я пришлю вопрос с вариантами ответа\n"
            "2. Выберите смайлик, соответствующий вашему настроению\n"
            "3. Напишите, над каким проектом работали\n"
            "4. Готово! Спасибо за участие 😊\n\n"
            "🔧 **Доступные команды:**\n"
            "• `/test` - попробовать опрос прямо сейчас\n"
            "• `/help` - помощь\n\n"
            f"Увидимся в {SURVEY_TIME}! 🕐"
        )
    
    await message.answer(welcome_message, parse_mode='Markdown', reply_markup=admin_keyboard if chat_id == MANAGER_CHAT_ID else None)

async def menu_button_handler(message: Message):
    """Обработчик кнопки 📋 Меню для администратора"""
    user_id = str(message.from_user.id)
    
    # Проверяем что это администратор
    if user_id != MANAGER_CHAT_ID:
        return
    
    # Отправляем то же сообщение что и при /start
    user = message.from_user
    welcome_message = (
        f"👑 Меню администратора\n\n"
        "🔧 **Доступные команды:**\n"
        "• `/report` - получить отчет за сегодня\n"
        "• `/createreport` - принудительно создать отчет (перезапишет старый)\n"
        "• `/download` - скачать CSV файл за сегодня\n"
        "• `/download YYYY-MM-DD` - скачать за конкретную дату\n"
        "• `/reports` - список всех отчетов\n"
        "• `/stats` - статистика по боту\n"
        "• `/test` - тестовый опрос\n"
        "• `/schedule` - текущее расписание\n"
        "• `/help` - помощь по командам\n\n"
        "📊 **Автоматическое расписание:**\n"
        f"• {SURVEY_TIME} МСК - опрос сотрудников\n"
        f"• {REPORT_TIME} МСК - отчет + CSV файл вам в личные сообщения"
    )
    
    await message.answer(welcome_message, parse_mode='Markdown', reply_markup=admin_keyboard)

async def test_survey_command(message: Message):
    """Команда для тестового опроса"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"{MOOD_OPTIONS['excellent']['emoji']} {MOOD_OPTIONS['excellent']['text']}", callback_data='mood_excellent'),
            InlineKeyboardButton(text=f"{MOOD_OPTIONS['good']['emoji']} {MOOD_OPTIONS['good']['text']}", callback_data='mood_good')
        ],
        [
            InlineKeyboardButton(text=f"{MOOD_OPTIONS['bad']['emoji']} {MOOD_OPTIONS['bad']['text']}", callback_data='mood_bad'),
            InlineKeyboardButton(text=f"{MOOD_OPTIONS['hard']['emoji']} {MOOD_OPTIONS['hard']['text']}", callback_data='mood_hard')
        ],
        [
            InlineKeyboardButton(text=f"{MOOD_OPTIONS['critical']['emoji']} {MOOD_OPTIONS['critical']['text']}", callback_data='mood_critical')
        ]
    ])
    
    await message.answer("Как прошел твой день? 🤔", reply_markup=keyboard)

async def mood_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора настроения"""
    await callback.answer()
    
    user_id = str(callback.from_user.id)
    mood = callback.data.replace('mood_', '')
    
    # Валидация настроения
    if mood not in MOOD_OPTIONS:
        logger.warning(f"Неизвестное настроение: {mood} от пользователя {user_id}")
        await callback.message.answer("❌ Произошла ошибка. Попробуйте еще раз.")
        return
    
    today = datetime.now(MSK_TZ).strftime('%Y-%m-%d')
    
    if today not in feedback_bot.responses:
        feedback_bot.responses[today] = {}
    
    # Получаем данные пользователя безопасно
    user_data = feedback_bot.users.get(user_id, {})
    username = user_data.get('username', 'Неизвестный')
    
    feedback_bot.responses[today][user_id] = {
        'username': username,
        'mood': mood,
        'mood_text': MOOD_OPTIONS[mood]['text'],
        'mood_emoji': MOOD_OPTIONS[mood]['emoji'],
        'timestamp': datetime.now(MSK_TZ).isoformat()
    }
    
    try:
        await callback.message.edit_text(f"Ты выбрал: {MOOD_OPTIONS[mood]['emoji']} {MOOD_OPTIONS[mood]['text']}")
        await callback.message.answer("Каким объектом/проектом сегодня занимался? 📝")
        
        # Устанавливаем состояние ожидания проекта
        await state.set_state(FeedbackStates.waiting_for_project)
        feedback_bot.save_responses()
        
    except Exception as e:
        logger.error(f"Ошибка обработки выбора настроения: {e}")
        await callback.message.answer("❌ Произошла ошибка. Попробуйте команду /test еще раз.")

async def project_message(message: Message, state: FSMContext):
    """Обработчик текстовых сообщений (ответ о проекте)"""
    user_id = str(message.from_user.id)
    today = datetime.now(MSK_TZ).strftime('%Y-%m-%d')
    
    # Валидация входных данных
    project_text = message.text.strip()
    if len(project_text) > 500:
        await message.answer("❌ Описание проекта слишком длинное. Максимум 500 символов.")
        return
    
    if not project_text:
        await message.answer("❌ Пожалуйста, напишите название проекта или задачи.")
        return
    
    # Базовая фильтрация нежелательного контента
    forbidden_words = ['<script', 'javascript:', 'data:', 'vbscript:']
    if any(word.lower() in project_text.lower() for word in forbidden_words):
        await message.answer("❌ Недопустимый текст. Пожалуйста, опишите проект корректно.")
        return
    
    if (today in feedback_bot.responses and user_id in feedback_bot.responses[today]):
        feedback_bot.responses[today][user_id]['project'] = project_text
        feedback_bot.responses[today][user_id]['completed_at'] = datetime.now(MSK_TZ).isoformat()
    
    await state.clear()
    feedback_bot.save_responses()
    
    await message.answer(f"Спасибо за обратную связь! 👍\nУвидимся завтра в {SURVEY_TIME}.")

async def report_command(message: Message):
    """Команда для ручной генерации отчета (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    await message.answer("📊 Формирую отчет за сегодня...")
    await generate_daily_report_async(bot)

async def force_report_command(message: Message):
    """Команда для принудительного создания отчета с перезаписью (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    today = datetime.now(MSK_TZ).strftime('%Y-%m-%d')
    csv_file = REPORTS_DIR / f"report_{today}.csv"
    
    # Проверяем существует ли отчет
    file_exists = csv_file.exists()
    
    if file_exists:
        await message.answer("⚠️ Отчет за сегодня уже существует. Создаю новый (старый будет заменен)...")
    else:
        await message.answer("📊 Создаю отчет за сегодня...")
    
    # Генерируем отчет (он автоматически перезапишет старый файл)
    await generate_daily_report_async(bot)
    
    if file_exists:
        await message.answer("✅ Отчет обновлен и отправлен!")
    else:
        await message.answer("✅ Отчет создан и отправлен!")

async def stats_command(message: Message):
    """Команда статистики (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    total_users = len(feedback_bot.users)
    total_days = len(feedback_bot.responses)
    
    # Считаем админов и обычных пользователей
    admin_count = sum(1 for user in feedback_bot.users.values() if user.get('is_admin', False))
    employee_count = total_users - admin_count
    
    stats = f"📊 **Статистика бота:**\n\n"
    stats += f"👥 Всего пользователей: {total_users}\n"
    stats += f"👑 Администраторов: {admin_count}\n"
    stats += f"👤 Сотрудников: {employee_count}\n"
    stats += f"📅 Дней с ответами: {total_days}\n"
    
    if feedback_bot.responses:
        # Статистика по последним 7 дням
        recent_days = sorted(feedback_bot.responses.keys())[-7:]
        avg_response_rate = sum(
            len(feedback_bot.responses[day]) for day in recent_days
        ) / len(recent_days) if recent_days else 0
        
        stats += f"📊 Средняя активность (7 дней): {avg_response_rate:.1f} ответов/день\n"
        
        # Процент участия
        if employee_count > 0:
            participation_rate = (avg_response_rate / employee_count) * 100
            stats += f"📈 Процент участия: {participation_rate:.1f}%\n"
    
    await message.answer(stats, parse_mode='Markdown')

async def help_command(message: Message):
    """Команда помощи с разными версиями для админа и пользователя"""
    user_id = str(message.from_user.id)
    
    if user_id == MANAGER_CHAT_ID:
        # Помощь для администратора
        help_message = (
            "👑 **Справка для администратора**\n\n"
            "🔧 **Команды управления:**\n"
            "• `/start` - перезапуск и информация\n"
            "• `/report` - получить отчет за сегодня\n"
            "• `/createreport` - принудительно создать отчет (перезапишет старый)\n"
            "• `/download` - скачать CSV за сегодня\n"
            "• `/download YYYY-MM-DD` - скачать за дату\n"
            "• `/reports` - список всех отчетов\n"
            "• `/stats` - статистика по пользователям\n"
            "• `/test` - тестовый опрос\n"
            "• `/schedule` - посмотреть расписание\n"
            "• `/help` - эта справка\n\n"
            "�  **Автоматические процессы:**\n"
            f"• **{SURVEY_TIME} МСК** - автоматический опрос всех сотрудников\n"
            f"• **{REPORT_TIME} МСК** - автоматический отчет + CSV файл\n\n"
            "📁 **Работа с файлами:**\n"
            "• CSV файлы автоматически отправляются вместе с отчетом\n"
            "• Используйте `/download` для повторного скачивания\n"
            "• Все файлы хранятся в папке `reports/`\n"
            "• Формат имени: `report_YYYY-MM-DD.csv`\n\n"
            "⚙️ **Настройка времени:**\n"
            "Измените `SURVEY_TIME` и `REPORT_TIME` в файле `.env`\n"
            "Формат: HH:MM (например, 09:30 или 18:45)\n\n"
            "🔄 **Принудительное создание отчета:**\n"
            "• `/createreport` создаст отчет прямо сейчас\n"
            "• Если отчет за сегодня уже существует, он будет перезаписан\n"
            "• Полезно если нужно обновить данные после новых ответов\n\n"
            "💡 **Совет:** Используйте `/reports` для просмотра всех доступных отчетов"
        )
    else:
        # Помощь для сотрудника
        help_message = (
            "👋 **Справка для сотрудника**\n\n"
            "🔧 **Доступные команды:**\n"
            "• `/start` - перезапуск бота\n"
            "• `/test` - попробовать опрос прямо сейчас\n"
            "• `/help` - эта справка\n\n"
            "📝 **Как проходит опрос:**\n"
            f"1. **{SURVEY_TIME} МСК** - я пришлю вопрос о вашем дне\n"
            "2. Выберите смайлик, соответствующий настроению:\n"
            "   👍 Отлично • 👌 Нормально • 😔 Не очень\n"
            "   😓 Тяжело • 😭 Критично\n"
            "3. Напишите, над каким проектом работали сегодня\n"
            "4. Готово! Ваш ответ сохранен\n\n"
            "🔒 **Конфиденциальность:**\n"
            "Ваши ответы видит только руководитель.\n"
            "Личные данные не передаются третьим лицам.\n\n"
            "❓ **Вопросы?** Обратитесь к администратору."
        )
    
    await message.answer(help_message, parse_mode='Markdown')

async def schedule_command(message: Message):
    """Команда для просмотра текущего расписания (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    # Получаем текущее время в МСК
    current_time_msk = datetime.now(MSK_TZ).strftime('%H:%M:%S')
    current_date = datetime.now(MSK_TZ).strftime('%d.%m.%Y')
    
    schedule_message = (
        f"🕐 **Текущее расписание**\n\n"
        f"📅 Сегодня: {current_date}\n"
        f"🕐 Сейчас: {current_time_msk} МСК\n\n"
        f"⏰ **Автоматические задачи:**\n"
        f"• **Опрос сотрудников:** {SURVEY_TIME} МСК\n"
        f"• **Отчет менеджеру:** {REPORT_TIME} МСК\n\n"
        f"⚙️ **Настройка:**\n"
        f"Для изменения времени отредактируйте файл `.env`:\n"
        f"```\n"
        f"SURVEY_TIME={SURVEY_TIME}\n"
        f"REPORT_TIME={REPORT_TIME}\n"
        f"```\n"
        f"После изменения перезапустите бота."
    )
    
    await message.answer(schedule_message, parse_mode='Markdown')


async def main():
    """Основная функция запуска бота"""
    global bot
    
    if not BOT_TOKEN or not MANAGER_CHAT_ID:
        logger.error("Не указаны BOT_TOKEN или MANAGER_CHAT_ID в .env файле")
        return
    
    logger.info("Инициализация бота...")
    
    # Отладочная информация (скрываем часть токена для безопасности)
    token_preview = BOT_TOKEN[:10] + "..." + BOT_TOKEN[-10:] if len(BOT_TOKEN) > 20 else "Токен слишком короткий"
    logger.info(f"Токен: {token_preview}")
    logger.info(f"Manager Chat ID: {MANAGER_CHAT_ID}")
    
    try:
        # Создаем бота и диспетчер
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())
        
        # Регистрируем обработчики
        dp.message.register(start_command, CommandStart())
        dp.message.register(menu_button_handler, F.text == "📋 Меню")
        dp.message.register(test_survey_command, Command('test'))
        dp.message.register(report_command, Command('report'))
        dp.message.register(force_report_command, Command('createreport'))
        dp.message.register(download_command, Command('download'))
        dp.message.register(reports_list_command, Command('reports'))
        dp.message.register(stats_command, Command('stats'))
        dp.message.register(help_command, Command('help'))
        dp.message.register(schedule_command, Command('schedule'))
        dp.callback_query.register(mood_callback, F.data.startswith('mood_'))
        
        # Обработчик текстовых сообщений для проекта (только в состоянии waiting_for_project)
        dp.message.register(project_message, FeedbackStates.waiting_for_project)
        
        # Запускаем планировщик как фоновую задачу
        scheduler_task_handle = asyncio.create_task(scheduler_task(bot))
        
        logger.info("🚀 Бот запущен и готов к работе!")
        logger.info(f"📅 Опрос: {SURVEY_TIME} МСК")
        logger.info(f"📊 Отчет: {REPORT_TIME} МСК")
        
        # Запускаем бота
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        return
    finally:
        # Отменяем фоновую задачу при завершении
        if 'scheduler_task_handle' in locals():
            scheduler_task_handle.cancel()
            try:
                await scheduler_task_handle
            except asyncio.CancelledError:
                pass

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
        print("👋 Бот остановлен")