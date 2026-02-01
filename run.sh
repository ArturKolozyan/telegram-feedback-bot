#!/bin/bash

# Проверяем Python 3.12
if ! command -v python3.12 &> /dev/null; then
    echo "Python3.12 не найден. Используем системный python3"
    PYTHON_CMD="python3"
else
    echo "Используем Python 3.12"
    PYTHON_CMD="python3.12"
fi

# Проверяем .env
if [ ! -f ".env" ]; then
    echo "Файл .env не найден. Скопируйте .env.example в .env и настройте."
    exit 1
fi

# Создаем venv если нет
if [ ! -d "venv" ]; then
    echo "Создаем виртуальное окружение с $PYTHON_CMD..."
    $PYTHON_CMD -m venv venv
fi

# Активируем venv
source venv/bin/activate

# Устанавливаем зависимости
if ! pip show aiogram &> /dev/null; then
    echo "Устанавливаем зависимости..."
    pip install -r requirements.txt
fi

# Создаем папки
mkdir -p data reports

# Запускаем бота
while true; do
    $PYTHON_CMD src/bot.py
    if [ $? -eq 0 ]; then
        break
    fi
    echo "Бот завершился с ошибкой. Перезапуск через 10 секунд..."
    sleep 10
done