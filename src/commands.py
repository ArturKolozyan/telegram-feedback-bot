"""
Обработчики команд бота
"""
import csv
from datetime import datetime
from collections import Counter
from pathlib import Path

from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import (
    MANAGER_CHAT_ID, MSK_TZ, MOOD_OPTIONS,
    REPORTS_DIR, logger
)
from database import feedback_bot, calendar


# FSM состояния
class FeedbackStates(StatesGroup):
    waiting_for_project = State()

class VacationStates(StatesGroup):
    waiting_for_dates = State()
    waiting_for_edit_dates = State()


# Клавиатура для администратора
admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Меню")]
    ],
    resize_keyboard=True,
    persistent=True
)


# ============================================================================
# БАЗОВЫЕ КОМАНДЫ
# ============================================================================

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
        survey_time = feedback_bot.schedule_settings.get("survey_time", "17:00")
        report_time = feedback_bot.schedule_settings.get("report_time", "21:00")
        
        welcome_message = (
            f"👑 Добро пожаловать, {user.first_name}!\n\n"
            "Вы вошли как *администратор*\n\n"
            "📊 **ОТЧЕТЫ И СТАТИСТИКА**\n"
            "• `/report` - отчет за сегодня\n"
            "• `/createreport` - создать отчет заново\n"
            "• `/download` - скачать CSV за сегодня\n"
            "• `/download ДД.ММ.ГГГГ` - CSV за дату\n"
            "• `/reports` - список всех отчетов\n"
            "• `/stats` - статистика по боту\n\n"
            "👥 **УПРАВЛЕНИЕ СОТРУДНИКАМИ**\n"
            "• `/users` - список и удаление\n"
            "• `/vacation` - назначить отпуск\n"
            "• `/vacations` - список отпусков\n\n"
            "⚙️ **НАСТРОЙКИ**\n"
            "• `/reminders` - напоминания\n"
            "• `/weekends` - выходные дни\n"
            "• `/holidays` - праздники РФ\n"
            "• `/schedule` - расписание\n\n"
            "🔧 **ПРОЧЕЕ**\n"
            "• `/test` - тестовый опрос\n"
            "• `/help` - полная справка\n\n"
            "⏰ **Автоматика:**\n"
            f"• {survey_time} МСК - опрос\n"
            f"• {report_time} МСК - отчет\n\n"
            f"🆔 ID: `{chat_id}`"
        )
    else:
        survey_time = feedback_bot.schedule_settings.get("survey_time", "17:00")
        
        welcome_message = (
            f"👋 Привет, {user.first_name}!\n\n"
            f"Я буду каждый день в {survey_time} спрашивать, как прошел твой рабочий день.\n"
            "Это займет всего пару секунд и поможет улучшить рабочие процессы!\n\n"
            "📝 **Как это работает:**\n"
            f"1. В {survey_time} я пришлю вопрос с вариантами ответа\n"
            "2. Выберите смайлик, соответствующий вашему настроению\n"
            "3. Напишите, над каким проектом работали\n"
            "4. Готово! Спасибо за участие 😊\n\n"
            "🔧 **Доступные команды:**\n"
            "• `/test` - попробовать опрос прямо сейчас\n"
            "• `/mymonth` - мой отчет за прошлый месяц\n"
            "• `/help` - помощь\n\n"
            f"Увидимся в {survey_time}! 🕐"
        )
    
    await message.answer(welcome_message, parse_mode='Markdown', reply_markup=admin_keyboard if chat_id == MANAGER_CHAT_ID else None)


async def help_command(message: Message):
    """Команда помощи с разными версиями для админа и пользователя"""
    user_id = str(message.from_user.id)
    
    if user_id == MANAGER_CHAT_ID:
        survey_time = feedback_bot.schedule_settings.get("survey_time", "17:00")
        report_time = feedback_bot.schedule_settings.get("report_time", "21:00")
        
        # Помощь для администратора
        help_message = (
            "👑 **Справка для администратора**\n\n"
            "🔧 **Команды управления:**\n"
            "• `/start` - перезапуск и информация\n"
            "• `/report` - получить отчет за сегодня\n"
            "• `/createreport` - создать отчет (перезапишет старый)\n"
            "• `/download` - скачать CSV за сегодня\n"
            "• `/download ДД.ММ.ГГГГ` - скачать за дату\n"
            "• `/reports` - список всех отчетов\n"
            "• `/users` - управление пользователями\n"
            "• `/stats` - статистика по пользователям\n"
            "• `/test` - тестовый опрос\n"
            "• `/schedule` - посмотреть расписание\n"
            "• `/help` - эта справка\n\n"
            "⏰ **Напоминания:**\n"
            "• `/reminders` - настройки напоминаний\n"
            "• `/reminders set ЧЧ:ММ,ЧЧ:ММ` - установить время\n"
            "• `/reminders on/off` - включить/отключить\n\n"
            "📅 **Выходные и отпуска:**\n"
            "• `/weekends` - настройки выходных\n"
            "• `/saturday on/off` - суббота рабочий/выходной\n"
            "• `/sunday on/off` - воскресенье рабочий/выходной\n"
            "• `/holidays` - список праздников РФ\n"
            "• `/vacation @user ДД.ММ.ГГГГ-ДД.ММ.ГГГГ` - назначить отпуск\n"
            "• `/vacations` - список отпусков\n"
            "• `/removevacation @user` - отменить отпуск\n\n"
            "⏰ **Расписание:**\n"
            "• `/setsurvey ЧЧ:ММ` - изменить время опроса\n"
            "• `/setreport ЧЧ:ММ` - изменить время отчета\n"
            "• `/adminsurvey on/off` - включить/отключить опросы для админа\n\n"
            "📊 **Автоматические процессы:**\n"
            f"• **{survey_time} МСК** - автоматический опрос всех сотрудников\n"
            f"• **{report_time} МСК** - автоматический отчет + CSV файл\n"
            "• **01 число каждого месяца** - месячные отчеты сотрудникам"
        )
    else:
        survey_time = feedback_bot.schedule_settings.get("survey_time", "17:00")
        
        # Помощь для сотрудника
        help_message = (
            "👋 **Справка для сотрудника**\n\n"
            "🔧 **Доступные команды:**\n"
            "• `/start` - перезапуск бота\n"
            "• `/test` - попробовать опрос прямо сейчас\n"
            "• `/mymonth` - мой отчет за прошлый месяц\n"
            "• `/help` - эта справка\n\n"
            "📝 **Как проходит опрос:**\n"
            f"1. **{survey_time} МСК** - я пришлю вопрос о вашем дне\n"
            "2. Выберите смайлик, соответствующий настроению:\n"
            "   👍 Отлично • 👌 Нормально • 😔 Не очень\n"
            "   😓 Тяжело • 😭 Критично\n"
            "3. Напишите, над каким проектом работали сегодня\n"
            "4. Готово! Ваш ответ сохранен\n\n"
            "📊 **Месячные отчеты:**\n"
            "• Каждое 1-е число месяца вы получите отчет\n"
            "• Статистика настроения и активности\n"
            "• Топ проектов за месяц\n"
            "• Используйте `/mymonth` чтобы посмотреть отчет\n\n"
            "🔒 **Конфиденциальность:**\n"
            "Ваши ответы видит только руководитель.\n"
            "Личные данные не передаются третьим лицам.\n\n"
            "❓ **Вопросы?** Обратитесь к администратору."
        )
    
    await message.answer(help_message, parse_mode='Markdown')


async def menu_button_handler(message: Message):
    """Обработчик кнопки 📋 Меню для администратора"""
    user_id = str(message.from_user.id)
    
    # Проверяем что это администратор
    if user_id != MANAGER_CHAT_ID:
        return
    
    survey_time = feedback_bot.schedule_settings.get("survey_time", "17:00")
    report_time = feedback_bot.schedule_settings.get("report_time", "21:00")
    
    # Отправляем структурированное меню
    welcome_message = (
        f"👑 Меню администратора\n\n"
        "📊 **ОТЧЕТЫ И СТАТИСТИКА**\n"
        "• `/report` - отчет за сегодня\n"
        "• `/createreport` - создать отчет заново\n"
        "• `/download` - скачать CSV за сегодня\n"
        "• `/download ДД.ММ.ГГГГ` - CSV за дату\n"
        "• `/reports` - список всех отчетов\n"
        "• `/stats` - статистика по боту\n\n"
        "👥 **УПРАВЛЕНИЕ СОТРУДНИКАМИ**\n"
        "• `/users` - список и удаление\n"
        "• `/vacation` - назначить отпуск\n"
        "• `/vacations` - список отпусков\n\n"
        "⚙️ **НАСТРОЙКИ**\n"
        "• `/reminders` - напоминания\n"
        "• `/weekends` - выходные дни\n"
        "• `/holidays` - праздники РФ\n"
        "• `/schedule` - расписание\n\n"
        "🔧 **ПРОЧЕЕ**\n"
        "• `/test` - тестовый опрос\n"
        "• `/help` - полная справка\n\n"
        "⏰ **Автоматика:**\n"
        f"• {survey_time} МСК - опрос\n"
        f"• {report_time} МСК - отчет"
    )
    
    await message.answer(welcome_message, parse_mode='Markdown', reply_markup=admin_keyboard)


# ============================================================================
# ОПРОСЫ
# ============================================================================

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
    
    survey_time = feedback_bot.schedule_settings.get("survey_time", "17:00")
    await message.answer(f"Спасибо за обратную связь! 👍\nУвидимся завтра в {survey_time}.")


# ============================================================================
# КОМАНДЫ АДМИНИСТРАТОРА - ОТЧЕТЫ
# ============================================================================

async def save_report_to_csv(date_str, responses):
    """Сохраняет отчет в CSV формате для Excel"""
    try:
        csv_file = REPORTS_DIR / f"report_{date_str}.csv"
        
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Дата', 'Пользователь', 'Настроение', 'Проект', 'Время ответа'])
            
            for response in responses.values():
                writer.writerow([
                    date_str,
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


async def send_csv_file(bot_instance, chat_id, csv_path, date_str):
    """Отправляет CSV файл в Telegram"""
    try:
        # Конвертируем дату в русский формат для отображения
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d.%m.%Y')
        except:
            formatted_date = date_str
        
        file = FSInputFile(csv_path)
        await bot_instance.send_document(
            chat_id=chat_id,
            document=file,
            caption=f"📎 Отчет за {formatted_date} в формате CSV\n\nОткройте в Excel для удобного просмотра."
        )
        logger.info(f"CSV файл отправлен: {csv_path}")
    except Exception as e:
        logger.error(f"Ошибка отправки CSV файла: {e}")


async def report_command(message: Message, bot_instance):
    """Команда для ручной генерации отчета (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    await message.answer("📊 Формирую отчет за сегодня...")
    
    # Импортируем функцию из bot.py
    from bot import generate_daily_report_async
    await generate_daily_report_async(bot_instance)


async def force_report_command(message: Message, bot_instance):
    """Команда для создания отчета с перезаписью (только для админа)"""
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
    
    # Генерируем отчет
    from bot import generate_daily_report_async
    await generate_daily_report_async(bot_instance)
    
    if file_exists:
        await message.answer("✅ Отчет обновлен и отправлен!")
    else:
        await message.answer("✅ Отчет создан и отправлен!")


async def download_command(message: Message, bot_instance):
    """Команда для скачивания отчета (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    # Парсим аргументы команды
    args = message.text.split(maxsplit=1)
    
    if len(args) == 1:
        # Без аргументов - отчет за сегодня
        date_str = datetime.now(MSK_TZ).strftime('%Y-%m-%d')
    else:
        # С датой в русском формате (ДД.ММ.ГГГГ)
        date_input = args[1].strip()
        
        # Пробуем парсить русский формат
        try:
            date_obj = datetime.strptime(date_input, '%d.%m.%Y')
            date_str = date_obj.strftime('%Y-%m-%d')
        except ValueError:
            # Если не получилось, пробуем старый формат для совместимости
            try:
                datetime.strptime(date_input, '%Y-%m-%d')
                date_str = date_input
            except ValueError:
                await message.answer(
                    "❌ Неверный формат даты. Используйте:\n"
                    "• `/download` - отчет за сегодня\n"
                    "• `/download ДД.ММ.ГГГГ` - отчет за конкретную дату"
                )
                return
    
    csv_file = REPORTS_DIR / f"report_{date_str}.csv"
    
    if not csv_file.exists():
        await message.answer(
            f"❌ Отчет за {date_str} не найден.\n\n"
            "Возможные причины:\n"
            "• Отчет еще не был создан\n"
            "• Никто не ответил на опрос в этот день\n"
            "• Неверная дата"
        )
        return
    
    await message.answer("📎 Отправляю файл...")
    await send_csv_file(bot_instance, message.chat.id, csv_file, date_str)


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
    
    for i, csv_file in enumerate(csv_files[:10], 1):
        # Извлекаем дату из имени файла
        date_str = csv_file.stem.replace('report_', '')
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d.%m.%Y')
            
            # Получаем размер файла
            file_size = csv_file.stat().st_size
            size_kb = file_size / 1024
            
            report_list += f"{i}. {formatted_date} - {size_kb:.1f} KB\n"
        except:
            continue
    
    if len(csv_files) > 10:
        report_list += f"\n... и еще {len(csv_files) - 10} отчетов\n"
    
    report_list += (
        f"\n📊 Всего отчетов: {len(csv_files)}\n\n"
        "**Как скачать:**\n"
        "• `/download` - отчет за сегодня\n"
        "• `/download ДД.ММ.ГГГГ` - отчет за конкретную дату"
    )
    
    await message.answer(report_list, parse_mode='Markdown')


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


async def schedule_command(message: Message):
    """Команда для просмотра текущего расписания (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    # Получаем текущее время в МСК
    current_time_msk = datetime.now(MSK_TZ).strftime('%H:%M:%S')
    current_date = datetime.now(MSK_TZ).strftime('%d.%m.%Y')
    
    # Получаем настройки расписания
    survey_time = feedback_bot.schedule_settings.get("survey_time", "17:00")
    report_time = feedback_bot.schedule_settings.get("report_time", "21:00")
    admin_as_employee = feedback_bot.schedule_settings.get("admin_as_employee", False)
    
    # Статус напоминаний
    reminders_enabled = feedback_bot.reminder_settings.get("enabled", True)
    reminder_times = feedback_bot.reminder_settings.get("times", [])
    reminders_status = "✅ Включены" if reminders_enabled else "❌ Отключены"
    
    # Статус админа
    admin_status = "✅ Включен" if admin_as_employee else "❌ Отключен"
    
    schedule_message = (
        f"🕐 **Текущее расписание**\n\n"
        f"📅 Сегодня: {current_date}\n"
        f"🕐 Сейчас: {current_time_msk} МСК\n\n"
        f"⏰ **Автоматические задачи:**\n"
        f"• **Опрос сотрудников:** {survey_time} МСК\n"
        f"• **Отчет менеджеру:** {report_time} МСК\n\n"
        f"🔔 **Напоминания:** {reminders_status}\n"
    )
    
    if reminders_enabled and reminder_times:
        schedule_message += f"• Время: {', '.join(reminder_times)}\n"
    
    schedule_message += (
        f"\n👤 **Администратор как сотрудник:** {admin_status}\n"
        f"\n⚙️ **Изменение расписания:**\n"
        f"• `/setsurvey ЧЧ:ММ` - изменить время опроса\n"
        f"• `/setreport ЧЧ:ММ` - изменить время отчета\n"
        f"• `/adminsurvey on/off` - включить/отключить опросы для админа\n\n"
        f"Изменения применяются сразу, перезапуск не требуется."
    )
    
    await message.answer(schedule_message, parse_mode='Markdown')


# ============================================================================
# УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
# ============================================================================

async def users_command(message: Message):
    """Команда для просмотра списка пользователей с пагинацией"""
    user_id = str(message.from_user.id)

    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return

    if not feedback_bot.users:
        await message.answer("👥 Пользователей пока нет.")
        return

    # Показываем первую страницу
    await show_users_page(message, page=0)


async def show_users_page(message_or_callback, page=0, edit=False):
    """Показывает страницу со списком пользователей"""
    USERS_PER_PAGE = 10
    
    # Получаем список пользователей (исключая админа)
    users_list = [(uid, data) for uid, data in feedback_bot.users.items() if uid != MANAGER_CHAT_ID]
    total_users = len(users_list)
    total_pages = (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE
    
    if total_pages == 0:
        text = "👥 Нет сотрудников для управления"
        keyboard = None
    else:
        # Ограничиваем страницу
        page = max(0, min(page, total_pages - 1))
        
        # Получаем пользователей для текущей страницы
        start_idx = page * USERS_PER_PAGE
        end_idx = start_idx + USERS_PER_PAGE
        page_users = users_list[start_idx:end_idx]
        
        # Формируем текст
        total_days = len(feedback_bot.responses)
        text = f"👥 Пользователи ({total_users})\n"
        text += f"Страница {page + 1} из {total_pages}\n\n"
        
        keyboard_buttons = []
        
        for idx, (chat_id, user_data) in enumerate(page_users, start=start_idx + 1):
            username = user_data.get('username', 'Неизвестный')
            first_name = user_data.get('first_name', 'Неизвестный')
            
            # Считаем ответы
            user_responses = sum(1 for day_resp in feedback_bot.responses.values() if chat_id in day_resp)
            participation = (user_responses / total_days * 100) if total_days > 0 else 0
            
            text += f"{idx}. {first_name} (@{username})\n"
            text += f"   📊 Ответов: {user_responses}/{total_days} ({participation:.0f}%)\n\n"
            
            # Кнопка удаления
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"❌ {idx}. {first_name}",
                    callback_data=f"delete_user_{chat_id}"
                )
            ])
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"users_page_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="users_page_current"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"users_page_{page+1}"))
        
        keyboard_buttons.append(nav_buttons)
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    # Отправляем или редактируем сообщение
    if edit and isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=keyboard)
    else:
        msg = message_or_callback if isinstance(message_or_callback, Message) else message_or_callback.message
        await msg.answer(text, reply_markup=keyboard)


async def users_page_callback(callback: CallbackQuery):
    """Обработчик переключения страниц пользователей"""
    await callback.answer()
    
    if str(callback.from_user.id) != MANAGER_CHAT_ID:
        return
    
    # Извлекаем номер страницы
    if callback.data == "users_page_current":
        return
    
    page = int(callback.data.split('_')[-1])
    await show_users_page(callback, page=page, edit=True)


async def delete_user_callback(callback: CallbackQuery):
    """Обработчик кнопки удаления пользователя"""
    await callback.answer()
    
    # Проверяем что это админ
    if str(callback.from_user.id) != MANAGER_CHAT_ID:
        await callback.message.answer("❌ Только администратор может удалять пользователей.")
        return
    
    # Извлекаем ID пользователя из callback_data
    user_to_delete = callback.data.replace('delete_user_', '')
    
    # Проверяем что пользователь существует
    if user_to_delete not in feedback_bot.users:
        await callback.message.answer("❌ Пользователь не найден.")
        return
    
    # Получаем данные пользователя
    user_data = feedback_bot.users[user_to_delete]
    username = user_data.get('first_name', 'Неизвестный')
    
    # Создаем кнопки подтверждения
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{user_to_delete}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")
        ]
    ])
    
    await callback.message.answer(
        f"⚠️ Подтверждение удаления\n\n"
        f"Вы действительно хотите удалить пользователя {username}?\n\n"
        f"❗ Это действие нельзя отменить!\n"
        f"❗ Все ответы пользователя останутся в отчетах.",
        reply_markup=confirm_keyboard
    )


async def confirm_delete_callback(callback: CallbackQuery):
    """Обработчик подтверждения удаления пользователя"""
    await callback.answer()
    
    # Проверяем что это админ
    if str(callback.from_user.id) != MANAGER_CHAT_ID:
        return
    
    if callback.data.startswith('confirm_delete_'):
        # Извлекаем ID пользователя
        user_to_delete = callback.data.replace('confirm_delete_', '')
        
        # Проверяем что пользователь существует
        if user_to_delete not in feedback_bot.users:
            await callback.message.edit_text("❌ Пользователь не найден.")
            return
        
        # Получаем данные пользователя для логирования
        user_data = feedback_bot.users[user_to_delete]
        username = user_data.get('first_name', 'Неизвестный')
        user_username = user_data.get('username', 'Неизвестный')
        
        # Удаляем отпуск если есть
        vacations = feedback_bot.holidays_settings.get("vacations", {})
        had_vacation = user_to_delete in vacations
        if had_vacation:
            del feedback_bot.holidays_settings["vacations"][user_to_delete]
            feedback_bot.save_holidays_settings(feedback_bot.holidays_settings)
        
        # Удаляем пользователя
        del feedback_bot.users[user_to_delete]
        feedback_bot.save_users()
        
        # Логируем удаление
        logger.info(f"Администратор удалил пользователя: {username} (@{user_username}, ID: {user_to_delete})")
        
        vacation_note = "\n\n📅 Отпуск пользователя также удален" if had_vacation else ""
        
        await callback.message.edit_text(
            f"✅ Пользователь удален\n\n"
            f"Пользователь {username} (@{user_username}) успешно удален из системы.{vacation_note}"
        )
        
    elif callback.data == 'cancel_delete':
        await callback.message.edit_text("❌ Удаление отменено.")


# ============================================================================
# КОМАНДЫ НАПОМИНАНИЙ
# ============================================================================

async def reminders_command(message: Message):
    """Команда для управления напоминаниями (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    enabled = feedback_bot.reminder_settings.get("enabled", True)
    times = feedback_bot.reminder_settings.get("times", [])
    status = "✅ Включены" if enabled else "❌ Отключены"
    
    reminder_text = (
        f"⏰ **Настройки напоминаний**\n\n"
        f"Статус: {status}\n"
        f"Время напоминаний: {', '.join(times)}\n\n"
        f"**Команды:**\n"
        f"• `/reminders set 17:30,18:00,18:30` - установить время\n"
        f"• `/reminders on` - включить напоминания\n"
        f"• `/reminders off` - отключить напоминания"
    )
    
    await message.answer(reminder_text, parse_mode='Markdown')


async def reminders_set_command(message: Message):
    """Обработка команд настройки напоминаний"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    args = message.text.split(maxsplit=2)
    
    if len(args) < 2:
        await message.answer("❌ Неверный формат команды. Используйте:\n`/reminders set 17:30,18:00,18:30`\n`/reminders on`\n`/reminders off`", parse_mode='Markdown')
        return
    
    action = args[1].lower()
    
    if action == "set":
        if len(args) < 3:
            await message.answer("❌ Неверный формат команды. Используйте:\n`/reminders set 17:30,18:00,18:30`", parse_mode='Markdown')
            return
            
        # Парсим время
        times_str = args[2]
        times = [t.strip() for t in times_str.split(',')]
        
        # Валидация времени
        valid_times = []
        for time_str in times:
            try:
                datetime.strptime(time_str, '%H:%M')
                valid_times.append(time_str)
            except ValueError:
                await message.answer(f"❌ Неверный формат времени: {time_str}\nИспользуйте формат ЧЧ:ММ")
                return
        
        feedback_bot.reminder_settings["times"] = valid_times
        feedback_bot.save_reminder_settings(feedback_bot.reminder_settings)
        
        await message.answer(f"✅ Время напоминаний обновлено:\n{', '.join(valid_times)}")
        
    elif action == "on":
        feedback_bot.reminder_settings["enabled"] = True
        feedback_bot.save_reminder_settings(feedback_bot.reminder_settings)
        await message.answer("✅ Напоминания включены")
        
    elif action == "off":
        feedback_bot.reminder_settings["enabled"] = False
        feedback_bot.save_reminder_settings(feedback_bot.reminder_settings)
        await message.answer("❌ Напоминания отключены")
    else:
        await message.answer("❌ Неизвестная команда. Используйте: set, on, off")


# ============================================================================
# КОМАНДЫ ВЫХОДНЫХ И ОТПУСКОВ
# ============================================================================

async def weekends_command(message: Message):
    """Команда для просмотра настроек выходных (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    saturday_working = feedback_bot.holidays_settings.get("saturday_working", False)
    sunday_working = feedback_bot.holidays_settings.get("sunday_working", False)
    
    saturday_status = "✅ Рабочий день" if saturday_working else "❌ Выходной"
    sunday_status = "✅ Рабочий день" if sunday_working else "❌ Выходной"
    
    weekends_text = (
        f"📅 **Настройки выходных:**\n\n"
        f"Суббота: {saturday_status} (опросы {'отправляются' if saturday_working else 'не отправляются'})\n"
        f"Воскресенье: {sunday_status} (опросы {'отправляются' if sunday_working else 'не отправляются'})\n\n"
        f"**Команды:**\n"
        f"• `/saturday on` - сделать субботу рабочим днем\n"
        f"• `/saturday off` - сделать субботу выходным\n"
        f"• `/sunday on` - сделать воскресенье рабочим днем\n"
        f"• `/sunday off` - сделать воскресенье выходным"
    )
    
    await message.answer(weekends_text, parse_mode='Markdown')


async def saturday_command(message: Message):
    """Команда для настройки субботы (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Используйте: `/saturday on` или `/saturday off`", parse_mode='Markdown')
        return
    
    action = args[1].lower()
    if action == "on":
        feedback_bot.holidays_settings["saturday_working"] = True
        feedback_bot.save_holidays_settings(feedback_bot.holidays_settings)
        await message.answer("✅ Суббота теперь рабочий день. Опросы будут отправляться.")
    elif action == "off":
        feedback_bot.holidays_settings["saturday_working"] = False
        feedback_bot.save_holidays_settings(feedback_bot.holidays_settings)
        await message.answer("❌ Суббота теперь выходной. Опросы не будут отправляться.")
    else:
        await message.answer("❌ Используйте: `/saturday on` или `/saturday off`", parse_mode='Markdown')


async def sunday_command(message: Message):
    """Команда для настройки воскресенья (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Используйте: `/sunday on` или `/sunday off`", parse_mode='Markdown')
        return
    
    action = args[1].lower()
    if action == "on":
        feedback_bot.holidays_settings["sunday_working"] = True
        feedback_bot.save_holidays_settings(feedback_bot.holidays_settings)
        await message.answer("✅ Воскресенье теперь рабочий день. Опросы будут отправляться.")
    elif action == "off":
        feedback_bot.holidays_settings["sunday_working"] = False
        feedback_bot.save_holidays_settings(feedback_bot.holidays_settings)
        await message.answer("❌ Воскресенье теперь выходной. Опросы не будут отправляться.")
    else:
        await message.answer("❌ Используйте: `/sunday on` или `/sunday off`", parse_mode='Markdown')


async def holidays_command(message: Message):
    """Команда для просмотра праздников РФ"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    year = datetime.now(MSK_TZ).year
    holidays = calendar.holidays(year)
    
    holidays_text = f"📅 **Праздничные дни {year}:**\n\n"
    
    # Группируем по месяцам
    months_dict = {}
    for holiday_date, holiday_name in holidays:
        month = holiday_date.strftime('%B')
        month_ru = {
            'January': 'Январь', 'February': 'Февраль', 'March': 'Март',
            'April': 'Апрель', 'May': 'Май', 'June': 'Июнь',
            'July': 'Июль', 'August': 'Август', 'September': 'Сентябрь',
            'October': 'Октябрь', 'November': 'Ноябрь', 'December': 'Декабрь'
        }.get(month, month)
        
        if month_ru not in months_dict:
            months_dict[month_ru] = []
        
        months_dict[month_ru].append((holiday_date, holiday_name))
    
    # Формируем текст
    for month, month_holidays in months_dict.items():
        holidays_text += f"**{month}:**\n"
        for holiday_date, holiday_name in month_holidays:
            holidays_text += f"• {holiday_date.strftime('%d.%m')} - {holiday_name}\n"
        holidays_text += "\n"
    
    await message.answer(holidays_text, parse_mode='Markdown')


async def vacation_command(message: Message, state: FSMContext):
    """Команда для назначения отпуска с выбором пользователя или через аргументы"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    # Проверяем есть ли аргументы (старый формат: /vacation @user ДД.ММ.ГГГГ-ДД.ММ.ГГГГ)
    args = message.text.split(maxsplit=2)
    
    if len(args) >= 3:
        # Старый формат с аргументами
        username = args[1].replace('@', '')
        dates_str = args[2]
        
        # Находим пользователя
        target_user_id = None
        for uid, user_data in feedback_bot.users.items():
            if user_data.get('username', '').lower() == username.lower():
                target_user_id = uid
                break
        
        if not target_user_id:
            await message.answer(f"❌ Пользователь @{username} не найден")
            return
        
        # Парсим даты
        try:
            start_str, end_str = dates_str.split('-')
            start_date = datetime.strptime(start_str.strip(), '%d.%m.%Y').date()
            end_date = datetime.strptime(end_str.strip(), '%d.%m.%Y').date()
            
            if end_date < start_date:
                await message.answer("❌ Дата окончания не может быть раньше даты начала")
                return
            
            # Сохраняем отпуск
            if "vacations" not in feedback_bot.holidays_settings:
                feedback_bot.holidays_settings["vacations"] = {}
            
            feedback_bot.holidays_settings["vacations"][target_user_id] = {
                "username": username,
                "start": start_date.strftime('%Y-%m-%d'),
                "end": end_date.strftime('%Y-%m-%d'),
                "set_by_admin": user_id,
                "set_at": datetime.now(MSK_TZ).isoformat()
            }
            
            feedback_bot.save_holidays_settings(feedback_bot.holidays_settings)
            
            days_count = (end_date - start_date).days + 1
            user_data = feedback_bot.users[target_user_id]
            first_name = user_data.get('first_name', 'Неизвестный')
            
            await message.answer(
                f"✅ Отпуск установлен:\n"
                f"👤 {first_name} (@{username})\n"
                f"📅 С {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')}\n"
                f"📊 Продолжительность: {days_count} дней"
            )
            return
            
        except ValueError:
            await message.answer(
                "❌ Неверный формат даты.\n\n"
                "Используйте формат: ДД.ММ.ГГГГ-ДД.ММ.ГГГГ\n"
                "Например: 10.03.2026-20.03.2026"
            )
            return
    
    # Новый формат - интерактивный выбор
    if not feedback_bot.users or len(feedback_bot.users) <= 1:
        await message.answer("👥 Нет сотрудников для назначения отпуска")
        return
    
    await show_vacation_page(message, page=0)


async def show_vacation_page(message_or_callback, page=0, edit=False):
    """Показывает страницу со списком пользователей для назначения отпуска"""
    USERS_PER_PAGE = 10
    
    # Получаем список пользователей (исключая админа)
    users_list = [(uid, data) for uid, data in feedback_bot.users.items() if uid != MANAGER_CHAT_ID]
    total_users = len(users_list)
    
    # Проверяем есть ли сотрудники без отпусков
    vacations = feedback_bot.holidays_settings.get("vacations", {})
    users_without_vacation = [uid for uid, _ in users_list if uid not in vacations]
    
    if total_users == 0:
        text = "👥 Нет сотрудников"
        keyboard = None
    elif len(users_without_vacation) == 0:
        text = "📅 Назначение отпуска\n\n✅ Все сотрудники уже имеют назначенные отпуска\n\nИспользуйте /vacations для управления отпусками"
        keyboard = None
    else:
        total_pages = (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE
        
        # Ограничиваем страницу
        page = max(0, min(page, total_pages - 1))
        
        # Получаем пользователей для текущей страницы
        start_idx = page * USERS_PER_PAGE
        end_idx = start_idx + USERS_PER_PAGE
        page_users = users_list[start_idx:end_idx]
        
        # Формируем текст
        text = f"📅 Назначение отпуска\n"
        text += f"Выберите сотрудника (Страница {page + 1} из {total_pages}):\n\n"
        
        keyboard_buttons = []
        today = datetime.now(MSK_TZ).date()
        
        for idx, (chat_id, user_data) in enumerate(page_users, start=start_idx + 1):
            first_name = user_data.get('first_name', 'Неизвестный')
            username = user_data.get('username', 'Неизвестный')
            
            # Проверяем есть ли отпуск
            vacation_info = ""
            if chat_id in vacations:
                try:
                    vacation = vacations[chat_id]
                    start = datetime.strptime(vacation["start"], '%Y-%m-%d').date()
                    end = datetime.strptime(vacation["end"], '%Y-%m-%d').date()
                    days_count = (end - start).days + 1
                    
                    if start <= today <= end:
                        status = "🏖️ Отпуск"
                    elif start > today:
                        status = "📅 Запланирован"
                    else:
                        status = "⏹️ Завершен"
                    
                    vacation_info = f"\n   {status}: {start.strftime('%d.%m.%Y')}-{end.strftime('%d.%m.%Y')} ({days_count} дн.)"
                except (ValueError, KeyError) as e:
                    logger.error(f"Ошибка парсинга дат отпуска для пользователя {chat_id}: {e}")
                    vacation_info = "\n   ⚠️ Ошибка данных отпуска"
            
            text += f"{idx}. {first_name} (@{username}){vacation_info}\n"
            
            # Кнопка выбора пользователя
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{idx}. {first_name}",
                    callback_data=f"vacation_select_{chat_id}"
                )
            ])
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"vacation_page_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="vacation_page_current"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"vacation_page_{page+1}"))
        
        if nav_buttons:
            keyboard_buttons.append(nav_buttons)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    # Отправляем или редактируем сообщение
    if edit and isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=keyboard)
    else:
        msg = message_or_callback if isinstance(message_or_callback, Message) else message_or_callback.message
        await msg.answer(text, reply_markup=keyboard)


async def vacation_page_callback(callback: CallbackQuery):
    """Обработчик переключения страниц отпусков"""
    await callback.answer()
    
    if str(callback.from_user.id) != MANAGER_CHAT_ID:
        return
    
    if callback.data == "vacation_page_current":
        return
    
    page = int(callback.data.split('_')[-1])
    await show_vacation_page(callback, page=page, edit=True)


async def vacation_select_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора пользователя для отпуска"""
    await callback.answer()
    
    if str(callback.from_user.id) != MANAGER_CHAT_ID:
        return
    
    # Извлекаем ID пользователя
    user_id = callback.data.replace('vacation_select_', '')
    
    if user_id not in feedback_bot.users:
        await callback.message.answer("❌ Пользователь не найден")
        return
    
    user_data = feedback_bot.users[user_id]
    first_name = user_data.get('first_name', 'Неизвестный')
    username = user_data.get('username', 'Неизвестный')
    
    # Проверяем есть ли уже отпуск
    if user_id in feedback_bot.holidays_settings.get("vacations", {}):
        vacation = feedback_bot.holidays_settings["vacations"][user_id]
        start = datetime.strptime(vacation["start"], '%Y-%m-%d').date()
        end = datetime.strptime(vacation["end"], '%Y-%m-%d').date()
        days_count = (end - start).days + 1
        today = datetime.now(MSK_TZ).date()
        
        # Определяем статус
        if start <= today <= end:
            status = "🏖️ Сейчас в отпуске"
        elif start > today:
            status = "📅 Запланирован"
        else:
            status = "⏹️ Завершен"
        
        # Сохраняем данные для редактирования
        await state.update_data(
            vacation_user_id=user_id, 
            vacation_username=username, 
            vacation_first_name=first_name
        )
        
        # Показываем предупреждение с кнопками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Изменить даты", callback_data=f"vacation_edit_{user_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="vacation_cancel")
            ]
        ])
        
        await callback.message.answer(
            f"⚠️ У сотрудника {first_name} (@{username}) уже есть отпуск:\n\n"
            f"📅 С {start.strftime('%d.%m.%Y')} по {end.strftime('%d.%m.%Y')}\n"
            f"📊 Продолжительность: {days_count} дней\n"
            f"📌 Статус: {status}\n\n"
            f"Хотите изменить даты отпуска?",
            reply_markup=keyboard
        )
        return
    
    # Если отпуска нет - просим ввести даты
    await state.update_data(vacation_user_id=user_id, vacation_username=username, vacation_first_name=first_name)
    await state.set_state(VacationStates.waiting_for_dates)
    
    await callback.message.answer(
        f"✅ Выбран: {first_name} (@{username})\n\n"
        f"Введите даты отпуска в формате:\n"
        f"ДД.ММ.ГГГГ-ДД.ММ.ГГГГ\n\n"
        f"Например: 10.03.2026-20.03.2026"
    )


async def vacation_edit_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Изменить даты'"""
    await callback.answer()
    
    if str(callback.from_user.id) != MANAGER_CHAT_ID:
        return
    
    # Получаем данные из state
    user_data = await state.get_data()
    first_name = user_data.get('vacation_first_name', 'Неизвестный')
    username = user_data.get('vacation_username', 'Неизвестный')
    
    # Переводим в состояние редактирования
    await state.set_state(VacationStates.waiting_for_edit_dates)
    
    await callback.message.answer(
        f"✏️ Изменение отпуска для {first_name} (@{username})\n\n"
        f"Введите новые даты отпуска в формате:\n"
        f"ДД.ММ.ГГГГ-ДД.ММ.ГГГГ\n\n"
        f"Например: 10.03.2026-20.03.2026"
    )


async def vacation_cancel_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Отмена'"""
    await callback.answer()
    
    if str(callback.from_user.id) != MANAGER_CHAT_ID:
        return
    
    await state.clear()
    await callback.message.answer("❌ Операция отменена")


async def vacation_dates_handler(message: Message, state: FSMContext):
    """Обработчик ввода дат отпуска (новый отпуск)"""
    user_data = await state.get_data()
    target_user_id = user_data.get('vacation_user_id')
    username = user_data.get('vacation_username')
    first_name = user_data.get('vacation_first_name')
    
    if not target_user_id:
        await message.answer("❌ Ошибка: пользователь не выбран")
        await state.clear()
        return
    
    # Парсим даты
    try:
        dates_str = message.text.strip()
        start_str, end_str = dates_str.split('-')
        start_date = datetime.strptime(start_str.strip(), '%d.%m.%Y').date()
        end_date = datetime.strptime(end_str.strip(), '%d.%m.%Y').date()
        
        if end_date < start_date:
            await message.answer("❌ Дата окончания не может быть раньше даты начала\n\nПопробуйте еще раз:")
            return
        
        # Сохраняем отпуск
        if "vacations" not in feedback_bot.holidays_settings:
            feedback_bot.holidays_settings["vacations"] = {}
        
        feedback_bot.holidays_settings["vacations"][target_user_id] = {
            "username": username,
            "start": start_date.strftime('%Y-%m-%d'),
            "end": end_date.strftime('%Y-%m-%d'),
            "set_by_admin": str(message.from_user.id),
            "set_at": datetime.now(MSK_TZ).isoformat()
        }
        
        feedback_bot.save_holidays_settings(feedback_bot.holidays_settings)
        
        days_count = (end_date - start_date).days + 1
        
        await message.answer(
            f"✅ Отпуск установлен:\n"
            f"👤 {first_name} (@{username})\n"
            f"📅 С {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')}\n"
            f"📊 Продолжительность: {days_count} дней"
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты.\n\n"
            "Используйте формат: ДД.ММ.ГГГГ-ДД.ММ.ГГГГ\n"
            "Например: 10.03.2026-20.03.2026\n\n"
            "Попробуйте еще раз:"
        )


async def vacation_edit_dates_handler(message: Message, state: FSMContext):
    """Обработчик ввода дат отпуска (изменение существующего)"""
    user_data = await state.get_data()
    target_user_id = user_data.get('vacation_user_id')
    username = user_data.get('vacation_username')
    first_name = user_data.get('vacation_first_name')
    
    if not target_user_id:
        await message.answer("❌ Ошибка: пользователь не выбран")
        await state.clear()
        return
    
    # Парсим даты
    try:
        dates_str = message.text.strip()
        start_str, end_str = dates_str.split('-')
        start_date = datetime.strptime(start_str.strip(), '%d.%m.%Y').date()
        end_date = datetime.strptime(end_str.strip(), '%d.%m.%Y').date()
        
        if end_date < start_date:
            await message.answer("❌ Дата окончания не может быть раньше даты начала\n\nПопробуйте еще раз:")
            return
        
        # Обновляем отпуск
        if "vacations" not in feedback_bot.holidays_settings:
            feedback_bot.holidays_settings["vacations"] = {}
        
        feedback_bot.holidays_settings["vacations"][target_user_id] = {
            "username": username,
            "start": start_date.strftime('%Y-%m-%d'),
            "end": end_date.strftime('%Y-%m-%d'),
            "set_by_admin": str(message.from_user.id),
            "set_at": datetime.now(MSK_TZ).isoformat()
        }
        
        feedback_bot.save_holidays_settings(feedback_bot.holidays_settings)
        
        days_count = (end_date - start_date).days + 1
        
        await message.answer(
            f"✅ Отпуск изменен:\n"
            f"👤 {first_name} (@{username})\n"
            f"📅 С {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')}\n"
            f"📊 Продолжительность: {days_count} дней"
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты.\n\n"
            "Используйте формат: ДД.ММ.ГГГГ-ДД.ММ.ГГГГ\n"
            "Например: 10.03.2026-20.03.2026\n\n"
            "Попробуйте еще раз:"
        )


async def vacations_command(message: Message):
    """Команда для просмотра списка отпусков с пагинацией (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    # Автоматически удаляем завершенные отпуска
    feedback_bot.cleanup_expired_vacations()
    
    # Показываем первую страницу
    await show_vacations_page(message, page=0)


async def show_vacations_page(message_or_callback, page=0, edit=False):
    """Показывает страницу со списком отпусков"""
    VACATIONS_PER_PAGE = 10
    
    vacations = feedback_bot.holidays_settings.get("vacations", {})
    
    if not vacations:
        text = "📅 Список отпусков\n\n❌ Отпусков пока не назначено"
        keyboard = None
    else:
        # Подготавливаем список отпусков с сортировкой по дате окончания
        today = datetime.now(MSK_TZ).date()
        vacations_list = []
        
        for user_id, vacation in vacations.items():
            if user_id not in feedback_bot.users:
                continue  # Пропускаем удаленных пользователей
            
            try:
                start_date = datetime.strptime(vacation["start"], '%Y-%m-%d').date()
                end_date = datetime.strptime(vacation["end"], '%Y-%m-%d').date()
            except (ValueError, KeyError) as e:
                logger.error(f"Ошибка парсинга дат отпуска для пользователя {user_id}: {e}")
                continue  # Пропускаем поврежденные данные
            
            user_data = feedback_bot.users[user_id]
            
            vacations_list.append({
                'user_id': user_id,
                'first_name': user_data.get('first_name', 'Неизвестный'),
                'username': user_data.get('username', 'Неизвестный'),
                'start_date': start_date,
                'end_date': end_date,
                'days_count': (end_date - start_date).days + 1
            })
        
        # Сортируем по дате окончания (ближайшие к завершению первыми)
        vacations_list.sort(key=lambda x: x['end_date'])
        
        total_vacations = len(vacations_list)
        total_pages = (total_vacations + VACATIONS_PER_PAGE - 1) // VACATIONS_PER_PAGE
        
        if total_pages == 0:
            text = "📅 Список отпусков\n\n❌ Отпусков пока не назначено"
            keyboard = None
        else:
            # Ограничиваем страницу
            page = max(0, min(page, total_pages - 1))
            
            # Получаем отпуска для текущей страницы
            start_idx = page * VACATIONS_PER_PAGE
            end_idx = start_idx + VACATIONS_PER_PAGE
            page_vacations = vacations_list[start_idx:end_idx]
            
            # Формируем текст
            text = f"📅 Список отпусков ({total_vacations})\n"
            text += f"Страница {page + 1} из {total_pages}\n\n"
            
            keyboard_buttons = []
            
            for idx, vac in enumerate(page_vacations, start=start_idx + 1):
                # Определяем статус
                if vac['start_date'] <= today <= vac['end_date']:
                    status = "🏖️ Отпуск"
                elif vac['start_date'] > today:
                    status = "📅 Запланирован"
                else:
                    status = "⏹️ Завершен"
                
                text += f"{idx}. {vac['first_name']} (@{vac['username']})\n"
                text += f"   {status}\n"
                text += f"   📅 {vac['start_date'].strftime('%d.%m.%Y')} - {vac['end_date'].strftime('%d.%m.%Y')}\n"
                text += f"   📊 {vac['days_count']} дней\n\n"
                
                # Кнопка удаления
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"❌ {idx}. {vac['first_name']}",
                        callback_data=f"vacations_delete_{vac['user_id']}"
                    )
                ])
            
            # Кнопки навигации
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"vacations_page_{page-1}"))
            nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="vacations_page_current"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"vacations_page_{page+1}"))
            
            if nav_buttons:
                keyboard_buttons.append(nav_buttons)
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    # Отправляем или редактируем сообщение
    if edit and isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=keyboard)
    else:
        msg = message_or_callback if isinstance(message_or_callback, Message) else message_or_callback.message
        await msg.answer(text, reply_markup=keyboard)


async def vacations_page_callback(callback: CallbackQuery):
    """Обработчик переключения страниц отпусков"""
    await callback.answer()
    
    if str(callback.from_user.id) != MANAGER_CHAT_ID:
        return
    
    if callback.data == "vacations_page_current":
        return
    
    page = int(callback.data.split('_')[-1])
    await show_vacations_page(callback, page=page, edit=True)


async def vacations_delete_callback(callback: CallbackQuery):
    """Обработчик кнопки удаления отпуска"""
    await callback.answer()
    
    if str(callback.from_user.id) != MANAGER_CHAT_ID:
        await callback.message.answer("❌ Только администратор может удалять отпуска.")
        return
    
    # Извлекаем ID пользователя
    user_id = callback.data.replace('vacations_delete_', '')
    
    # Проверяем что отпуск существует
    vacations = feedback_bot.holidays_settings.get("vacations", {})
    if user_id not in vacations:
        await callback.message.answer("❌ Отпуск не найден")
        return
    
    # Получаем данные отпуска
    vacation = vacations[user_id]
    start_date = datetime.strptime(vacation["start"], '%Y-%m-%d').date()
    end_date = datetime.strptime(vacation["end"], '%Y-%m-%d').date()
    days_count = (end_date - start_date).days + 1
    
    # Получаем данные пользователя
    user_data = feedback_bot.users.get(user_id, {})
    first_name = user_data.get('first_name', 'Неизвестный')
    username = user_data.get('username', 'Неизвестный')
    
    # Создаем кнопки подтверждения
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_vacations_delete_{user_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_vacations_delete")
        ]
    ])
    
    await callback.message.answer(
        f"⚠️ Подтверждение удаления\n\n"
        f"Вы действительно хотите удалить отпуск?\n\n"
        f"👤 {first_name} (@{username})\n"
        f"📅 {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n"
        f"📊 {days_count} дней",
        reply_markup=confirm_keyboard
    )


async def confirm_vacations_delete_callback(callback: CallbackQuery):
    """Обработчик подтверждения удаления отпуска"""
    await callback.answer()
    
    if str(callback.from_user.id) != MANAGER_CHAT_ID:
        return
    
    if callback.data.startswith('confirm_vacations_delete_'):
        # Извлекаем ID пользователя
        user_id = callback.data.replace('confirm_vacations_delete_', '')
        
        # Проверяем что отпуск существует
        vacations = feedback_bot.holidays_settings.get("vacations", {})
        if user_id not in vacations:
            await callback.message.edit_text("❌ Отпуск не найден")
            return
        
        # Получаем данные для логирования
        vacation = vacations[user_id]
        start_date = datetime.strptime(vacation["start"], '%Y-%m-%d').date()
        end_date = datetime.strptime(vacation["end"], '%Y-%m-%d').date()
        
        user_data = feedback_bot.users.get(user_id, {})
        first_name = user_data.get('first_name', 'Неизвестный')
        username = user_data.get('username', 'Неизвестный')
        
        # Удаляем отпуск
        del feedback_bot.holidays_settings["vacations"][user_id]
        feedback_bot.save_holidays_settings(feedback_bot.holidays_settings)
        
        logger.info(f"Администратор удалил отпуск: {first_name} (@{username}, {start_date} - {end_date})")
        
        await callback.message.edit_text(
            f"✅ Отпуск удален\n\n"
            f"👤 {first_name} (@{username})\n"
            f"📅 Отпуск с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')} удален"
        )
        
        # Возвращаемся к обновленному списку
        await show_vacations_page(callback, page=0, edit=False)
        
    elif callback.data == 'cancel_vacations_delete':
        await callback.message.edit_text("❌ Удаление отменено")
        # Возвращаемся к списку
        await show_vacations_page(callback, page=0, edit=False)


async def removevacation_command(message: Message):
    """Команда для отмены отпуска (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Используйте: `/removevacation @username`", parse_mode='Markdown')
        return
    
    username = args[1].replace('@', '')
    
    # Находим пользователя
    target_user_id = None
    for uid, user_data in feedback_bot.users.items():
        if user_data.get('username', '').lower() == username.lower():
            target_user_id = uid
            break
    
    if not target_user_id:
        await message.answer(f"❌ Пользователь @{username} не найден")
        return
    
    vacations = feedback_bot.holidays_settings.get("vacations", {})
    
    if target_user_id not in vacations:
        await message.answer(f"❌ У пользователя @{username} нет назначенного отпуска")
        return
    
    vacation = vacations[target_user_id]
    start_date = datetime.strptime(vacation["start"], '%Y-%m-%d').date()
    end_date = datetime.strptime(vacation["end"], '%Y-%m-%d').date()
    
    del feedback_bot.holidays_settings["vacations"][target_user_id]
    feedback_bot.save_holidays_settings(feedback_bot.holidays_settings)
    
    user_data = feedback_bot.users[target_user_id]
    first_name = user_data.get('first_name', 'Неизвестный')
    
    await message.answer(
        f"✅ Отпуск отменен:\n"
        f"👤 {first_name} (@{username})\n"
        f"📅 Отпуск с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')} отменен"
    )


# ============================================================================
# МЕСЯЧНЫЕ ОТЧЕТЫ
# ============================================================================

async def mymonth_command(message: Message):
    """Команда для получения месячного отчета сотрудником"""
    user_id = str(message.from_user.id)
    
    if user_id not in feedback_bot.users:
        await message.answer("❌ Вы не зарегистрированы в системе. Используйте /start")
        return
    
    # Получаем прошлый месяц
    today = datetime.now(MSK_TZ)
    if today.month == 1:
        year = today.year - 1
        month = 12
    else:
        year = today.year
        month = today.month - 1
    
    await message.answer("📊 Формирую твой отчет за прошлый месяц...")
    
    report = await generate_user_monthly_report(user_id, year, month)
    await message.answer(report)


async def generate_user_monthly_report(user_id, year, month):
    """Генерирует месячный отчет для сотрудника"""
    try:
        month_name = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
        }[month]
        
        # Собираем ответы пользователя за месяц
        user_responses = []
        working_days = 0
        
        for date_str, day_responses in feedback_bot.responses.items():
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            if date_obj.year == year and date_obj.month == month:
                # Считаем рабочие дни
                if feedback_bot.is_working_day(date_obj) and not feedback_bot.is_user_on_vacation(user_id, date_obj):
                    working_days += 1
                    
                    if user_id in day_responses:
                        user_responses.append(day_responses[user_id])
        
        if not user_responses:
            return f"📊 Твой отчет: {month_name} {year}\n\n❌ За этот месяц нет данных"
        
        # Статистика по настроению
        mood_counts = Counter([r['mood'] for r in user_responses])
        total_responses = len(user_responses)
        
        # Средняя оценка
        mood_scores = {'excellent': 5, 'good': 4, 'bad': 3, 'hard': 2, 'critical': 1}
        avg_score = sum(mood_scores[r['mood']] for r in user_responses) / total_responses
        
        # Статистика по проектам
        projects = [r.get('project', 'Не указан') for r in user_responses if r.get('project')]
        project_counts = Counter(projects)
        top_projects = project_counts.most_common(5)
        
        # Среднее время ответа
        response_times = []
        for response in user_responses:
            if 'timestamp' in response and 'completed_at' in response:
                try:
                    start = datetime.fromisoformat(response['timestamp'].replace('Z', '+00:00'))
                    end = datetime.fromisoformat(response['completed_at'].replace('Z', '+00:00'))
                    delta = (end - start).total_seconds() / 60
                    response_times.append(delta)
                except:
                    pass
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Серия дней подряд
        max_streak = 1
        current_streak = 1
        sorted_dates = sorted([datetime.strptime(date_str, '%Y-%m-%d').date() 
                              for date_str, day_resp in feedback_bot.responses.items() 
                              if date_str.startswith(f"{year}-{month:02d}") and user_id in day_resp])
        
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i-1]).days == 1:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1
        
        # Формируем отчет
        report = f"📊 Твой отчет: {month_name} {year}\n\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        report += "😊 НАСТРОЕНИЕ\n\n"
        
        for mood_key in ['excellent', 'good', 'bad', 'hard', 'critical']:
            count = mood_counts.get(mood_key, 0)
            percentage = (count / total_responses * 100) if total_responses > 0 else 0
            emoji = MOOD_OPTIONS[mood_key]['emoji']
            text = MOOD_OPTIONS[mood_key]['text']
            bar_length = int(percentage / 10)
            bar = '█' * bar_length + '░' * (10 - bar_length)
            # Разделяем на две строки для правильного выравнивания
            report += f"{emoji} {text}\n"
            report += f"{bar} {count} дней ({percentage:.0f}%)\n\n"
        
        report += f"\n📈 Средняя оценка: {avg_score:.1f}/5\n\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        report += "📋 АКТИВНОСТЬ\n\n"
        report += f"✅ Ответил:     {total_responses} из {working_days} дней"
        
        if working_days > 0:
            participation = (total_responses / working_days * 100)
            report += f" ({participation:.0f}%)\n"
        else:
            report += "\n"
        
        if max_streak > 1:
            report += f"🏆 Серия:       {max_streak} дней подряд!\n"
        
        if avg_response_time > 0:
            report += f"⏱ Среднее время ответа: {avg_response_time:.0f} минут\n"
        
        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        report += "🎯 ПРОЕКТЫ\n\n"
        report += "Над чем работал чаще всего:\n\n"
        
        for i, (project, count) in enumerate(top_projects, 1):
            percentage = (count / total_responses * 100)
            medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, '')
            report += f"{i}. {medal} {project:30} {count} дней ({percentage:.0f}%)\n"
        
        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Определяем следующий месяц
        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year
        
        next_month_name = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
        }[next_month]
        
        report += f"📅 Следующий отчет: 01 {next_month_name} {next_year}"
        
        return report
        
    except Exception as e:
        logger.error(f"Ошибка генерации месячного отчета: {e}")
        return "❌ Ошибка при формировании отчета"


# ============================================================================
# КОМАНДЫ УПРАВЛЕНИЯ РАСПИСАНИЕМ
# ============================================================================

async def setsurvey_command(message: Message):
    """Команда для изменения времени опроса (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Используйте: `/setsurvey ЧЧ:ММ`\n\nНапример: `/setsurvey 18:00`", parse_mode='Markdown')
        return
    
    new_time = args[1].strip()
    
    # Валидация формата времени
    try:
        datetime.strptime(new_time, '%H:%M')
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте формат ЧЧ:ММ\n\nНапример: `18:00`", parse_mode='Markdown')
        return
    
    # Сохраняем новое время
    feedback_bot.schedule_settings["survey_time"] = new_time
    feedback_bot.save_schedule_settings(feedback_bot.schedule_settings)
    
    await message.answer(
        f"✅ Время опроса изменено на {new_time} МСК\n\n"
        f"Изменения вступят в силу немедленно, перезапуск не требуется."
    )
    
    logger.info(f"Администратор изменил время опроса на {new_time}")


async def setreport_command(message: Message):
    """Команда для изменения времени отчета (только для админа)"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Используйте: `/setreport ЧЧ:ММ`\n\nНапример: `/setreport 22:00`", parse_mode='Markdown')
        return
    
    new_time = args[1].strip()
    
    # Валидация формата времени
    try:
        datetime.strptime(new_time, '%H:%M')
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте формат ЧЧ:ММ\n\nНапример: `22:00`", parse_mode='Markdown')
        return
    
    # Сохраняем новое время
    feedback_bot.schedule_settings["report_time"] = new_time
    feedback_bot.save_schedule_settings(feedback_bot.schedule_settings)
    
    await message.answer(
        f"✅ Время отчета изменено на {new_time} МСК\n\n"
        f"Изменения вступят в силу немедленно, перезапуск не требуется."
    )
    
    logger.info(f"Администратор изменил время отчета на {new_time}")


async def adminsurvey_command(message: Message):
    """Команда для включения/выключения опросов для администратора"""
    user_id = str(message.from_user.id)
    
    if user_id != MANAGER_CHAT_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Используйте: `/adminsurvey on` или `/adminsurvey off`", parse_mode='Markdown')
        return
    
    action = args[1].lower()
    
    if action == "on":
        feedback_bot.schedule_settings["admin_as_employee"] = True
        feedback_bot.save_schedule_settings(feedback_bot.schedule_settings)
        await message.answer(
            "✅ Администратор включен как сотрудник\n\n"
            "Теперь вы будете:\n"
            "• Получать ежедневные опросы\n"
            "• Учитываться в статистике и отчетах\n"
            "• Получать напоминания (если не ответили)"
        )
        logger.info("Администратор включил себя как сотрудника")
        
    elif action == "off":
        feedback_bot.schedule_settings["admin_as_employee"] = False
        feedback_bot.save_schedule_settings(feedback_bot.schedule_settings)
        await message.answer(
            "❌ Администратор исключен из сотрудников\n\n"
            "Теперь вы:\n"
            "• НЕ будете получать ежедневные опросы\n"
            "• НЕ будете учитываться в статистике\n"
            "• НЕ будете получать напоминания"
        )
        logger.info("Администратор исключил себя из сотрудников")
        
    else:
        await message.answer("❌ Используйте: `/adminsurvey on` или `/adminsurvey off`", parse_mode='Markdown')
