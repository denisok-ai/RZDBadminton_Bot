"""
@file: news.py
@description: Модерация новостей — отправка админу, кнопки [Опубликовать], [Отклонить], [Редактировать]
@dependencies: aiogram, config, database.repositories, services.llm
@created: 2025-02-25
"""

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app_state import get_session_factory
from config import get_settings, get_publish_chat_id
from ui.design import SEP, card
from ui.keyboards import news_moderation_keyboard, variant_buttons_keyboard
from database.repositories import (
    create_news_moderation,
    get_news_moderation,
    update_news_moderation_variants,
)
from services.llm import generate_news_variants, rewrite_news

logger = logging.getLogger("rzdbadminton")

router = Router(name="news")

# Префиксы callback_data: news_mod:{action}:{moderation_id} или news_var:{moderation_id}:{index}
CALLBACK_PUBLISH = "news_mod:publish:"
CALLBACK_REJECT = "news_mod:reject:"
CALLBACK_EDIT = "news_mod:edit:"
CALLBACK_VARIANT = "news_var:"
CALLBACK_PUBLISH_CONFIRM = "news_mod:publish_confirm:"
CALLBACK_REJECT_CONFIRM = "news_mod:reject_confirm:"
CALLBACK_BACK = "news_mod:back:"
CALLBACK_REJECT_REASON = "news_mod:reject_reason:"
CALLBACK_VARIANTS_BACK = "news_mod:variants_back:"

REJECT_REASONS: dict[str, str] = {
    "offtopic": "Не по тематике канала",
    "quality": "Недостаточно ценности для аудитории",
    "duplicate": "Похоже на дубликат",
    "other": "Другая причина",
}


def _news_keyboard(moderation_id: int) -> InlineKeyboardMarkup:
    """Клавиатура модерации — цветные кнопки SportTech."""
    return news_moderation_keyboard(
        moderation_id,
        CALLBACK_PUBLISH,
        CALLBACK_REJECT,
        CALLBACK_EDIT,
    )


def _variant_keyboard(moderation_id: int, count: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора варианта."""
    return variant_buttons_keyboard(
        moderation_id,
        count,
        CALLBACK_VARIANT,
        back_callback_data=f"{CALLBACK_VARIANTS_BACK}{moderation_id}",
    )


def _confirm_keyboard(moderation_id: int, action: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения критичного действия."""
    if action == "publish":
        confirm_cb = f"{CALLBACK_PUBLISH_CONFIRM}{moderation_id}"
        confirm_text = "✅ Подтвердить публикацию"
        confirm_style = "success"
    else:
        confirm_cb = f"{CALLBACK_REJECT_CONFIRM}{moderation_id}"
        confirm_text = "⛔ Подтвердить отклонение"
        confirm_style = "danger"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=confirm_text,
                    callback_data=confirm_cb,
                    style=confirm_style,
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data=f"{CALLBACK_BACK}{moderation_id}",
                    style="primary",
                )
            ],
        ]
    )


def _reject_reason_keyboard(moderation_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора причины отклонения."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▫️ Не по теме",
                    callback_data=f"{CALLBACK_REJECT_REASON}{moderation_id}:offtopic",
                    style="danger",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="▫️ Низкая ценность",
                    callback_data=f"{CALLBACK_REJECT_REASON}{moderation_id}:quality",
                    style="danger",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="▫️ Дубликат",
                    callback_data=f"{CALLBACK_REJECT_REASON}{moderation_id}:duplicate",
                    style="danger",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="▫️ Другое",
                    callback_data=f"{CALLBACK_REJECT_REASON}{moderation_id}:other",
                    style="danger",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data=f"{CALLBACK_BACK}{moderation_id}",
                    style="primary",
                ),
            ],
        ]
    )


def _format_for_publish(text: str, source_channel: str) -> str:
    """Форматировать текст новости для публикации в чат: добавить источник."""
    link = f"https://t.me/{source_channel}"
    return f"📰 {text}\n\n🔗 <a href='{link}'>Источник: @{source_channel}</a>"


async def _set_status_on_message(callback: CallbackQuery, status_line: str) -> None:
    """Добавить строку статуса к карточке модерации (если возможно)."""
    if not callback.message or not isinstance(callback.message, Message):
        return
    text = callback.message.html_text or callback.message.text or ""
    if not text:
        return
    if "Статус:" in text:
        text = text.split("\n\nСтатус:", 1)[0]
    await callback.message.edit_text(f"{text}\n\nСтатус: {status_line}", reply_markup=None)


async def send_news_to_moderation(
    bot: Bot,
    channel_id: int,
    message_id: int,
    source_channel: str,
    original_text: str,
    rewritten_text: str,
) -> bool:
    """
    Отправить новость админу на модерацию.

    Returns:
        True если отправлено успешно.
    """
    session_factory = get_session_factory()
    if not session_factory:
        logger.error("session_factory не инициализирована")
        return False

    try:
        async with session_factory() as session:
            nm = await create_news_moderation(
                session=session,
                channel_id=channel_id,
                message_id=message_id,
                source_channel=source_channel,
                original_text=original_text,
                rewritten_text=rewritten_text,
            )
            moderation_id = nm.id

        settings = get_settings()
        text = card(
            "📰 На модерации",
            f"Источник: <code>{source_channel}</code>",
            rewritten_text,
        )
        # F-012: модерация всегда идёт в личку ADMIN_ID
        await bot.send_message(
            settings.admin_id,
            text,
            reply_markup=_news_keyboard(moderation_id),
        )
        return True
    except TelegramForbiddenError:
        logger.error(
            "Админ (id=%s) не начал диалог с ботом. "
            "Отправьте /start боту в личку — тогда новости будут приходить.",
            get_settings().admin_id,
        )
        return False
    except Exception as e:
        logger.exception("Ошибка отправки новости на модерацию: %s", e)
        return False


@router.callback_query(F.data.startswith(CALLBACK_PUBLISH))
async def cb_publish(callback: CallbackQuery) -> None:
    """Запросить подтверждение публикации новости."""
    if callback.from_user and callback.from_user.id != get_settings().admin_id:
        await callback.answer("Доступно только админу.", show_alert=True)
        return

    moderation_id = int(callback.data.replace(CALLBACK_PUBLISH, ""))
    await callback.message.edit_reply_markup(
        reply_markup=_confirm_keyboard(moderation_id, "publish")
    )
    await callback.answer("Подтвердите публикацию")


@router.callback_query(F.data.startswith(CALLBACK_REJECT))
async def cb_reject(callback: CallbackQuery) -> None:
    """Запросить подтверждение отклонения новости."""
    if callback.from_user and callback.from_user.id != get_settings().admin_id:
        await callback.answer("Доступно только админу.", show_alert=True)
        return

    moderation_id = int(callback.data.replace(CALLBACK_REJECT, ""))
    await callback.message.edit_reply_markup(
        reply_markup=_confirm_keyboard(moderation_id, "reject")
    )
    await callback.answer("Подтвердите отклонение")


@router.callback_query(F.data.startswith(CALLBACK_BACK))
async def cb_back(callback: CallbackQuery) -> None:
    """Вернуться к основной клавиатуре модерации."""
    if callback.from_user and callback.from_user.id != get_settings().admin_id:
        await callback.answer("Доступно только админу.", show_alert=True)
        return

    moderation_id = int(callback.data.replace(CALLBACK_BACK, ""))
    await callback.message.edit_reply_markup(reply_markup=_news_keyboard(moderation_id))
    await callback.answer()


@router.callback_query(F.data.startswith(CALLBACK_PUBLISH_CONFIRM))
async def cb_publish_confirm(callback: CallbackQuery, bot: Bot) -> None:
    """Опубликовать новость в основной чат (после подтверждения)."""
    if callback.from_user and callback.from_user.id != get_settings().admin_id:
        await callback.answer("Доступно только админу.", show_alert=True)
        return

    moderation_id = int(callback.data.replace(CALLBACK_PUBLISH_CONFIRM, ""))
    session_factory = get_session_factory()
    if not session_factory:
        await callback.answer("Ошибка БД.", show_alert=True)
        return

    async with session_factory() as session:
        nm = await get_news_moderation(session, moderation_id)
        if not nm or nm.status != "pending":
            await callback.answer("Новость уже обработана.", show_alert=True)
            return

        settings = get_settings()
        chat_id = get_publish_chat_id(settings)
        text = _format_for_publish(nm.rewritten_text, nm.source_channel)

        try:
            await bot.send_message(chat_id, text)
            nm.status = "published"
            await session.commit()
            await _set_status_on_message(callback, "опубликовано ✅")
            await callback.message.answer(f"✅ Опубликовано в чат <code>{chat_id}</code>")

        except TelegramForbiddenError:
            # Бот в группе, но без права отправлять сообщения
            await _set_status_on_message(callback, "ошибка: нет прав в группе")
            await callback.message.answer(
                "⛔ <b>Бот не имеет прав на отправку сообщений в группе.</b>\n\n"
                "Исправьте в Telegram:\n"
                "1. Откройте группу → Управление → Администраторы\n"
                "2. Добавьте <b>@RZDBadminton_Bot</b> как администратора\n"
                "3. Включите право «Отправка сообщений»\n\n"
                "После этого нажмите «В ленту» ещё раз."
            )
            # Статус остаётся pending — можно повторить

        except TelegramBadRequest as e:
            err = str(e).lower()
            if "chat not found" in err or "chat_not_found" in err:
                await _set_status_on_message(callback, "ошибка: чат не найден")
                await callback.message.answer(
                    f"⛔ <b>Чат не найден</b> (id: <code>{chat_id}</code>).\n\n"
                    "Проверьте:\n"
                    f"• {'TEST_CHAT_ID' if settings.debug_mode else 'MAIN_CHAT_ID'} в .env\n"
                    "• Бот добавлен в группу\n"
                    "• Перезапустите бота после изменения .env\n\n"
                    "После исправления нажмите «В ленту» ещё раз."
                )
                # Статус остаётся pending — можно повторить
            else:
                logger.error("TelegramBadRequest при публикации: %s", e)
                await callback.answer(f"Ошибка Telegram: {e}", show_alert=True)

        except Exception as e:
            logger.exception("Ошибка публикации новости: %s", e)
            await callback.answer(f"Ошибка: {e}", show_alert=True)

    await callback.answer()


@router.callback_query(F.data.startswith(CALLBACK_REJECT_CONFIRM))
async def cb_reject_confirm(callback: CallbackQuery) -> None:
    """Попросить выбрать причину отклонения."""
    if callback.from_user and callback.from_user.id != get_settings().admin_id:
        await callback.answer("Доступно только админу.", show_alert=True)
        return

    moderation_id = int(callback.data.replace(CALLBACK_REJECT_CONFIRM, ""))
    await callback.message.edit_reply_markup(reply_markup=_reject_reason_keyboard(moderation_id))
    await callback.answer("Выберите причину отклонения")


@router.callback_query(F.data.startswith(CALLBACK_REJECT_REASON))
async def cb_reject_reason(callback: CallbackQuery) -> None:
    """Отклонить новость с выбранной причиной."""
    if callback.from_user and callback.from_user.id != get_settings().admin_id:
        await callback.answer("Доступно только админу.", show_alert=True)
        return

    payload = callback.data.replace(CALLBACK_REJECT_REASON, "")
    parts = payload.split(":")
    if len(parts) != 2:
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    moderation_id = int(parts[0])
    reason_code = parts[1]
    reason_text = REJECT_REASONS.get(reason_code, REJECT_REASONS["other"])

    session_factory = get_session_factory()
    if not session_factory:
        await callback.answer("Ошибка БД.", show_alert=True)
        return

    async with session_factory() as session:
        nm = await get_news_moderation(session, moderation_id)
        if not nm or nm.status != "pending":
            await callback.answer("Новость уже обработана.", show_alert=True)
            return

        nm.status = "rejected"
        await session.commit()

    await _set_status_on_message(callback, f"отклонено · {reason_text}")
    await callback.message.answer(f"✗ Отклонено\nПричина: {reason_text}")
    await callback.answer()


@router.callback_query(F.data.startswith(CALLBACK_EDIT))
async def cb_edit(callback: CallbackQuery, bot: Bot) -> None:
    """Показать варианты рерайта для выбора."""
    if callback.from_user and callback.from_user.id != get_settings().admin_id:
        await callback.answer("Доступно только админу.", show_alert=True)
        return

    moderation_id = int(callback.data.replace(CALLBACK_EDIT, ""))
    session_factory = get_session_factory()
    if not session_factory:
        await callback.answer("Ошибка БД.", show_alert=True)
        return

    async with session_factory() as session:
        nm = await get_news_moderation(session, moderation_id)
        if not nm or nm.status != "pending":
            await callback.answer("Новость уже обработана.", show_alert=True)
            return

        variants = await generate_news_variants(nm.original_text, count=3)
        if not variants:
            await callback.answer("Не удалось сгенерировать варианты.", show_alert=True)
            return

        await update_news_moderation_variants(session, moderation_id, variants)

    from ui.design import SEP
    text = "<b>▸ Выберите вариант</b>\n" + SEP + "\n"
    for i, v in enumerate(variants, 1):
        text += f"{i}. {v}\n\n"

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        text,
        reply_markup=_variant_keyboard(moderation_id, len(variants)),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(CALLBACK_VARIANT))
async def cb_variant(callback: CallbackQuery, bot: Bot) -> None:
    """Выбрать вариант и опубликовать."""
    if callback.from_user and callback.from_user.id != get_settings().admin_id:
        await callback.answer("Доступно только админу.", show_alert=True)
        return

    parts = callback.data.replace(CALLBACK_VARIANT, "").split(":")
    if len(parts) != 2:
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    moderation_id = int(parts[0])
    index = int(parts[1])

    session_factory = get_session_factory()
    if not session_factory:
        await callback.answer("Ошибка БД.", show_alert=True)
        return

    async with session_factory() as session:
        nm = await get_news_moderation(session, moderation_id)
        if not nm or nm.status != "pending":
            await callback.answer("Новость уже обработана.", show_alert=True)
            return

        variants = (nm.variants or "").split("\n---\n")
        if index < 0 or index >= len(variants):
            await callback.answer("Вариант не найден.", show_alert=True)
            return

        chosen_text = variants[index].strip()
        settings = get_settings()
        chat_id = get_publish_chat_id(settings)
        try:
            await bot.send_message(chat_id, _format_for_publish(chosen_text, nm.source_channel))
            nm.status = "published"
            await session.commit()
        except TelegramForbiddenError:
            await callback.message.answer(
                "⛔ <b>Бот не имеет прав на отправку сообщений в группе.</b>\n"
                "Добавьте бота как администратора с правом «Отправка сообщений»."
            )
            await callback.answer()
            return
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "chat not found" in err or "chat_not_found" in err:
                await callback.message.answer(
                    f"⛔ <b>Чат не найден</b> (id: <code>{chat_id}</code>).\n"
                    f"Проверьте {'TEST_CHAT_ID' if settings.debug_mode else 'MAIN_CHAT_ID'} в .env."
                )
            else:
                await callback.answer(f"Ошибка: {e}", show_alert=True)
            await callback.answer()
            return
        except Exception as e:
            logger.exception("Ошибка публикации варианта: %s", e)
            await callback.answer(f"Ошибка: {e}", show_alert=True)
            return

    await callback.message.edit_reply_markup(reply_markup=None)
    await _set_status_on_message(callback, "опубликовано (вариант) ✅")
    await callback.message.answer("✅ Опубликовано")
    await callback.answer()


@router.callback_query(F.data.startswith(CALLBACK_VARIANTS_BACK))
async def cb_variants_back(callback: CallbackQuery) -> None:
    """Закрыть список вариантов и вернуть админа к карточке новости."""
    if callback.from_user and callback.from_user.id != get_settings().admin_id:
        await callback.answer("Доступно только админу.", show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("↩️ Вернитесь к карточке новости выше для модерации.")
    await callback.answer()
