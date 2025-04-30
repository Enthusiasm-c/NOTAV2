"""Утилиты для логирования."""

import logging
import sys
from typing import Optional

from app.core.constants import LOG_FORMAT, LOG_LEVEL, LOG_DATE_FORMAT

def setup_logger(
    name: str,
    level: Optional[str] = None,
    format_str: Optional[str] = None,
    date_format: Optional[str] = None,
) -> logging.Logger:
    """Настраивает логгер.

    Args:
        name: Имя логгера
        level: Уровень логирования
        format_str: Формат сообщений
        date_format: Формат даты

    Returns:
        logging.Logger: Настроенный логгер
    """
    logger = logging.getLogger(name)
    logger.setLevel(level or LOG_LEVEL)

    # Создаем обработчик для вывода в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level or LOG_LEVEL)

    # Создаем форматтер
    formatter = logging.Formatter(
        format_str or LOG_FORMAT,
        datefmt=date_format or LOG_DATE_FORMAT
    )
    console_handler.setFormatter(formatter)

    # Добавляем обработчик к логгеру
    logger.addHandler(console_handler)

    return logger

def get_logger(name: str) -> logging.Logger:
    """Получает логгер по имени.

    Args:
        name: Имя логгера

    Returns:
        logging.Logger: Логгер
    """
    return logging.getLogger(name)
