"""
@file: polls.py
@description: Опросы посещаемости — отправка и обработка ответов
@dependencies: aiogram, config, database, services.llm
@created: 2025-02-25
"""

from datetime import date

from aiogram import Bot, Router
from aiogram.types import PollAnswer

from config import get_settings, get_poll_chat_id
from app_state import get_session_factory
from services.llm import generate_poll_question
from database.repositories import (
    clear_attendance_rating,
    create_poll,
    delete_poll_vote,
    get_feedback_poll_by_telegram_id,
    get_or_create_user,
    get_poll_by_telegram_id,
    upsert_attendance_rating,
    upsert_poll_vote,
)

router = Router(name="polls")

POLL_OPTIONS = ["Приду 🙋‍♂️", "Не приду 😔", "Может быть 🤔"]

WEEKDAY_NAMES = {0: "Понедельник", 2: "Среда"}

FALLBACK_QUESTIONS = {
    0: "Всем привет! Понедельник, 20:15 — кто на тренировку? Отмечаемся! 🏸",
    2: "Всем привет! Среда, Стромынка — отмечаемся, не стесняемся! 🏸",
}


async def get_poll_question(poll_date: date) -> str:
    """Вопрос опроса: генерируется через LLM, fallback — шаблон."""
    weekday = poll_date.weekday()
    weekday_name = WEEKDAY_NAMES.get(weekday) or "сегодня"
    question = await generate_poll_question(weekday_name)
    if question and question.strip():
        if "🏸" not in question and "👋" not in question and "🎯" not in question:
            question = question.rstrip() + " 🏸"
        return question[:200]
    return FALLBACK_QUESTIONS.get(
        weekday,
        "Всем привет! Кто придёт сегодня на тренировку? 🏸",
    )


async def send_attendance_poll(
    bot: Bot,
    session_factory,
    chat_id: int | None = None,
) -> bool:
    """
    Отправить опрос посещаемости в чат.
    chat_id: если None — берётся из config (DEBUG_MODE → TEST/MAIN).
    Returns: True при успехе, False при ошибке.
    """
    settings = get_settings()
    if chat_id is None:
        chat_id = get_poll_chat_id(settings)
    poll_date = date.today()

    question = await get_poll_question(poll_date)
    msg = await bot.send_poll(
        chat_id=chat_id,
        question=question,
        options=POLL_OPTIONS,
        is_anonymous=False,
        allows_multiple_answers=False,
    )

    if msg.poll:
        async with session_factory() as session:
            await create_poll(
                session,
                telegram_poll_id=str(msg.poll.id),
                chat_id=chat_id,
                poll_date=poll_date,
            )
    return True


@router.poll_answer()
async def on_poll_answer(poll_answer: PollAnswer) -> None:
    """Обработка ответа на опрос (посещаемость или обратная связь)."""
    session_factory = get_session_factory()
    if not session_factory:
        return
    user = poll_answer.user
    if not user:
        return

    poll_id_str = str(poll_answer.poll_id)

    async with session_factory() as session:
        # Сначала проверяем — это опрос обратной связи?
        feedback_poll = await get_feedback_poll_by_telegram_id(session, poll_id_str)
        if feedback_poll:
            if poll_answer.option_ids:
                rating = poll_answer.option_ids[0] + 1  # 0–4 → 1–5
                await upsert_attendance_rating(
                    session,
                    user_id=user.id,
                    attendance_date=feedback_poll.training_date,
                    rating=rating,
                )
            else:
                await clear_attendance_rating(
                    session,
                    user_id=user.id,
                    attendance_date=feedback_poll.training_date,
                )
            return

        # Иначе — опрос посещаемости
        poll = await get_poll_by_telegram_id(session, poll_id_str)
        if poll is None:
            return

        if poll_answer.option_ids:
            await get_or_create_user(
                session,
                user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            await upsert_poll_vote(
                session,
                poll_id=poll.id,
                user_id=user.id,
                option_index=poll_answer.option_ids[0],
            )
        else:
            await delete_poll_vote(
                session,
                poll_id=poll.id,
                user_id=user.id,
            )
