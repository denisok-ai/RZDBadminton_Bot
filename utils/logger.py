"""
@file: logger.py
@description: Настройка логирования в файл и консоль с ротацией по размеру
@dependencies: logging
@created: 2025-02-25
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Ротация: при достижении размера файла создаётся новый, старые переименовываются (.1, .2, …)
LOG_MAX_BYTES = 2 * 1024 * 1024  # 2 МБ
LOG_BACKUP_COUNT = 5  # хранить 5 архивных файлов


def setup_logger(
    name: str = "rzdbadminton",
    log_dir: Path | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Настраивает логгер с выводом в консоль и файл.

    Args:
        name: Имя логгера.
        log_dir: Директория для логов. Если None — только консоль.
        level: Уровень логирования.

    Returns:
        Настроенный логгер.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "bot.log",
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

        error_handler = RotatingFileHandler(
            log_dir / "errors.log",
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)
        logger.addHandler(error_handler)

    return logger
