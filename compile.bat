@echo off
chcp 65001 >nul
title Компиляция Telegram Feedback Bot

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    КОМПИЛЯЦИЯ БОТА                          ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Проверяем виртуальное окружение
if not exist "venv" (
    echo ❌ ОШИБКА: Виртуальное окружение не найдено
    echo Сначала запустите run.bat для создания venv
    pause
    exit /b 1
)

echo ✅ Виртуальное окружение найдено

:: Проверяем PyInstaller
venv\Scripts\pip.exe show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 📦 Устанавливаем PyInstaller...
    venv\Scripts\pip.exe install pyinstaller
    if errorlevel 1 (
        echo ❌ ОШИБКА: Не удалось установить PyInstaller
        pause
        exit /b 1
    )
    echo ✅ PyInstaller установлен
) else (
    echo ✅ PyInstaller уже установлен
)

:: Создаем папки если не существуют
if not exist "compiled" mkdir compiled
if not exist "compiled\bot" mkdir "compiled\bot"

echo.
echo 🔨 Компилируем бота...
echo.

:: Компилируем
venv\Scripts\pyinstaller.exe compiled\bot.spec
if errorlevel 1 (
    echo ❌ ОШИБКА: Компиляция не удалась
    pause
    exit /b 1
)

echo ✅ Компиляция завершена

:: Перемещаем exe файл
if exist "dist\TelegramFeedbackBot.exe" (
    echo 📁 Перемещаем exe файл...
    move "dist\TelegramFeedbackBot.exe" "compiled\bot\"
    if errorlevel 1 (
        echo ❌ ОШИБКА: Не удалось переместить файл
        pause
        exit /b 1
    )
    echo ✅ Файл перемещен в compiled\bot\
) else (
    echo ❌ ОШИБКА: Exe файл не найден
    pause
    exit /b 1
)

:: Очищаем временные файлы
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
echo ✅ Временные файлы очищены

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    КОМПИЛЯЦИЯ ЗАВЕРШЕНА                     ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo 🎉 Бот успешно скомпилирован!
echo.
echo 📁 Exe файл: compiled\bot\TelegramFeedbackBot.exe
echo 🚀 Запуск: compiled\run_compiled.bat
echo.
pause