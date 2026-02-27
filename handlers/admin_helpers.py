"""
@file: admin_helpers.py
@description: Хелперы выполнения админ-действий (опрос, отчёт, новости, квиз, топ-3, рейтинги, YouTube)
@dependencies: aiogram, config, database, services, handlers
@created: 2026-02-26
"""

from calendar import monthrange
from collections.abc import Awaitable, Callable
from datetime import date

from aiogram import Bot

from app_state import get_session_factory
from config import get_settings, get_publish_chat_id
from database.repositories import get_monthly_attendance_records, get_ratings_by_trainer
from handlers.polls import send_attendance_poll
from handlers.quiz import send_friday_quiz
from handlers.top3 import send_monthly_top3
from services.scheduler import run_news_monitor
from services.excel_reporter import MONTHS_RU, get_report_file as generate_report
from services.youtube_monitor import check_highlights_status
from ui.design import card


class AdminContext:
    """Контекст выполнения админ-действия: бот, отправка ответов, чат."""

    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        *,
        reply: Callable[[str], Awaitable[None]],
        is_private: bool = True,
    ):
        self.bot = bot
        self.chat_id = chat_id
        self.reply = reply
        self._is_private = is_private

    @property
    def target_chat_id(self) -> int | None:
        """Чат для опроса/квиза/топ-3: None если личка — тогда берём из config."""
        if self._is_private:
            return None
        return self.chat_id


async def run_admin_poll(
    ctx: AdminContext,
    send_start: Callable[[str], Awaitable[None]],
    send_success: Callable[[str], Awaitable[None]],
    send_error: Callable[[str], Awaitable[None]],
) -> None:
    """Отправить опрос посещаемости."""
    session_factory = get_session_factory()
    if not session_factory:
        await send_error("БД не инициализирована")
        return
    await send_start("Отправляю опрос посещаемости")
    try:
        await send_attendance_poll(ctx.bot, session_factory, chat_id=ctx.target_chat_id)
        await send_success("Опрос отправлен")
    except Exception as e:
        await send_error(str(e))


async def run_admin_report(
    ctx: AdminContext,
    send_start: Callable[[str], Awaitable[None]],
    send_success: Callable[[str], Awaitable[None]],
    send_error: Callable[[str], Awaitable[None]],
) -> None:
    """Сформировать месячный отчёт посещаемости и отправить файл."""
    session_factory = get_session_factory()
    if not session_factory:
        await send_error("БД не инициализирована")
        return
    report_date = date.today()
    await send_start(f"Формирую отчёт за {MONTHS_RU.get(report_date.month, '')} {report_date.year}")
    async with session_factory() as session:
        records = await get_monthly_attendance_records(session, report_date.year, report_date.month)
    path = await generate_report(report_date, records)
    if not path:
        await send_error("Не удалось сформировать отчёт")
        return
    unique_users = len({r[0] for r in records})
    sessions = len({r[3] for r in records})
    from aiogram.types import FSInputFile
    from ui.design import success_msg
    await ctx.bot.send_document(
        ctx.chat_id,
        document=FSInputFile(path),
        caption=success_msg(
            f"Отчёт · {MONTHS_RU.get(report_date.month, '')} {report_date.year}",
            f"{unique_users} участников · {sessions} тренировок",
        ),
    )
    await send_success(f"Отчёт готов · {unique_users} участников · {sessions} тренировок")


async def run_admin_news(
    ctx: AdminContext,
    send_start: Callable[[str], Awaitable[None]],
    send_success: Callable[[str], Awaitable[None]],
    send_error: Callable[[str], Awaitable[None]],
) -> None:
    """Запустить парсинг новостей и отправку на модерацию."""
    session_factory = get_session_factory()
    if not session_factory:
        await send_error("БД не инициализирована")
        return
    await send_start("Сканирую каналы и готовлю новости")
    try:
        await run_news_monitor(ctx.bot, session_factory)
        await send_success("Парсинг завершён, новые посты отправлены на модерацию")
    except Exception as e:
        await send_error(str(e))


async def run_admin_quiz(
    ctx: AdminContext,
    send_start: Callable[[str], Awaitable[None]],
    send_success: Callable[[str], Awaitable[None]],
    send_error: Callable[[str], Awaitable[None]],
) -> None:
    """Отправить квиз."""
    await send_start("Генерирую квиз через LLM")
    if await send_friday_quiz(ctx.bot, ctx.target_chat_id):
        await send_success("Квиз отправлен")
    else:
        await send_error("Не удалось сгенерировать квиз")


async def run_admin_top3(
    ctx: AdminContext,
    send_start: Callable[[str], Awaitable[None]],
    send_success: Callable[[str], Awaitable[None]],
    send_error: Callable[[str], Awaitable[None]],
) -> None:
    """Отправить Топ-3 за текущий месяц (кнопка) — прошлый месяц только в планировщике."""
    await send_start("Считаю лидеров посещаемости")
    if await send_monthly_top3(ctx.bot, ctx.target_chat_id, use_previous_month=False):
        await send_success("Топ-3 отправлен · текущий месяц")
    else:
        await send_error("Ошибка отправки Топ-3")


async def run_admin_ratings(
    ctx: AdminContext,
    send_start: Callable[[str], Awaitable[None]],
    send_success: Callable[[str], Awaitable[None]],
    send_error: Callable[[str], Awaitable[None]],
) -> None:
    """Показать рейтинги за текущий месяц."""
    session_factory = get_session_factory()
    if not session_factory:
        await send_error("БД не инициализирована")
        return
    await send_start("Считаю рейтинги за текущий месяц")
    from ui.design import ratings_card
    today = date.today()
    start_date = date(today.year, today.month, 1)
    last_day = monthrange(today.year, today.month)[1]
    end_date = date(today.year, today.month, last_day)
    MONTHS_RU = {
        1: "январь", 2: "февраль", 3: "март", 4: "апрель", 5: "май", 6: "июнь",
        7: "июль", 8: "август", 9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь",
    }
    month_name = MONTHS_RU.get(today.month, str(today.month))
    settings = get_settings()
    async with session_factory() as session:
        data = await get_ratings_by_trainer(session, start_date, end_date)
    _, overall_count = data.get("overall", (0.0, 0))
    if overall_count == 0:
        await send_success(f"Рейтинги за {month_name} {today.year}: нет оценок")
    else:
        text = ratings_card(month_name, today.year, data, settings.trainer_mon, settings.trainer_wed)
        await ctx.reply(text)
        await send_success("Отчёт по рейтингам готов")


async def run_admin_youtube(
    ctx: AdminContext,
    send_start: Callable[[str], Awaitable[None]],
    send_success: Callable[[str], Awaitable[None]],
    send_error: Callable[[str], Awaitable[None]],
) -> None:
    """Проверить новые Highlights и отправить в чат."""
    await send_start("Проверяю новые Highlights BWF TV")
    try:
        result = await check_highlights_status()
        all_count = len(result["all"])
        new_videos = result["new"]
        seen_count = len(result["seen"])

        if not new_videos:
            hint = " · /clearyoutube для повторной отправки" if seen_count > 0 else " · RSS пуст или нет Highlights"
            await send_success(f"Новых видео нет · в RSS: {all_count}{hint}")
            return

        chat_id = ctx.target_chat_id or get_publish_chat_id(get_settings())
        for v in new_videos:
            text = card("🏸 Highlights", v.title, footer=f"<a href='{v.link}'>Смотреть →</a>")
            await ctx.bot.send_message(chat_id, text)
        await send_success(f"Опубликовано {len(new_videos)} из {all_count} видео в RSS")
    except Exception as e:
        await send_error(str(e))


ADMIN_ACTIONS: dict[str, str] = {
    "poll": "🚀 Опрос",
    "report": "📊 Отчёт",
    "news": "📰 Новости",
    "quiz": "🎯 Квиз",
    "top3": "🏆 Топ-3",
    "ratings": "📈 Рейтинги",
    "youtube": "🎬 YouTube",
}
