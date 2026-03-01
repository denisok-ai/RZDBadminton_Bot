#!/bin/bash
# Запуск бота с автоперезапуском при падении (без systemd).
# Использование: ./run-watchdog.sh
# Остановка: Ctrl+C один раз — корректная остановка бота; повторный запуск через RESTART_SEC.

set -e
cd "$(dirname "$0")"

RESTART_SEC=10

if [ ! -d ".venv" ]; then
    echo "Создаю виртуальное окружение..."
    python3 -m venv .venv
fi
source .venv/bin/activate

if ! python3 -c "import aiogram" 2>/dev/null; then
    echo "Устанавливаю зависимости..."
    pip install -r requirements.txt
fi

echo "Запуск бота (автоперезапуск при падении каждые ${RESTART_SEC} с). Остановка: Ctrl+C."
while true; do
    python3 bot.py || true
    echo "Бот завершился. Перезапуск через ${RESTART_SEC} с..."
    sleep "$RESTART_SEC"
done
