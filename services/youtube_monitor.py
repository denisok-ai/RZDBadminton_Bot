"""
@file: youtube_monitor.py
@description: Мониторинг YouTube BWF TV на новые Highlights (RSS)
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

# BWF channel ID (можно переопределить через YOUTUBE_CHANNEL_ID в .env)
DEFAULT_BWF_CHANNEL_ID = "UCsRNTi1LIrgsxpOrejJo6Xw"  # BWF Group
RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
HIGHLIGHTS_KEYWORDS = ("highlight", "highlights", "хайлайт", "обзор", "best moments", "recap")


@dataclass
class YoutubeVideo:
    """Видео из RSS."""
    video_id: str
    title: str
    published: str
    link: str


def _is_highlight(title: str) -> bool:
    """Проверить, похоже ли видео на Highlights по названию."""
    lower = title.lower()
    return any(kw in lower for kw in HIGHLIGHTS_KEYWORDS)


async def fetch_new_highlights(channel_id: str | None = None) -> list[YoutubeVideo]:
    """
    Получить последние видео из RSS, отфильтровать по Highlights.

    Returns:
        Список видео, похожих на Highlights.
    """
    ch_id = channel_id or get_settings().youtube_channel_id or DEFAULT_BWF_CHANNEL_ID
    url = RSS_URL.format(channel_id=ch_id)
    videos = []

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.warning("YouTube RSS вернул %s", resp.status)
                    return []
                text = await resp.text()

        # YouTube RSS: <yt:videoId>xxx</yt:videoId>, <title>...</title>
        vid_pattern = re.compile(r"<yt:videoId>([^<]+)</yt:videoId>")
        title_pattern = re.compile(r"<title>([^<]*)</title>")
        pub_pattern = re.compile(r"<published>([^<]+)</published>")
        parts = re.split(r"<entry>", text)
        for part in parts[1:6]:  # первые 5 entry
            vid_m = vid_pattern.search(part)
            title_m = title_pattern.search(part)
            pub_m = pub_pattern.search(part)
            if vid_m and title_m:
                vid_id = vid_m.group(1)
                title = (title_m.group(1) or "").replace("&amp;", "&").replace("&#39;", "'")
                published = pub_m.group(1) if pub_m else ""
                if _is_highlight(title):
                    videos.append(
                        YoutubeVideo(
                            video_id=vid_id,
                            title=title,
                            published=published,
                            link=f"https://www.youtube.com/watch?v={vid_id}",
                        )
                    )

        return videos[:5]
    except Exception as e:
        logger.exception("Ошибка парсинга YouTube RSS: %s", e)
        return []


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
    Получить новые Highlights, которых ещё не было в рассылке.
    """
    processed = _load_processed()
    all_highlights = await fetch_new_highlights()
    new_ones = [v for v in all_highlights if v.video_id not in processed]
    for v in new_ones:
        processed.add(v.video_id)
    if new_ones:
        _save_processed(processed)
    return new_ones


async def check_highlights_status() -> dict:
    """
    Подробный статус для диагностики: сколько всего в RSS, сколько новых, сколько уже видели.

    Returns:
        {"all": [...], "new": [...], "seen": [...]}
    """
    processed = _load_processed()
    all_highlights = await fetch_new_highlights()
    new_ones = [v for v in all_highlights if v.video_id not in processed]
    seen_ones = [v for v in all_highlights if v.video_id in processed]
    if new_ones:
        for v in new_ones:
            processed.add(v.video_id)
        _save_processed(processed)
    return {"all": all_highlights, "new": new_ones, "seen": seen_ones}


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
