"""
@file: __init__.py
@description: Инициализация БД, сессий, моделей
@dependencies: sqlalchemy, aiosqlite
@created: 2025-02-25
"""

import logging
import sqlite3
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from database.models import Base

logger = logging.getLogger("rzdbadminton")


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


def create_engine(database_url: str) -> AsyncEngine:
    """Создать асинхронный движок БД."""
    _ensure_db_dir(database_url)
    return create_async_engine(
        database_url,
        echo=False,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Создать фабрику сессий."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def init_db(engine: AsyncEngine) -> None:
    """Создать таблицы в БД."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _get_sqlite_path(engine: AsyncEngine) -> Path | None:
    """Извлечь путь к файлу SQLite из URL движка. Для не-SQLite возвращает None."""
    url = str(engine.url)
    if "sqlite" not in url:
        return None
    path_part = url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "").strip()
    if path_part.startswith("./"):
        path_part = path_part[2:]
    return Path(path_part).resolve()


async def ensure_migrations(engine: AsyncEngine) -> None:
    """
    Проверить наличие нужных таблиц и колонок; при необходимости добавить (миграция для SQLite).
    Вызывать после init_db(engine). Для существующих БД добавляет колонки quiz_records.correct_answer
    и quiz_records.explanation, если их ещё нет.
    """
    db_path = _get_sqlite_path(engine)
    if db_path is None or not db_path.exists():
        return
    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        cur = conn.execute("PRAGMA table_info(quiz_records)")
        columns = [row[1] for row in cur.fetchall()]
        if "correct_answer" not in columns:
            conn.execute("ALTER TABLE quiz_records ADD COLUMN correct_answer VARCHAR(500)")
            logger.info("Миграция БД: добавлена колонка quiz_records.correct_answer")
        if "explanation" not in columns:
            conn.execute("ALTER TABLE quiz_records ADD COLUMN explanation TEXT")
            logger.info("Миграция БД: добавлена колонка quiz_records.explanation")
        conn.commit()
        conn.close()
    except sqlite3.OperationalError as e:
        logger.warning("Миграция БД (quiz_records): %s", e)
    except Exception as e:
        logger.warning("Ошибка проверки миграций БД: %s", e)


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
