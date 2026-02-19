"""
Главный файл бота - запуск, планировщик, регистрация команд
"""
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage

from config import (
    BOT_TOKEN, MANAGER_CHAT_ID, SURVEY_TIME, REPORT_TIME, MSK_TZ,
    MOOD_OPTIONS, REPORTS_DIR, logger
)
from database import feedback_bot
from commands import (
    # Базовые команды
    start_command, help_command, menu_button_handler, test_survey_command,
    mood_callback, project_message, FeedbackStates,
    # Команды админа - отчеты
    report_command, force_report_command, download_command, reports_list_command,
    stats_command, schedule_command, save_report_to_csv, send_csv_file,
    # Управление пользователями
    users_command, delete_user_callback, confirm_delete_callback,
    users_page_callback, show_users_page,
    # Напоминания
    reminders_command, reminders_set_command,
    # Выходные и отпуска
    weekends_command, saturday_command, sunday_command, holidays_command,
    vacation_command, vacations_command, removevacation_command,
    vacation_page_callback, vacation_select_callback, vacation_dates_handler, 
    vacation_edit_callback, vacation_cancel_callback, vacation_edit_dates_handler,
    vacations_page_callback, vacations_delete_callback, confirm_vacations_delete_callback,
    VacationStates, show_vacation_page,
    # Месячные отчеты
    mymonth_command
)

# Глобальная переменная для бота
bot = None


# ============================================================================
# ПЛАНИРОВЩИК - ОПРОСЫ И ОТЧЕТЫ
# ============================================================================

async def send_daily_survey_async(bot_instance):
    """Отправляет ежедневный опрос всем пользователям"""
    
    if not bot_instance:
        logger.error("Бот не инициализирован")
        return
    
    try:
        # Автоматически удаляем завершенные отпуска
        feedback_bot.cleanup_expired_vacations()
        
        today = datetime.now(MSK_TZ).strftime('%Y-%m-%d')
        today_date = datetime.now(MSK_TZ).date()
        
        # Проверяем, рабочий ли день
        if not feedback_bot.is_working_day(today_date):
            logger.info(f"Сегодня выходной/праздник ({today}), опросы не отправляются")
            return
        
        # Инициализируем responses для сегодня если еще нет
        if today not in feedback_bot.responses:
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
        vacation_count = 0
        
        for chat_id in feedback_bot.users:
            # Проверяем отпуск
            if feedback_bot.is_user_on_vacation(chat_id, today_date):
                vacation_count += 1
                logger.info(f"Пользователь {chat_id} в отпуске, опрос не отправлен")
                continue
            
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
        
        logger.info(f"Опрос завершен. Отправлено: {sent_count}, в отпуске: {vacation_count}, ошибок: {error_count}")
        feedback_bot.save_responses()
        
        # Запускаем напоминания если они включены
        if feedback_bot.reminder_settings.get("enabled", True):
            await schedule_reminders(bot_instance, today)
        
    except Exception as e:
        logger.error(f"Ошибка в отправке опроса: {e}")


async def schedule_reminders(bot_instance, today):
    """Планирует напоминания для тех, кто не ответил"""
    reminder_times = feedback_bot.reminder_settings.get("times", [])
    
    for reminder_time in reminder_times:
        # Создаем задачу для каждого времени напоминания
        asyncio.create_task(send_reminder_at_time(bot_instance, today, reminder_time))


async def send_reminder_at_time(bot_instance, today, reminder_time):
    """Отправляет напоминание в указанное время"""
    try:
        # Парсим время напоминания
        hour, minute = map(int, reminder_time.split(':'))
        now = datetime.now(MSK_TZ)
        reminder_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Если время уже прошло, пропускаем
        if reminder_datetime <= now:
            logger.info(f"Время напоминания {reminder_time} уже прошло, пропускаем")
            return
        
        # Ждем до времени напоминания
        wait_seconds = (reminder_datetime - now).total_seconds()
        logger.info(f"Напоминание запланировано на {reminder_time} (через {wait_seconds:.0f} сек)")
        await asyncio.sleep(wait_seconds)
        
        # Отправляем напоминания тем, кто не ответил
        await send_reminders(bot_instance, today)
        
    except Exception as e:
        logger.error(f"Ошибка в планировании напоминания на {reminder_time}: {e}")


async def send_reminders(bot_instance, today):
    """Отправляет напоминания пользователям, которые не ответили"""
    try:
        today_responses = feedback_bot.responses.get(today, {})
        
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
        for chat_id in feedback_bot.users:
            # Проверяем, ответил ли пользователь
            if chat_id in today_responses:
                continue
            
            # Проверяем, не в отпуске ли
            today_date = datetime.now(MSK_TZ).date()
            if feedback_bot.is_user_on_vacation(chat_id, today_date):
                continue
            
            try:
                await bot_instance.send_message(
                    chat_id=int(chat_id),
                    text="⏰ Напоминание: не забудь ответить на опрос!",
                    reply_markup=keyboard
                )
                sent_count += 1
                logger.info(f"Напоминание отправлено пользователю {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки напоминания пользователю {chat_id}: {e}")
        
        logger.info(f"Напоминания отправлены: {sent_count}")
        
    except Exception as e:
        logger.error(f"Ошибка в отправке напоминаний: {e}")


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
        today_date = datetime.now(MSK_TZ).date()
        today_formatted = datetime.now(MSK_TZ).strftime('%d.%m.%Y')
        
        responses = feedback_bot.responses.get(today, {})
        
        # Считаем пользователей в отпуске
        vacation_users = []
        for user_id in feedback_bot.users:
            if feedback_bot.is_user_on_vacation(user_id, today_date):
                user_data = feedback_bot.users[user_id]
                vacation_users.append(f"@{user_data.get('username', 'Неизвестный')}")
        
        if not responses:
            report = f"📊 Отчет за {today_formatted}\n\n"
            if vacation_users:
                report += f"❌ Не отправлено:\n• Отпуск: {', '.join(vacation_users)} ({len(vacation_users)} чел.)\n\n"
            report += "❌ Сегодня никто не ответил на опрос."
        else:
            report = f"📊 Отчет за {today_formatted}\n\n"
            
            if vacation_users:
                report += f"❌ Не отправлено:\n• Отпуск: {', '.join(vacation_users)} ({len(vacation_users)} чел.)\n\n"
            
            total_users = len(feedback_bot.users) - len(vacation_users)
            responded_users = len(responses)
            
            report += f"👥 Ответили: {responded_users} из {total_users}"
            if total_users > 0:
                percentage = (responded_users / total_users) * 100
                report += f" ({percentage:.0f}%)"
            report += "\n\n"
            
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
            
            # Кто не ответил (исключая тех кто в отпуске)
            responded_user_ids = set(responses.keys())
            not_responded = [user_id for user_id in feedback_bot.users 
                           if user_id not in responded_user_ids 
                           and not feedback_bot.is_user_on_vacation(user_id, today_date)]
            
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


async def send_monthly_reports(bot_instance):
    """Отправляет месячные отчеты всем сотрудникам 1-го числа"""
    try:
        from commands import generate_user_monthly_report
        
        # Получаем прошлый месяц
        today = datetime.now(MSK_TZ)
        if today.month == 1:
            year = today.year - 1
            month = 12
        else:
            year = today.year
            month = today.month - 1
        
        logger.info(f"Отправка месячных отчетов за {month}/{year}")
        
        sent_count = 0
        for user_id in feedback_bot.users:
            # Пропускаем админа
            if user_id == MANAGER_CHAT_ID:
                continue
            
            try:
                report = await generate_user_monthly_report(user_id, year, month)
                await bot_instance.send_message(chat_id=int(user_id), text=report)
                sent_count += 1
                logger.info(f"Месячный отчет отправлен пользователю {user_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки месячного отчета пользователю {user_id}: {e}")
        
        logger.info(f"Месячные отчеты отправлены: {sent_count}")
        
    except Exception as e:
        logger.error(f"Ошибка в отправке месячных отчетов: {e}")


async def scheduler_task(bot_instance):
    """Планировщик задач"""
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
            
            # Опрос
            if current_time == SURVEY_TIME:
                logger.info("Запуск ежедневного опроса...")
                await send_daily_survey_async(bot_instance)
            
            # Отчет
            elif current_time == REPORT_TIME:
                logger.info("Запуск формирования отчета...")
                await generate_daily_report_async(bot_instance)
            
            # Месячные отчеты (1-го числа в 09:00)
            elif current_time == "09:00" and next_minute.day == 1:
                logger.info("Запуск отправки месячных отчетов...")
                await send_monthly_reports(bot_instance)
            
            # Логирование каждые 10 минут
            if next_minute.minute % 10 == 0:
                logger.info(f"Планировщик активен. Время МСК: {current_time}")
                
        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
            await asyncio.sleep(60)


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

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
        
        # Автоматически удаляем завершенные отпуска при запуске
        feedback_bot.cleanup_expired_vacations()
        logger.info("Проверка и очистка завершенных отпусков выполнена")
        
        # Создаем async обертки для команд с bot_instance
        async def report_wrapper(m):
            await report_command(m, bot)
        
        async def force_report_wrapper(m):
            await force_report_command(m, bot)
        
        async def download_wrapper(m):
            await download_command(m, bot)
        
        # Регистрируем обработчики команд
        dp.message.register(start_command, CommandStart())
        dp.message.register(menu_button_handler, F.text == "📋 Меню")
        dp.message.register(test_survey_command, Command('test'))
        dp.message.register(report_wrapper, Command('report'))
        dp.message.register(force_report_wrapper, Command('createreport'))
        dp.message.register(download_wrapper, Command('download'))
        dp.message.register(reports_list_command, Command('reports'))
        dp.message.register(users_command, Command('users'))
        dp.message.register(stats_command, Command('stats'))
        dp.message.register(help_command, Command('help'))
        dp.message.register(schedule_command, Command('schedule'))
        
        # Команды напоминаний
        dp.message.register(reminders_set_command, F.text.startswith('/reminders '))
        dp.message.register(reminders_command, Command('reminders'))
        
        # Команды выходных и отпусков
        dp.message.register(saturday_command, F.text.startswith('/saturday '))
        dp.message.register(sunday_command, F.text.startswith('/sunday '))
        dp.message.register(vacation_command, Command('vacation'))
        dp.message.register(removevacation_command, F.text.startswith('/removevacation '))
        dp.message.register(weekends_command, Command('weekends'))
        dp.message.register(holidays_command, Command('holidays'))
        dp.message.register(vacations_command, Command('vacations'))
        
        # Месячные отчеты
        dp.message.register(mymonth_command, Command('mymonth'))
        
        # Callback обработчики
        dp.callback_query.register(mood_callback, F.data.startswith('mood_'))
        dp.callback_query.register(delete_user_callback, F.data.startswith('delete_user_'))
        dp.callback_query.register(confirm_delete_callback, F.data.startswith('confirm_delete_'))
        dp.callback_query.register(confirm_delete_callback, F.data == 'cancel_delete')
        dp.callback_query.register(users_page_callback, F.data.startswith('users_page_'))
        
        # Callback обработчики для отпусков
        dp.callback_query.register(vacation_page_callback, F.data.startswith('vacation_page_'))
        dp.callback_query.register(vacation_select_callback, F.data.startswith('vacation_select_'))
        dp.callback_query.register(vacation_edit_callback, F.data.startswith('vacation_edit_'))
        dp.callback_query.register(vacation_cancel_callback, F.data == 'vacation_cancel')
        dp.callback_query.register(vacations_page_callback, F.data.startswith('vacations_page_'))
        dp.callback_query.register(vacations_delete_callback, F.data.startswith('vacations_delete_'))
        dp.callback_query.register(confirm_vacations_delete_callback, F.data.startswith('confirm_vacations_delete_'))
        dp.callback_query.register(confirm_vacations_delete_callback, F.data == 'cancel_vacations_delete')
        
        # Обработчик текстовых сообщений для проекта (только в состоянии waiting_for_project)
        dp.message.register(project_message, FeedbackStates.waiting_for_project)
        
        # Обработчики ввода дат отпуска
        dp.message.register(vacation_dates_handler, VacationStates.waiting_for_dates)
        dp.message.register(vacation_edit_dates_handler, VacationStates.waiting_for_edit_dates)
        
        # Запускаем планировщик как фоновую задачу
        scheduler_task_handle = asyncio.create_task(scheduler_task(bot))
        
        logger.info("🚀 Бот запущен и готов к работе!")
        logger.info(f"📅 Опрос: {SURVEY_TIME} МСК")
        logger.info(f"📊 Отчет: {REPORT_TIME} МСК")
        logger.info(f"📊 Месячные отчеты: 1-го числа в 09:00 МСК")
        
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
