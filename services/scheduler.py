"""
@file: scheduler.py
@description: APScheduler — опросы, отчёты, новости, квиз, обратная связь, Топ-3
@dependencies: apscheduler, aiogram, config
@created: 2025-02-25
"""

import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import get_settings, get_publish_chat_id
from database.repositories import (
    create_youtube_moderation,
    get_monthly_attendance_records,
    try_mark_news_processed,
    unmark_news_processed,
)
from handlers.feedback import (
    send_feedback_requests,
    send_monthly_feedback_summary,
    send_weekly_feedback_summary,
)
from handlers.news import send_news_to_moderation
from handlers.polls import send_attendance_poll
from handlers.quiz import send_friday_quiz, send_quiz_answer_publication
from handlers.top3 import send_monthly_top3
from handlers.youtube_moderation import send_youtube_to_moderation
from services.db_backup import run_backup
from services.excel_reporter import get_report_file as generate_report
from services.llm import rewrite_news
from services.news_parser import ParsedPost, run_parse
from services.youtube_monitor import (
    DEFAULT_BWF_CHANNEL_ID,
    get_unseen_highlights,
    mark_youtube_sent_to_moderation,
)
from utils.constants import MONTHS_RU

logger = logging.getLogger("rzdbadminton")


def setup_scheduler(bot, session_factory) -> AsyncIOScheduler:
    """Настроить планировщик: опросы Пн/Ср 08:00, отчёты 23:00."""
    scheduler = AsyncIOScheduler(timezone=get_settings().timezone)

    async def job_send_poll():
        try:
            await send_attendance_poll(bot, session_factory)
            logger.info("Опрос посещаемости отправлен")
        except Exception as e:
            logger.exception("Ошибка отправки опроса: %s", e)

    async def job_generate_report():
        try:
            report_date = date.today()
            async with session_factory() as session:
                records = await get_monthly_attendance_records(
                    session, report_date.year, report_date.month
                )
            path = await generate_report(report_date, records)
            if path:
                from aiogram.types import FSInputFile
                unique_users = len({r[0] for r in records})
                sessions = len({r[3] for r in records})
                month_name = MONTHS_RU.get(report_date.month, str(report_date.month))
                await bot.send_document(
                    chat_id=get_settings().admin_id,
                    document=FSInputFile(path),
                    caption=f"📊 Отчёт · {month_name} {report_date.year} · {unique_users} участников · {sessions} тренировок",
                )
                logger.info("Отчёт за %s/%s сформирован и отправлен", report_date.month, report_date.year)
            else:
                await bot.send_message(
                    get_settings().admin_id,
                    f"⚠️ Не удалось сформировать отчёт за {report_date.month}/{report_date.year}",
                )
        except Exception as e:
            logger.exception("Ошибка формирования отчёта: %s", e)
            try:
                await bot.send_message(
                    get_settings().admin_id,
                    f"⚠️ Ошибка отчёта: {e}",
                )
            except Exception:
                pass

    scheduler.add_job(
        job_send_poll,
        CronTrigger(day_of_week="mon,wed", hour=8, minute=0),
        id="attendance_poll",
    )
    scheduler.add_job(
        job_generate_report,
        CronTrigger(day_of_week="mon,wed", hour=23, minute=0),
        id="daily_report",
    )

    async def job_news_monitor():
        """Парсинг каналов, рерайт, отправка на модерацию."""
        await run_news_monitor(bot, session_factory)

    scheduler.add_job(
        job_news_monitor,
        CronTrigger(hour="10,12,14,16,18,20,22", minute=15),  # Каждые 2 часа с 10:15 до 22:15
        id="news_monitor",
    )

    async def job_friday_quiz():
        try:
            await send_friday_quiz(bot)
            logger.info("Квиз пятницы отправлен")
        except Exception as e:
            logger.exception("Ошибка отправки квиза: %s", e)

    scheduler.add_job(
        job_friday_quiz,
        CronTrigger(day_of_week="fri", hour=12, minute=0),
        id="friday_quiz",
    )

    async def job_quiz_answer():
        """Пятница 21:00 — публикация правильного ответа на квиз в общий чат."""
        try:
            chat_id = get_publish_chat_id(get_settings())
            ok = await send_quiz_answer_publication(bot, chat_id)
            if ok:
                logger.info("Правильный ответ на квиз опубликован")
        except Exception as e:
            logger.exception("Ошибка публикации ответа квиза: %s", e)

    scheduler.add_job(
        job_quiz_answer,
        CronTrigger(day_of_week="fri", hour=21, minute=0),
        id="quiz_answer_publication",
    )

    async def job_feedback():
        """Пн 22:45 — опрос за понедельник, Ср 22:45 — за среду (в общий чат)."""
        try:
            today = date.today()
            if today.weekday() not in (0, 2):  # только Пн или Ср
                return
            training_date = today  # опрос в день тренировки вечером
            sent = await send_feedback_requests(bot, training_date)
            logger.info("Обратная связь (опрос в чат) отправлена за %s: %s", training_date, sent)
        except Exception as e:
            logger.exception("Ошибка отправки обратной связи: %s", e)

    scheduler.add_job(
        job_feedback,
        CronTrigger(day_of_week="mon,wed", hour=22, minute=45),
        id="feedback",
    )

    async def job_weekly_feedback_summary():
        """Пт 11:45 — итоги обратной связи за неделю в общий чат."""
        try:
            chat_id = get_publish_chat_id(get_settings())
            ok = await send_weekly_feedback_summary(bot, chat_id)
            if ok:
                logger.info("Итоги обратной связи за неделю отправлены")
        except Exception as e:
            logger.exception("Ошибка отправки итогов обратной связи за неделю: %s", e)

    scheduler.add_job(
        job_weekly_feedback_summary,
        CronTrigger(day_of_week="fri", hour=11, minute=45),
        id="feedback_weekly_summary",
    )

    async def job_monthly_feedback_summary():
        """1-го числа в 10:00 — итоги обратной связи за прошлый месяц в общий чат."""
        try:
            chat_id = get_publish_chat_id(get_settings())
            ok = await send_monthly_feedback_summary(bot, chat_id)
            if ok:
                logger.info("Итоги обратной связи за месяц отправлены")
        except Exception as e:
            logger.exception("Ошибка отправки итогов обратной связи за месяц: %s", e)

    scheduler.add_job(
        job_monthly_feedback_summary,
        CronTrigger(day=1, hour=10, minute=0),
        id="feedback_monthly_summary",
    )

    async def job_db_backup():
        """Ежедневный бекап БД; хранятся последние 10 дней."""
        try:
            ok, msg = run_backup()
            if ok:
                logger.info("Бекап БД: %s", msg)
            else:
                logger.warning("Бекап БД: %s", msg)
        except Exception as e:
            logger.exception("Ошибка бекапа БД: %s", e)

    scheduler.add_job(
        job_db_backup,
        CronTrigger(hour=4, minute=0),  # Ежедневно в 04:00
        id="db_backup",
    )

    async def job_top3():
        try:
            await send_monthly_top3(bot)
            logger.info("Топ-3 отправлен")
        except Exception as e:
            logger.exception("Ошибка отправки Топ-3: %s", e)

    scheduler.add_job(
        job_top3,
        CronTrigger(day=1, hour=9, minute=0),  # 1-го числа в 09:00
        id="monthly_top3",
    )

    async def job_youtube_highlights():
        """Новые видео с BWF TV — на модерацию админу (публикация в чат только после одобрения)."""
        try:
            videos = await get_unseen_highlights()
            if not videos:
                return
            settings = get_settings()
            channel_id = settings.youtube_channel_id or DEFAULT_BWF_CHANNEL_ID
            sent = 0
            for v in videos:
                async with session_factory() as session:
                    ym = await create_youtube_moderation(
                        session, v.video_id, v.title, v.link, channel_id
                    )
                if ym is None:
                    continue  # дубликат
                ok = await send_youtube_to_moderation(
                    bot, ym.id, ym.title, ym.link
                )
                if ok:
                    mark_youtube_sent_to_moderation(v.video_id)
                    sent += 1
            if sent:
                logger.info("YouTube: на модерацию отправлено %s", sent)
        except Exception as e:
            logger.exception("Ошибка job_youtube_highlights: %s", e)

    scheduler.add_job(
        job_youtube_highlights,
        CronTrigger(hour="10,14,18,22", minute=30),  # Каждые 4 часа с 10:30 до 22:30
        id="youtube_highlights",
    )

    return scheduler


async def run_news_monitor(bot, session_factory) -> dict[str, int]:
    """
    Запустить парсинг каналов (для job и команды /news).

    Returns:
        Словарь с ключами: total (найдено постов), new (новых), sent (отправлено на модерацию).
    """
    stats = {"total": 0, "new": 0, "sent": 0}

    async def on_new_post(post: ParsedPost) -> None:
        stats["total"] += 1
        async with session_factory() as session:
            claimed = await try_mark_news_processed(session, post.channel_id, post.message_id)
        if not claimed:
            return  # уже обработан ранее

        stats["new"] += 1
        rewritten = await rewrite_news(post.text)
        if not rewritten:
            logger.warning("Рерайт не удался для поста %s:%s", post.channel_username, post.message_id)
            async with session_factory() as session:
                await unmark_news_processed(session, post.channel_id, post.message_id)
            return

        ok = await send_news_to_moderation(
            bot,
            channel_id=post.channel_id,
            message_id=post.message_id,
            source_channel=post.channel_username,
            original_text=post.text,
            rewritten_text=rewritten,
        )
        if ok:
            stats["sent"] += 1
        else:
            async with session_factory() as session:
                await unmark_news_processed(session, post.channel_id, post.message_id)

    async def on_session_error(exc: Exception) -> None:
        logger.exception("Ошибка сессии Telethon: %s", exc)
        try:
            await bot.send_message(
                get_settings().admin_id,
                f"⚠️ Ошибка парсинга новостей (Telethon): {exc}",
            )
        except Exception:
            pass

    try:
        await run_parse(on_new_post=on_new_post, on_session_error=on_session_error)
    except Exception as e:
        logger.exception("Ошибка run_news_monitor: %s", e)
        try:
            await bot.send_message(
                get_settings().admin_id,
                f"⚠️ Ошибка мониторинга новостей: {e}",
            )
        except Exception:
            pass

    return stats
