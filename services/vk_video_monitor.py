"""
@file: vk_video_monitor.py
@description: Получение последних видео из каналов VK Видео (vkvideo.ru) через VK API video.get
@dependencies: aiohttp, config
@created: 2026-03-01
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import aiohttp

from config import get_settings
from utils.file_reader import read_sources

logger = logging.getLogger("rzdbadminton")

VK_API_BASE = "https://api.vk.com/method"
VK_API_VERSION = "5.199"


@dataclass
class VkVideo:
    """Видео из VK."""

    video_id: str  # уникальный ключ: owner_id_video_id (например -230702540_12345)
    title: str
    link: str
    owner_id: int
    channel_id: str  # для отображения (owner_id или screen_name)


def _parse_owner_from_source(line: str) -> tuple[int | None, str]:
    """
    Извлечь owner_id и метку канала из строки (URL или идентификатор).

    Поддерживает:
    - https://vkvideo.ru/@club230702540 -> (-230702540, "club230702540")
    - https://vkvideo.ru/@club89858131
    - https://vkvideo.ru/@bad_coach -> нужен resolve (пока возвращаем None для не-numeric)
    - club230702540 -> (-230702540, "club230702540")

    Returns:
        (owner_id, channel_id для логов). owner_id None если не удалось распознать.
    """
    line = line.strip()
    if not line:
        return (None, "")
    # URL: vkvideo.ru/@club123 -> club123
    match = re.search(r"@(club\d+)|@([a-zA-Z0-9_]+)", line)
    if match:
        club = match.group(1)
        screen_name = match.group(2)
        if club:
            num = club.replace("club", "")
            try:
                return (-int(num), club)
            except ValueError:
                return (None, club)
        if screen_name:
            # Для screen_name нужен resolve; пока поддерживаем только club*
            if screen_name.startswith("club"):
                try:
                    num = screen_name.replace("club", "")
                    return (-int(num), screen_name)
                except ValueError:
                    pass
            return (None, screen_name)
    # Просто "club230702540"
    if line.startswith("club"):
        try:
            num = line.replace("club", "")
            return (-int(num), line)
        except ValueError:
            pass
    return (None, line)


async def _resolve_screen_name(screen_name: str, access_token: str) -> int | None:
    """Разрешить screen_name в owner_id через utils.resolveScreenName. Для пользователя — положительный id."""
    url = f"{VK_API_BASE}/utils.resolveScreenName"
    params = {
        "screen_name": screen_name,
        "access_token": access_token,
        "v": VK_API_VERSION,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if "error" in data:
                    return None
                r = data.get("response")
                if not isinstance(r, dict):
                    return None
                obj_id = r.get("object_id")
                obj_type = r.get("type")
                if obj_id is None:
                    return None
                if obj_type == "group":
                    return -int(obj_id)
                return int(obj_id)
    except Exception as e:
        logger.warning("VK resolveScreenName %s: %s", screen_name, e)
        return None


async def _fetch_channel_videos(owner_id: int, access_token: str, count: int = 5) -> list[VkVideo]:
    """Получить последние видео канала через video.get."""
    url = f"{VK_API_BASE}/video.get"
    params = {
        "owner_id": owner_id,
        "count": count,
        "access_token": access_token,
        "v": VK_API_VERSION,
    }
    videos: list[VkVideo] = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.warning("VK video.get owner_id=%s HTTP %s", owner_id, resp.status)
                    return videos
                data = await resp.json()
                if "error" in data:
                    err = data["error"]
                    logger.warning("VK video.get owner_id=%s error: %s", owner_id, err.get("error_msg", err))
                    return videos
                raw = data.get("response")
                if isinstance(raw, list):
                    items = raw[1:] if len(raw) > 1 else []
                else:
                    items = (raw or {}).get("items") or []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    vid = item.get("id") or item.get("vid")
                    title = (item.get("title") or "").strip() or "Без названия"
                    oid_raw = item.get("owner_id", owner_id)
                    try:
                        oid = int(oid_raw) if oid_raw is not None else owner_id
                    except (TypeError, ValueError):
                        oid = owner_id
                    if vid is None:
                        continue
                    link = f"https://vk.com/video{oid}_{vid}"
                    video_id_str = f"{oid}_{vid}"
                    videos.append(
                        VkVideo(
                            video_id=video_id_str,
                            title=title,
                            link=link,
                            owner_id=oid,
                            channel_id=str(owner_id),
                        )
                    )
    except Exception as e:
        logger.exception("VK video.get owner_id=%s: %s", owner_id, e)
    return videos


def _get_vk_owner_ids(settings) -> list[tuple[int | None, str]]:
    """Прочитать источники и вернуть список (owner_id или None, channel_id). None — нужен resolve по screen_name."""
    path = getattr(settings, "vk_sources_file", Path("Doc/vk_sources.txt"))
    if isinstance(path, str):
        path = Path(path)
    lines = read_sources(path)
    result: list[tuple[int | None, str]] = []
    for line in lines:
        owner_id, channel_id = _parse_owner_from_source(line)
        if owner_id is not None:
            result.append((owner_id, channel_id))
        elif channel_id:
            result.append((None, channel_id))
    return result


async def fetch_vk_videos() -> list[VkVideo]:
    """
    Получить последние видео со всех каналов из vk_sources_file.

    Требуется vk_access_token в .env. Без токена возвращается пустой список.
    """
    settings = get_settings()
    token = (settings.vk_access_token or "").strip().strip('"\'')
    if not token:
        logger.debug("VK: vk_access_token не задан, пропуск")
        return []

    owner_specs = _get_vk_owner_ids(settings)
    if not owner_specs:
        logger.warning("VK: нет каналов в vk_sources_file или не удалось распознать owner_id")
        return []

    all_videos: list[VkVideo] = []
    for spec in owner_specs:
        owner_id, channel_id = spec
        if owner_id is None:
            resolved = await _resolve_screen_name(channel_id, token)
            if resolved is None:
                logger.warning("VK: не удалось разрешить screen_name %s", channel_id)
                continue
            owner_id = resolved
        vids = await _fetch_channel_videos(owner_id, token, count=5)
        for v in vids:
            v.channel_id = channel_id
        all_videos.extend(vids)

    return all_videos
