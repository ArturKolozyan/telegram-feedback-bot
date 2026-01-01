import asyncio
import json
import os
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging
import schedule
import time
import threading

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
DATA_DIR = Path(__file__).parent.parent / 'data'
REPORTS_DIR = Path(__file__).parent.parent / 'reports'
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


# Функции планировщика
def send_survey_sync():
    """Синхронная обертка для отправки опроса"""
    logger.info("Запуск ежедневного опроса...")
    try:
        # Создаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_daily_survey_async())
    except Exception as e:
        logger.error(f"Ошибка в планировщике опроса: {e}")
    finally:
        try:
            loop.close()
        except:
            pass

def send_report_sync():
    """Синхронная обертка для отправки отчета"""
    logger.info("Запуск формирования отчета...")
    try:
        # Создаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(generate_daily_report_async())
    except Exception as e:
        logger.error(f"Ошибка в планировщике отчета: {e}")
    finally:
        try:
            loop.close()
        except:
            pass

async def send_daily_survey_async():
    """Отправляет ежедневный опрос всем пользователям"""
    global bot
    
    if not bot:
        logger.error("Бот не инициализирован")
        return
    
    # Создаем новый экземпляр бота для этого потока
    survey_bot = Bot(token=BOT_TOKEN)
    
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
                await survey_bot.send_message(
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
        
    finally:
        await survey_bot.session.close()

async def generate_daily_report_async():
    """Генерирует и отправляет ежедневный отчет менеджеру"""
    global bot
    
    if not MANAGER_CHAT_ID:
        logger.error("MANAGER_CHAT_ID не настроен")
        return
    
    # Создаем новый экземпляр бота для этого потока
    report_bot = Bot(token=BOT_TOKEN)
    
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
        
        # Отправляем отчет
        await report_bot.send_message(chat_id=int(MANAGER_CHAT_ID), text=report)
        logger.info("Отчет отправлен менеджеру")
        
        # Сохраняем в CSV
        if today in feedback_bot.responses:
            await save_report_to_csv(today, feedback_bot.responses[today])
            
    except Exception as e:
        logger.error(f"Ошибка отправки отчета: {e}")
    finally:
        await report_bot.session.close()

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
        
    except Exception as e:
        logger.error(f"Ошибка сохранения CSV: {e}")

def setup_scheduler():
    """Настройка планировщика задач"""
    logger.info(f"Настройка планировщика...")
    logger.info(f"Текущее время МСК: {datetime.now(MSK_TZ).strftime('%H:%M:%S')}")
    
    try:
        # Планируем задачи напрямую на московское время
        schedule.every().day.at(SURVEY_TIME).do(send_survey_sync)
        schedule.every().day.at(REPORT_TIME).do(send_report_sync)
        
        logger.info("Планировщик настроен:")
        logger.info(f"- Ежедневный опрос: {SURVEY_TIME} МСК")
        logger.info(f"- Ежедневный отчет: {REPORT_TIME} МСК")
        
    except Exception as e:
        logger.error(f"Ошибка настройки планировщика: {e}")
        return
    
    # Добавляем heartbeat для мониторинга
    def scheduler_heartbeat():
        current_time_msk = datetime.now(MSK_TZ).strftime('%H:%M:%S')
        logger.info(f"Планировщик работает. Время МСК: {current_time_msk}")
    
    # Каждые 10 минут (чтобы не спамить)
    schedule.every(10).minutes.do(scheduler_heartbeat)
    
    logger.info(f"- Мониторинг каждые 10 минут")

def run_scheduler():
    """Запуск планировщика в отдельном потоке"""
    setup_scheduler()
    while True:
        schedule.run_pending()
        time.sleep(60)


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
            "• `/stats` - статистика по боту\n"
            "• `/test` - тестовый опрос\n"
            "• `/schedule` - текущее расписание\n"
            "• `/help` - помощь по командам\n\n"
            "📊 **Автоматическое расписание:**\n"
            f"• {SURVEY_TIME} МСК - опрос сотрудников\n"
            f"• {REPORT_TIME} МСК - отчет вам в личные сообщения\n\n"
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
    
    await message.answer(welcome_message, parse_mode='Markdown')

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
    await generate_daily_report_async()
    await message.answer("✅ Отчет сформирован и отправлен!")

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
            "• `/stats` - статистика по пользователям\n"
            "• `/test` - тестовый опрос\n"
            "• `/schedule` - посмотреть расписание\n"
            "• `/help` - эта справка\n\n"
            "📊 **Автоматические процессы:**\n"
            f"• **{SURVEY_TIME} МСК** - автоматический опрос всех сотрудников\n"
            f"• **{REPORT_TIME} МСК** - автоматический отчет вам в личные сообщения\n\n"
            "📁 **Файлы данных:**\n"
            "• `data/users.json` - база пользователей\n"
            "• `data/responses.json` - все ответы\n"
            "• `reports/report_YYYY-MM-DD.csv` - ежедневные отчеты для Excel\n\n"
            "⚙️ **Настройка времени:**\n"
            "Измените `SURVEY_TIME` и `REPORT_TIME` в файле `.env`\n"
            "Формат: HH:MM (например, 09:30 или 18:45)\n\n"
            "💡 **Совет:** Используйте `/test` для проверки работы опроса"
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
    
    # Создаем бота и диспетчер
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрируем обработчики
    dp.message.register(start_command, CommandStart())
    dp.message.register(test_survey_command, Command('test'))
    dp.message.register(report_command, Command('report'))
    dp.message.register(stats_command, Command('stats'))
    dp.message.register(help_command, Command('help'))
    dp.message.register(schedule_command, Command('schedule'))
    dp.callback_query.register(mood_callback, F.data.startswith('mood_'))
    
    # Обработчик текстовых сообщений для проекта (только в состоянии waiting_for_project)
    dp.message.register(project_message, FeedbackStates.waiting_for_project)
    
    # Запускаем планировщик в отдельном потоке
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    logger.info("🚀 Бот запущен и готов к работе!")
    logger.info(f"📅 Опрос: {SURVEY_TIME} МСК")
    logger.info(f"📊 Отчет: {REPORT_TIME} МСК")
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
        print("👋 Бот остановлен")