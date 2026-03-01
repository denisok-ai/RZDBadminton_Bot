"""
@file: news_parser.py
@description: Парсинг новых постов из Telegram-каналов через Telethon
@dependencies: telethon, utils.file_reader
@created: 2025-02-25
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import Message

from config import get_settings
from utils.file_reader import read_sources

logger = logging.getLogger("rzdbadminton")

SESSION_FILE = Path("data/telethon_session.session")


@dataclass
class ParsedPost:
    """Пост из канала."""

    channel_id: int
    channel_username: str
    message_id: int
    text: str


def _extract_channel_username(link: str) -> str | None:
    """Извлечь username из ссылки t.me/channel или t.me/s/channel."""
    link = link.strip()
    if "t.me/" in link:
        part = link.split("t.me/")[-1].split("?")[0]
        if part.startswith("s/"):
            part = part[2:]
        return part.strip() or None
    return None


async def fetch_new_posts(
    client: TelegramClient,
    channel_links: list[str],
    limit_per_channel: int = 5,
) -> list[ParsedPost]:
    """
    Получить последние посты из каналов.

    Returns:
        Список постов с текстом (без репостов, без пустых).
    """
    posts = []
    for link in channel_links:
        username = _extract_channel_username(link)
        if not username:
            continue
        try:
            entity = await client.get_entity(username)
            async for msg in client.iter_messages(username, limit=limit_per_channel):
                if not isinstance(msg, Message) or not msg.text:
                    continue
                if msg.forward:
                    continue
                if len(msg.text.strip()) < 20:
                    continue
                posts.append(
                    ParsedPost(
                        channel_id=entity.id,
                        channel_username=username,
                        message_id=msg.id,
                        text=msg.text[:2000],
                    )
                )
        except Exception as e:
            logger.warning("Ошибка чтения канала %s: %s", username, e)
    return posts


async def create_telethon_client() -> TelegramClient:
    """Создать Telethon-клиент с сохранением сессии."""
    settings = get_settings()
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(
        str(SESSION_FILE),
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )
    return client


async def run_parse(
    on_new_post: Callable[[ParsedPost], Awaitable[None]],
    on_session_error: Callable[[Exception], Awaitable[None]] | None = None,
) -> None:
    """
    Запустить клиент, парсить каналы, вызывать on_new_post для каждого поста.

    on_new_post — async, проверка на processed в вызывающем коде.
    """
    settings = get_settings()
    sources = read_sources(settings.sources_file)
    if not sources:
        logger.warning("Нет каналов в sources.txt")
        if on_session_error:
            await on_session_error(
                RuntimeError(
                    "Файл sources.txt пуст или не найден. "
                    f"Ожидается: {settings.sources_file}"
                )
            )
        return

    if not SESSION_FILE.exists():
        logger.error("Telethon-сессия не найдена: %s", SESSION_FILE)
        if on_session_error:
            await on_session_error(
                RuntimeError(
                    f"Сессия Telethon не найдена ({SESSION_FILE}). "
                    "Запустите бот интерактивно для первичной авторизации."
                )
            )
        return

    client = await create_telethon_client()
    try:
        await client.start()
        posts = await fetch_new_posts(client, sources)
        for post in posts:
            await on_new_post(post)
    except Exception as e:
        logger.exception("Ошибка Telethon: %s", e)
        if on_session_error:
            await on_session_error(e)
    finally:
        await client.disconnect()
