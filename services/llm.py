"""
@file: llm.py
@description: Клиент DeepSeek API для генерации текстов
@dependencies: openai, config
@created: 2025-02-25
"""

import logging
import json
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger("rzdbadminton")

# Максимум символов из .docx правил, подставляемых в промпт квиза (чтобы не перегружать контекст)
QUIZ_RULES_CONTEXT_MAX_CHARS = 6000

HISTORY_FILE = Path("data/llm_generation_history.json")
USAGE_FILE = Path("data/llm_usage.json")
MAX_HISTORY_ITEMS = 200
POLL_HISTORY_WINDOW = 30
QUIZ_HISTORY_WINDOW = 50
MAX_GENERATION_ATTEMPTS = 4

POLL_QUESTION_SYSTEM = """Ты — редактор опросов секции «Бадминтон РЖД». Генерируешь текст опроса посещаемости на тренировку.

Структура: [Приветствие] + [Эмодзи] + [Инфо о тренировке] + [Вопрос] + [Эмодзи]

Правила:
1. Приветствие: "Всем привет!" / "Доброе утро!" / "Физкульт-привет!" / "Доброе утро, бадминтонисты!" — варьируй
2. Инфо: укажи день (Понедельник/Среда), время (20:15) или "вечерняя тренировка", место Стромынка
3. Призыв: "Отмечаемся!" / "Отмечаемся, не стесняемся!"
4. Вопрос: "Кто придёт на тренировку?" / "Кто сегодня на тренировочку?" — варьируй
5. Эмодзи: используй 2–3 из 🏸 🏆 👋 😊 🎯
6. Длина: до 200 символов
7. Тон: дружеский, мотивирующий
8. Только русский язык, без кавычек
9. НЕ включай варианты ответа — они фиксированы

Ответь ТОЛЬКО текстом опроса, без пояснений."""


def _record_response_usage(response) -> None:
    """Учесть токены из ответа API (если поле usage присутствует)."""
    usage = getattr(response, "usage", None)
    if usage is not None and hasattr(usage, "total_tokens") and usage.total_tokens:
        _record_usage(int(usage.total_tokens))


async def generate_poll_question(weekday_name: str) -> str | None:
    """
    Сгенерировать вопрос опроса посещаемости через DeepSeek.

    Args:
        weekday_name: "Понедельник" или "Среда"

    Returns:
        Текст вопроса или None при ошибке
    """
    if _is_over_limit():
        logger.error(
            "DeepSeek: месячный лимит токенов достигнут (лимит %s). Генерация опроса пропущена.",
            get_settings().deepseek_monthly_token_limit,
        )
        return None
    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    recent_polls = _get_recent_history("poll", POLL_HISTORY_WINDOW)
    last_candidate: str | None = None
    for _ in range(MAX_GENERATION_ATTEMPTS):
        try:
            recent_block = _format_recent_items(recent_polls)
            seed = uuid4().hex[:8]
            response = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": POLL_QUESTION_SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            f"Сегодня {weekday_name}. Вечерняя тренировка 20:15, Стромынка. "
                            "Сгенерируй новый вариант опроса, не повторяй последние формулировки.\n"
                            f"Творческий идентификатор варианта: {seed}\n"
                            f"{recent_block}"
                        ),
                    },
                ],
                max_tokens=150,
                temperature=1.0,
            )
            text = response.choices[0].message.content
            _record_response_usage(response)
            if not text:
                continue
            candidate = _sanitize_poll_text(text)
            last_candidate = candidate
            if _remember_generation("poll", candidate):
                return candidate
            logger.info("LLM poll duplicate detected, retrying generation")
        except Exception as e:
            logger.exception("Ошибка генерации вопроса опроса: %s", e)
            return None

    if last_candidate:
        # Даже при повторе возвращаем последний вариант, чтобы не сорвать отправку опроса.
        _force_remember_generation("poll", last_candidate)
        return last_candidate
    return None


NEWS_REWRITE_SYSTEM = """Ты — экспертный спортивный редактор и активный участник секции бадминтона РЖД. Твоя задача — превращать сухие новости из профессиональных каналов в живой, вовлекающий контент для коллег.

Твой стиль:
- Дружелюбный, энергичный, профессиональный
- Используй терминологию (смеш, дроп, бекхэнд), но объясняй сложное просто
- Избегай канцеляризмов. Мы — одна команда

Рерайт: Выдели самое главное. Добавь в конце призыв к действию (например: "Отличный повод отработать этот приём на нашей тренировке в среду!").

Ограничения:
- До 600 символов
- Минимум эмодзи (только по делу: 🏸, 🚂, ✅)
- Обращайся на "вы" или "друзья"."""


async def rewrite_news(original_text: str) -> str | None:
    """Рерайт новости через DeepSeek."""
    if _is_over_limit():
        logger.error(
            "DeepSeek: месячный лимит токенов достигнут (лимит %s). Рерайт новости пропущен.",
            get_settings().deepseek_monthly_token_limit,
        )
        return None
    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    try:
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": NEWS_REWRITE_SYSTEM},
                {"role": "user", "content": f"Перепиши эту новость:\n\n{original_text}"},
            ],
            max_tokens=500,
            temperature=0.7,
        )
        _record_response_usage(response)
        text = response.choices[0].message.content
        if text:
            text = text.strip().strip('"\'')
            if len(text) > 600:
                text = text[:597] + "..."
            return text
    except Exception as e:
        logger.exception("Ошибка рерайта новости: %s", e)
    return None


async def generate_news_variants(original_text: str, count: int = 3) -> list[str]:
    """Сгенерировать несколько вариантов рерайта для выбора."""
    if _is_over_limit():
        logger.error(
            "DeepSeek: месячный лимит токенов достигнут (лимит %s). Варианты новости не сгенерированы.",
            get_settings().deepseek_monthly_token_limit,
        )
        return []
    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    try:
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": NEWS_REWRITE_SYSTEM},
                {
                    "role": "user",
                    "content": f"Дай ровно {count} разных варианта рерайта этой новости. Каждый вариант с новой строки, начинай с номера (1., 2., 3.):\n\n{original_text}",
                },
            ],
            max_tokens=800,
            temperature=0.9,
        )
        _record_response_usage(response)
        text = response.choices[0].message.content
        if text:
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            variants = []
            for line in lines:
                if line and line[0].isdigit() and "." in line:
                    variants.append(line.split(".", 1)[1].strip())
                elif line:
                    variants.append(line)
            return variants[:count] if variants else [text[:600]]
    except Exception as e:
        logger.exception("Ошибка генерации вариантов: %s", e)
    return []


# Правила НФБР: приказ Минспорта РФ от 12.07.2021 № 546, актуальная редакция на странице НФБР
NFBR_RULES_URL = "https://nfbr.ru/documents/rules"

# Доверенные источники для квизов по истории и тактике (см. docs/Источники_квизы_история_тактика.md)
QUIZ_URL_OLYMPICS = "https://www.olympics.com/ru/sports/badminton/"
QUIZ_URL_BWF_RULES = "https://worldbadminton.com/rules/"
QUIZ_URL_BWF_HISTORY = "https://worldbadminton.com/rules/history.htm"
QUIZ_URL_BWF_DEVELOPMENT = "https://development.bwfbadminton.com/"

# База знаний для квизов: история и тактика (краткие факты из доверенных источников)
QUIZ_KNOWLEDGE_BASE = """
База знаний (история и тактика) — используй для вопросов по истории и тактике бадминтона.

История:
- Происхождение: игра «пуна» (Индия), battledore and shuttlecock; английские офицеры привезли игру в Англию в XIX веке.
- 1873: герцог Бофорт, поместье Badminton House (Глостершир, Англия) — появление названия «бадминтон».
- 1877: Bath Badminton Club — первый свод правил.
- 1893: Badminton Association of England — первый официальный регламент правил.
- 1934: создание International Badminton Federation (IBF); с 2006 — BWF (Badminton World Federation), штаб-квартира в Куала-Лумпуре.
- 1992: бадминтон в программе летних Олимпийских игр (Барселона).
- Реформы правил: 2006 — счёт 3x21 (ралли); 2018 — фиксированная высота подачи.

Тактика и термины (по правилам НФБР/BWF и BWF Coach Education):
- Типы ударов: смеш (атакующий удар сверху), дроп (короткий обводящий удар), драйв (плоский быстрый удар), сметка (удар у сетки).
- Подача: высокая (в заднюю линию), низкая (короткая), плоская; подача выполняется снизу, ракетка не выше пояса.
- Площадка: одиночная 5,18×13,40 м, парная 6,10×13,40 м; сетка 1,524 м по центру.
- Тактика: выбор удара в зависимости от позиции соперника, розыгрыш подачи, смена темпа, выход к сетке.
"""


def _get_rules_context_from_docx() -> str:
    """
    Извлечь текст из файла правил НФБР (.docx) для использования в промпте квиза.

    Файл задаётся в конфиге: rules_docx_file (например Doc/pravila_nfbr.docx).
    Подойдёт документ «Правила игры» НФБР в формате .docx (в т.ч. pravila_06_11_2024.docx).
    Возвращает пустую строку, если файл не задан, не найден или python-docx недоступен.
    """
    settings = get_settings()
    path = getattr(settings, "rules_docx_file", None)
    if not path:
        return ""
    path = path.strip() if isinstance(path, str) else path
    if not path or not Path(path).exists():
        return ""

    try:
        from docx import Document
        doc = Document(path)
        parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(parts)
        if len(text) > QUIZ_RULES_CONTEXT_MAX_CHARS:
            text = text[: QUIZ_RULES_CONTEXT_MAX_CHARS] + "\n\n… (фрагмент, далее см. полный документ)"
        return text
    except ImportError:
        logger.debug("python-docx не установлен — контекст правил из .docx недоступен")
        return ""
    except Exception as e:
        logger.warning("Ошибка чтения правил из .docx %s: %s", path, e)
        return ""

QUIZ_SYSTEM = f"""Ты — эксперт по правилам, истории и тактике бадминтона (НФБР, BWF). Генерируешь вопросы для квиза секции «Бадминтон РЖД».

Источники:
- Правила: НФБР, приказ Минспорта РФ от 12.07.2021 № 546 — {NFBR_RULES_URL}
- История и тактика: база знаний в запросе пользователя (даты, факты, термины из доверенных источников: Olympics.com, BWF, Britannica).

Темы вопросов: правила игры (счёт, подача, площадка, экипировка), история бадминтона (даты, события, организации), тактика и термины (типы ударов, подачи, базовые тактические понятия). Чередуй темы: не подряд только правила или только история.

Формат ответа (строго, все 6 полей обязательны):
QUESTION: [вопрос одной строкой]
OPTIONS:
1. [вариант 1]
2. [вариант 2]
3. [вариант 3]
4. [вариант 4]
CORRECT: [номер 1-4]
EXPLANATION: [подробное объяснение правильного ответа, 1-2 предложения; для правил — ссылка на НФБР, для истории/тактики — кратко по факту]

Правила:
- Вопрос короткий, по делу (правила, история, тактика, термины)
- Варианты не очевидные для новичка, заставляют подумать
- Ровно 4 варианта, один правильный
- Только русский язык
- Длина вопроса до 100 символов, вариантов до 50 символов каждый
- EXPLANATION: объясняет ПОЧЕМУ этот ответ правильный; для правил — упомяни НФБР или {NFBR_RULES_URL}
- CORRECT — только цифра 1, 2, 3 или 4"""


async def generate_quiz_question() -> tuple[str, list[str], int, str] | None:
    """
    Сгенерировать вопрос квиза по правилам бадминтона.

    Returns:
        (question, options, correct_index, explanation) или None при ошибке.
        correct_index: 0-3 (индекс в options).
        explanation: объяснение правильного ответа.
    """
    if _is_over_limit():
        logger.error(
            "DeepSeek: месячный лимит токенов достигнут (лимит %s). Генерация квиза пропущена.",
            get_settings().deepseek_monthly_token_limit,
        )
        return None
    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    recent_quizzes = _get_recent_history("quiz", QUIZ_HISTORY_WINDOW)

    rules_context = _get_rules_context_from_docx()
    context_block = ""
    if rules_context:
        context_block = (
            "\n\nИспользуй следующий фрагмент правил НФБР из официального документа (опирайся на него для формулировок и объяснений):\n"
            "---\n"
            f"{rules_context}\n"
            "---\n"
        )
    # База знаний: история и тактика (доверенные источники, см. docs/Источники_квизы_история_тактика.md)
    knowledge_block = (
        "\n\nДополнительная база знаний (история и тактика) — используй для вопросов по истории и тактике, не только по правилам:\n"
        "---\n"
        f"{QUIZ_KNOWLEDGE_BASE.strip()}\n"
        "---\n"
    )

    for _ in range(MAX_GENERATION_ATTEMPTS):
        try:
            recent_block = _format_recent_items(recent_quizzes)
            seed = uuid4().hex[:8]
            user_content = (
                "Сгенерируй новый вопрос квиза по бадминтону: правила НФБР, история или тактика/термины (опирайся на базу знаний выше). "
                "Вопрос и набор вариантов должны отличаться от последних.\n"
                f"Творческий идентификатор варианта: {seed}\n"
                f"{recent_block}"
            )
            if context_block:
                user_content = context_block + user_content
            user_content = knowledge_block + user_content

            response = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": QUIZ_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=400,
                temperature=1.0,
            )
            text = response.choices[0].message.content
            _record_response_usage(response)
            if not text:
                continue

            parsed = _parse_quiz_response(text)
            if not parsed:
                continue
            question, options, correct, explanation = parsed
            signature = _quiz_signature(question, options)
            if _remember_generation("quiz", signature):
                return (question, options, correct, explanation)
            logger.info("LLM quiz duplicate detected, retrying generation")
        except Exception as e:
            logger.exception("Ошибка генерации квиза: %s", e)
            return None
    return None


def _sanitize_poll_text(text: str) -> str:
    """Обрезать кавычки и пробелы, ограничить длину текста опроса до 200 символов."""
    cleaned = text.strip().strip('"\'')
    if len(cleaned) > 200:
        cleaned = cleaned[:197] + "..."
    return cleaned


def _normalize_text(text: str) -> str:
    """Привести строку к нижнему регистру и схлопнуть пробелы (для сравнения и дедупликации)."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _quiz_signature(question: str, options: list[str]) -> str:
    """Строковая подпись квиза (вопрос + варианты) для проверки дубликатов."""
    normalized = [_normalize_text(question)] + [_normalize_text(o) for o in options]
    return " | ".join(normalized)


def _read_history() -> dict[str, list[str]]:
    if not HISTORY_FILE.exists():
        return {"poll": [], "quiz": []}
    try:
        raw = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        poll = raw.get("poll", [])
        quiz = raw.get("quiz", [])
        if isinstance(poll, list) and isinstance(quiz, list):
            return {"poll": poll, "quiz": quiz}
    except Exception:
        logger.warning("История LLM повреждена, будет пересоздана")
    return {"poll": [], "quiz": []}


def _write_history(history: dict[str, list[str]]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _get_recent_history(kind: str, limit: int) -> list[str]:
    """Вернуть последние limit записей истории по типу (poll/quiz) для передачи в промпт."""
    history = _read_history()
    items = history.get(kind, [])
    if not isinstance(items, list):
        return []
    return [str(x) for x in items[-limit:]]


def _format_recent_items(items: list[str]) -> str:
    """Отформатировать список недавних формулировок для вставки в промпт (не повторять)."""
    if not items:
        return "Недавних формулировок нет."
    lines = "\n".join(f"- {item}" for item in items[-10:])
    return f"Последние формулировки, которые нельзя повторять:\n{lines}"


def _remember_generation(kind: str, item: str) -> bool:
    """Добавить сгенерированный элемент в историю. Возвращает False, если такой уже есть (дубликат)."""
    normalized_item = _normalize_text(item)
    history = _read_history()
    items = history.get(kind, [])
    normalized_existing = {_normalize_text(str(x)) for x in items}
    if normalized_item in normalized_existing:
        return False
    items.append(item)
    history[kind] = items[-MAX_HISTORY_ITEMS:]
    _write_history(history)
    return True


def _force_remember_generation(kind: str, item: str) -> None:
    history = _read_history()
    items = history.get(kind, [])
    items.append(item)
    history[kind] = items[-MAX_HISTORY_ITEMS:]
    _write_history(history)


def _current_month_key() -> str:
    """Ключ текущего месяца для учёта расхода (YYYY-MM)."""
    return datetime.now().strftime("%Y-%m")


def _read_usage() -> dict:
    """Прочитать учёт токенов из файла. При смене месяца данные обнуляются для нового месяца."""
    current_key = _current_month_key()
    if not USAGE_FILE.exists():
        return {"year_month": current_key, "total_tokens": 0}
    try:
        raw = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        prev_key = raw.get("year_month", "")
        total = int(raw.get("total_tokens", 0)) if isinstance(raw.get("total_tokens"), (int, float)) else 0
        if prev_key != current_key:
            return {"year_month": current_key, "total_tokens": 0}
        return {"year_month": current_key, "total_tokens": max(0, total)}
    except Exception:
        logger.debug("Файл учёта LLM повреждён или пуст, начинаем с нуля")
        return {"year_month": current_key, "total_tokens": 0}


def _write_usage(data: dict) -> None:
    """Записать учёт токенов в файл."""
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _record_usage(tokens: int) -> None:
    """Учесть потраченные токены за текущий месяц."""
    if tokens <= 0:
        return
    data = _read_usage()
    data["total_tokens"] = data["total_tokens"] + tokens
    _write_usage(data)


def _get_monthly_usage() -> int:
    """Текущий расход токенов за месяц."""
    return _read_usage()["total_tokens"]


def _is_over_limit() -> bool:
    """Проверить, достигнут ли месячный лимит токенов (если лимит включён)."""
    limit = get_settings().deepseek_monthly_token_limit
    if not limit or limit <= 0:
        return False
    return _get_monthly_usage() >= limit


def _parse_quiz_response(text: str) -> tuple[str, list[str], int, str] | None:
    """Разобрать ответ LLM в структуру квиза.

    Returns:
        (question, options, correct_index, explanation) или None при ошибке парсинга.
    """
    question = ""
    options: list[str] = []
    correct = 0
    explanation = ""

    for line in text.strip().split("\n"):
        line = line.strip()
        if line.upper().startswith("QUESTION:"):
            question = line.split(":", 1)[1].strip()[:100]
        elif line.upper().startswith("OPTIONS:"):
            continue
        elif line and line[0].isdigit() and "." in line:
            opt = line.split(".", 1)[1].strip()[:50]
            if opt:
                options.append(opt)
        elif line.upper().startswith("CORRECT:"):
            part = line.split(":", 1)[1].strip()
            # Берём только первую цифру (на случай если LLM добавит лишний текст)
            digits = "".join(c for c in part if c.isdigit())
            if digits:
                correct = int(digits[0]) - 1  # 1-based → 0-based
        elif line.upper().startswith("EXPLANATION:"):
            explanation = line.split(":", 1)[1].strip()[:400]

    if question and len(options) == 4 and 0 <= correct < 4:
        # Добавляем ссылку на правила НФБР если её нет в объяснении
        if explanation and NFBR_RULES_URL not in explanation:
            explanation = f"{explanation}\n📖 Правила НФБР: {NFBR_RULES_URL}"
        elif not explanation:
            explanation = f"📖 Правила игры НФБР (приказ Минспорта РФ от 12.07.2021 № 546): {NFBR_RULES_URL}"
        return (question, options, correct, explanation)
    return None
