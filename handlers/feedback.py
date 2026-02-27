"""
@file: feedback.py
@description: Обратная связь — групповой опрос оценки тренировки 1–5 в общий чат.
  Один опрос на весь чат вместо личных сообщений каждому.
@dependencies: aiogram, config, database.repositories
@created: 2025-02-25
"""

import logging
from datetime import date, timedelta

from aiogram import Bot, Router

from app_state import get_session_factory
from config import get_publish_chat_id, get_settings
from database.repositories import create_feedback_poll

logger = logging.getLogger("rzdbadminton")

router = Router(name="feedback")

FEEDBACK_OPTIONS = ["1 😔", "2 🙁", "3 😐", "4 🙂", "5 🏆"]


async def send_feedback_poll_to_chat(
    bot: Bot,
    training_date: date,
    chat_id: int,
) -> bool:
    """
    Отправить групповой опрос оценки тренировки в чат.

    Один опрос для всех — не требует, чтобы пользователь писал боту первым.

    Args:
        training_date: дата тренировки для заголовка и записи в БД.
        chat_id: ID чата куда отправить.
    Returns:
        True при успехе.
    """
    session_factory = get_session_factory()
    if not session_factory:
        logger.error("session_factory не инициализирована")
        return False
    try:
        day_name = "Понедельник" if training_date.weekday() == 0 else "Среда"
        question = (
            f"🏸 Оцените тренировку\n"
            f"{day_name}, {training_date.strftime('%d.%m.%Y')}"
        )
        msg = await bot.send_poll(
            chat_id=chat_id,
            question=question,
            options=FEEDBACK_OPTIONS,
            is_anonymous=False,
            allows_multiple_answers=False,
        )
        if msg.poll:
            async with session_factory() as session:
                # user_id=0 означает групповой опрос (не привязан к конкретному пользователю)
                await create_feedback_poll(
                    session,
                    telegram_poll_id=str(msg.poll.id),
                    user_id=0,
                    training_date=training_date,
                )
        logger.info("Групповой опрос оценки отправлен в чат %s за %s", chat_id, training_date)
        return True
    except Exception as e:
        logger.exception("Ошибка отправки группового опроса оценки: %s", e)
        return False


async def send_feedback_requests(bot: Bot, training_date: date) -> int:
    """
    Отправить групповой опрос оценки в основной чат (вызов из планировщика).

    Returns:
        1 при успехе, 0 при ошибке.
    """
    settings = get_settings()
    chat_id = get_publish_chat_id(settings)
    ok = await send_feedback_poll_to_chat(bot, training_date, chat_id)
    return 1 if ok else 0


def get_last_training_date() -> date | None:
    """Дата последней тренировки (Пн или Ср)."""
    today = date.today()
    wd = today.weekday()  # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    if wd == 0:  # Понедельник — последняя среда
        return today - timedelta(days=4)
    if wd == 1:  # Вторник — понедельник
        return today - timedelta(days=1)
    if wd == 2:  # Среда — понедельник
        return today - timedelta(days=2)
    if wd == 3:  # Четверг — среда
        return today - timedelta(days=1)
    if wd in (4, 5, 6):  # Пт–Вс — среда
        return today - timedelta(days=wd - 2)
    return None
