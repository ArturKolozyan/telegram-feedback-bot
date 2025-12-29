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

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
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
SURVEY_TIME = os.getenv('SURVEY_TIME', '17:00')
REPORT_TIME = os.getenv('REPORT_TIME', '21:00')

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

# Глобальная переменная для бота
bot_instance = None

class FeedbackBot:
    def __init__(self):
        self.users = self.load_users()
        self.responses = self.load_responses()
        self.waiting_for_project = set()
    
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

feedback_bot = FeedbackBot()

def send_survey_sync():
    """Синхронная обертка для отправки опроса"""
    logger.info("Запуск ежедневного опроса...")
    asyncio.run(send_daily_survey_async())

def send_report_sync():
    """Синхронная обертка для отправки отчета"""
    logger.info("Запуск формирования отчета...")
    asyncio.run(generate_daily_report_async())

async def send_daily_survey_async():
    """Отправляет ежедневный опрос всем пользователям"""
    global bot_instance
    
    today = datetime.now(MSK_TZ).strftime('%Y-%m-%d')
    feedback_bot.responses[today] = {}
    
    keyboard = [
        [
            InlineKeyboardButton(f"{MOOD_OPTIONS['excellent']['emoji']} {MOOD_OPTIONS['excellent']['text']}", callback_data='mood_excellent'),
            InlineKeyboardButton(f"{MOOD_OPTIONS['good']['emoji']} {MOOD_OPTIONS['good']['text']}", callback_data='mood_good')
        ],
        [
            InlineKeyboardButton(f"{MOOD_OPTIONS['bad']['emoji']} {MOOD_OPTIONS['bad']['text']}", callback_data='mood_bad'),
            InlineKeyboardButton(f"{MOOD_OPTIONS['hard']['emoji']} {MOOD_OPTIONS['hard']['text']}", callback_data='mood_hard')
        ],
        [
            InlineKeyboardButton(f"{MOOD_OPTIONS['critical']['emoji']} {MOOD_OPTIONS['critical']['text']}", callback_data='mood_critical')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot = Bot(token=BOT_TOKEN)
    
    for chat_id in feedback_bot.users.keys():
        try:
            await bot.send_message(
                chat_id=int(chat_id),
                text="Как прошел твой день? 🤔",
                reply_markup=reply_markup
            )
            logger.info(f"Опрос отправлен пользователю {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю {chat_id}: {e}")

async def generate_daily_report_async():
    """Генерирует и отправляет ежедневный отчет менеджеру"""
    today = datetime.now(MSK_TZ).strftime('%Y-%m-%d')
    today_formatted = datetime.now(MSK_TZ).strftime('%A, %d %B %Y')
    
    # Переводим день недели на русский
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
    
    if (today not in feedback_bot.responses or not feedback_bot.responses[today]):
        report = f"📊 Отчет за {today_formatted}\n\n❌ Сегодня никто не ответил на опрос."
    else:
        responses = feedback_bot.responses[today]
        total_users = len(feedback_bot.users)
        responded_users = len(responses)
        
        report = f"📊 Отчет за {today_formatted}\n\n"
        report += f"👥 Ответили: {responded_users} из {total_users} сотрудников\n\n"
        
        # Группируем по настроению
        mood_groups = {}
        for response in responses.values():
            mood = response['mood']
            if mood not in mood_groups:
                mood_groups[mood] = []
            mood_groups[mood].append(response)
        
        # Формируем отчет по группам настроения
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
        
        # Список не ответивших
        responded_user_ids = set(responses.keys())
        not_responded = [user_id for user_id in feedback_bot.users.keys() if user_id not in responded_user_ids]
        
        if not_responded:
            report += f"❌ Не ответили ({len(not_responded)}):\n"
            for user_id in not_responded:
                user = feedback_bot.users[user_id]
                username = user['username']
                report += f"  • @{username}\n"
    
    # Отправляем отчет менеджеру
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=int(MANAGER_CHAT_ID), text=report)
        logger.info("Отчет отправлен менеджеру")
        
        # Сохраняем отчет в CSV
        if today in feedback_bot.responses and feedback_bot.responses[today]:
            await save_report_to_csv(today, feedback_bot.responses[today])
        
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
                    f"{response['mood_emoji']} {response['mood_text']}",
                    response.get('project', 'Не указан'),
                    response.get('completed_at', response['timestamp'])
                ])
        
        logger.info(f"Отчет сохранен: {csv_file}")
        
    except Exception as e:
        logger.error(f"Ошибка сохранения отчета в CSV: {e}")

def setup_scheduler():
    """Настройка планировщика"""
    logger.info(f"Настройка планировщика...")
    logger.info(f"Текущее системное время: {datetime.now().strftime('%H:%M:%S')}")
    logger.info(f"Текущее время МСК: {datetime.now(MSK_TZ).strftime('%H:%M:%S')}")
    
    # Планируем задачи на определенное время
    schedule.every().day.at(SURVEY_TIME).do(send_survey_sync)
    schedule.every().day.at(REPORT_TIME).do(send_report_sync)
    
    # Добавляем проверку работы планировщика каждую минуту (только для логирования)
    def scheduler_heartbeat():
        current_time = datetime.now().strftime('%H:%M')
        logger.info(f"Планировщик работает. Текущее время: {current_time}")
    
    # Проверяем каждую минуту (только для мониторинга)
    schedule.every().minute.do(scheduler_heartbeat)
    
    logger.info(f"Расписание настроено:")
    logger.info(f"- Ежедневный опрос: {SURVEY_TIME} (локальное время)")
    logger.info(f"- Ежедневный отчет: {REPORT_TIME} (локальное время)")
    logger.info(f"- Мониторинг каждую минуту")

def run_scheduler():
    """Запуск планировщика в отдельном потоке"""
    setup_scheduler()
    while True:
        schedule.run_pending()
        time.sleep(60)

# Обработчики команд (копируем из основного файла)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = str(user.id)
    
    logger.info(f"Пользователь {user.username or user.first_name} подключился. Chat ID: {chat_id}")
    
    feedback_bot.users[chat_id] = {
        'username': user.username or user.first_name or 'Пользователь',
        'first_name': user.first_name,
        'last_name': user.last_name,
        'registered_at': datetime.now(MSK_TZ).isoformat(),
        'is_admin': chat_id == MANAGER_CHAT_ID
    }
    
    feedback_bot.save_users()
    
    if chat_id == MANAGER_CHAT_ID:
        welcome_message = (
            f"👑 Добро пожаловать, {user.first_name}!\n\n"
            "Вы вошли как **администратор** системы сбора обратной связи.\n\n"
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
            f"Привет, {user.first_name}! 👋\n\n"
            f"Я буду каждый день в **{SURVEY_TIME} МСК** спрашивать, как прошел твой рабочий день.\n"
            "Это займет всего пару секунд и поможет команде лучше понимать общее настроение.\n\n"
            "📝 **Как это работает:**\n"
            f"1. В {SURVEY_TIME} я пришлю вопрос с вариантами ответа\n"
            "2. Выберите смайлик, соответствующий вашему дню\n"
            "3. Напишите, над каким проектом работали\n"
            "4. Готово! Спасибо за участие 😊\n\n"
            "🔧 **Доступные команды:**\n"
            "• `/test` - попробовать опрос прямо сейчас\n"
            "• `/help` - помощь\n\n"
            f"Увидимся в {SURVEY_TIME}! 🕐"
        )
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def test_survey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(f"{MOOD_OPTIONS['excellent']['emoji']} {MOOD_OPTIONS['excellent']['text']}", callback_data='mood_excellent'),
            InlineKeyboardButton(f"{MOOD_OPTIONS['good']['emoji']} {MOOD_OPTIONS['good']['text']}", callback_data='mood_good')
        ],
        [
            InlineKeyboardButton(f"{MOOD_OPTIONS['bad']['emoji']} {MOOD_OPTIONS['bad']['text']}", callback_data='mood_bad'),
            InlineKeyboardButton(f"{MOOD_OPTIONS['hard']['emoji']} {MOOD_OPTIONS['hard']['text']}", callback_data='mood_hard')
        ],
        [
            InlineKeyboardButton(f"{MOOD_OPTIONS['critical']['emoji']} {MOOD_OPTIONS['critical']['text']}", callback_data='mood_critical')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🧪 Тестовый опрос:\n\nКак прошел твой день? 🤔", reply_markup=reply_markup)

async def mood_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    mood = query.data.replace('mood_', '')
    today = datetime.now(MSK_TZ).strftime('%Y-%m-%d')
    
    if today not in feedback_bot.responses:
        feedback_bot.responses[today] = {}
    
    feedback_bot.responses[today][user_id] = {
        'username': feedback_bot.users.get(user_id, {}).get('username', 'Unknown'),
        'mood': mood,
        'mood_text': MOOD_OPTIONS[mood]['text'],
        'mood_emoji': MOOD_OPTIONS[mood]['emoji'],
        'timestamp': datetime.now(MSK_TZ).isoformat()
    }
    
    await query.edit_message_text(f"Ты выбрал: {MOOD_OPTIONS[mood]['emoji']} {MOOD_OPTIONS[mood]['text']}")
    await context.bot.send_message(chat_id=query.message.chat_id, text="Каким объектом/проектом сегодня занимался? 📝")
    
    feedback_bot.waiting_for_project.add(user_id)
    feedback_bot.save_responses()

async def project_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if user_id in feedback_bot.waiting_for_project and update.message.text:
        today = datetime.now(MSK_TZ).strftime('%Y-%m-%d')
        
        if (today in feedback_bot.responses and user_id in feedback_bot.responses[today]):
            feedback_bot.responses[today][user_id]['project'] = update.message.text
            feedback_bot.responses[today][user_id]['completed_at'] = datetime.now(MSK_TZ).isoformat()
        
        feedback_bot.waiting_for_project.discard(user_id)
        feedback_bot.save_responses()
        
        await update.message.reply_text(f"Спасибо за обратную связь! 👍\nУвидимся завтра в {SURVEY_TIME}.")

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    await update.message.reply_text("📊 Формирую отчет...")
    await generate_daily_report_async()
    await update.message.reply_text("✅ Отчет сформирован и отправлен!")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для просмотра статистики (только для менеджера)"""
    user_id = str(update.effective_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await update.message.reply_text(
            "❌ У вас нет прав для выполнения этой команды.\n"
            "Эта команда доступна только администратору."
        )
        return
    
    total_users = len(feedback_bot.users)
    total_days = len(feedback_bot.responses)
    
    # Считаем админов и обычных пользователей
    admin_count = sum(1 for user in feedback_bot.users.values() if user.get('is_admin', False))
    employee_count = total_users - admin_count
    
    stats = f"📈 **Статистика бота:**\n\n"
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
            stats += f"📈 Процент участия: {participation_rate:.1f}%"
    
    await update.message.reply_text(stats, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи с разными сообщениями для админа и сотрудников"""
    user_id = str(update.effective_user.id)
    
    if user_id == MANAGER_CHAT_ID:
        # Помощь для администратора
        help_message = (
            "👑 **Справка для администратора**\n\n"
            "🔧 **Команды управления:**\n"
            "• `/start` - перезапуск и информация\n"
            "• `/report` - получить отчет за сегодня\n"
            "• `/stats` - статистика по боту и пользователям\n"
            "• `/test` - тестовый опрос (для проверки)\n"
            "• `/schedule` - посмотреть текущее расписание\n"
            "• `/help` - эта справка\n\n"
            "📊 **Автоматические процессы:**\n"
            f"• **{SURVEY_TIME} МСК** - автоматический опрос всех сотрудников\n"
            f"• **{REPORT_TIME} МСК** - автоматический отчет вам в ЛС\n\n"
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
            "2. Выберите один из 5 смайликов:\n"
            "   👍 Отлично • 👌 Нормально • 😔 Не очень\n"
            "   😓 Тяжело • 😭 Критично\n"
            "3. Напишите, над каким проектом/задачей работали\n"
            "4. Готово! Ваш ответ сохранен\n\n"
            "🔒 **Конфиденциальность:**\n"
            "Ваши ответы видит только руководитель в общем отчете.\n"
            "Личные данные не передаются третьим лицам.\n\n"
            "❓ **Вопросы?** Обратитесь к администратору."
        )
    
    await update.message.reply_text(help_message, parse_mode='Markdown')

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для просмотра текущего расписания (только для админа)"""
    user_id = str(update.effective_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await update.message.reply_text(
            "❌ У вас нет прав для выполнения этой команды.\n"
            "Эта команда доступна только администратору."
        )
        return
    
    # Получаем текущее время в МСК
    current_time_msk = datetime.now(MSK_TZ).strftime('%H:%M')
    current_date = datetime.now(MSK_TZ).strftime('%d.%m.%Y')
    
    schedule_info = (
        f"🕐 **Текущее расписание**\n\n"
        f"📅 Сегодня: {current_date}\n"
        f"🕐 Сейчас: {current_time_msk} МСК\n\n"
        f"📋 **Автоматические задачи:**\n"
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
    
    await update.message.reply_text(schedule_info, parse_mode='Markdown')

def main():
    if not BOT_TOKEN or not MANAGER_CHAT_ID:
        logger.error("BOT_TOKEN или MANAGER_CHAT_ID не найдены в переменных окружения!")
        return
    
    # Запускаем планировщик в отдельном потоке
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("test", test_survey_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("schedule", schedule_command))
    application.add_handler(CallbackQueryHandler(mood_callback, pattern="^mood_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, project_message))
    
    logger.info("🚀 Бот запущен и готов к работе!")
    logger.info(f"📅 Опрос: {SURVEY_TIME} МСК")
    logger.info(f"📊 Отчет: {REPORT_TIME} МСК")
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()