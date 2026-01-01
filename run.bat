@echo off
chcp 65001 >nul
title Telegram Feedback Bot

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    TELEGRAM FEEDBACK BOT                    ║
echo ║                     Система обратной связи                  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ОШИБКА: Python не найден в системе
    echo.
    echo 💡 Установите Python с официального сайта:
    echo    https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo ✅ Python найден
python --version

:: Проверяем файл конфигурации
if not exist ".env" (
    echo.
    echo ⚠️  ВНИМАНИЕ: Файл конфигурации .env не найден!
    echo.
    echo 📋 Для настройки бота выполните следующие шаги:
    echo.
    echo 1. Скопируйте файл .env.example в .env:
    echo    copy .env.example .env
    echo.
    echo 2. Откройте .env в текстовом редакторе и заполните:
    echo    • BOT_TOKEN - токен от @BotFather
    echo    • MANAGER_CHAT_ID - ваш Chat ID ^(получить у @userinfobot^)
    echo    • SURVEY_TIME - время опроса ^(например: 17:00^)
    echo    • REPORT_TIME - время отчета ^(например: 21:00^)
    echo.
    echo 3. Сохраните файл и запустите run.bat снова
    echo.
    pause
    exit /b 1
)

echo ✅ Конфигурация найдена

:: Проверяем виртуальное окружение
if not exist ".venv" (
    echo.
    echo 📦 Создаем виртуальное окружение...
    python -m venv .venv
    if errorlevel 1 (
        echo ❌ ОШИБКА: Не удалось создать виртуальное окружение
        pause
        exit /b 1
    )
    echo ✅ Виртуальное окружение создано
)

:: Активируем виртуальное окружение
echo 🔄 Активируем виртуальное окружение...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ ОШИБКА: Не удалось активировать виртуальное окружение
    pause
    exit /b 1
)

echo ✅ Виртуальное окружение активировано

:: Проверяем и устанавливаем зависимости
echo 📚 Проверяем зависимости...
pip show aiogram >nul 2>&1
if errorlevel 1 (
    echo 🔄 Устанавливаем зависимости...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ ОШИБКА: Не удалось установить зависимости
        pause
        exit /b 1
    )
    echo ✅ Зависимости установлены
) else (
    echo ✅ Зависимости уже установлены
)

:: Создаем необходимые директории
if not exist "data" mkdir data
if not exist "reports" mkdir reports

:: Создаем пустые JSON файлы если их нет
if not exist "data\users.json" echo {}> data\users.json
if not exist "data\responses.json" echo {}> data\responses.json

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                        ЗАПУСК БОТА                          ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo 🚀 Запускаем Telegram Feedback Bot...
echo.
echo 💡 Информация:
echo    • Для остановки нажмите Ctrl+C
echo    • Не закрывайте это окно во время работы
echo    • Логи отображаются в реальном времени
echo.
echo ⏰ Бот будет автоматически:
echo    • Отправлять опросы сотрудникам
echo    • Формировать отчеты для менеджера
echo    • Сохранять данные в CSV файлы
echo.
echo ═══════════════════════════════════════════════════════════════
echo.

:: Запускаем бота
python src/bot.py

:: Обработка завершения
echo.
echo ═══════════════════════════════════════════════════════════════
echo.
if errorlevel 1 (
    echo ❌ Бот завершился с ошибкой
    echo.
    echo 🔍 Возможные причины:
    echo    • Неверный токен бота в .env файле
    echo    • Отсутствует интернет-соединение
    echo    • Неправильно настроен MANAGER_CHAT_ID
    echo.
    echo 💡 Проверьте настройки в .env файле и попробуйте снова
) else (
    echo ✅ Бот завершил работу корректно
)

echo.
echo 📊 Данные сохранены в:
echo    • data\users.json - пользователи
echo    • data\responses.json - ответы
echo    • reports\ - CSV отчеты
echo.
pause