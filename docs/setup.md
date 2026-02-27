# Установка и запуск RZDBadminton Bot

## Быстрый старт (локально)

```bash
cd /home/denisok/projects/RZDBadminton_Bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Заполнить переменные
python3 bot.py
```

Или через скрипт: `./run.sh`

---

## Systemd (автозапуск на сервере)

### 1. Скопировать unit-файл

```bash
sudo cp deploy/rzdbadminton-bot.service /etc/systemd/system/
```

### 2. Отредактировать пути (если нужно)

```bash
sudo nano /etc/systemd/system/rzdbadminton-bot.service
```

Изменить:
- `User` и `Group` — ваш пользователь
- `WorkingDirectory` — путь к проекту
- `ExecStart` — путь к python в venv
- `EnvironmentFile` — путь к `.env`

### 3. Включить и запустить

```bash
sudo systemctl daemon-reload
sudo systemctl enable rzdbadminton-bot
sudo systemctl start rzdbadminton-bot
```

### 4. Проверить статус

```bash
sudo systemctl status rzdbadminton-bot
journalctl -u rzdbadminton-bot -f
```

### Команды

| Команда | Описание |
|---------|----------|
| `systemctl start rzdbadminton-bot` | Запустить |
| `systemctl stop rzdbadminton-bot` | Остановить |
| `systemctl restart rzdbadminton-bot` | Перезапустить |
| `journalctl -u rzdbadminton-bot -n 100` | Последние 100 строк лога |

---

## Docker

```bash
# Сборка и запуск
docker compose up -d --build

# Логи
docker compose logs -f bot

# Остановка
docker compose down
```

Требуется файл `.env` в корне проекта. Логи сохраняются в volume `bot_logs`.

---

## Развёртывание на сервере

1. Склонировать/скопировать проект на сервер
2. Создать venv, установить зависимости: `pip install -r requirements.txt`
3. Создать `.env` из `.env.example`, заполнить все переменные
4. **Перед первым запуском:** отправить боту `/start` в личку (от имени ADMIN_ID)
5. Настроить systemd (см. выше) или Docker
6. При необходимости — настроить VPN/прокси для доступа к Telegram

## Переменные окружения (.env)

См. `.env.example` — скопировать и заполнить все значения.
