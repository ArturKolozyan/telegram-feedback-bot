#!/bin/bash

echo
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           TELEGRAM FEEDBACK BOT - COMPILED VERSION          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo

# Проверяем .env файл
if [ ! -f "../.env" ]; then
    echo "❌ ОШИБКА: Файл .env не найден в корневой папке проекта!"
    echo
    echo "📋 Скопируйте .env.example в .env и настройте его."
    echo
    exit 1
fi

echo "✅ Конфигурация найдена"
echo

# Создаем необходимые папки
mkdir -p ../data ../reports

# Создаем пустые JSON файлы если их нет
if [ ! -f "../data/users.json" ]; then
    echo "{}" > "../data/users.json"
fi
if [ ! -f "../data/responses.json" ]; then
    echo "{}" > "../data/responses.json"
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                        ЗАПУСК БОТА                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo
echo "🚀 Запускаем Telegram Feedback Bot..."
echo
echo "💡 Информация:"
echo "   • Для остановки нажмите Ctrl+C"
echo "   • Не закрывайте терминал во время работы"
echo
echo "═══════════════════════════════════════════════════════════════"
echo

# Запускаем бота с автоматическим перезапуском
while true; do
    ./bot/TelegramFeedbackBot
    
    # Обработка завершения
    exit_code=$?
    echo
    echo "═══════════════════════════════════════════════════════════════"
    echo
    
    if [ $exit_code -ne 0 ]; then
        echo "❌ Бот завершился с ошибкой"
        echo
        echo "🔄 Перезапуск через 10 секунд..."
        echo "💡 Для отмены нажмите Ctrl+C"
        sleep 10
        echo
        echo "🚀 Перезапускаем бота..."
        echo
    else
        echo "✅ Бот завершил работу корректно"
        break
    fi
done

echo