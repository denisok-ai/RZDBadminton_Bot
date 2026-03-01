"""
@file: repositories.py
@description: CRUD операции для моделей БД
@dependencies: database.models, sqlalchemy
@created: 2025-02-25
"""

import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    Attendance,
    FeedbackPoll,
    NewsModeration,
    Poll,
    PollVote,
    ProcessedNews,
    QuizRecord,
    QuizVote,
    User,
    YouTubeModeration,
)

logger = logging.getLogger("rzdbadminton")


async def get_or_create_user(session: AsyncSession, user_id: int, **kwargs) -> User:
    """Получить или создать пользователя."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(id=user_id, **kwargs)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def create_feedback_poll(
    session: AsyncSession,
    telegram_poll_id: str,
    user_id: int,
    training_date: date,
) -> FeedbackPoll:
    """Сохранить опрос обратной связи для последующей обработки ответа."""
    fp = FeedbackPoll(
        telegram_poll_id=telegram_poll_id,
        user_id=user_id,
        training_date=training_date,
    )
    session.add(fp)
    await session.commit()
    await session.refresh(fp)
    return fp


async def get_feedback_poll_by_telegram_id(
    session: AsyncSession,
    telegram_poll_id: str,
) -> FeedbackPoll | None:
    """Найти опрос обратной связи по telegram_poll_id."""
    result = await session.execute(
        select(FeedbackPoll).where(FeedbackPoll.telegram_poll_id == telegram_poll_id)
    )
    return result.scalar_one_or_none()


async def upsert_attendance_rating(
    session: AsyncSession,
    user_id: int,
    attendance_date: date,
    rating: int,
) -> None:
    """Добавить или обновить рейтинг посещаемости (из обратной связи)."""
    result = await session.execute(
        select(Attendance).where(
            Attendance.user_id == user_id,
            Attendance.attendance_date == attendance_date,
        )
    )
    att = result.scalar_one_or_none()
    if att:
        att.rating = rating
    else:
        session.add(Attendance(user_id=user_id, attendance_date=attendance_date, rating=rating))
    await session.commit()


async def clear_attendance_rating(
    session: AsyncSession,
    user_id: int,
    attendance_date: date,
) -> None:
    """Сбросить оценку тренировки, если пользователь снял голос в опросе обратной связи."""
    result = await session.execute(
        select(Attendance).where(
            Attendance.user_id == user_id,
            Attendance.attendance_date == attendance_date,
        )
    )
    att = result.scalar_one_or_none()
    if att:
        att.rating = None
        await session.commit()


async def add_attendance(
    session: AsyncSession,
    user_id: int,
    attendance_date: date,
    rating: int | None = None,
) -> Attendance:
    """Добавить запись о посещаемости."""
    att = Attendance(user_id=user_id, attendance_date=attendance_date, rating=rating)
    session.add(att)
    await session.commit()
    await session.refresh(att)
    return att


async def get_avg_ratings_for_period(
    session: AsyncSession,
    start_date: date,
    end_date: date,
) -> tuple[float, int]:
    """
    Средний рейтинг и количество оценок за период.
    Returns: (avg_rating, count).
    """
    from sqlalchemy import func

    result = await session.execute(
        select(func.avg(Attendance.rating), func.count(Attendance.id))
        .where(
            Attendance.attendance_date >= start_date,
            Attendance.attendance_date <= end_date,
            Attendance.rating.isnot(None),
        )
    )
    row = result.one()
    avg_val, cnt = row[0], row[1] or 0
    return (round(float(avg_val), 1) if avg_val else 0.0, int(cnt))


async def get_ratings_by_trainer(
    session: AsyncSession,
    start_date: date,
    end_date: date,
) -> dict[str, tuple[float, int]]:
    """
    Средний рейтинг по тренировочным дням (Пн и Ср) за период.

    SQLite strftime('%w'): '0'=Вс, '1'=Пн, '2'=Вт, '3'=Ср, ...

    Returns:
        {"mon": (avg, count), "wed": (avg, count), "overall": (avg, count)}
    """
    from sqlalchemy import func

    result = await session.execute(
        select(
            func.strftime("%w", Attendance.attendance_date).label("dow"),
            func.avg(Attendance.rating).label("avg_rating"),
            func.count(Attendance.id).label("cnt"),
        )
        .where(
            Attendance.attendance_date >= start_date,
            Attendance.attendance_date <= end_date,
            Attendance.rating.isnot(None),
        )
        .group_by(func.strftime("%w", Attendance.attendance_date))
    )

    by_day: dict[str, tuple[float, int]] = {}
    total_weighted = 0.0
    total_count = 0

    for row in result.all():
        avg_val, cnt = row.avg_rating, int(row.cnt)
        avg = round(float(avg_val), 1) if avg_val else 0.0
        by_day[row.dow] = (avg, cnt)
        if avg_val:
            total_weighted += float(avg_val) * cnt
            total_count += cnt

    mon = by_day.get("1", (0.0, 0))   # Понедельник
    wed = by_day.get("3", (0.0, 0))   # Среда
    overall_avg = round(total_weighted / total_count, 1) if total_count > 0 else 0.0

    return {"mon": mon, "wed": wed, "overall": (overall_avg, total_count)}


async def get_attendances_by_date(
    session: AsyncSession,
    attendance_date: date,
) -> Sequence[Attendance]:
    """Получить посещаемость за дату."""
    result = await session.execute(
        select(Attendance).where(Attendance.attendance_date == attendance_date)
    )
    return result.scalars().all()


async def get_top_by_attendances(
    session: AsyncSession,
    start_date: date,
    end_date: date,
    limit: int = 3,
) -> Sequence[tuple[User, int]]:
    """Топ пользователей по посещаемости за период."""
    from sqlalchemy import func

    result = await session.execute(
        select(User, func.count(Attendance.id).label("count"))
        .join(Attendance, User.id == Attendance.user_id)
        .where(Attendance.attendance_date >= start_date, Attendance.attendance_date <= end_date)
        .group_by(User.id)
        .order_by(func.count(Attendance.id).desc())
        .limit(limit)
    )
    return result.all()


async def is_news_processed(
    session: AsyncSession,
    channel_id: int,
    message_id: int,
) -> bool:
    """Проверить, обработан ли пост (дедупликация)."""
    result = await session.execute(
        select(ProcessedNews).where(
            ProcessedNews.channel_id == channel_id,
            ProcessedNews.message_id == message_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def create_poll(
    session: AsyncSession,
    telegram_poll_id: str,
    chat_id: int,
    poll_date: date,
) -> Poll:
    """Создать запись об опросе."""
    poll = Poll(
        telegram_poll_id=telegram_poll_id,
        chat_id=chat_id,
        poll_date=poll_date,
    )
    session.add(poll)
    await session.commit()
    await session.refresh(poll)
    return poll


async def get_poll_by_telegram_id(
    session: AsyncSession,
    telegram_poll_id: str,
) -> Poll | None:
    """Найти опрос по telegram_poll_id."""
    result = await session.execute(
        select(Poll).where(Poll.telegram_poll_id == telegram_poll_id)
    )
    return result.scalar_one_or_none()


async def upsert_poll_vote(
    session: AsyncSession,
    poll_id: int,
    user_id: int,
    option_index: int,
) -> None:
    """Добавить или обновить голос (при смене ответа)."""
    result = await session.execute(
        select(PollVote).where(
            PollVote.poll_id == poll_id,
            PollVote.user_id == user_id,
        )
    )
    vote = result.scalar_one_or_none()
    if vote:
        vote.option_index = option_index
    else:
        session.add(
            PollVote(poll_id=poll_id, user_id=user_id, option_index=option_index)
        )
    await session.commit()


async def delete_poll_vote(
    session: AsyncSession,
    poll_id: int,
    user_id: int,
) -> None:
    """Удалить голос пользователя в опросе (если пользователь снял голос)."""
    await session.execute(
        delete(PollVote).where(
            PollVote.poll_id == poll_id,
            PollVote.user_id == user_id,
        )
    )
    await session.commit()


async def get_top_by_poll_votes(
    session: AsyncSession,
    start_date: date,
    end_date: date,
    limit: int = 3,
) -> list[tuple[int, str, int]]:
    """
    Топ пользователей по голосам «Приду» за период (для месячного Топ-3).

    Returns:
        Список (user_id, display_name, count).
    """
    from sqlalchemy import func

    result = await session.execute(
        select(User.id, User.first_name, User.last_name, User.username, func.count(PollVote.id).label("cnt"))
        .join(PollVote, User.id == PollVote.user_id)
        .join(Poll, Poll.id == PollVote.poll_id)
        .where(
            Poll.poll_date >= start_date,
            Poll.poll_date <= end_date,
            PollVote.option_index == 0,
        )
        .group_by(User.id)
        .order_by(func.count(PollVote.id).desc())
        .limit(limit)
    )
    rows = result.all()
    out = []
    for row in rows:
        user_id, first, last, username = row[:4]
        cnt = row[4]
        name = " ".join(filter(None, [first or "", last or ""])).strip()
        if not name:
            name = username or f"id{user_id}"
        out.append((user_id, name, cnt))
    return out


async def get_monthly_attendance_records(
    session: AsyncSession,
    year: int,
    month: int,
) -> list[tuple[int, str, str, date]]:
    """
    Все записи «Приду» (option_index=0) за указанный месяц.

    Args:
        year: год.
        month: месяц (1–12).

    Returns:
        Список (user_id, display_name, full_name, poll_date), отсортированный по дате и user_id.
        display_name — @username, иначе полное имя, иначе «idXXX».
        full_name — «Имя Фамилия» или пустая строка.
    """
    import calendar

    _, last_day = calendar.monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)
    result = await session.execute(
        select(User.id, User.first_name, User.last_name, User.username, Poll.poll_date)
        .join(PollVote, User.id == PollVote.user_id)
        .join(Poll, Poll.id == PollVote.poll_id)
        .where(
            Poll.poll_date >= start,
            Poll.poll_date <= end,
            PollVote.option_index == 0,
        )
        .order_by(Poll.poll_date, User.id)
    )
    rows = result.all()
    out = []
    for row in rows:
        user_id, first, last, username, poll_date = row
        full_name = " ".join(filter(None, [first or "", last or ""])).strip()
        display_name = (
            (f"@{username}" if username and not username.startswith("@") else username)
            or full_name
            or f"id{user_id}"
        )
        out.append((user_id, display_name, full_name, poll_date))
    return out


async def get_poll_voters_attending(
    session: AsyncSession,
    poll_date: date,
    *,
    use_username_for_report: bool = False,
) -> list[tuple[int, str]]:
    """
    Список пользователей, проголосовавших «Приду» (option_index=0) за дату.

    Args:
        use_username_for_report: если True, в качестве имени брать @username
            (название учётной записи для отчёта), иначе first_name + last_name.

    Returns:
        Список (user_id, display_name).
    """
    result = await session.execute(
        select(User.id, User.first_name, User.last_name, User.username)
        .join(PollVote, User.id == PollVote.user_id)
        .join(Poll, Poll.id == PollVote.poll_id)
        .where(
            Poll.poll_date == poll_date,
            PollVote.option_index == 0,
        )
    )
    rows = result.all()
    out = []
    for row in rows:
        user_id, first, last, username = row
        if use_username_for_report and username:
            name = f"@{username}" if not username.startswith("@") else username
        else:
            name = " ".join(filter(None, [first or "", last or ""])).strip()
            if not name:
                name = (f"@{username}" if username and not username.startswith("@") else username) or f"id{user_id}"
        out.append((user_id, name))
    return out


async def create_news_moderation(
    session: AsyncSession,
    channel_id: int,
    message_id: int,
    source_channel: str,
    original_text: str,
    rewritten_text: str,
) -> NewsModeration:
    """Создать запись новости на модерации."""
    nm = NewsModeration(
        channel_id=channel_id,
        message_id=message_id,
        source_channel=source_channel,
        original_text=original_text,
        rewritten_text=rewritten_text,
    )
    session.add(nm)
    await session.commit()
    await session.refresh(nm)
    return nm


async def get_news_moderation(
    session: AsyncSession,
    moderation_id: int,
) -> NewsModeration | None:
    """Получить новость на модерации по ID."""
    result = await session.execute(
        select(NewsModeration).where(NewsModeration.id == moderation_id)
    )
    return result.scalar_one_or_none()


async def update_news_moderation_variants(
    session: AsyncSession,
    moderation_id: int,
    variants: list[str],
) -> None:
    """Обновить варианты текста для [Редактировать]."""
    result = await session.execute(
        select(NewsModeration).where(NewsModeration.id == moderation_id)
    )
    nm = result.scalar_one_or_none()
    if nm:
        nm.variants = "\n---\n".join(variants)
        await session.commit()


async def mark_news_processed(
    session: AsyncSession,
    channel_id: int,
    message_id: int,
) -> None:
    """Отметить пост как обработанный."""
    pn = ProcessedNews(channel_id=channel_id, message_id=message_id)
    session.add(pn)
    await session.commit()


async def try_mark_news_processed(
    session: AsyncSession,
    channel_id: int,
    message_id: int,
) -> bool:
    """
    Попытаться атомарно пометить пост как обработанный.

    Returns:
        True, если пометка создана в этом процессе; False, если уже была.
    """
    session.add(ProcessedNews(channel_id=channel_id, message_id=message_id))
    try:
        await session.commit()
        return True
    except IntegrityError:
        await session.rollback()
        return False


async def unmark_news_processed(
    session: AsyncSession,
    channel_id: int,
    message_id: int,
) -> None:
    """Снять пометку обработанного поста, чтобы повторить обработку в следующем цикле."""
    await session.execute(
        delete(ProcessedNews).where(
            ProcessedNews.channel_id == channel_id,
            ProcessedNews.message_id == message_id,
        )
    )
    await session.commit()


async def create_youtube_moderation(
    session: AsyncSession,
    video_id: str,
    title: str,
    link: str,
    channel_id: str,
) -> YouTubeModeration | None:
    """
    Создать запись YouTube-видео на модерации.
    Returns:
        Запись при успехе; None при дубликате video_id.
    """
    ym = YouTubeModeration(
        video_id=video_id,
        title=title,
        link=link,
        channel_id=channel_id,
    )
    session.add(ym)
    try:
        await session.commit()
        await session.refresh(ym)
        return ym
    except IntegrityError:
        await session.rollback()
        return None


async def get_youtube_moderation(
    session: AsyncSession,
    moderation_id: int,
) -> YouTubeModeration | None:
    """Получить запись YouTube на модерации по ID."""
    result = await session.execute(
        select(YouTubeModeration).where(YouTubeModeration.id == moderation_id)
    )
    return result.scalar_one_or_none()


async def clear_pending_youtube_moderation(session: AsyncSession) -> int:
    """Удалить все записи YouTube на модерации (очистка очереди предложений). Возвращает количество удалённых."""
    result = await session.execute(delete(YouTubeModeration))
    count = result.rowcount if result.rowcount is not None else 0
    await session.commit()
    return count


async def create_quiz_record(
    session: AsyncSession,
    telegram_poll_id: str,
    chat_id: int,
    question: str | None = None,
    correct_answer: str | None = None,
    explanation: str | None = None,
) -> QuizRecord | None:
    """Сохранить запись об отправленном квизе. При дубликате telegram_poll_id возвращает None."""
    record = QuizRecord(
        telegram_poll_id=telegram_poll_id,
        chat_id=chat_id,
        question=question,
        correct_answer=correct_answer,
        explanation=explanation,
    )
    session.add(record)
    try:
        await session.commit()
        await session.refresh(record)
        return record
    except IntegrityError:
        await session.rollback()
        logger.debug(
            "Дубликат quiz_record (poll_id=%s, chat_id=%s), запись уже есть в БД",
            telegram_poll_id,
            chat_id,
        )
        return None
    except Exception as e:
        await session.rollback()
        logger.warning(
            "Не удалось сохранить quiz_record (poll_id=%s): %s",
            telegram_poll_id,
            e,
        )
        return None


async def get_quiz_record_by_telegram_id(
    session: AsyncSession,
    telegram_poll_id: str,
) -> QuizRecord | None:
    """Найти запись квиза по Telegram poll_id (для определения, что ответ пришёл на квиз)."""
    result = await session.execute(
        select(QuizRecord).where(QuizRecord.telegram_poll_id == telegram_poll_id)
    )
    return result.scalar_one_or_none()


async def upsert_quiz_vote(
    session: AsyncSession,
    telegram_poll_id: str,
    user_id: int,
) -> None:
    """Сохранить ответ пользователя на квиз (один голос на пользователя на квиз; при повторе — игнор)."""
    vote = QuizVote(telegram_poll_id=telegram_poll_id, user_id=user_id)
    session.add(vote)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logger.debug("quiz_vote дубликат: poll_id=%s user_id=%s", telegram_poll_id, user_id)


async def get_latest_quiz_for_chat(
    session: AsyncSession,
    chat_id: int,
    within_hours: int = 12,
) -> QuizRecord | None:
    """
    Последний квиз, отправленный в чат за последние within_hours часов.
    Используется для публикации правильного ответа (пятница 21:00).
    """
    cutoff = datetime.now(UTC) - timedelta(hours=within_hours)
    result = await session.execute(
        select(QuizRecord)
        .where(
            QuizRecord.chat_id == chat_id,
            QuizRecord.sent_at >= cutoff,
        )
        .order_by(QuizRecord.sent_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_activity_stats(
    session: AsyncSession,
    year: int,
    month: int,
) -> dict:
    """
    Статистика активности за месяц.

    Returns:
        Словарь с ключами:
        - polls_sent: кол-во опросов посещаемости
        - poll_participants: уникальных участников (любой ответ)
        - poll_attending: проголосовали «Приду»
        - news_published: опубликованных новостей
        - quizzes_sent: отправлено квизов
        - quiz_participants: уникальных участников квизов за месяц
        - feedback_sent: опросов обратной связи
        - feedback_avg: средняя оценка (float, 0.0 если нет оценок)
        - feedback_count: кол-во оценок
        - youtube_sent: отправлено на модерацию за месяц
        - youtube_published: опубликовано за месяц
        - youtube_rejected: отклонено за месяц
        - youtube_pending_total: всего в очереди (ожидают решения)
    """
    import calendar
    from datetime import datetime as dt
    from sqlalchemy import func

    _, last_day = calendar.monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)
    start_dt = dt(year, month, 1, 0, 0, 0)
    end_dt = dt(year, month, last_day, 23, 59, 59)

    # Опросы посещаемости
    polls_res = await session.execute(
        select(func.count(Poll.id)).where(
            Poll.poll_date >= start_date,
            Poll.poll_date <= end_date,
        )
    )
    polls_sent = polls_res.scalar_one() or 0

    # Уникальные участники (любой голос)
    participants_res = await session.execute(
        select(func.count(func.distinct(PollVote.user_id)))
        .join(Poll, Poll.id == PollVote.poll_id)
        .where(
            Poll.poll_date >= start_date,
            Poll.poll_date <= end_date,
        )
    )
    poll_participants = participants_res.scalar_one() or 0

    # Проголосовали «Приду» (option_index=0)
    attending_res = await session.execute(
        select(func.count(func.distinct(PollVote.user_id)))
        .join(Poll, Poll.id == PollVote.poll_id)
        .where(
            Poll.poll_date >= start_date,
            Poll.poll_date <= end_date,
            PollVote.option_index == 0,
        )
    )
    poll_attending = attending_res.scalar_one() or 0

    # Опубликованные новости
    news_res = await session.execute(
        select(func.count(NewsModeration.id)).where(
            NewsModeration.status == "published",
            NewsModeration.created_at >= start_dt,
            NewsModeration.created_at <= end_dt,
        )
    )
    news_published = news_res.scalar_one() or 0

    # Квизы
    quizzes_res = await session.execute(
        select(func.count(QuizRecord.id)).where(
            QuizRecord.sent_at >= start_dt,
            QuizRecord.sent_at <= end_dt,
        )
    )
    quizzes_sent = quizzes_res.scalar_one() or 0

    # Участники квизов за месяц (уникальные пользователи, ответившие на квизы за период)
    quiz_part_res = await session.execute(
        select(func.count(func.distinct(QuizVote.user_id)))
        .select_from(QuizVote)
        .join(QuizRecord, QuizVote.telegram_poll_id == QuizRecord.telegram_poll_id)
        .where(
            QuizRecord.sent_at >= start_dt,
            QuizRecord.sent_at <= end_dt,
        )
    )
    quiz_participants = quiz_part_res.scalar_one() or 0

    # Опросы обратной связи
    feedback_res = await session.execute(
        select(func.count(FeedbackPoll.id)).where(
            FeedbackPoll.created_at >= start_dt,
            FeedbackPoll.created_at <= end_dt,
        )
    )
    feedback_sent = feedback_res.scalar_one() or 0

    # Средняя оценка за месяц
    rating_res = await session.execute(
        select(func.avg(Attendance.rating), func.count(Attendance.id)).where(
            Attendance.attendance_date >= start_date,
            Attendance.attendance_date <= end_date,
            Attendance.rating.isnot(None),
        )
    )
    row = rating_res.one()
    avg_rating = round(float(row[0]), 1) if row[0] else 0.0
    rating_count = int(row[1]) if row[1] else 0

    # YouTube за месяц (по created_at)
    yt_sent_res = await session.execute(
        select(func.count(YouTubeModeration.id)).where(
            YouTubeModeration.created_at >= start_dt,
            YouTubeModeration.created_at <= end_dt,
        )
    )
    youtube_sent = yt_sent_res.scalar_one() or 0

    yt_pub_res = await session.execute(
        select(func.count(YouTubeModeration.id)).where(
            YouTubeModeration.created_at >= start_dt,
            YouTubeModeration.created_at <= end_dt,
            YouTubeModeration.status == "published",
        )
    )
    youtube_published = yt_pub_res.scalar_one() or 0

    yt_rej_res = await session.execute(
        select(func.count(YouTubeModeration.id)).where(
            YouTubeModeration.created_at >= start_dt,
            YouTubeModeration.created_at <= end_dt,
            YouTubeModeration.status == "rejected",
        )
    )
    youtube_rejected = yt_rej_res.scalar_one() or 0

    yt_pending_res = await session.execute(
        select(func.count(YouTubeModeration.id)).where(
            YouTubeModeration.status == "pending",
        )
    )
    youtube_pending_total = yt_pending_res.scalar_one() or 0

    return {
        "polls_sent": polls_sent,
        "poll_participants": poll_participants,
        "poll_attending": poll_attending,
        "news_published": news_published,
        "quizzes_sent": quizzes_sent,
        "quiz_participants": quiz_participants,
        "feedback_sent": feedback_sent,
        "feedback_avg": avg_rating,
        "feedback_count": rating_count,
        "youtube_sent": youtube_sent,
        "youtube_published": youtube_published,
        "youtube_rejected": youtube_rejected,
        "youtube_pending_total": youtube_pending_total,
    }
