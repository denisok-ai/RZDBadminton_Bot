"""
@file: logger.py
@description: Настройка логирования в файл и консоль
@dependencies: logging
@created: 2025-02-25
"""

import logging
import sys
from pathlib import Path


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
        file_handler = logging.FileHandler(
            log_dir / "bot.log",
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

        error_handler = logging.FileHandler(
            log_dir / "errors.log",
            encoding="utf-8",
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)
        logger.addHandler(error_handler)

    return logger
