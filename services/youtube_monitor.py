"""
@file: youtube_monitor.py
@description: Мониторинг YouTube BWF TV на новые видео (YouTube Data API v3 или RSS)
@dependencies: aiohttp, config
@created: 2025-02-25
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
import aiohttp

from config import get_settings

logger = logging.getLogger("rzdbadminton")

# Официальный канал BWF TV: https://www.youtube.com/@BWF/videos
# Варианты ID: UChh-akEbUM8_6ghGVnJd6cQ (BWF TV), UCdBDkMCBO1Ni7Fkys-1dKdA — задайте YOUTUBE_CHANNEL_ID в .env при необходимости
DEFAULT_BWF_CHANNEL_ID = "UChh-akEbUM8_6ghGVnJd6cQ"
# RSS часто возвращает 404 — при наличии YOUTUBE_API_KEY используем YouTube Data API v3
API_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
API_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
RSS_BASE = "https://www.youtube.com/feeds/videos.xml"

# Ключевые слова для фильтрации: если пустой список — публикуются все видео канала
# Можно сделать строже, добавив слова типа "final", "highlight", "semi"
HIGHLIGHTS_KEYWORDS: tuple[str, ...] = ()


class YoutubeApiKeyInvalidError(Exception):
    """Ключ YouTube API отклонён (400). Используется для тихого перехода на RSS без показа длинной ошибки админу."""


class YoutubeApiDisabledError(Exception):
    """YouTube Data API v3 не включён в проекте (403). Тихий переход на RSS."""



@dataclass
class YoutubeVideo:
    """Видео из RSS."""
    video_id: str
    title: str
    published: str
    link: str


def _is_relevant(title: str) -> bool:
    """Проверить релевантность видео по заголовку.

    Если HIGHLIGHTS_KEYWORDS пуст — пропускаем все видео.
    """
    if not HIGHLIGHTS_KEYWORDS:
        return True
    lower = title.lower()
    return any(kw in lower for kw in HIGHLIGHTS_KEYWORDS)


async def _fetch_via_api(channel_id: str, api_key: str) -> list[YoutubeVideo]:
    """Получить последние видео канала через YouTube Data API v3 (channels + playlistItems)."""
    videos: list[YoutubeVideo] = []
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Получить ID плейлиста «Загрузки» канала
            params = {"part": "contentDetails", "id": channel_id, "key": api_key}
            async with session.get(
                API_CHANNELS_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    if resp.status == 400 and "API key not valid" in text:
                        raise YoutubeApiKeyInvalidError()
                    if resp.status == 403 and (
                        "disabled" in text.lower() or "has not been used" in text
                    ):
                        raise YoutubeApiDisabledError()
                    raise RuntimeError(
                        f"YouTube API channels: HTTP {resp.status} — {text[:200]}"
                    )
                data = await resp.json()
            items = data.get("items") or []
            if not items:
                logger.warning("YouTube API: канал %s не найден", channel_id)
                return []
            uploads_id = (
                items[0]
                .get("contentDetails", {})
                .get("relatedPlaylists", {})
                .get("uploads")
            )
            if not uploads_id:
                logger.warning("YouTube API: у канала %s нет плейлиста uploads", channel_id)
                return []

            # 2. Список последних видео плейлиста
            params = {
                "part": "snippet",
                "playlistId": uploads_id,
                "key": api_key,
                "maxResults": 5,
            }
            async with session.get(
                API_PLAYLIST_ITEMS_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    if resp.status == 403 and (
                        "disabled" in text.lower() or "has not been used" in text
                    ):
                        raise YoutubeApiDisabledError()
                    raise RuntimeError(
                        f"YouTube API playlistItems: HTTP {resp.status} — {text[:200]}"
                    )
                data = await resp.json()
            for item in (data.get("items") or [])[:5]:
                sn = item.get("snippet") or {}
                vid = (sn.get("resourceId") or {}).get("videoId")
                if not vid:
                    continue
                title = (sn.get("title") or "").strip()
                published = sn.get("publishedAt") or ""
                if _is_relevant(title):
                    videos.append(
                        YoutubeVideo(
                            video_id=vid,
                            title=title,
                            published=published,
                            link=f"https://www.youtube.com/watch?v={vid}",
                        )
                    )
        return videos[:5]
    except (YoutubeApiKeyInvalidError, YoutubeApiDisabledError):
        raise  # не логируем как ERROR — в fetch_new_highlights перейдём на RSS
    except Exception as e:
        logger.exception("YouTube API: %s", e)
        raise


async def validate_rss_url(playlist_id: str) -> tuple[bool, str]:
    """
    Проверить, отдаёт ли YouTube RSS для данного playlist_id (UU...).
    Возвращает (успех, url). Для ручной проверки подставьте playlist_id из канала.
    """
    url = f"{RSS_BASE}?playlist_id={playlist_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return (resp.status == 200, url)
    except Exception as e:
        logger.debug("validate_rss_url %s: %s", playlist_id, e)
        return (False, url)


async def _fetch_via_rss(channel_id: str) -> list[YoutubeVideo]:
    """Получить последние видео из RSS-ленты (playlist_id=UU...). Может вернуть 404."""
    playlist_id = "UU" + (channel_id[2:] if channel_id.startswith("UC") and len(channel_id) >= 24 else channel_id)
    url = f"{RSS_BASE}?playlist_id={playlist_id}"
    videos = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                raise RuntimeError(
                    f"YouTube RSS вернул HTTP {resp.status} для канала {channel_id}. "
                    "Добавьте YOUTUBE_API_KEY в .env (YouTube Data API v3 в Google Cloud Console)."
                )
            text = await resp.text()
    if "<entry>" not in text:
        return []
    vid_pattern = re.compile(r"<yt:videoId>([^<]+)</yt:videoId>")
    title_pattern = re.compile(r"<title>([^<]*)</title>")
    pub_pattern = re.compile(r"<published>([^<]+)</published>")
    parts = re.split(r"<entry>", text)
    for part in parts[1:6]:
        vid_m = vid_pattern.search(part)
        title_m = title_pattern.search(part)
        pub_m = pub_pattern.search(part)
        if vid_m and title_m:
            vid_id = vid_m.group(1)
            title = (title_m.group(1) or "").replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
            published = pub_m.group(1) if pub_m else ""
            if _is_relevant(title):
                videos.append(
                    YoutubeVideo(
                        video_id=vid_id,
                        title=title,
                        published=published,
                        link=f"https://www.youtube.com/watch?v={vid_id}",
                    )
                )
    return videos[:5]


async def fetch_new_highlights(channel_id: str | None = None) -> list[YoutubeVideo]:
    """
    Получить последние видео канала.

    Если в .env задан YOUTUBE_API_KEY — используется YouTube Data API v3 (надёжно).
    Иначе — попытка через RSS; при 404 нужно добавить YOUTUBE_API_KEY.

    Args:
        channel_id: ID YouTube-канала. Если None — из конфига или дефолтный.

    Returns:
        Список новых видео (до 5 штук).
    """
    settings = get_settings()
    ch_id = channel_id or settings.youtube_channel_id or DEFAULT_BWF_CHANNEL_ID
    api_key = (settings.youtube_api_key or "").strip().strip('"\'') or None
    if api_key:
        try:
            return await _fetch_via_api(ch_id, api_key)
        except (YoutubeApiKeyInvalidError, YoutubeApiDisabledError):
            logger.warning(
                "YouTube API недоступен (ключ или API отключён), используем RSS для канала %s",
                ch_id,
            )
            return await _fetch_via_rss(ch_id)
        except RuntimeError as e:
            err = str(e)
            if "API key not valid" in err or "неверный ключ" in err:
                logger.warning(
                    "YouTube API ключ отклонён, пробуем RSS для канала %s",
                    ch_id,
                )
                return await _fetch_via_rss(ch_id)
            raise
    return await _fetch_via_rss(ch_id)


def _get_processed_path() -> Path:
    """Путь к файлу с обработанными video_id."""
    return Path("data/youtube_processed.txt")


def _load_processed() -> set[str]:
    """Загрузить список обработанных video_id."""
    p = _get_processed_path()
    if not p.exists():
        return set()
    return set(p.read_text(encoding="utf-8").splitlines())


def _save_processed(ids: set[str]) -> None:
    """Сохранить обработанные video_id."""
    p = _get_processed_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(sorted(ids)), encoding="utf-8")


async def get_unseen_highlights() -> list[YoutubeVideo]:
    """
    Получить новые видео, которых ещё не отправляли на модерацию.

    Не помечает видео как обработанные — это делает вызывающий код после
    успешной отправки на модерацию (mark_youtube_sent_to_moderation).

    Returns:
        Список новых видео (пустой список при ошибке или если новинок нет).
    """
    try:
        processed = _load_processed()
        all_videos = await fetch_new_highlights()
        return [v for v in all_videos if v.video_id not in processed]
    except Exception as e:
        logger.error("get_unseen_highlights: %s", e)
        return []


def mark_youtube_sent_to_moderation(video_id: str) -> None:
    """Пометить видео как отправленное на модерацию (чтобы не слать повторно)."""
    processed = _load_processed()
    processed.add(video_id)
    _save_processed(processed)


async def check_highlights_status() -> dict:
    """
    Подробный статус для диагностики: сколько всего в RSS, сколько новых, сколько уже видели.
    Не изменяет список обработанных (processed) — пометка только при отправке на модерацию.

    Returns:
        {"all": [...], "new": [...], "seen": [...], "error": str | None}
    """
    processed = _load_processed()
    error_msg: str | None = None
    all_videos: list[YoutubeVideo] = []
    try:
        all_videos = await fetch_new_highlights()
    except Exception as e:
        error_msg = str(e)
        logger.error("check_highlights_status: %s", e)

    new_ones = [v for v in all_videos if v.video_id not in processed]
    seen_ones = [v for v in all_videos if v.video_id in processed]
    return {"all": all_videos, "new": new_ones, "seen": seen_ones, "error": error_msg}


def clear_youtube_processed() -> int:
    """
    Очистить список обработанных video_id (для повторной публикации).

    Returns:
        Количество удалённых записей.
    """
    p = _get_processed_path()
    if not p.exists():
        return 0
    ids = _load_processed()
    count = len(ids)
    p.write_text("", encoding="utf-8")
    return count
