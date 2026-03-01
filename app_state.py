"""
@file: app_state.py
@description: Глобальное состояние приложения (session_factory для handlers)
@dependencies: sqlalchemy
@created: 2025-02-25
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Фабрика async-сессий БД, устанавливается в bot.py при старте
session_factory: "async_sessionmaker[AsyncSession] | None" = None


def set_session_factory(factory: "async_sessionmaker[AsyncSession]") -> None:
    """Установить фабрику сессий (вызывается из bot.py)."""
    global session_factory
    session_factory = factory


def get_session_factory() -> "async_sessionmaker[AsyncSession] | None":
    """Получить фабрику сессий. None до инициализации в bot.py."""
    return session_factory
