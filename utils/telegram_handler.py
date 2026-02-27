"""
@file: telegram_handler.py
@description: Logging Handler — отправка ERROR в Telegram админу
@dependencies: logging, aiogram
@created: 2025-02-25
"""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Bot


class TelegramErrorHandler(logging.Handler):
    """
    При записи ERROR — дублирует сообщение админу в Telegram.
    """

    def __init__(self, bot: "Bot", admin_id: int) -> None:
        super().__init__(level=logging.ERROR)
        self._bot = bot
        self._admin_id = admin_id
        self._max_len = 4000

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            if len(msg) > self._max_len:
                msg = msg[: self._max_len - 20] + "\n...(обрезано)"
            text = f"⚠ <b>ERROR</b>\n▬▬▬\n<code>{msg.replace('<', '&lt;').replace('>', '&gt;')}</code>"
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
            asyncio.run_coroutine_threadsafe(self._send(text), loop)
        except Exception:
            self.handleError(record)

    async def _send(self, text: str) -> None:
        try:
            await self._bot.send_message(self._admin_id, text)
        except Exception:
            pass  # Не логируем, чтобы избежать рекурсии
