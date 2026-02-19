"""
Работа с JSON файлами (база данных)
"""
import json
from datetime import datetime, date
from workalendar.europe import Russia
from config import (
    USER_DATA_FILE, RESPONSES_FILE, REMINDER_SETTINGS_FILE, HOLIDAYS_FILE,
    logger
)

# Производственный календарь РФ
calendar = Russia()


class FeedbackBot:
    def __init__(self):
        self.users = self.load_users()
        self.responses = self.load_responses()
        self.reminder_settings = self.load_reminder_settings()
        self.holidays_settings = self.load_holidays_settings()
        self.reminder_tasks = {}  # Хранение задач напоминаний
    
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
    
    def load_reminder_settings(self):
        """Загружает настройки напоминаний"""
        try:
            if REMINDER_SETTINGS_FILE.exists():
                with open(REMINDER_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.info("Создаю файл reminder_settings.json с дефолтными настройками")
                default = {
                    "enabled": True,
                    "times": ["17:30", "18:00", "18:30"]
                }
                self.save_reminder_settings(default)
                return default
        except Exception as e:
            logger.error(f"Ошибка загрузки reminder_settings.json: {e}")
            return {"enabled": True, "times": ["17:30", "18:00", "18:30"]}
    
    def save_reminder_settings(self, settings):
        """Сохраняет настройки напоминаний"""
        try:
            with open(REMINDER_SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            logger.info("Настройки напоминаний сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения reminder_settings.json: {e}")
    
    def load_holidays_settings(self):
        """Загружает настройки выходных и отпусков"""
        try:
            if HOLIDAYS_FILE.exists():
                with open(HOLIDAYS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.info("Создаю файл holidays.json с дефолтными настройками")
                default = {
                    "saturday_working": False,
                    "sunday_working": False,
                    "vacations": {}
                }
                self.save_holidays_settings(default)
                return default
        except Exception as e:
            logger.error(f"Ошибка загрузки holidays.json: {e}")
            return {"saturday_working": False, "sunday_working": False, "vacations": {}}
    
    def save_holidays_settings(self, settings):
        """Сохраняет настройки выходных и отпусков"""
        try:
            with open(HOLIDAYS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            logger.info("Настройки выходных и отпусков сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения holidays.json: {e}")
    
    def is_working_day(self, check_date):
        """Проверяет, является ли день рабочим"""
        # Проверяем праздники РФ
        if not calendar.is_working_day(check_date):
            return False
        
        # Проверяем настройки выходных
        weekday = check_date.weekday()
        if weekday == 5 and not self.holidays_settings.get("saturday_working", False):  # Суббота
            return False
        if weekday == 6 and not self.holidays_settings.get("sunday_working", False):  # Воскресенье
            return False
        
        return True
    
    def is_user_on_vacation(self, user_id, check_date):
        """Проверяет, находится ли пользователь в отпуске"""
        vacations = self.holidays_settings.get("vacations", {})
        if user_id not in vacations:
            return False
        
        vacation = vacations[user_id]
        start_date = datetime.strptime(vacation["start"], '%Y-%m-%d').date()
        end_date = datetime.strptime(vacation["end"], '%Y-%m-%d').date()
        
        return start_date <= check_date <= end_date
    
    def cleanup_expired_vacations(self):
        """Удаляет завершенные отпуска (которые уже закончились)"""
        from datetime import timedelta
        
        vacations = self.holidays_settings.get("vacations", {})
        if not vacations:
            return
        
        today = date.today()
        expired_users = []
        
        for user_id, vacation in vacations.items():
            end_date = datetime.strptime(vacation["end"], '%Y-%m-%d').date()
            # Удаляем отпуска, которые уже закончились (дата окончания в прошлом)
            if end_date < today:
                expired_users.append(user_id)
        
        if expired_users:
            for user_id in expired_users:
                del self.holidays_settings["vacations"][user_id]
            self.save_holidays_settings(self.holidays_settings)
            logger.info(f"Удалено завершенных отпусков: {len(expired_users)}")


# Создаем глобальный экземпляр
feedback_bot = FeedbackBot()
