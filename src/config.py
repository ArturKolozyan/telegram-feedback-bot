"""
Конфигурация бота и константы
"""
import os
from datetime import timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
import logging

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация из .env
BOT_TOKEN = os.getenv('BOT_TOKEN')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID')


def validate_time_format(time_str, default_time):
    """Валидирует формат времени HH:MM"""
    from datetime import datetime
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
REMINDER_SETTINGS_FILE = DATA_DIR / 'reminder_settings.json'
HOLIDAYS_FILE = DATA_DIR / 'holidays.json'

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
