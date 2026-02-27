"""
@file: top3.py
@description: Месячный пост Топ-3 по посещаемости (1-го числа)
@dependencies: aiogram, config, database.repositories
@created: 2025-02-25
"""

import logging
from calendar import monthrange
from datetime import date

from aiogram import Bot

from app_state import get_session_factory
from config import get_settings, get_publish_chat_id
from ui.design import card
from database.repositories import get_top_by_poll_votes

logger = logging.getLogger("rzdbadminton")


MONTHS_RU = {
    1: "январь", 2: "февраль", 3: "март", 4: "апрель", 5: "май", 6: "июнь",
    7: "июль", 8: "август", 9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь",
}


async def send_monthly_top3(
    bot: Bot,
    chat_id: int | None = None,
    *,
    use_previous_month: bool = True,
) -> bool:
    """
    Отправить пост с Топ-3 по посещаемости.

    Args:
        chat_id: если None — MAIN_CHAT_ID.
        use_previous_month: True — прошлый месяц (планировщик, 1-го числа),
                            False — текущий месяц (ручной запрос кнопкой).
    Returns:
        True при успехе.
    """
    if chat_id is None:
        chat_id = get_publish_chat_id(get_settings())

    session_factory = get_session_factory()
    if not session_factory:
        logger.error("session_factory не инициализирована")
        return False

    today = date.today()
    if use_previous_month:
        if today.month == 1:
            start_date = date(today.year - 1, 12, 1)
            end_date = date(today.year - 1, 12, 31)
        else:
            start_date = date(today.year, today.month - 1, 1)
            last_day = monthrange(today.year, today.month - 1)[1]
            end_date = date(today.year, today.month - 1, last_day)
        label = "прошлый месяц"
    else:
        start_date = date(today.year, today.month, 1)
        last_day = monthrange(today.year, today.month)[1]
        end_date = date(today.year, today.month, last_day)
        label = "текущий месяц"

    async with session_factory() as session:
        top = await get_top_by_poll_votes(session, start_date, end_date, limit=3)

    month_name = MONTHS_RU.get(start_date.month, str(start_date.month))
    header = f"🏆 Топ-3 · {month_name} {start_date.year}"

    if not top:
        text = card(header, f"Пока нет данных за {label}.", "Отмечайтесь в опросах!")
    else:
        lines = [
            f"{medal} {name} — {cnt} тренировок"
            for medal, (_, name, cnt) in zip(["🥇", "🥈", "🥉"], top)
        ]
        text = card(header, *lines)

    try:
        await bot.send_message(chat_id, text)
        return True
    except Exception as e:
        logger.exception("Ошибка отправки Топ-3: %s", e)
        return False
