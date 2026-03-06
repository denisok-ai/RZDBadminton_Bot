"""
@file: commands.py
@description: Обработчики команд /start, /location, /rules, /timetable
@dependencies: aiogram, config, ui.design
@created: 2025-02-25
"""

import asyncio
import logging
from calendar import monthrange
from datetime import date
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, or_f
from aiogram.types import CallbackQuery, FSInputFile, Message

from ui.keyboards import main_menu_keyboard, report_month_keyboard, stats_month_keyboard

from app_state import get_session_factory
from config import get_settings
from ui.design import (
    admin_action_error,
    admin_action_start,
    admin_action_success,
    card,
    error_msg,
    help_screen,
    location_card,
    start_screen,
    success_msg,
    timetable_card,
)
from database.repositories import (
    clear_pending_vk_moderation,
    clear_pending_youtube_moderation,
    get_monthly_attendance_records,
)
from handlers.admin_helpers import (
    ADMIN_ACTIONS,
    AdminContext,
    run_admin_news,
    run_admin_poll,
    run_admin_quiz,
    run_admin_quiz_answer,
    run_admin_ratings,
    run_admin_report,
    run_admin_stats,
    run_admin_top3,
    run_admin_video,
)
from handlers.feedback import get_last_training_date, send_feedback_poll_to_chat
from handlers.polls import send_attendance_poll
from handlers.quiz import send_friday_quiz
from handlers.top3 import send_monthly_top3
from services.scheduler import run_news_monitor
from services.excel_reporter import get_report_file as generate_report
from utils.constants import MONTHS_RU

router = Router(name="commands")
logger = logging.getLogger("rzdbadminton")

LOCATION_URL = "https://yandex.ru/maps/org/olimpiyskiy_tsentr_imeni_bratyev_znamenskikh/1084660232/"


def _is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id == get_settings().admin_id


async def _delete_after(msg: Message, seconds: float) -> None:
    """Удалить сообщение бота через заданное время (для служебного обновления клавиатуры)."""
    try:
        await asyncio.sleep(seconds)
        await msg.delete()
    except Exception:
        pass


def _parse_year_month(callback_data: str | None, prefix: str) -> tuple[int, int] | None:
    """
    Разобрать callback_data вида prefix + "YYYY:MM" в (year, month).
    prefix — например "report_sel:" или "stats_sel:" (с двоеточием).
    Returns (year, month) или None при неверном формате.
    """
    if not callback_data or not callback_data.startswith(prefix):
        return None
    part = callback_data.split(":", 1)[-1].strip()
    parts = part.split(":")
    if len(parts) != 2:
        return None
    try:
        y, m = int(parts[0]), int(parts[1])
        if not (1 <= m <= 12):
            return None
        return (y, m)
    except (ValueError, TypeError):
        return None


async def _block_in_group(message: Message) -> bool:
    """
    Если сообщение из группового чата — удалить его, обновить клавиатуру до 3 кнопок и вернуть True.
    В группе кнопки Оценить/Рейтинги/Помощь недоступны; ответа бот не даёт.
    Бот должен иметь право «Удаление сообщений» в группе.
    """
    if message.chat.type == "private":
        return False
    try:
        await message.delete()
    except Exception as e:
        logger.warning(
            "Не удалось удалить сообщение в группе %s: %s. Выдайте боту право «Удаление сообщений».",
            message.chat.id,
            e,
        )
    # Принудительно обновить клавиатуру в группе до 3 кнопок; служебное сообщение удалить через 2 с
    try:
        sent = await message.answer(
            "\u200b",  # нулевая ширина — почти не видно
            reply_markup=main_menu_keyboard(is_admin=False),
        )
        asyncio.create_task(_delete_after(sent, 2.0))
    except Exception as e:
        logger.debug("Не удалось обновить клавиатуру в группе: %s", e)
    return True


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Приветствие + меню кнопок. В группе — только 3 кнопки (Зал, Расписание, Правила); в личке — полное меню для админа."""
    if message.chat.type != "private":
        # В группе — короткое меню (без Оценить, Рейтинги, Помощь и админ-кнопок)
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer(
            "🏸 Бот секции «Бадминтон РЖД». Зал, расписание, правила — кнопки ниже.",
            reply_markup=main_menu_keyboard(is_admin=False),
        )
        return
    is_admin = bool(message.from_user and _is_admin(message.from_user.id))
    await message.answer(
        start_screen(is_admin=is_admin),
        reply_markup=main_menu_keyboard(is_admin=is_admin),
    )


@router.message(or_f(Command("help"), F.text == "❓ Помощь"))
async def cmd_help(message: Message) -> None:
    """Справка — только в личном чате. В группе — удалить сообщение и не отвечать."""
    if await _block_in_group(message):
        return
    is_admin = bool(message.from_user and _is_admin(message.from_user.id))
    await message.answer(help_screen(is_admin=is_admin))


@router.message(or_f(Command("poll"), F.text == "🚀 Опрос"))
async def cmd_poll(message: Message, bot: Bot) -> None:
    """Ручная отправка опроса (только для админа, только в личке)."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if await _block_in_group(message):
        return
    session_factory = get_session_factory()
    if not session_factory:
        await message.answer(error_msg("БД не инициализирована"))
        return
    chat_id = message.chat.id if message.chat.type != "private" else None
    try:
        await send_attendance_poll(bot, session_factory, chat_id=chat_id)
        await message.answer(success_msg("Опрос отправлен"))
    except Exception as e:
        err = str(e).lower()
        if "chat not found" in err or "chat_not_found" in err:
            await message.answer(error_msg(
                "Чат не найден",
                "Проверьте MAIN_CHAT_ID и TEST_CHAT_ID в .env. Или отправьте /poll из группы.",
            ))
        else:
            await message.answer(error_msg(str(e)))


@router.message(or_f(Command("news"), F.text == "📰 Новости"))
async def cmd_news(message: Message, bot: Bot) -> None:
    """Ручной запуск парсинга новостей (только для админа, только в личке)."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if await _block_in_group(message):
        return
    session_factory = get_session_factory()
    if not session_factory:
        await message.answer(error_msg("БД не инициализирована"))
        return
    await message.answer("▸ Сканирую каналы...")
    try:
        stats = await run_news_monitor(bot, session_factory)
        sent = stats.get("sent", 0)
        total = stats.get("total", 0)
        new = stats.get("new", 0)
        if sent > 0:
            await message.answer(
                success_msg("Парсинг завершён", f"Найдено: {total} · Новых: {new} · Отправлено в личку: {sent}")
            )
        elif total == 0:
            await message.answer(
                error_msg(
                    "Парсинг завершён — постов не найдено",
                    "Возможные причины:\n"
                    "• Telethon-сессия не авторизована (запустите бот интерактивно)\n"
                    "• Файл sources.txt пуст\n"
                    "• Ошибка соединения\n\n"
                    "Подробности — в логах бота."
                )
            )
        elif new == 0:
            await message.answer(
                success_msg(
                    "Парсинг завершён",
                    f"Найдено: {total} постов — все уже обработаны ранее\n"
                    "Используйте /clearnews для повторной проверки"
                )
            )
        else:
            await message.answer(
                error_msg(
                    "Парсинг завершён, но не удалось отправить",
                    f"Новых: {new} · Отправлено: {sent}\n"
                    "Проверьте DeepSeek API и логи бота"
                )
            )
    except Exception as e:
        await message.answer(error_msg(str(e)))


@router.message(or_f(Command("quiz"), F.text == "🎯 Квиз"))
async def cmd_quiz(message: Message, bot: Bot) -> None:
    """Ручная отправка квиза (только для админа, только в личке)."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if await _block_in_group(message):
        return
    chat_id = message.chat.id if message.chat and message.chat.type != "private" else None
    if await send_friday_quiz(bot, chat_id):
        await message.answer(success_msg("Квиз отправлен"))
    else:
        await message.answer(error_msg("Не удалось сгенерировать квиз"))


@router.message(or_f(Command("top3"), F.text == "🏆 Топ-3"))
async def cmd_top3(message: Message, bot: Bot) -> None:
    """Ручная отправка Топ-3 за текущий месяц (только для админа, только в личке)."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if await _block_in_group(message):
        return
    chat_id = message.chat.id if message.chat and message.chat.type != "private" else None
    if await send_monthly_top3(bot, chat_id, use_previous_month=False):
        await message.answer(success_msg("Топ-3 отправлен", "Показан текущий месяц"))
    else:
        await message.answer(error_msg("Ошибка отправки Топ-3"))


@router.message(or_f(Command("youtube"), Command("video"), F.text == "🎬 Видео"))
async def cmd_video(message: Message, bot: Bot) -> None:
    """Проверка новых видео (YouTube + VK) — отправка на модерацию; в чат только после «В ленту»."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if await _block_in_group(message):
        return
    action_title = "Видео"

    async def send_start(detail: str = "") -> None:
        await message.answer(admin_action_start(action_title, detail))

    async def send_success(detail: str = "") -> None:
        await message.answer(
            admin_action_success(action_title, detail),
            reply_markup=main_menu_keyboard(is_admin=True),
        )

    async def send_error(problem: str) -> None:
        await message.answer(
            admin_action_error(action_title, problem),
            reply_markup=main_menu_keyboard(is_admin=True),
        )

    ctx = AdminContext(bot, message.chat.id, reply=message.answer, is_private=True)
    await run_admin_video(ctx, send_start, send_success, send_error)


@router.message(Command("clearyoutube"))
async def cmd_clearyoutube(message: Message) -> None:
    """Сбросить список уже опубликованных YouTube-видео (для повторной публикации). Только в личке."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if message.chat.type != "private":
        try:
            await message.delete()
        except Exception:
            pass
        return
    from services.youtube_monitor import clear_youtube_processed
    cleared = clear_youtube_processed()
    await message.answer(
        success_msg(
            "Список опубликованных видео очищен",
            f"Удалено записей: {cleared}\n"
            "Теперь кнопка «🎬 Видео» повторно проверит YouTube и VK.",
        )
    )


@router.message(or_f(Command("clearyoutubequeue"), F.text == "🧹 Очистить предложения"))
async def cmd_clearyoutubequeue(message: Message) -> None:
    """Очистить очередь видео на модерации (YouTube + VK). Только админ, только личка."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if message.chat.type != "private":
        try:
            await message.delete()
        except Exception:
            pass
        return
    session_factory = get_session_factory()
    if not session_factory:
        await message.answer(error_msg("БД не инициализирована"))
        return
    try:
        async with session_factory() as session:
            count_yt = await clear_pending_youtube_moderation(session)
            try:
                count_vk = await clear_pending_vk_moderation(session)
            except Exception:
                count_vk = 0  # таблица vk_video_moderation может отсутствовать в старых БД
        total = count_yt + count_vk
        await message.answer(
            success_msg(
                "Очередь предложений очищена",
                f"Удалено из очереди модерации: YouTube {count_yt}, VK {count_vk} (всего {total}).",
            )
        )
    except Exception as e:
        await message.answer(error_msg(str(e)))


@router.message(or_f(Command("ratings"), F.text == "📈 Рейтинги"))
async def cmd_ratings(message: Message) -> None:
    """Рейтинги тренировок — только в личном чате, только для админа. В группе — удалить сообщение и не отвечать."""
    if await _block_in_group(message):
        return
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    session_factory = get_session_factory()
    if not session_factory:
        await message.answer(error_msg("БД не инициализирована"))
        return
    from database.repositories import get_ratings_by_trainer
    from ui.design import ratings_card
    today = date.today()
    start_date = date(today.year, today.month, 1)
    last_day = monthrange(today.year, today.month)[1]
    end_date = date(today.year, today.month, last_day)
    month_name = MONTHS_RU.get(today.month, str(today.month))
    settings = get_settings()
    async with session_factory() as session:
        data = await get_ratings_by_trainer(session, start_date, end_date)
    text = ratings_card(month_name, today.year, data, settings.trainer_mon, settings.trainer_wed)
    await message.answer(text)


@router.message(or_f(Command("report"), F.text == "📊 Отчёт"))
async def cmd_report(message: Message) -> None:
    """Показать выбор месяца для формирования отчёта (только для админа, только в личке)."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if await _block_in_group(message):
        return
    await message.answer(
        "📊 <b>Выберите месяц для отчёта</b>",
        reply_markup=report_month_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("report_sel:"))
async def cb_report_month(callback: CallbackQuery, bot: Bot) -> None:
    """Сформировать отчёт за выбранный месяц и отправить файл админу."""
    if not (callback.from_user and _is_admin(callback.from_user.id)):
        await callback.answer("Доступно только админу.", show_alert=True)
        return
    if not callback.message:
        await callback.answer()
        return
    parsed = _parse_year_month(callback.data, "report_sel:")
    if not parsed:
        await callback.answer("Неверный формат.", show_alert=True)
        return
    y, m = parsed
    report_date = date(y, m, 1)
    await callback.answer("Формирую отчёт…")
    session_factory = get_session_factory()
    if not session_factory:
        await callback.message.answer(error_msg("БД не инициализирована"))
        return
    async with session_factory() as session:
        records = await get_monthly_attendance_records(session, report_date.year, report_date.month)
    path = await generate_report(report_date, records)
    if path:
        unique_users = len({r[0] for r in records})
        sessions = len({r[3] for r in records})
        month_name = MONTHS_RU.get(report_date.month, str(report_date.month))
        chat_id = callback.message.chat.id if callback.message else get_settings().admin_id
        await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(path),
            caption=success_msg(
                f"Отчёт · {month_name} {report_date.year}",
                f"{unique_users} участников · {sessions} тренировок",
            ),
        )
        if callback.message:
            try:
                await callback.message.edit_text(
                    f"✅ Отчёт за {month_name} {report_date.year} сформирован и отправлен.",
                    reply_markup=None,
                )
            except Exception:
                pass
    else:
        await callback.message.answer(error_msg("Не удалось сформировать отчёт")) if callback.message else None


@router.message(F.text.in_({"⚙️ Админ", "Админ"}))
async def cmd_admin_refresh(message: Message) -> None:
    """Напоминание: управление — кнопки основного меню (без отдельной inline-панели). Только в личке, только для админа."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if message.chat.type != "private":
        try:
            await message.delete()
        except Exception:
            pass
        return
    await message.answer(
        "Используйте кнопки меню ниже: Опрос, Отчёт, Новости, Квиз, Топ-3, Рейтинги, Видео, Статистика, Ответ квиза.",
        reply_markup=main_menu_keyboard(is_admin=True),
    )


def _admin_runner_for_callback(callback: CallbackQuery, bot: Bot):
    """Собрать контекст и обёртки send для inline-панели админа."""
    msg = callback.message
    action_title = ADMIN_ACTIONS.get((callback.data or "").split(":", 1)[-1], "Неизвестное действие")

    async def reply(text: str) -> None:
        await msg.answer(text)

    async def send_start(detail: str = "") -> None:
        await msg.answer(admin_action_start(action_title, detail))

    async def send_success(detail: str = "") -> None:
        await msg.answer(admin_action_success(action_title, detail))

    async def send_error(problem: str) -> None:
        await msg.answer(admin_action_error(action_title, problem))

    chat_id = msg.chat.id
    is_private = getattr(msg.chat, "type", "private") == "private"
    ctx = AdminContext(bot, chat_id, reply=reply, is_private=is_private)
    return ctx, send_start, send_success, send_error


@router.callback_query(F.data.startswith("admin:"))
async def cb_admin_action(callback: CallbackQuery, bot: Bot) -> None:
    """Inline-действия админ-панели — делегирование в хелперы."""
    if not _is_admin(callback.from_user.id if callback.from_user else None):
        await callback.answer("Доступно только админу.", show_alert=True)
        return
    if not callback.message:
        await callback.answer()
        return

    action = (callback.data or "").split(":", 1)[-1]
    ctx, send_start, send_success, send_error = _admin_runner_for_callback(callback, bot)

    runners = {
        "poll": run_admin_poll,
        "report": run_admin_report,
        "news": run_admin_news,
        "quiz": run_admin_quiz,
        "quiz_answer": run_admin_quiz_answer,
        "top3": run_admin_top3,
        "ratings": run_admin_ratings,
        "youtube": run_admin_video,
        "stats": run_admin_stats,
    }
    runner = runners.get(action)
    if runner:
        await runner(ctx, send_start, send_success, send_error)
    else:
        await send_error("Неизвестное действие панели")
    await callback.answer()


@router.message(or_f(Command("feedback"), F.text == "📝 Оценить"))
async def cmd_feedback(message: Message, bot: Bot) -> None:
    """Отправить групповой опрос оценки тренировки — только в личке, только для админа."""
    if await _block_in_group(message):
        return
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    training_date = get_last_training_date()
    if not training_date:
        await message.answer(error_msg("Не удалось определить дату тренировки"))
        return
    settings = get_settings()
    from config import get_publish_chat_id
    chat_id = get_publish_chat_id(settings)
    if await send_feedback_poll_to_chat(bot, training_date, chat_id):
        await message.answer(
            success_msg("Опрос отправлен в чат", f"Тренировка {training_date.strftime('%d.%m')}")
        )
    else:
        await message.answer(error_msg("Не удалось отправить опрос"))


def _group_reply_markup(message: Message):
    """В группе — только короткое меню (3 кнопки), чтобы не показывать Оценить/Рейтинги/Помощь."""
    if message.chat.type != "private":
        return main_menu_keyboard(is_admin=False)
    return None


@router.message(F.text.in_({"📍 Зал", "/location"}))
async def cmd_location(message: Message) -> None:
    """Обработка кнопки «Зал» и команды /location. В группе — ответ с коротким меню."""
    await message.answer(
        location_card(
            "Олимпийский центр имени братьев Знаменских",
            "ул. Стромынка, д.4, стр.1",
            LOCATION_URL,
        ),
        reply_markup=_group_reply_markup(message),
    )


@router.message(F.text.in_({"⏱ Расписание", "/timetable"}))
async def cmd_timetable(message: Message) -> None:
    """Обработка кнопки «Расписание» и команды /timetable. В группе — ответ с коротким меню."""
    await message.answer(
        timetable_card(
            "Понедельник и Среда",
            "20:15 – 22:45",
            "Олимпийский центр, Стромынка д.4",
        ),
        reply_markup=_group_reply_markup(message),
    )


@router.message(F.text.in_({"📋 Правила", "/rules"}))
async def cmd_rules(message: Message) -> None:
    """Обработка кнопки «Правила» и команды /rules. В группе — ответ с коротким меню."""
    settings = get_settings()
    rules_path = Path(settings.rules_file)
    if not rules_path.exists():
        await message.answer(
            error_msg("Правила пока не добавлены"),
            reply_markup=_group_reply_markup(message),
        )
        return
    text = rules_path.read_text(encoding="utf-8")
    if not text.strip():
        await message.answer(
            error_msg("Правила пока не добавлены"),
            reply_markup=_group_reply_markup(message),
        )
        return
    await message.answer(
        card("📋 Регламент секции", text),
        reply_markup=_group_reply_markup(message),
    )


@router.message(Command("chatid"))
async def cmd_chatid(message: Message, bot: Bot) -> None:
    """Показать ID текущего чата (работает в группах, ответ всегда в личку)."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    settings = get_settings()
    chat = message.chat
    text = (
        f"<b>ID чата:</b> <code>{chat.id}</code>\n"
        f"<b>Тип:</b> {chat.type}\n"
        f"<b>Название:</b> {chat.title or chat.username or '—'}\n"
        "\n"
        f"<b>Текущие настройки .env:</b>\n"
        f"• DEBUG_MODE: <code>{settings.debug_mode}</code>\n"
        f"• TEST_CHAT_ID: <code>{settings.test_chat_id}</code>\n"
        f"• MAIN_CHAT_ID: <code>{settings.main_chat_id}</code>\n"
        "\n"
        f"<b>Публикация идёт в:</b> <code>"
        f"{'TEST_CHAT_ID = ' + str(settings.test_chat_id) if settings.debug_mode and settings.test_chat_id else 'MAIN_CHAT_ID = ' + str(settings.main_chat_id)}"
        f"</code>"
    )
    if message.chat.type != "private":
        # В группе: удалить команду, ответить только в личку
        try:
            await message.delete()
        except Exception:
            pass
        await bot.send_message(settings.admin_id, text)
    else:
        await message.answer(text)


@router.message(Command("resetpending"))
async def cmd_reset_pending(message: Message) -> None:
    """Вернуть все 'published' новости в статус 'pending'. Только в личке."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if message.chat.type != "private":
        try:
            await message.delete()
        except Exception:
            pass
        return
    session_factory = get_session_factory()
    if not session_factory:
        await message.answer(error_msg("БД не инициализирована"))
        return
    from sqlalchemy import text as sql_text
    async with session_factory() as session:
        result = await session.execute(
            sql_text("UPDATE news_moderation SET status='pending' WHERE status='published'")
        )
        updated = result.rowcount
        await session.commit()
    await message.answer(
        success_msg(
            "Статус новостей сброшен",
            f"Обновлено записей: {updated}\n"
            "Теперь старые карточки с кнопками снова активны.\n"
            "Найдите любую карточку «📰 На модерации» и нажмите «🚀 В ленту».",
        )
    )


@router.message(Command("clearnews"))
async def cmd_clear_news(message: Message) -> None:
    """Сбросить список обработанных постов. Только в личке."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if message.chat.type != "private":
        try:
            await message.delete()
        except Exception:
            pass
        return
    session_factory = get_session_factory()
    if not session_factory:
        await message.answer(error_msg("БД не инициализирована"))
        return
    from sqlalchemy import text as sql_text
    async with session_factory() as session:
        result = await session.execute(sql_text("DELETE FROM processed_news"))
        deleted = result.rowcount
        await session.commit()
    await message.answer(
        success_msg(
            "Список обработанных постов очищен",
            f"Удалено записей: {deleted}\nТеперь «📰 Новости» заново обработает последние посты из каналов.",
        )
    )


@router.message(F.text == "📋 Ответ квиза")
async def cmd_quiz_answer(message: Message, bot: Bot) -> None:
    """Опубликовать правильный ответ на последний квиз в чат — только для админа, только в личке."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if await _block_in_group(message):
        return
    action_title = "📋 Ответ квиза"

    async def send_start(detail: str = "") -> None:
        await message.answer(admin_action_start(action_title, detail))

    async def send_success(detail: str = "") -> None:
        await message.answer(admin_action_success(action_title, detail))

    async def send_error(problem: str) -> None:
        await message.answer(admin_action_error(action_title, problem))

    ctx = AdminContext(bot, message.chat.id, reply=message.answer, is_private=True)
    await run_admin_quiz_answer(ctx, send_start, send_success, send_error)


@router.message(or_f(Command("stats"), F.text == "📊 Статистика"))
async def cmd_stats(message: Message) -> None:
    """Показать выбор месяца для отчёта «Статистика» — только для админа, только в личке."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if await _block_in_group(message):
        return
    await message.answer(
        "📊 <b>Выберите месяц для статистики</b>",
        reply_markup=stats_month_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("stats_sel:"))
async def cb_stats_month(callback: CallbackQuery, bot: Bot) -> None:
    """Показать статистику активности за выбранный месяц."""
    if not (callback.from_user and _is_admin(callback.from_user.id)):
        await callback.answer("Доступно только админу.", show_alert=True)
        return
    if not callback.message:
        await callback.answer()
        return
    parsed = _parse_year_month(callback.data, "stats_sel:")
    if not parsed:
        await callback.answer("Неверный формат.", show_alert=True)
        return
    y, m = parsed
    await callback.answer("Загружаю статистику…")
    session_factory = get_session_factory()
    if not session_factory:
        await bot.send_message(
            callback.message.chat.id,
            error_msg("БД не инициализирована"),
        )
        return
    from ui.design import activity_stats_card
    from database.repositories import get_activity_stats
    from services.llm import _get_monthly_usage
    month_name = MONTHS_RU.get(m, str(m))
    async with session_factory() as session:
        stats = await get_activity_stats(session, y, m)
    limit = get_settings().deepseek_monthly_token_limit or 0
    llm_tokens = _get_monthly_usage() if limit else None
    text = activity_stats_card(
        month_name, y, stats,
        llm_tokens=llm_tokens,
        llm_limit=limit,
    )
    await bot.send_message(callback.message.chat.id, text)
    try:
        await callback.message.edit_text(
            f"✅ Статистика за {month_name} {y} показана выше.",
            reply_markup=None,
        )
    except Exception:
        pass


@router.message(Command("resetreport"))
async def cmd_reset_report(message: Message) -> None:
    """Информация о новом формате отчётов. Только в личке."""
    if not (message.from_user and _is_admin(message.from_user.id)):
        return
    if message.chat.type != "private":
        try:
            await message.delete()
        except Exception:
            pass
        return
    await message.answer(
        success_msg(
            "Отчёт теперь без шаблона",
            "Каждый отчёт генерируется заново из данных БД.\n"
            "Файл: <code>data/reports/attendance_ГГГГ_ММ.xlsx</code>",
        )
    )
