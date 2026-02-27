# Changelog

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
