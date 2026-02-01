#!/bin/bash

echo
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    КОМПИЛЯЦИЯ БОТА                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo

# Проверяем виртуальное окружение
if [ ! -d "venv" ]; then
    echo "❌ ОШИБКА: Виртуальное окружение не найдено"
    echo "Сначала запустите ./run.sh для создания venv"
    exit 1
fi

echo "✅ Виртуальное окружение найдено"

# Активируем виртуальное окружение
source venv/bin/activate

# Проверяем PyInstaller
if ! pip show pyinstaller &> /dev/null; then
    echo "📦 Устанавливаем PyInstaller..."
    pip install pyinstaller
    if [ $? -ne 0 ]; then
        echo "❌ ОШИБКА: Не удалось установить PyInstaller"
        exit 1
    fi
    echo "✅ PyInstaller установлен"
else
    echo "✅ PyInstaller уже установлен"
fi

# Создаем папки если не существуют
mkdir -p compiled/bot

echo
echo "🔨 Компилируем бота..."
echo

# Компилируем
pyinstaller compiled/bot.spec
if [ $? -ne 0 ]; then
    echo "❌ ОШИБКА: Компиляция не удалась"
    exit 1
fi

echo "✅ Компиляция завершена"

# Перемещаем исполняемый файл
if [ -f "dist/TelegramFeedbackBot" ]; then
    echo "📁 Перемещаем исполняемый файл..."
    mv "dist/TelegramFeedbackBot" "compiled/bot/"
    if [ $? -ne 0 ]; then
        echo "❌ ОШИБКА: Не удалось переместить файл"
        exit 1
    fi
    echo "✅ Файл перемещен в compiled/bot/"
else
    echo "❌ ОШИБКА: Исполняемый файл не найден"
    exit 1
fi

# Делаем файл исполняемым
chmod +x "compiled/bot/TelegramFeedbackBot"

# Очищаем временные файлы
if [ -d "build" ]; then
    rm -rf "build"
fi
if [ -d "dist" ]; then
    rm -rf "dist"
fi
echo "✅ Временные файлы очищены"

echo
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    КОМПИЛЯЦИЯ ЗАВЕРШЕНА                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo
echo "🎉 Бот успешно скомпилирован!"
echo
echo "📁 Исполняемый файл: compiled/bot/TelegramFeedbackBot"
echo "🚀 Запуск: ./compiled/run_compiled.sh"
echo