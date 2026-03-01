"""
@file: quiz.py
@description: Пятничный квиз (12:00), публикация правильного ответа (21:00)
@dependencies: aiogram, config, services.llm, database.repositories
@created: 2025-02-25
"""

import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest

from app_state import get_session_factory
from config import get_settings, get_poll_chat_id
from services.llm import generate_quiz_question

NFBR_RULES_URL = "https://nfbr.ru/documents/rules"

logger = logging.getLogger("rzdbadminton")

router = Router(name="quiz")

CHAT_NOT_FOUND_HINT = (
    "Проверьте MAIN_CHAT_ID и TEST_CHAT_ID в .env. "
    "Бот должен быть добавлен в группу. ID супергруппы: -100xxxxxxxxxx"
)


async def _save_quiz_record(
    telegram_poll_id: str,
    chat_id: int,
    question: str,
    correct_answer: str | None = None,
    explanation: str | None = None,
) -> None:
    """Сохранить запись о квизе в БД (статистика и публикация ответа в 21:00)."""
    session_factory = get_session_factory()
    if not session_factory:
        return
    try:
        from database.repositories import create_quiz_record
        async with session_factory() as session:
            await create_quiz_record(
                session,
                telegram_poll_id,
                chat_id,
                question,
                correct_answer=correct_answer,
                explanation=explanation,
            )
    except Exception as e:
        logger.warning("Не удалось сохранить QuizRecord: %s", e)


async def send_friday_quiz(bot: Bot, chat_id: int | None = None) -> bool:
    """
    Отправить квиз в чат (Пятница 12:00).

    chat_id: если None — берётся из config.
    Returns: True при успехе.
    """
    settings = get_settings()
    if chat_id is None:
        chat_id = get_poll_chat_id(settings)

    quiz_data = await generate_quiz_question()
    if not quiz_data:
        logger.warning("Не удалось сгенерировать квиз")
        return False

    question, options, correct_index, explanation = quiz_data
    correct_answer_text = options[correct_index] if 0 <= correct_index < len(options) else ""

    # Telegram ограничивает explanation: до 200 символов
    explanation_trimmed = explanation[:200] if explanation else ""

    async def _send_poll(target_chat_id: int) -> str | None:
        """Отправить квиз и вернуть telegram_poll_id при успехе."""
        msg = await bot.send_poll(
            chat_id=target_chat_id,
            question=f"⚡ Квиз пятницы\n▬▬▬\n{question}",
            options=options,
            is_anonymous=False,
            type="quiz",
            correct_option_id=correct_index,
            explanation=explanation_trimmed,
        )
        return str(msg.poll.id) if msg.poll else None

    try:
        poll_id = await _send_poll(chat_id)
        if poll_id:
            await _save_quiz_record(
                poll_id,
                chat_id,
                question,
                correct_answer=correct_answer_text,
                explanation=explanation,
            )
        return True
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "chat not found" in err or "chat_not_found" in err:
            logger.error("Квиз: чат %s не найден. %s", chat_id, CHAT_NOT_FOUND_HINT)
            try:
                await bot.send_message(
                    settings.admin_id,
                    f"⚠ Чат {chat_id} не найден. Квиз отправлен вам в личку.\n\n{CHAT_NOT_FOUND_HINT}",
                )
                poll_id = await _send_poll(settings.admin_id)
                if poll_id:
                    await _save_quiz_record(
                        poll_id,
                        settings.admin_id,
                        question,
                        correct_answer=correct_answer_text,
                        explanation=explanation,
                    )
                return True
            except Exception:
                pass
        else:
            logger.exception("Ошибка отправки квиза: %s", e)
        return False
    except Exception as e:
        logger.exception("Ошибка отправки квиза: %s", e)
        return False


async def send_quiz_answer_publication(bot: Bot, chat_id: int | None = None) -> bool:
    """
    Опубликовать в чат правильный ответ на квиз пятницы (запуск Пт 21:00).

    Берёт последний квиз за последние 12 часов для данного чата и отправляет
    сообщение с правильным ответом и объяснением.
    """
    from config import get_publish_chat_id
    from database.repositories import get_latest_quiz_for_chat

    settings = get_settings()
    if chat_id is None:
        chat_id = get_publish_chat_id(settings)
    session_factory = get_session_factory()
    if not session_factory:
        logger.warning("Публикация ответа квиза: БД не инициализирована")
        return False
    async with session_factory() as session:
        record = await get_latest_quiz_for_chat(session, chat_id, within_hours=12)
    if not record:
        logger.info("Публикация ответа квиза: за последние 12 ч квиза в чат %s не отправлялось", chat_id)
        return False
    correct = (record.correct_answer or "").strip()
    explanation = (record.explanation or "").strip()
    if not correct and not explanation:
        logger.info("Публикация ответа квиза: у записи нет correct_answer и explanation")
        return False
    lines = ["🎯 <b>Правильный ответ на квиз пятницы</b>"]
    if correct:
        lines.append(f"\n✅ <b>Правильный ответ:</b> {correct}")
    if explanation:
        if NFBR_RULES_URL not in explanation:
            explanation = f"{explanation}\n\n📖 Правила НФБР: {NFBR_RULES_URL}"
        lines.append(f"\n{explanation}")
    text = "\n".join(lines)
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML")
        logger.info("Правильный ответ на квиз опубликован в чат %s", chat_id)
        return True
    except Exception as e:
        logger.exception("Ошибка публикации ответа квиза в чат %s: %s", chat_id, e)
        return False
