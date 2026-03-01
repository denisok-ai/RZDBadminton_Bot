#!/usr/bin/env bash
# Обновление и перезапуск бота на сервере (Docker).
# Запускать из каталога проекта: cd /opt/RZDBadminton_Bot && ./deploy/update_on_server.sh

set -e
cd "$(dirname "$0")/.."
echo "Каталог проекта: $(pwd)"

if [ -n "$(git rev-parse --is-inside-work-tree 2>/dev/null)" ]; then
  echo "Обновление кода (git pull)..."
  git pull
else
  echo "Не git-репозиторий — пропуск git pull."
fi

echo "Сборка и перезапуск контейнера..."
docker compose up -d --build

echo "Готово. Логи: docker compose logs -f bot"
