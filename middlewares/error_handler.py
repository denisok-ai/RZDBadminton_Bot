"""
@file: error_handler.py
@description: Обработка ошибок — логирование и уведомление админу
@dependencies: aiogram, config, logging
@created: 2025-02-25
"""

import logging

from aiogram import Bot
from aiogram.types import ErrorEvent

from config import get_settings

logger = logging.getLogger("rzdbadminton")

MAX_MESSAGE_LENGTH = 4000  # Лимит Telegram


async def on_error(event: ErrorEvent, bot: Bot) -> None:
    """
    Глобальный обработчик ошибок: логирует и отправляет админу.
    """
    exc = event.exception
    logger.exception("Необработанная ошибка: %s", exc)

    admin_id = get_settings().admin_id
    err_text = str(exc).replace("<", "&lt;").replace(">", "&gt;")
    text = f"⚠ <b>Ошибка бота</b>\n▬▬▬\n<code>{err_text}</code>"
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH - 20] + "\n\n...(обрезано)"

    try:
        await bot.send_message(admin_id, text)
    except Exception as send_err:
        logger.warning("Не удалось отправить алерт админу: %s", send_err)
