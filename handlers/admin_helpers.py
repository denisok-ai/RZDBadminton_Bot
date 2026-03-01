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
from database.repositories import get_ratings_by_trainer
from handlers.polls import send_attendance_poll
from handlers.quiz import send_friday_quiz, send_quiz_answer_publication
from handlers.top3 import send_monthly_top3
from services.scheduler import run_news_monitor
from ui.keyboards import report_month_keyboard, stats_month_keyboard
from utils.constants import MONTHS_RU
from services.youtube_monitor import check_highlights_status


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
    """Показать выбор месяца для формирования отчёта; файл отправится после выбора (callback report_sel)."""
    session_factory = get_session_factory()
    if not session_factory:
        await send_error("БД не инициализирована")
        return
    await ctx.bot.send_message(
        ctx.chat_id,
        "📊 <b>Выберите месяц для отчёта</b>",
        reply_markup=report_month_keyboard(),
        parse_mode="HTML",
    )


async def run_admin_quiz_answer(
    ctx: AdminContext,
    send_start: Callable[[str], Awaitable[None]],
    send_success: Callable[[str], Awaitable[None]],
    send_error: Callable[[str], Awaitable[None]],
) -> None:
    """Опубликовать правильный ответ на последний квиз в чат (тот же, куда уходит квиз в 12:00)."""
    await send_start("Публикую ответ на квиз в чат…")
    chat_id = get_publish_chat_id(get_settings())
    try:
        ok = await send_quiz_answer_publication(ctx.bot, chat_id)
        if ok:
            await send_success("Ответ на квиз опубликован в чат")
        else:
            await send_error("Нет данных: за последние 12 ч квиз в этот чат не отправлялся или запись без ответа")
    except Exception as e:
        await send_error(str(e))


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
    """Проверить новые видео BWF TV и отправить на модерацию (в личку); публикация в чат — по кнопке «В ленту»."""
    from services.youtube_monitor import DEFAULT_BWF_CHANNEL_ID, mark_youtube_sent_to_moderation

    from database.repositories import create_youtube_moderation
    from handlers.youtube_moderation import send_youtube_to_moderation

    settings = get_settings()
    ch_id = settings.youtube_channel_id or DEFAULT_BWF_CHANNEL_ID
    await send_start("Проверяю канал BWF TV…")
    try:
        result = await check_highlights_status()
        all_count = len(result["all"])
        new_videos = result["new"]
        seen_count = len(result["seen"])
        rss_error = result.get("error")

        if rss_error:
            await send_error(
                f"Ошибка RSS: {rss_error}\n"
                f"Канал: {ch_id}\n"
                "Проверьте YOUTUBE_CHANNEL_ID в .env"
            )
            return

        if not new_videos:
            hint = " · /clearyoutube для повторной проверки" if seen_count > 0 else " · RSS пуст"
            await send_success(f"Новых видео нет · в RSS: {all_count}{hint}")
            return

        session_factory = get_session_factory()
        if not session_factory:
            await send_error("Ошибка БД")
            return
        sent = 0
        for v in new_videos:
            async with session_factory() as session:
                ym = await create_youtube_moderation(
                    session, v.video_id, v.title, v.link, ch_id
                )
            if ym is None:
                continue
            ok = await send_youtube_to_moderation(ctx.bot, ym.id, ym.title, ym.link)
            if ok:
                mark_youtube_sent_to_moderation(v.video_id)
                sent += 1
        await send_success(
            f"На модерацию отправлено {sent} из {len(new_videos)} новых · одобренные публикуйте кнопкой «В ленту»"
        )
    except Exception as e:
        await send_error(str(e))


async def run_admin_stats(
    ctx: AdminContext,
    send_start: Callable[[str], Awaitable[None]],
    send_success: Callable[[str], Awaitable[None]],
    send_error: Callable[[str], Awaitable[None]],
) -> None:
    """Показать выбор месяца для отчёта «Статистика»; результат — по callback stats_sel."""
    session_factory = get_session_factory()
    if not session_factory:
        await send_error("БД не инициализирована")
        return
    await ctx.bot.send_message(
        ctx.chat_id,
        "📊 <b>Выберите месяц для статистики</b>",
        reply_markup=stats_month_keyboard(),
        parse_mode="HTML",
    )


ADMIN_ACTIONS: dict[str, str] = {
    "poll": "🚀 Опрос",
    "report": "📊 Отчёт",
    "news": "📰 Новости",
    "quiz": "🎯 Квиз",
    "quiz_answer": "📋 Ответ квиза",
    "top3": "🏆 Топ-3",
    "ratings": "📈 Рейтинги",
    "youtube": "🎬 YouTube",
    "stats": "📊 Статистика",
}
