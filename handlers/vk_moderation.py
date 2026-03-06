"""
@file: vk_moderation.py
@description: Модерация VK Видео — отправка админу, кнопки [В ленту], [Отклонить]; публикация в чат только после одобрения.
@dependencies: aiogram, config, database.repositories, ui.design, ui.keyboards
@created: 2026-03-01
"""

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from app_state import get_session_factory
from config import get_settings, get_publish_chat_id
from database.repositories import get_vk_moderation
from ui.design import card
from ui.keyboards import youtube_moderation_keyboard

logger = logging.getLogger("rzdbadminton")

router = Router(name="vk_moderation")

CALLBACK_PUBLISH = "vk_mod:publish:"
CALLBACK_REJECT = "vk_mod:reject:"


def _parse_moderation_id(callback_data: str | None, prefix: str) -> int | None:
    """Извлечь moderation_id из callback_data."""
    if not callback_data or not callback_data.startswith(prefix):
        return None
    try:
        raw = callback_data.replace(prefix, "", 1).strip()
        return int(raw) if raw else None
    except ValueError:
        return None


async def _require_admin(callback: CallbackQuery) -> bool:
    """Проверить, что callback от админа."""
    if callback.from_user and callback.from_user.id == get_settings().admin_id:
        return True
    await callback.answer("Доступно только админу.", show_alert=True)
    return False


def _vk_keyboard(moderation_id: int) -> InlineKeyboardMarkup:
    return youtube_moderation_keyboard(
        moderation_id,
        CALLBACK_PUBLISH,
        CALLBACK_REJECT,
    )


async def send_vk_to_moderation(
    bot: Bot,
    moderation_id: int,
    title: str,
    link: str,
) -> bool:
    """
    Отправить карточку VK Видео админу на модерацию (в личку).
    """
    try:
        settings = get_settings()
        text = card(
            "🏸 VK Видео на модерации",
            title,
            footer=f"<a href='{link}'>Смотреть →</a>",
        )
        await bot.send_message(
            settings.admin_id,
            text,
            reply_markup=_vk_keyboard(moderation_id),
        )
        return True
    except TelegramForbiddenError:
        logger.error(
            "Админ (id=%s) не начал диалог с ботом. VK видео не отправлено.",
            get_settings().admin_id,
        )
        return False
    except Exception as e:
        logger.exception("Ошибка отправки VK видео на модерацию: %s", e)
        return False


@router.callback_query(F.data.startswith(CALLBACK_PUBLISH))
async def cb_vk_publish(callback: CallbackQuery, bot: Bot) -> None:
    """Опубликовать VK Видео в основной чат."""
    if not await _require_admin(callback):
        return
    moderation_id = _parse_moderation_id(callback.data, CALLBACK_PUBLISH)
    if moderation_id is None:
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    session_factory = get_session_factory()
    if not session_factory:
        await callback.answer("Ошибка БД.", show_alert=True)
        return

    async with session_factory() as session:
        vm = await get_vk_moderation(session, moderation_id)
        if not vm or vm.status != "pending":
            await callback.answer("Видео уже обработано.", show_alert=True)
            return

        settings = get_settings()
        chat_id = get_publish_chat_id(settings)
        text = card(
            "🏸 Видео",
            vm.title,
            footer=f"<a href='{vm.link}'>Смотреть →</a>",
        )
        try:
            await bot.send_message(chat_id, text)
            vm.status = "published"
            await session.commit()
            if callback.message:
                old_text = (callback.message.html_text or callback.message.text or "").split("\n\nСтатус:")[0]
                await callback.message.edit_text(
                    f"{old_text}\n\nСтатус: опубликовано ✅",
                    reply_markup=None,
                )
            await callback.answer("Опубликовано в чат")
        except TelegramForbiddenError:
            await callback.answer(
                "Бот не имеет прав на отправку в группе. Добавьте бота в админы.",
                show_alert=True,
            )
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "chat not found" in err or "chat_not_found" in err:
                await callback.answer("Чат не найден. Проверьте MAIN_CHAT_ID.", show_alert=True)
            else:
                logger.error("TelegramBadRequest при публикации VK: %s", e)
                await callback.answer(f"Ошибка: {e}", show_alert=True)
        except Exception as e:
            logger.exception("Ошибка публикации VK: %s", e)
            await callback.answer(f"Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith(CALLBACK_REJECT))
async def cb_vk_reject(callback: CallbackQuery) -> None:
    """Отклонить VK Видео (не публиковать)."""
    if not await _require_admin(callback):
        return
    moderation_id = _parse_moderation_id(callback.data, CALLBACK_REJECT)
    if moderation_id is None:
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    session_factory = get_session_factory()
    if not session_factory:
        await callback.answer("Ошибка БД.", show_alert=True)
        return

    async with session_factory() as session:
        vm = await get_vk_moderation(session, moderation_id)
        if not vm or vm.status != "pending":
            await callback.answer("Видео уже обработано.", show_alert=True)
            return
        vm.status = "rejected"
        await session.commit()

    if callback.message:
        old_text = (callback.message.html_text or callback.message.text or "").split("\n\nСтатус:")[0]
        await callback.message.edit_text(
            f"{old_text}\n\nСтатус: отклонено",
            reply_markup=None,
        )
    await callback.answer("Отклонено")
