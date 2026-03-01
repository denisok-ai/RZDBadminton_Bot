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

**При старте бота** автоматически выполняются: проверка установленных библиотек (при отсутствии — попытка `pip install -r requirements.txt`), создание таблиц БД и при необходимости добавление недостающих колонок (миграция для SQLite). Подробнее: [Сборка и перенос на сервер](Сборка_и_перенос_на_сервер.md).

---

## Локальный запуск для тестовой отладки (без влияния на продуктивный чат)

Чтобы проверять бота в тестовой группе и **не задевать основной чат**, включите режим отладки: опросы, публикации новостей, квизы и Топ-3 будут уходить в **тестовую группу**, а не в `MAIN_CHAT_ID`. Отчёты по посещаемости по-прежнему приходят **в личные сообщения админу** (не в чат).

### Шаг 1. Создать тестовую группу в Telegram

1. Создайте новую группу (или используйте существующую тестовую).
2. Добавьте в группу вашего бота (через @BotFather найдите бота по имени и добавьте в участники).
3. **Выдайте боту право «Удаление сообщений»:** Управление группой → Администраторы → выберите бота → включите «Удаление сообщений». Иначе сообщения с кнопками «Рейтинги», «Помощь», «Оценить» в группе не будут удаляться. Если в группе по-прежнему отображаются 6 кнопок — отправьте в группе **/start** или нажмите **«Зал»** или **«Расписание»**: бот ответит и подставит короткое меню (3 кнопки). При нажатии «Рейтинги»/«Помощь»/«Оценить» ваше сообщение удалится и меню обновится до 3 кнопок.
4. Узнайте ID группы:
   - Добавьте в группу бота [@userinfobot](https://t.me/userinfobot) или [@getidsbot](https://t.me/getidsbot), он напишет ID группы (число вида `-100xxxxxxxxxx`).
   - Либо после первого сообщения в группу от вашего бота откройте в браузере:  
     `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates`  
     в ответе найдите `"chat":{"id":-100...}` — это и есть ID группы.

### Шаг 2. Настроить .env для отладки

В корне проекта откройте (или создайте) файл `.env` и задайте:

```env
# Режим отладки: ВСЕ опросы и публикации идут в тестовую группу
DEBUG_MODE=True

# ID вашей тестовой группы (число, например -1001234567890)
TEST_CHAT_ID=-1001234567890
```

Остальные переменные оставьте как для прода: `MAIN_CHAT_ID` — ID **продуктивного** чата (бот туда при отладке не пишет), `BOT_TOKEN`, `ADMIN_ID` и т.д. — те же, что и в проде.

Важно: один и тот же бот может работать либо в режиме отладки (в тестовую группу), либо в проде (в основной чат). Переключение — только через `DEBUG_MODE` в `.env`.

### Шаг 3. Запустить бота локально

```bash
cd /home/denisok/projects/RZDBadminton_Bot
source .venv/bin/activate   # если используете venv
python3 bot.py
```

Бот подключится к Telegram; опросы (Пн/Ср 08:00), квиз (Пт 12:00), новости после модерации и Топ-3 будут уходить **только в тестовую группу** (`TEST_CHAT_ID`). Отчёты (Пн/Ср 23:00 и по кнопке «📊 Отчёт») всегда приходят **в личку админу**, а не в чат. Продуктивный чат (`MAIN_CHAT_ID`) затронут не будет.

### Шаг 4. Проверить режим

- В личке с ботом отправьте команду **/start** и нажмите кнопку **«Админ»** → выберите любое действие (например «Опрос» или «Статистика»). В ответе бот покажет текущий режим: `DEBUG_MODE: True` и чат `TEST_CHAT_ID = ...`.
- Либо в коде/логах при старте можно убедиться, что используется тестовый чат (в логах при отправке опроса будет указан `chat_id`, совпадающий с `TEST_CHAT_ID`).

### Возврат к продуктивному режиму

Перед запуском на сервере или для работы с основным чатом верните в `.env`:

```env
DEBUG_MODE=False
```

И перезапустите бота. После этого все действия снова пойдут в `MAIN_CHAT_ID`.

### Ошибка «Conflict: terminated by other getUpdates request»

Если при запуске `python3 bot.py` появляется **TelegramConflictError** и текст про «only one bot instance» — с одним токеном бота одновременно работает больше одного процесса (polling). Нужно оставить **только один** экземпляр:

1. **Другой терминал** — закройте или остановите (Ctrl+C) все остальные запуски `python3 bot.py`.
2. **Сервис systemd** — если бот поднят как сервис, перед ручным запуском остановите его:
   ```bash
   sudo systemctl stop rzdbadminton-bot
   ```
3. **Docker на сервере** — если бот запущен в контейнере на удалённом сервере, зайдите по SSH и остановите контейнер. Проект может находиться в `/opt` (см. раздел «Продакшен-сервер» ниже):
   ```bash
   ssh root@46.19.68.241
   docker stop rzdbadminton_bot
   # или из каталога проекта:
   cd /opt/RZDBadminton_Bot && docker compose down
   ```
4. **Другой сервер/ПК** — если тот же бот запущен где-то ещё, остановите его там.
5. Проверить процессы: `ps aux | grep "python.*bot.py"` (локально) или `docker ps | grep rzdbadminton` (на сервере) — должен быть один экземпляр.
6. Подождать 10–20 секунд после остановки и снова запустить: `python3 bot.py`.

### YouTube: «RSS вернул HTTP 404»

Если при проверке канала (кнопка «🎬 YouTube» или фоновые задачи) бот пишет, что YouTube RSS вернул 404 — публичные RSS-ленты для каналов часто недоступны. Добавьте **YouTube Data API v3** и ключ в `.env` (см. ниже).

### YouTube: «API key not valid»

Если бот пишет, что ключ YouTube API недействителен (HTTP 400):

1. **В .env ключ — без кавычек.** Правильно: `YOUTUBE_API_KEY=AIzaSy...`  
   Неправильно: `YOUTUBE_API_KEY="AIzaSy..."` (кавычки могут попасть в значение). Бот сам обрезает кавычки, но лучше не ставить их.
2. **В Google Cloud Console** для вашего проекта включён **YouTube Data API v3**: APIs & Services → Library → YouTube Data API v3 → Enable.
3. Ключ скопирован **целиком**, без пробелов в начале/конце.
4. После создания ключа подождите 1–2 минуты и перезапустите бота.

Если ключ по-прежнему не принимается, бот автоматически попробует получить ленту через RSS (для канала BWF TV по умолчанию используется ID `UChh-akEbUM8_6ghGVnJd6cQ`). При необходимости задайте в .env свой канал: `YOUTUBE_CHANNEL_ID=UC...`.

**Очистка очереди YouTube:** чтобы сбросить список видео, ожидающих модерации (предложений), используйте команду `/clearyoutubequeue` или кнопку «🧹 Очистить предложения» в меню админа. Команда `/clearyoutube` сбрасывает список уже *опубликованных* видео — после неё «🎬 YouTube» снова предложит последние ролики из ленты.

**Как получить ключ:**

1. [Google Cloud Console](https://console.cloud.google.com/) → выберите проект.
2. **APIs & Services** → **Enable APIs and Services** → найдите **YouTube Data API v3** → **Enable**.
3. **Credentials** → **Create credentials** → **API key**.
4. В `.env`: `YOUTUBE_API_KEY=AIzaSy...ваш_ключ` (без кавычек).
5. Перезапустите бота.

---

## Продакшен-сервер (Docker)

На продакшене бот запущен в Docker. Актуальные данные сервера:

| Параметр | Значение |
|----------|----------|
| **Подключение** | `ssh root@46.19.68.241` |
| **Хостнейм** | ams-1-vm-43kf (Amsterdam) |
| **Каталог проекта** | `/opt/RZDBadminton_Bot` |
| **Контейнер** | `rzdbadminton_bot` (образ `rzdbadminton_bot:latest`) |

### Команды на сервере

```bash
# Перейти в каталог проекта
cd /opt/RZDBadminton_Bot

# Остановить бота
docker compose down
# или только остановить контейнер (без удаления):
docker stop rzdbadminton_bot

# Запустить бота
docker compose up -d --build

# Логи
docker compose logs -f bot

# Проверить, запущен ли контейнер
docker ps | grep rzdbadminton
```

Если не помните путь к проекту, найти его можно так:

```bash
find / -name "docker-compose.yml" -path "*RZDB*" 2>/dev/null
# или
find / -name "bot.py" -path "*RZDB*" 2>/dev/null
```

Поиск только в `/root` и `/home` может не найти проект, если он развёрнут в `/opt`.

### Логи на продакшен-сервере

В Docker-развёртывании каталоги `./data` и `./logs` монтируются в контейнер из хоста. На сервере они находятся по путям:

| Назначение | Путь на сервере |
|------------|-----------------|
| Логи бота | `/opt/RZDBadminton_Bot/logs/` |
| Файлы данных (БД, отчёты) | `/opt/RZDBadminton_Bot/data/` |

Просмотр логов:

```bash
# Поток логов из контейнера (стандартный вывод + stderr)
docker compose -f /opt/RZDBadminton_Bot/docker-compose.yml logs -f bot

# Файловые логи на хосте (с ротацией: bot.log, bot.log.1, …; errors.log, errors.log.1, …)
tail -f /opt/RZDBadminton_Bot/logs/bot.log
tail -f /opt/RZDBadminton_Bot/logs/errors.log
```

Ротация логов (до 2 МБ на файл, 5 архивов) настраивается в `utils/logger.py` и действует и в контейнере.

### Бекапы БД на продакшен-сервере

Ежедневно в **04:00** (по времени сервера) планировщик создаёт копию БД и удаляет бекапы старше 10 дней. Путь на сервере:

| Назначение | Путь на сервере |
|------------|-----------------|
| Каталог бекапов | `/opt/RZDBadminton_Bot/data/backups/` |
| Имя файла | `badminton_bot_YYYY-MM-DD.db` |

Проверка бекапов:

```bash
ls -la /opt/RZDBadminton_Bot/data/backups/
```

При необходимости восстановления — скопировать нужный файл поверх текущей БД (предварительно остановить бота), см. `services/db_backup.py` и конфиг `database_url`.

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

### Автоподнятие после сбоя и падения сервера

При установке сервиса через systemd (`systemctl enable rzdbadminton-bot`) бот автоматически:

1. **Запускается после перезагрузки сервера** — unit в `WantedBy=multi-user.target`, при загрузке ОС сервис поднимается.
2. **Перезапускается при падении процесса** — в unit заданы `Restart=on-failure` и `RestartSec=10`: при завершении с ошибкой или по сигналу systemd перезапустит процесс через 10 секунд.
3. **Не уходит в бесконечный цикл рестартов** — `StartLimitIntervalSec=300` и `StartLimitBurst=5`: если за 5 минут произойдёт 5 падений, systemd переведёт сервис в состояние failed и перестанет перезапускать (нужно проверить логи: `journalctl -u rzdbadminton-bot -n 200` и исправить причину).

В коде (`bot.py`) необработанные исключения приводят к `sys.exit(1)`, чтобы systemd считал это сбоем и выполнял перезапуск.

**Без systemd (ручной запуск):** можно использовать скрипт с циклом перезапуска:

```bash
chmod +x run-watchdog.sh
./run-watchdog.sh
```

Бот будет перезапускаться через 10 секунд после любого завершения (в том числе по ошибке). Остановка: Ctrl+C.

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

Требуется файл `.env` в корне проекта. В контейнер монтируются каталоги хоста: `./data` (БД, бекапы, отчёты) и `./logs` (логи). На продакшен-сервере пути: `/opt/RZDBadminton_Bot/data`, `/opt/RZDBadminton_Bot/logs` (см. раздел «Продакшен-сервер»).

---

## Логи и ротация

При запуске без Docker логи пишутся в каталог **`logs/`** в корне проекта; при запуске в Docker на сервере — в смонтированный каталог (на продакшене: **`/opt/RZDBadminton_Bot/logs/`**):

- **`logs/bot.log`** — все сообщения (DEBUG и выше);
- **`logs/errors.log`** — только ERROR.

Включена **ротация по размеру** (`utils/logger.py`): при достижении **2 МБ** файл переименовывается (например, `bot.log` → `bot.log.1`), создаётся новый `bot.log`. Хранится **5** архивных файлов (итого до ~12 МБ на каждый лог). Параметры заданы константами `LOG_MAX_BYTES` и `LOG_BACKUP_COUNT` в `utils/logger.py`.

---

## Развёртывание на сервере

1. Склонировать/скопировать проект на сервер
2. Создать venv, установить зависимости: `pip install -r requirements.txt`
3. Создать `.env` из `.env.example`, заполнить все переменные
4. **Перед первым запуском:** отправить боту `/start` в личку (от имени ADMIN_ID)
5. Настроить systemd (см. выше) или Docker
6. При необходимости — настроить VPN/прокси для доступа к Telegram

**Миграция БД при обновлении:** если при нажатии «📋 Ответ квиза» или при задании по расписанию (Пт 21:00) появляется ошибка `no such column: quiz_records.correct_answer`, в таблицу нужно добавить колонки. Выполните **один раз** из корня проекта:

```bash
cd /home/denisok/projects/RZDBadminton_Bot   # или ваш путь к проекту
python3 scripts/migrate_quiz_records.py
```

Скрипт прочитает `DATABASE_URL` из `.env` и добавит колонки `correct_answer` и `explanation`, если их ещё нет. Альтернатива вручную (путь к БД из `DATABASE_URL`):

```bash
sqlite3 data/badminton_bot.db "ALTER TABLE quiz_records ADD COLUMN correct_answer VARCHAR(500);"
sqlite3 data/badminton_bot.db "ALTER TABLE quiz_records ADD COLUMN explanation TEXT;"
```

## Переменные окружения (.env)

См. `.env.example` — скопировать и заполнить все значения.

**Опционально:** `RULES_DOCX_FILE` — путь к файлу правил НФБР в формате .docx (например `Doc/pravila_nfbr.docx`). Если задан, текст подставляется в промпт квиза. Требуется пакет `python-docx` (уже в `requirements.txt`). Подробнее: [docs/rules_nfbr_docx.md](rules_nfbr_docx.md).

---

## Разработка: тесты и линтер

**Установка инструментов для тестов и линтера (один раз):**
```bash
cd /home/denisok/projects/RZDBadminton_Bot
source .venv/bin/activate
pip install -r requirements-dev.txt
```
Файл `requirements-dev.txt` подключает `requirements.txt` и добавляет `pytest` и `ruff`.

**Тесты (pytest):**
```bash
python3 -m pytest tests/ -v
```
Конфиг pytest: `pyproject.toml` (testpaths, pythonpath).

**Линтер ruff:**
```bash
ruff check .
ruff format --check .   # только проверка; ruff format . — применить форматирование
```
Конфиг: `pyproject.toml` (секция `[tool.ruff]`).

**Перед коммитом** рекомендуется выполнить проверку и форматирование:
```bash
ruff check . && ruff format . && python3 -m pytest tests/ -q
```

**Pre-commit (опционально):** в корне проекта есть `.pre-commit-config.yaml` (ruff + pytest). Один раз выполнить:
```bash
pip install pre-commit
pre-commit install
```
После этого при каждом `git commit` будут запускаться проверки.
