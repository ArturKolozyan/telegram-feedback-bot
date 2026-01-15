@echo off
chcp 65001 >nul

:: Проверяем Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python не найден. Установите Python 3.8+
    pause
    exit /b 1
)

:: Проверяем .env
if not exist ".env" (
    echo Файл .env не найден. Скопируйте .env.example в .env и настройте.
    pause
    exit /b 1
)

:: Создаем venv если нет
if not exist "venv" (
    echo Создаем виртуальное окружение...
    python -m venv venv
)

:: Активируем venv
call venv\Scripts\activate.bat

:: Устанавливаем зависимости
pip show aiogram >nul 2>&1
if errorlevel 1 (
    echo Устанавливаем зависимости...
    pip install -r requirements.txt
)

:: Создаем папки
if not exist "data" mkdir data
if not exist "reports" mkdir reports

:: Запускаем бота
:restart
python src/bot.py

:: Перезапуск при ошибке
if errorlevel 1 (
    echo Бот завершился с ошибкой. Перезапуск через 10 секунд...
    timeout /t 10 /nobreak
    goto restart
)

pause
