"""
@file: scheduler.py
@description: APScheduler — опросы, отчёты, новости, квиз, обратная связь, Топ-3
@dependencies: apscheduler, aiogram, config
@created: 2025-02-25
"""

import json
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from config import get_settings, get_poll_chat_id, get_publish_chat_id
from database.repositories import (
    create_vk_moderation,
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
from handlers.vk_moderation import send_vk_to_moderation
from handlers.youtube_moderation import send_youtube_to_moderation
from services.db_backup import run_backup
from services.excel_reporter import get_report_file as generate_report
from services.llm import rewrite_news
from services.news_parser import ParsedPost, run_parse
from services.vk_video_monitor import fetch_vk_videos
from services.youtube_monitor import (
    DEFAULT_BWF_CHANNEL_ID,
    get_unseen_highlights,
    mark_youtube_sent_to_moderation,
)
from utils.constants import MONTHS_RU

logger = logging.getLogger("rzdbadminton")


async def _notify_admin(bot, text: str) -> None:
    """Отправить админу короткое уведомление о фоновой задаче (игнорируем ошибки отправки)."""
    try:
        await bot.send_message(get_settings().admin_id, text)
    except Exception as e:
        logger.warning("Не удалось отправить уведомление админу: %s", e)


def setup_scheduler(bot, session_factory) -> AsyncIOScheduler:
    """Настроить планировщик: опросы Пн/Ср 08:00, отчёты 23:00 (все времена в Europe/Moscow)."""
    tz_name = get_settings().timezone
    tz = ZoneInfo(tz_name)  # объект таймзоны — надёжнее строки для APScheduler
    scheduler = AsyncIOScheduler(timezone=tz)

    # #region agent log
    try:
        now = datetime.now(tz)
        with open("logs/debug-1df0fa.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({"sessionId": "1df0fa", "hypothesisId": "H2", "location": "scheduler.py:setup_scheduler", "message": "scheduler_start", "data": {"timezone": tz_name, "now_iso": now.isoformat(), "weekday": now.weekday(), "hour": now.hour, "minute": now.minute}, "timestamp": int(now.timestamp() * 1000)}, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion

    async def job_send_poll():
        # #region agent log
        try:
            now = datetime.now(tz)
            with open("logs/debug-1df0fa.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId": "1df0fa", "hypothesisId": "H2,H3,H4", "location": "scheduler.py:job_send_poll", "message": "job_send_poll_fired", "data": {"now_iso": now.isoformat(), "weekday": now.weekday(), "hour": now.hour, "minute": now.minute}, "timestamp": int(now.timestamp() * 1000)}, ensure_ascii=False) + "\n")
        except Exception:
            pass
        # #endregion
        try:
            logger.info("scheduler_job: attendance_poll запущен")
            await send_attendance_poll(bot, session_factory)
            logger.info("Опрос посещаемости отправлен")
            await _notify_admin(bot, "📋 Опрос посещаемости: отправлен в чат")
        except Exception as e:
            logger.exception("Ошибка отправки опроса: %s", e)
            await _notify_admin(bot, f"⚠️ Опрос посещаемости: ошибка — {e}")

    async def job_generate_report():
        try:
            logger.info("scheduler_job: daily_report запущен")
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
                await _notify_admin(bot, "📋 Ежедневный отчёт: сформирован и отправлен")
            else:
                await _notify_admin(
                    bot,
                    f"⚠️ Ежедневный отчёт: не удалось сформировать за {report_date.month}/{report_date.year}",
                )
        except Exception as e:
            logger.exception("Ошибка формирования отчёта: %s", e)
            await _notify_admin(bot, f"⚠️ Ежедневный отчёт: ошибка — {e}")

    scheduler.add_job(
        job_send_poll,
        CronTrigger(day_of_week="mon,wed", hour=8, minute=0, timezone=tz),
        id="attendance_poll",
    )

    async def job_unpin_attendance_poll():
        """Пн/Ср 20:15 — открепить опрос посещаемости перед тренировкой."""
        try:
            logger.info("scheduler_job: unpin_attendance_poll запущен")
            chat_id = get_poll_chat_id(get_settings())
            await bot.unpin_chat_message(chat_id)
            logger.info("Опрос посещаемости откреплён в чате %s", chat_id)
            await _notify_admin(bot, "📋 Опрос посещаемости: откреплён (до тренировки)")
        except Exception as e:
            logger.warning("Не удалось открепить опрос: %s", e)
            await _notify_admin(bot, f"⚠️ Открепление опроса: ошибка — {e}")

    scheduler.add_job(
        job_unpin_attendance_poll,
        CronTrigger(day_of_week="mon,wed", hour=20, minute=15, timezone=tz),
        id="unpin_attendance_poll",
    )

    # Одноразовая диагностика: срабатывает ли планировщик через 3 мин после старта
    async def _diagnostic_job():
        try:
            now = datetime.now(tz)
            with open("logs/debug-1df0fa.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId": "1df0fa", "hypothesisId": "H3", "location": "scheduler.py:_diagnostic_job", "message": "diagnostic_job_fired", "data": {"now_iso": now.isoformat()}, "timestamp": int(now.timestamp() * 1000)}, ensure_ascii=False) + "\n")
        except Exception:
            pass

    run_at = datetime.now(tz) + timedelta(minutes=3)
    scheduler.add_job(_diagnostic_job, DateTrigger(run_date=run_at), id="diagnostic_once")
    scheduler.add_job(
        job_generate_report,
        CronTrigger(day_of_week="mon,wed", hour=23, minute=0, timezone=tz),
        id="daily_report",
    )

    async def job_news_monitor():
        """Парсинг каналов, рерайт, отправка на модерацию (10:15, 12:15, …, 22:15 МСК)."""
        try:
            logger.info("scheduler_job: news_monitor запущен")
            await run_news_monitor(bot, session_factory)
        except Exception as e:
            logger.exception("Ошибка job_news_monitor: %s", e)

    scheduler.add_job(
        job_news_monitor,
        CronTrigger(hour="10,12,14,16,18,20,22", minute=15, timezone=tz),
        id="news_monitor",
    )

    async def job_friday_quiz():
        try:
            logger.info("scheduler_job: friday_quiz запущен")
            ok = await send_friday_quiz(bot)
            logger.info("Квиз пятницы отправлен")
            await _notify_admin(
                bot,
                "📋 Квиз пятницы: отправлен в чат" if ok else "📋 Квиз пятницы: не удалось отправить",
            )
        except Exception as e:
            logger.exception("Ошибка отправки квиза: %s", e)
            await _notify_admin(bot, f"⚠️ Квиз пятницы: ошибка — {e}")

    scheduler.add_job(
        job_friday_quiz,
        CronTrigger(day_of_week="fri", hour=12, minute=0, timezone=tz),
        id="friday_quiz",
    )

    async def job_quiz_answer():
        """Пятница 21:00 — открепить квиз и опубликовать правильный ответ в общий чат."""
        try:
            logger.info("scheduler_job: quiz_answer запущен")
            poll_chat_id = get_poll_chat_id(get_settings())
            try:
                await bot.unpin_chat_message(poll_chat_id)
                logger.info("Квиз пятницы откреплён в чате %s", poll_chat_id)
            except Exception as e:
                logger.warning("Не удалось открепить квиз: %s", e)
            chat_id = get_publish_chat_id(get_settings())
            ok = await send_quiz_answer_publication(bot, chat_id)
            if ok:
                logger.info("Правильный ответ на квиз опубликован")
            await _notify_admin(
                bot,
                "📋 Ответ на квиз: опубликован в чат" if ok else "📋 Ответ на квиз: не опубликован",
            )
        except Exception as e:
            logger.exception("Ошибка публикации ответа квиза: %s", e)
            await _notify_admin(bot, f"⚠️ Ответ на квиз: ошибка — {e}")

    scheduler.add_job(
        job_quiz_answer,
        CronTrigger(day_of_week="fri", hour=21, minute=0, timezone=tz),
        id="quiz_answer_publication",
    )

    async def job_feedback():
        """Пн 22:45 — опрос за понедельник, Ср 22:45 — за среду (в общий чат)."""
        try:
            logger.info("scheduler_job: feedback запущен")
            today = date.today()
            if today.weekday() not in (0, 2):  # только Пн или Ср
                await _notify_admin(bot, "📋 Обратная связь: не сегодня (не Пн/Ср)")
                return
            training_date = today  # опрос в день тренировки вечером
            sent = await send_feedback_requests(bot, training_date)
            logger.info("Обратная связь (опрос в чат) отправлена за %s: %s", training_date, sent)
            await _notify_admin(bot, f"📋 Обратная связь: отправлено запросов — {sent}")
        except Exception as e:
            logger.exception("Ошибка отправки обратной связи: %s", e)
            await _notify_admin(bot, f"⚠️ Обратная связь: ошибка — {e}")

    scheduler.add_job(
        job_feedback,
        CronTrigger(day_of_week="mon,wed", hour=22, minute=45, timezone=tz),
        id="feedback",
    )

    async def job_weekly_feedback_summary():
        """Пт 11:45 — итоги обратной связи за неделю в общий чат."""
        try:
            logger.info("scheduler_job: feedback_weekly_summary запущен")
            chat_id = get_publish_chat_id(get_settings())
            ok = await send_weekly_feedback_summary(bot, chat_id)
            if ok:
                logger.info("Итоги обратной связи за неделю отправлены")
            await _notify_admin(
                bot,
                "📋 Итоги ОС за неделю: отправлены" if ok else "📋 Итоги ОС за неделю: не отправлены",
            )
        except Exception as e:
            logger.exception("Ошибка отправки итогов обратной связи за неделю: %s", e)
            await _notify_admin(bot, f"⚠️ Итоги ОС за неделю: ошибка — {e}")

    scheduler.add_job(
        job_weekly_feedback_summary,
        CronTrigger(day_of_week="fri", hour=11, minute=45, timezone=tz),
        id="feedback_weekly_summary",
    )

    async def job_monthly_feedback_summary():
        """1-го числа в 10:00 — итоги обратной связи за прошлый месяц в общий чат."""
        try:
            logger.info("scheduler_job: feedback_monthly_summary запущен")
            chat_id = get_publish_chat_id(get_settings())
            ok = await send_monthly_feedback_summary(bot, chat_id)
            if ok:
                logger.info("Итоги обратной связи за месяц отправлены")
            await _notify_admin(
                bot,
                "📋 Итоги ОС за месяц: отправлены" if ok else "📋 Итоги ОС за месяц: не отправлены",
            )
        except Exception as e:
            logger.exception("Ошибка отправки итогов обратной связи за месяц: %s", e)
            await _notify_admin(bot, f"⚠️ Итоги ОС за месяц: ошибка — {e}")

    scheduler.add_job(
        job_monthly_feedback_summary,
        CronTrigger(day=1, hour=10, minute=0, timezone=tz),
        id="feedback_monthly_summary",
    )

    async def job_db_backup():
        """Ежедневный бекап БД; хранятся последние 10 дней."""
        try:
            logger.info("scheduler_job: db_backup запущен")
            ok, msg = run_backup()
            if ok:
                logger.info("Бекап БД: %s", msg)
                await _notify_admin(bot, f"📋 Бекап БД: OK ({msg})")
            else:
                logger.warning("Бекап БД: %s", msg)
                await _notify_admin(bot, f"📋 Бекап БД: {msg}")
        except Exception as e:
            logger.exception("Ошибка бекапа БД: %s", e)
            await _notify_admin(bot, f"⚠️ Бекап БД: ошибка — {e}")

    scheduler.add_job(
        job_db_backup,
        CronTrigger(hour=4, minute=0, timezone=tz),
        id="db_backup",
    )

    async def job_top3():
        try:
            logger.info("scheduler_job: monthly_top3 запущен")
            ok = await send_monthly_top3(bot)
            logger.info("Топ-3 отправлен")
            await _notify_admin(
                bot,
                "📋 Топ-3 за месяц: отправлен в чат" if ok else "📋 Топ-3 за месяц: не отправлен",
            )
        except Exception as e:
            logger.exception("Ошибка отправки Топ-3: %s", e)
            await _notify_admin(bot, f"⚠️ Топ-3: ошибка — {e}")

    scheduler.add_job(
        job_top3,
        CronTrigger(day=1, hour=9, minute=0, timezone=tz),
        id="monthly_top3",
    )

    async def job_youtube_highlights():
        """Новые видео с BWF TV — на модерацию админу (публикация в чат только после одобрения)."""
        try:
            logger.info("scheduler_job: youtube_highlights запущен")
            videos = await get_unseen_highlights()
            if not videos:
                await _notify_admin(bot, "📋 YouTube: новых видео нет")
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
            await _notify_admin(bot, f"📋 YouTube: на модерацию отправлено — {sent}")
        except Exception as e:
            logger.exception("Ошибка job_youtube_highlights: %s", e)
            await _notify_admin(bot, f"⚠️ YouTube: ошибка — {e}")

    scheduler.add_job(
        job_youtube_highlights,
        CronTrigger(hour="10,14,18,22", minute=30, timezone=tz),
        id="youtube_highlights",
    )

    async def job_vk_highlights():
        """Новые видео из каналов VK Видео (Doc/vk_sources.txt) — на модерацию админу."""
        try:
            logger.info("scheduler_job: vk_highlights запущен")
            if not (get_settings().vk_access_token or "").strip():
                return  # без токена тихо пропускаем (не спамим админа)
            videos = await fetch_vk_videos()
            if not videos:
                await _notify_admin(bot, "📋 VK: новых видео нет")
                return
            sent = 0
            for v in videos:
                async with session_factory() as session:
                    vm = await create_vk_moderation(
                        session, v.video_id, v.title, v.link, v.channel_id
                    )
                if vm is None:
                    continue
                if await send_vk_to_moderation(bot, vm.id, vm.title, vm.link):
                    sent += 1
            await _notify_admin(bot, f"📋 VK: на модерацию отправлено — {sent}")
        except Exception as e:
            logger.exception("Ошибка job_vk_highlights: %s", e)
            await _notify_admin(bot, f"⚠️ VK: ошибка — {e}")

    scheduler.add_job(
        job_vk_highlights,
        CronTrigger(hour="10,14,18,22", minute=30, timezone=tz),
        id="vk_highlights",
    )

    # Аудит: время следующего запуска каждой задачи (если уже вычислено — до start() может быть None)
    for job in scheduler.get_jobs():
        next_run = getattr(job, "next_run_time", None)
        logger.info("scheduler: job %s next_run=%s", job.id, next_run)

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

    # Всегда отправляем админу краткую сводку — чтобы видеть, что задача сработала (даже при 0 новых постов)
    try:
        summary = (
            f"📋 Мониторинг новостей: проверено {stats['total']}, новых {stats['new']}, "
            f"на модерацию {stats['sent']}."
        )
        await bot.send_message(get_settings().admin_id, summary)
        logger.info("run_news_monitor: %s", summary)
    except Exception as e:
        logger.warning("Не удалось отправить сводку новостей админу: %s", e)

    return stats
