"""
@file: llm.py
@description: Клиент DeepSeek API для генерации текстов
@dependencies: openai, config
@created: 2025-02-25
"""

import logging
import json
import re
from pathlib import Path
from uuid import uuid4

from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger("rzdbadminton")

HISTORY_FILE = Path("data/llm_generation_history.json")
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


async def generate_poll_question(weekday_name: str) -> str | None:
    """
    Сгенерировать вопрос опроса посещаемости через DeepSeek.

    Args:
        weekday_name: "Понедельник" или "Среда"

    Returns:
        Текст вопроса или None при ошибке
    """
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
        text = response.choices[0].message.content
        if text:
            lines = [l.strip() for l in text.split("\n") if l.strip()]
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


QUIZ_SYSTEM = """Ты — эксперт по правилам бадминтона (BWF). Генерируешь вопросы для квиза секции «Бадминтон РЖД».

Формат ответа (строго):
QUESTION: [вопрос одной строкой]
OPTIONS:
1. [вариант 1]
2. [вариант 2]
3. [вариант 3]
4. [вариант 4]
CORRECT: [номер 1-4]

Правила:
- Вопрос короткий, по делу (правила, счёт, экипировка, история)
- Варианты не очевидные для новичка
- Ровно 4 варианта, один правильный
- Только русский язык
- Длина вопроса до 100 символов, вариантов до 50 символов каждый
- CORRECT — только цифра 1, 2, 3 или 4"""


async def generate_quiz_question() -> tuple[str, list[str], int] | None:
    """
    Сгенерировать вопрос квиза по правилам бадминтона.

    Returns:
        (question, options, correct_index) или None при ошибке.
        correct_index: 0-3 (индекс в options).
    """
    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
    recent_quizzes = _get_recent_history("quiz", QUIZ_HISTORY_WINDOW)

    for _ in range(MAX_GENERATION_ATTEMPTS):
        try:
            recent_block = _format_recent_items(recent_quizzes)
            seed = uuid4().hex[:8]
            response = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": QUIZ_SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            "Сгенерируй новый вопрос квиза по правилам бадминтона BWF. "
                            "Вопрос и набор вариантов должны отличаться от последних.\n"
                            f"Творческий идентификатор варианта: {seed}\n"
                            f"{recent_block}"
                        ),
                    },
                ],
                max_tokens=300,
                temperature=1.0,
            )
            text = response.choices[0].message.content
            if not text:
                continue

            parsed = _parse_quiz_response(text)
            if not parsed:
                continue
            question, options, correct = parsed
            signature = _quiz_signature(question, options)
            if _remember_generation("quiz", signature):
                return (question, options, correct)
            logger.info("LLM quiz duplicate detected, retrying generation")
        except Exception as e:
            logger.exception("Ошибка генерации квиза: %s", e)
            return None
    return None


def _sanitize_poll_text(text: str) -> str:
    cleaned = text.strip().strip('"\'')
    if len(cleaned) > 200:
        cleaned = cleaned[:197] + "..."
    return cleaned


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _quiz_signature(question: str, options: list[str]) -> str:
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
    history = _read_history()
    items = history.get(kind, [])
    if not isinstance(items, list):
        return []
    return [str(x) for x in items[-limit:]]


def _format_recent_items(items: list[str]) -> str:
    if not items:
        return "Недавних формулировок нет."
    lines = "\n".join(f"- {item}" for item in items[-10:])
    return f"Последние формулировки, которые нельзя повторять:\n{lines}"


def _remember_generation(kind: str, item: str) -> bool:
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


def _parse_quiz_response(text: str) -> tuple[str, list[str], int] | None:
    question = ""
    options: list[str] = []
    correct = 0

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
            if part.isdigit():
                correct = int(part) - 1  # 1-based to 0-based

    if question and len(options) == 4 and 0 <= correct < 4:
        return (question, options, correct)
    return None
