"""
@file: __init__.py
@description: Инициализация БД, сессий, моделей
@dependencies: sqlalchemy, aiosqlite
@created: 2025-02-25
"""

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import Base


def _ensure_db_dir(database_url: str) -> None:
    """Создать директорию для файла БД, если её нет."""
    if "sqlite" not in database_url:
        return
    if "///" in database_url:
        path_part = database_url.split("///", 1)[-1].split("?")[0]
        if path_part.startswith("./"):
            path_part = path_part[2:]
        db_path = Path(path_part)
        if len(db_path.parts) > 1:
            db_path.parent.mkdir(parents=True, exist_ok=True)


def create_engine(database_url: str):
    """Создать асинхронный движок БД."""
    _ensure_db_dir(database_url)
    return create_async_engine(
        database_url,
        echo=False,
    )


def create_session_factory(engine):
    """Создать фабрику сессий."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def init_db(engine) -> None:
    """Создать таблицы в БД."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Генератор сессий для dependency injection."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
