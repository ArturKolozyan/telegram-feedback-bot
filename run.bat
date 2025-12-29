@echo off
echo Активируем виртуальное окружение...
call venv\Scripts\activate.bat

echo Устанавливаем зависимости...
pip install -r requirements.txt

echo Запускаем бота...
python src/bot.py

pause