"""
@file: file_reader.py
@description: Чтение sources.txt и других конфигурационных файлов
@dependencies: pathlib
@created: 2025-02-25
"""

from pathlib import Path


def read_sources(path: Path | str = "Doc/sources.txt") -> list[str]:
    """
    Прочитать список каналов из sources.txt (одна ссылка на строку).

    Returns:
        Список непустых строк, очищенных от пробелов.
    """
    p = Path(path)
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    return [line.strip() for line in lines if line.strip()]
