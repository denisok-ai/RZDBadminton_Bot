"""
@file: db_backup.py
@description: Бекапы SQLite БД с ротацией: глубина хранения 10 дней.
@dependencies: config, pathlib, shutil
@created: 2026-03-01
"""

import logging
import re
import shutil
from datetime import date, timedelta
from pathlib import Path

from config import get_settings

logger = logging.getLogger("rzdbadminton")

# Глубина хранения бекапов (дней)
BACKUP_RETENTION_DAYS = 10

# Имя файла бекапа: badminton_bot_YYYY-MM-DD.db
BACKUP_NAME_PATTERN = re.compile(r"^badminton_bot_(\d{4}-\d{2}-\d{2})\.db$")


def _get_db_path() -> Path | None:
    """Из database_url извлечь путь к файлу SQLite. Для не-sqlite вернуть None."""
    url = get_settings().database_url
    if "sqlite" not in url:
        return None
    # sqlite+aiosqlite:///./data/badminton_bot.db -> data/badminton_bot.db
    if "///" in url:
        path_part = url.split("///", 1)[-1].split("?")[0].strip()
        if path_part.startswith("./"):
            path_part = path_part[2:]
        return Path(path_part)
    return None


def _get_backup_dir(db_path: Path) -> Path:
    """Директория для бекапов — рядом с data, в data/backups."""
    return db_path.parent / "backups"


def run_backup() -> tuple[bool, str]:
    """
    Создать бекап БД и удалить бекапы старше BACKUP_RETENTION_DAYS дней.

    Returns:
        (успех, сообщение для лога/пользователя).
    """
    db_path = _get_db_path()
    if not db_path or not db_path.is_file():
        msg = f"Файл БД не найден: {db_path}"
        logger.warning(msg)
        return False, msg

    backup_dir = _get_backup_dir(db_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    today = date.today()
    backup_name = f"badminton_bot_{today.isoformat()}.db"
    backup_path = backup_dir / backup_name

    try:
        shutil.copy2(db_path, backup_path)
        logger.info("Бекап БД создан: %s", backup_path)
    except OSError as e:
        msg = f"Ошибка создания бекапа: {e}"
        logger.exception(msg)
        return False, msg

    # Удалить бекапы старше BACKUP_RETENTION_DAYS
    cutoff = today - timedelta(days=BACKUP_RETENTION_DAYS)
    removed = 0
    for f in backup_dir.iterdir():
        if not f.is_file():
            continue
        m = BACKUP_NAME_PATTERN.match(f.name)
        if not m:
            continue
        try:
            backup_date = date.fromisoformat(m.group(1))
            if backup_date < cutoff:
                f.unlink()
                removed += 1
                logger.debug("Удалён старый бекап: %s", f.name)
        except ValueError:
            continue

    if removed:
        logger.info("Удалено старых бекапов (старше %s дн.): %s", BACKUP_RETENTION_DAYS, removed)

    return True, f"Бекап: {backup_name}, удалено старых: {removed}"
