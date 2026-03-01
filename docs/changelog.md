# Changelog

## [2026-03-01] — Документация: приведение в соответствие с текущими функциями

### Изменено (документация)

- **README.md** — актуальный список возможностей: обратная связь (Пн/Ср 22:45, Пт 11:45, 1-го 10:00), YouTube с модерацией, кнопка «⚙️ Админ», бекапы БД, ротация логов, run-watchdog.sh
- **docs/Project.md** — требования F-016 (обратная связь), F-018 (YouTube с модерацией); дерево проекта (handlers: top3, admin_helpers, youtube_moderation; services: excel_reporter, db_backup); этапы 5–6; таблица переменных окружения (DEBUG_MODE, TIMEZONE, RULES_DOCX_FILE, YOUTUBE_CHANNEL_ID, TRAINER_*); диаграмма компонентов
- **docs/Tasktracker.md** — T5-2 (обратная связь), T5-4 (YouTube модерация); T6-6 (бекапы), T6-7 (ротация логов), T6-8 (кнопка Админ); сводка этапов; доработки (обратная связь, YouTube, бекапы, аудит)
- **docs/Описание_проекта_для_презентации.md** — обратная связь (расписание в чат + итоги), YouTube (модерация), админ-панель и устойчивость (бекапы, ротация логов, автоподнятие)

---

## [2026-03-01] — Рекомендации: DeepSeek лимит, docstrings, аудит, setup

### Добавлено

- **Мониторинг расхода DeepSeek** — опция `DEEPSEEK_MONTHLY_TOKEN_LIMIT` в .env (0 = отключено). Учёт токенов в `data/llm_usage.json`, при достижении лимита вызовы LLM блокируются, в лог пишется ERROR (алерт админу). В отчёте «📊 Статистика» — блок «DeepSeek: N токенов за месяц (лимит M)».
- **Docstrings** в `services/llm.py` для хелперов: `_sanitize_poll_text`, `_normalize_text`, `_quiz_signature`, `_get_recent_history`, `_format_recent_items`, `_remember_generation`.

### Изменено

- **docs/audit_code_2026-03.md** — описание app_state обновлено (типы добавлены), рекомендация отмечена выполненной.
- **docs/setup.md** — блок «Перед коммитом»: `ruff check . && ruff format . && pytest`; рекомендация по pre-commit.
- **docs/Project.md** — в таблицу переменных окружения добавлен `DEEPSEEK_MONTHLY_TOKEN_LIMIT`.
- **.env.example** — комментарий и пример `DEEPSEEK_MONTHLY_TOKEN_LIMIT`.

---

## [2026-03-01] — Тесты, типы, логирование

### Добавлено

- **tests/test_news_helpers.py** — тесты для `_parse_moderation_id` (граничные случаи callback_data)
- **tests/test_constants.py** — тесты для `MONTHS_RU` (12 месяцев, строчные названия)

### Изменено

- **handlers/news.py** — хелпер `_require_admin(callback)`; во всех callback-обработчиках модерации одна проверка
- **database/repositories.py** — в `create_quiz_record`: логирование при IntegrityError (debug) и при прочих ошибках (warning)
- **database/__init__.py** — аннотации типов: `create_engine` → `AsyncEngine`, `create_session_factory` → `async_sessionmaker[AsyncSession]`, `init_db(engine: AsyncEngine)`

---

## [2026-03-01] — НФБР, .docx для квиза, справка, статистика, меню, YouTube

### Добавлено

- **Квиз: правила НФБР** — источник правил: приказ Минспорта РФ от 12.07.2021 № 546, ссылка https://nfbr.ru/documents/rules в объяснении ответа
- **Контекст квиза из .docx** — опция `RULES_DOCX_FILE` в конфиге; при наличии файла текст подставляется в промпт (python-docx). См. `docs/rules_nfbr_docx.md`
- **Отчёт «📊 Статистика»** — модель QuizRecord, `get_activity_stats()`, кнопка в админ-панели и команда `/stats` (опросы, новости, квизы, обратная связь за месяц)
- **Кнопка «📊 Статистика»** в inline-админ-панели

### Изменено

- **Меню** — обычные пользователи видят только 3 кнопки (Зал, Расписание, Правила); «📝 Оценить», «📈 Рейтинги», «❓ Помощь» и админ-кнопки только для админа
- **Блокировка в группе** — /help, /ratings, «📝 Оценить» удаляются без ответа; /location, /timetable, /rules по-прежнему отвечают в группе
- **YouTube** — Channel ID BWF TV, убран строгий фильтр по словам, диагностика ошибок RSS
- **Квиз** — поле EXPLANATION в промпте + ссылка на правила НФБР; сохранение QuizRecord при отправке
- **Справка /help** — блок «Оценка и отчёты» (Оценить, Рейтинги, Статистика) только для админа
- **config**: `get_settings()` закэширован (lru_cache); добавлен `rules_docx_file`. **models**: `datetime.utcnow` → `datetime.now(UTC)`
- **Удалён** `services/report.py` (не использовался)

---

## [2026-02-26] — UX, админ-хелперы, справка

### Добавлено

- **Команда /help и кнопка «❓ Помощь»** — справка по командам и кнопкам в стиле SportTech (для всех и отдельный блок для админа)
- **handlers/admin_helpers.py** — вынесена логика админ-действий: AdminContext, run_admin_poll/report/news/quiz/top3/ratings/youtube; единый UX-kit (admin_action_start/success/error)
- **Единый UX-kit админ-панели** — все ответы из inline-панели в формате «Выполняю → Готово/Ошибка»

### Изменено

- **commands.py** — cb_admin_action делегирует в admin_helpers; добавлена _admin_runner_for_callback; обработчик /help
- **ui/design.py** — help_screen(is_admin); ui/keyboards.py — кнопка «❓ Помощь» в главном меню

---

## [2026-02-25] — Продолжение разработки

### Добавлено

- **Сохранение рейтингов обратной связи** — модель FeedbackPoll, при ответе на опрос 1–5 рейтинг сохраняется в Attendance
- **Обработчик опросов обратной связи** — при ответе на опрос «Оцените вчерашнюю тренировку» рейтинг записывается в БД
- **Обновление Tasktracker** — этапы 4, 5, 6 отмечены как завершённые
- **Кнопка «📝 Оценить»** — в главном меню для ручной оценки последней тренировки
- **Отчёт «📈 Рейтинги»** — для админа: средний балл и количество оценок за прошлый месяц
- **Команда /ratings** — альтернатива кнопке «Рейтинги»

### Изменено

- **Dockerfile** — CMD `python bot.py`
- **docker-compose** — volume для логов `bot_logs`
- **Tasktracker** — T6-5 (systemd) завершена, все 33 задачи выполнены
- **setup.md** — добавлена секция Docker

- **top3** — используется `get_publish_chat_id` для корректной работы в DEBUG_MODE
- **feedback** — при отправке опроса создаётся запись FeedbackPoll для связи ответа с датой тренировки
- **feedback** — добавлены `get_last_training_date()`, `send_feedback_to_user()` для кнопки «Оценить»

---

## [2025-02-25] — Этап 3: Отчётность (Яндекс.Диск)

### Добавлено

- `utils/file_reader.py` — read_sources() для sources.txt
- `services/yandex_disk.py` — скачивание шаблона, заполнение Excel, загрузка
- `get_poll_voters_attending()` — список проголосовавших «Приду»
- Job отчётности Пн, Ср 23:00
- Команда /report — ручное формирование отчёта

### Изменено

- config: report_upload_path
- requirements: requests

---

## [2025-02-25] — Промпты опросов: новая структура

### Добавлено

- Структура: [Приветствие] + [Эмодзи] + [Инфо] + [Вопрос] + [Эмодзи]
- Приветствия: Всем привет! / Доброе утро! / Физкульт-привет!
- Эмодзи: 🏸 🏆 👋 😊 🎯

### Изменено

- Варианты ответа: Приду 🙋‍♂️ | Не приду 😔 | Может быть 🤔
- Длина вопроса: до 200 символов
- Doc/Опросы/промпт_опроса_посещаемости.txt — полная структура

---

## [2025-02-25] — Генерация вопроса опроса через DeepSeek

### Добавлено

- `services/llm.py` — клиент DeepSeek, `generate_poll_question()`
- `Doc/Опросы/промпт_опроса_посещаемости.txt` — промпт по анализу скриншотов
- Вопрос опроса генерируется при каждой отправке (temperature=0.8)

### Изменено

- `handlers/polls.py` — вызов LLM вместо фиксированных шаблонов
- Fallback на шаблон при ошибке LLM
- `Doc/Опросы/промпт_опросов.txt` — добавлен промпт посещаемости

---

## [2025-02-25] — Этап 2: Опросы посещаемости

### Добавлено

- `handlers/polls.py` — отправка опроса, обработка poll_answer (включая смену ответа)
- `services/scheduler.py` — APScheduler, опросы Пн/Ср 08:00 по Москве
- `app_state.py` — хранение session_factory для handlers
- DEBUG_MODE в config — переключение тест/прод чата
- Команда /poll — ручная отправка опроса (только админ)
- Репозитории: create_poll, get_poll_by_telegram_id, upsert_poll_vote

### Изменено

- PollVote — UniqueConstraint (poll_id, user_id) для upsert при смене голоса
- .env.example — DEBUG_MODE

---

## [2025-02-25] — Установка: venv, setup.md

### Добавлено

- `docs/setup.md` — инструкция по установке (обход externally-managed-environment)
- `run.sh` — скрипт запуска с автосозданием venv

### Изменено

- `.gitignore` — добавлен env/

---

## [2025-02-25] — Опросы: стиль, промпт, план работ

### Добавлено

- Папка `Doc/Опросы/` с примерами и промптом
- `Doc/Опросы/README.md` — требования к опросам (неанонимные, смена ответа)
- `Doc/Опросы/пример_посещаемости.txt` — шаблон опроса посещаемости
- `Doc/Опросы/пример_квиз.txt` — пример квиза
- `Doc/Опросы/промпт_опросов.txt` — промпт для генерации квизов (JSON)
- Требования F-003a, F-003b, F-003c в Project.md
- Задачи T2-0, T2-5 в Tasktracker

### Изменено

- Project.md — структура Doc/, требования к опросам
- Tasktracker.md — этап 2 расширен (6 задач)
- Doc/Promt Bot.txt — уточнена логика опросов

### Исправлено

- —

---

## [2025-02-25] — Этап 1: Инфраструктура

### Добавлено

- Создана структура проекта: `handlers/`, `services/`, `database/`, `middlewares/`, `utils/`
- `config.py` — конфигурация через Pydantic Settings и `.env`
- `utils/logger.py` — логирование в консоль, файл `logs/bot.log` и `logs/errors.log`
- `database/models.py` — модели User, Poll, PollVote, Attendance, ProcessedNews, NewsModeration
- `database/repositories.py` — CRUD для пользователей, посещаемости, дедупликации новостей
- `handlers/commands.py` — команды /start, /location, /rules, /timetable
- `bot.py` — точка входа, инициализация БД и роутеров
- Dockerfile и docker-compose.yml
- `.gitignore`, `.env.example`
- `docs/servers.md` — рекомендации по VPS в Нидерландах
- `Doc/rules` — шаблон для правил экипировки

### Изменено

- `docs/qa.md` — все вопросы помечены как «Решено»
- `docs/Project.md` — добавлены уточнения из QA, ссылка для /location
- `docs/Diary.md` — запись об ответах на вопросы

### Исправлено

- —
