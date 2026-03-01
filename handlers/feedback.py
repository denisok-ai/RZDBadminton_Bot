"""
@file: feedback.py
@description: Обратная связь — групповой опрос оценки тренировки 1–5 в общий чат,
  итоги за неделю (Пт 11:45) и за месяц (1-го числа).
@dependencies: aiogram, config, database.repositories, ui.design
@created: 2025-02-25
"""

import logging
from calendar import monthrange
from datetime import date, timedelta

from aiogram import Bot

from app_state import get_session_factory
from config import get_publish_chat_id, get_settings
from database.repositories import create_feedback_poll, get_ratings_by_trainer
from ui.design import feedback_weekly_card, ratings_card
from utils.constants import MONTHS_RU

logger = logging.getLogger("rzdbadminton")

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
    if wd == 0:  # Понедельник — последняя среда (5 дней назад: Пн→Вс→Сб→Пт→Чт→Ср)
        return today - timedelta(days=5)
    if wd == 1:  # Вторник — понедельник
        return today - timedelta(days=1)
    if wd == 2:  # Среда — понедельник
        return today - timedelta(days=2)
    if wd == 3:  # Четверг — среда
        return today - timedelta(days=1)
    if wd in (4, 5, 6):  # Пт–Вс — среда
        return today - timedelta(days=wd - 2)
    return None


async def send_weekly_feedback_summary(bot: Bot, chat_id: int) -> bool:
    """
    Отправить в чат итоги обратной связи за текущую неделю (Пн + Ср).
    Вызывается по пятницам в 11:45.
    """
    session_factory = get_session_factory()
    if not session_factory:
        logger.error("session_factory не инициализирована")
        return False
    today = date.today()
    if today.weekday() != 4:  # только пятница
        return False
    mon_date = today - timedelta(days=4)
    wed_date = today - timedelta(days=2)
    start_date = mon_date
    end_date = wed_date
    try:
        async with session_factory() as session:
            data = await get_ratings_by_trainer(session, start_date, end_date)
        settings = get_settings()
        week_label = f"{mon_date.strftime('%d.%m')} и {wed_date.strftime('%d.%m')}"
        text = feedback_weekly_card(
            week_label, data, settings.trainer_mon, settings.trainer_wed
        )
        await bot.send_message(chat_id=chat_id, text=text)
        logger.info("Итоги обратной связи за неделю отправлены в чат %s", chat_id)
        return True
    except Exception as e:
        logger.exception("Ошибка отправки итогов обратной связи за неделю: %s", e)
        return False


async def send_monthly_feedback_summary(bot: Bot, chat_id: int) -> bool:
    """
    Отправить в чат итоги обратной связи за прошлый месяц.
    Вызывается 1-го числа в 10:00.
    """
    session_factory = get_session_factory()
    if not session_factory:
        logger.error("session_factory не инициализирована")
        return False
    today = date.today()
    if today.day != 1:
        return False
    if today.month == 1:
        start_date = date(today.year - 1, 12, 1)
        end_date = date(today.year - 1, 12, 31)
        month_name = MONTHS_RU.get(12, "декабрь")
        year = today.year - 1
    else:
        start_date = date(today.year, today.month - 1, 1)
        last_day = monthrange(today.year, today.month - 1)[1]
        end_date = date(today.year, today.month - 1, last_day)
        month_name = MONTHS_RU.get(today.month - 1, str(today.month - 1))
        year = today.year
    try:
        async with session_factory() as session:
            data = await get_ratings_by_trainer(session, start_date, end_date)
        settings = get_settings()
        text = ratings_card(
            month_name, year, data, settings.trainer_mon, settings.trainer_wed
        )
        # Заголовок заменить на «Обратная связь за месяц»
        text = text.replace("📈 Рейтинги", "📝 Обратная связь за месяц", 1)
        await bot.send_message(chat_id=chat_id, text=text)
        logger.info("Итоги обратной связи за месяц отправлены в чат %s", chat_id)
        return True
    except Exception as e:
        logger.exception("Ошибка отправки итогов обратной связи за месяц: %s", e)
        return False
