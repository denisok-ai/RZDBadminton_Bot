"""
@file: __init__.py
@description: Утилиты проекта
@created: 2025-02-25
"""

from utils.file_reader import read_sources
from utils.logger import setup_logger

__all__ = ["setup_logger", "read_sources"]
