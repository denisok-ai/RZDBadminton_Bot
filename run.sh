#!/bin/bash
# Запуск бота с виртуальным окружением
# Использование: ./run.sh

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Создаю виртуальное окружение..."
    python3 -m venv .venv
fi

source .venv/bin/activate

if ! python3 -c "import aiogram" 2>/dev/null; then
    echo "Устанавливаю зависимости..."
    pip install -r requirements.txt
fi

python3 bot.py
