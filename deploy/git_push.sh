#!/bin/bash
# Отправка сборки на git (origin main).
# Запуск из корня проекта: ./deploy/git_push.sh

set -e
cd "$(dirname "$0")/.."

echo "Каталог: $(pwd)"
echo "Ветка: $(git branch --show-current)"
echo "Изменённые файлы:"
git status -s

git add -A
if git diff --cached --quiet; then
  echo "Нет изменений для коммита."
  exit 0
fi

git commit -m "Сборка к переносу: проверка зависимостей и миграции БД при старте, документ и скрипт деплоя"
echo "Пуш на origin..."
git push origin main
echo "Готово."
