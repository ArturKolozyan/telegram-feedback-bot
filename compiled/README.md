# Telegram Feedback Bot - Compiled Version

Скомпилированная версия бота в виде exe файла.

## Структура

```
compiled/
├── bot/
│   └── TelegramFeedbackBot.exe    # Исполняемый файл бота
├── run_compiled.bat                # Скрипт запуска
├── bot.spec                        # Конфигурация PyInstaller
└── README.md                       # Эта инструкция
```

## Быстрый старт

1. Настройте .env файл в корневой папке проекта
2. Запустите run_compiled.bat

## Преимущества

- Не требует установки Python
- Не требует установки зависимостей
- Готов к работе из коробки
- Автоматический перезапуск при ошибках

## Компиляция

Для перекомпиляции:
```
pip install pyinstaller
pyinstaller bot.spec
```
