"""
@file: bot.py
@description: Точка входа, инициализация бота и роутеров
@dependencies: aiogram, config, database, utils.logger
@created: 2025-02-25
"""

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import get_settings
from app_state import set_session_factory
from handlers.commands import router as commands_router
from handlers.news import router as news_router
from handlers.polls import router as polls_router
from middlewares.error_handler import on_error
from database import create_engine, create_session_factory, init_db
from services.scheduler import setup_scheduler
from utils.logger import setup_logger
from utils.telegram_handler import TelegramErrorHandler

logger = setup_logger(
    log_dir=Path("logs"),
    level=20,
)


async def main() -> None:
    """Запуск бота."""
    settings = get_settings()

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    await init_db(engine)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    set_session_factory(session_factory)

    # Дублирование ERROR в Telegram админу
    tg_handler = TelegramErrorHandler(bot, settings.admin_id)
    tg_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(name)s | %(message)s")
    )
    logging.getLogger("rzdbadminton").addHandler(tg_handler)

    dp = Dispatcher()
    dp.errors.register(on_error)
    dp.include_router(commands_router)
    dp.include_router(polls_router)
    dp.include_router(news_router)

    scheduler = setup_scheduler(bot, session_factory)
    scheduler.start()

    logger.info("Бот запущен (опросы Пн, Ср 08:00)")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
        sys.exit(0)
