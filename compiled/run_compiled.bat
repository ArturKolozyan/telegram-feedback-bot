@echo off
chcp 65001 >nul
title Telegram Feedback Bot (Compiled)

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║           TELEGRAM FEEDBACK BOT - COMPILED VERSION          ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Проверяем .env файл
if not exist "..\\.env" (
    echo ❌ ОШИБКА: Файл .env не найден в корневой папке проекта!
    echo.
    echo 📋 Скопируйте .env.example в .env и настройте его.
    echo.
    pause
    exit /b 1
)

echo ✅ Конфигурация найдена
echo.

:: Создаем необходимые папки
if not exist "..\\data" mkdir "..\\data"
if not exist "..\\reports" mkdir "..\\reports"

:: Создаем пустые JSON файлы если их нет
if not exist "..\\data\\users.json" echo {}> "..\\data\\users.json"
if not exist "..\\data\\responses.json" echo {}> "..\\data\\responses.json"

echo ╔══════════════════════════════════════════════════════════════╗
echo ║                        ЗАПУСК БОТА                          ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo 🚀 Запускаем Telegram Feedback Bot...
echo.
echo 💡 Информация:
echo    • Для остановки нажмите Ctrl+C
echo    • Не закрывайте это окно во время работы
echo.
echo ═══════════════════════════════════════════════════════════════
echo.

:: Запускаем бота с автоматическим перезапуском
:restart
bot\\TelegramFeedbackBot.exe

:: Обработка завершения
echo.
echo ═══════════════════════════════════════════════════════════════
echo.
if errorlevel 1 (
    echo ❌ Бот завершился с ошибкой
    echo.
    echo 🔄 Перезапуск через 10 секунд...
    echo 💡 Для отмены нажмите Ctrl+C
    timeout /t 10 /nobreak
    echo.
    echo 🚀 Перезапускаем бота...
    echo.
    goto restart
) else (
    echo ✅ Бот завершил работу корректно
)

echo.
pause
