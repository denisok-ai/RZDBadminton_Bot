"""
@file: quiz.py
@description: Пятничный квиз по правилам бадминтона (12:00)
@dependencies: aiogram, config, services.llm
@created: 2025-02-25
"""

import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest

from config import get_settings, get_poll_chat_id
from services.llm import generate_quiz_question

logger = logging.getLogger("rzdbadminton")

router = Router(name="quiz")

CHAT_NOT_FOUND_HINT = (
    "Проверьте MAIN_CHAT_ID и TEST_CHAT_ID в .env. "
    "Бот должен быть добавлен в группу. ID супергруппы: -100xxxxxxxxxx"
)


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

    question, options, correct_index = quiz_data
    try:
        await bot.send_poll(
            chat_id=chat_id,
            question=f"⚡ Квиз пятницы\n▬▬▬\n{question}",
            options=options,
            is_anonymous=False,
            type="quiz",
            correct_option_id=correct_index,
            explanation="BWF rules · SportTech",
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
                await bot.send_poll(
                    chat_id=settings.admin_id,
                    question=f"⚡ Квиз пятницы\n▬▬▬\n{question}",
                    options=options,
                    is_anonymous=False,
                    type="quiz",
                    correct_option_id=correct_index,
                    explanation="BWF rules · SportTech",
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
