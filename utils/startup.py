"""
@file: startup.py
@description: Проверка окружения при старте бота: зависимости, при необходимости — доустановка.
@dependencies: pathlib, subprocess, sys
@created: 2026-03
"""

import subprocess
import sys
from pathlib import Path

# Пакеты, которые должны быть доступны (имя для import)
REQUIRED_PACKAGES = [
    "aiogram",
    "aiohttp",
    "apscheduler",
    "openai",
    "openpyxl",
    "pandas",
    "pydantic_settings",
    "dotenv",
    "sqlalchemy",
    "aiosqlite",
    "telethon",
    "yadisk",
    "docx",  # python-docx
]


def _project_root() -> Path:
    """Корень проекта (каталог с requirements.txt и bot.py)."""
    return Path(__file__).resolve().parent.parent


def _try_import_packages() -> str | None:
    """Попытка импорта всех пакетов. Возвращает имя первого неудачного или None."""
    for name in REQUIRED_PACKAGES:
        try:
            __import__(name)
        except ImportError:
            return name
    return None


def ensure_dependencies(project_root: Path | None = None) -> None:
    """
    Проверить наличие обязательных библиотек. При отсутствии — выполнить
    pip install -r requirements.txt и повторить проверку.
    При повторной неудаче — завершить процесс с кодом 1.
    """
    root = project_root or _project_root()
    requirements = root / "requirements.txt"
    failed = _try_import_packages()
    if failed is None:
        return

    # Первая неудача — пробуем доустановить
    if not requirements.exists():
        print(
            f"Ошибка: не найден {requirements}. Установите зависимости вручную: pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Не найден пакет '{failed}'. Устанавливаю зависимости из requirements.txt…", file=sys.stderr)
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements), "-q"],
            cwd=str(root),
            check=True,
            timeout=300,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(
            f"Не удалось установить зависимости: {e}. Выполните вручную: pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    failed = _try_import_packages()
    if failed is not None:
        print(
            f"После установки пакет '{failed}' по-прежнему недоступен. Проверьте requirements.txt и виртуальное окружение.",
            file=sys.stderr,
        )
        sys.exit(1)
