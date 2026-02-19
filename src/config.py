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

# Московский часовой пояс
MSK_TZ = timezone(timedelta(hours=3))

# Пути к файлам данных
DATA_DIR = Path.cwd() / 'data'
REPORTS_DIR = Path.cwd() / 'reports'
USER_DATA_FILE = DATA_DIR / 'users.json'
RESPONSES_FILE = DATA_DIR / 'responses.json'
REMINDER_SETTINGS_FILE = DATA_DIR / 'reminder_settings.json'
HOLIDAYS_FILE = DATA_DIR / 'holidays.json'
SCHEDULE_SETTINGS_FILE = DATA_DIR / 'schedule_settings.json'

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
