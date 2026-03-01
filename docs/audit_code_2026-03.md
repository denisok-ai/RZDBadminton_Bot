# Аудит кода RZDBadminton Bot — 2026-03

## 1. Безопасность

| Проверка | Статус | Комментарий |
|----------|--------|-------------|
| Секреты в .env | ✅ | Токены и ключи загружаются из конфига, .env в .gitignore |
| Проверка ADMIN_ID | ✅ | Все админ-команды и callback модерации проверяют `from_user.id == get_settings().admin_id` |
| Санитизация HTML в алертах | ✅ | В error_handler и telegram_handler текст экранируется: `<` → `&lt;`, `>` → `&gt;` |
| SQL-инъекции | ✅ | Используется SQLAlchemy ORM, параметризованные запросы |

**Рекомендация:** При появлении мультиадмина хранить список ID в конфиге/БД и проверять вхождение, а не единственное значение.

---

## 2. Обработка ошибок и граничные случаи

### 2.1 Критичные

| Место | Проблема | Риск |
|-------|----------|------|
| **handlers/news.py** | `moderation_id = int(callback.data.replace(...))` — при подменённом или битом callback_data возможен `ValueError` | Необработанное исключение → алерт админу, но callback.answer() может не вызваться; пользователь видит «зависание» кнопки |

**Исправлено:** Добавлена функция `_parse_moderation_id()` и проверки во всех callback-обработчиках; парсинг `parts` в cb_reject_reason и cb_variant обёрнут в try/except ValueError.

### 2.2 Средние

| Место | Наблюдение |
|-------|------------|
| **database/repositories.py** — `create_quiz_record` | При исключении делается rollback, но функция всё равно возвращает `record` (без id). Вызывающий код не использует возвращаемое значение; при сбое запись в БД не создаётся — статистика квизов может быть занижена. При желании можно после rollback делать `raise`, чтобы вызывающий знал о сбое. |
| **handlers/polls.py** — `send_attendance_poll` | ~~При сбое create_poll опрос в чате не учитывается~~ **Исправлено:** блок create_poll обёрнут в try/except, ошибка логируется через logger.exception, возврат True сохранён. |
| **config.py** | ~~Дефолтный database_url в корне~~ **Исправлено:** значение по умолчанию заменено на `./data/badminton_bot.db`. |

### 2.3 Низкие

| Место | Наблюдение |
|-------|------------|
| **utils/telegram_handler.py** | `emit()` при отсутствии running loop не отправляет сообщение (return). В обычном режиме бот работает в одном event loop — ок. |
| **services/llm.py** — `_get_rules_context_from_docx` | При пустом `path` после strip возвращается `""`. При неверном пути — try/except, логирование, возврат `""`. Ок. |

---

## 3. Архитектура и состояние

| Компонент | Оценка |
|-----------|--------|
| **app_state.py** | Глобальная переменная `session_factory`. Аннотации типов добавлены: `async_sessionmaker[AsyncSession] | None`, типизированы `set_session_factory`/`get_session_factory`. |
| **Роутеры** | commands, polls, quiz, news подключены. feedback.router не подключён и в feedback.py нет обработчиков — ок. |
| **Порядок роутеров** | quiz перед news — ок; callback admin: и news_mod: не конфликтуют. |

**Рекомендация:** Выполнено.

---

## 4. Стиль и соглашения проекта

| Правило (.cursorrules) | Соответствие |
|------------------------|--------------|
| Type hints для публичных функций | В основном есть; в database/__init__.py добавлены типы для create_engine, create_session_factory, init_db. |
| Docstrings в формате Google | Есть в ключевых модулях; в ряде хелперов кратко или отсутствуют. |
| Заголовок файла @file, @description, @dependencies, @created | Присутствует в handlers, services, database, utils. |
| Линтер ruff | Настроен в pyproject.toml; рекомендуется периодически запускать `ruff check .` и `ruff format .`. |

---

## 5. Потенциальные улучшения (не баги)

1. **Дублирование MONTHS_RU** — в commands.py, admin_helpers.py и excel_reporter.py определён свой словарь месяцев. Можно вынести в общий модуль (например `utils/constants.py` или использовать из `excel_reporter`).
2. **Повтор проверки админа в news** — вынесено в хелпер `_require_admin(callback)`; во всех callback-обработчиках используется `if not await _require_admin(callback): return`.
3. **create_quiz_record при IntegrityError** — при дубликате делается rollback и возврат None; добавлено логирование: при IntegrityError — `logger.debug`, при прочих ошибках — `logger.warning`.

---

## 6. Итог

- **Критичных уязвимостей** не выявлено.
- **Внесённые исправления:** (1) парсинг callback_data в news.py — введена `_parse_moderation_id()`, во всех обработчиках проверка на None и try/except для составных payload; (2) дефолтный `database_url` в config заменён на `./data/badminton_bot.db`.
- **Дополнительно внесено:** типы в app_state (session_factory: async_sessionmaker[AsyncSession] | None); вынесен MONTHS_RU в utils/constants.py, все импорты переведены на него; create_quiz_record при IntegrityError делает rollback и возвращает None (дубликат не ломает вызов).
