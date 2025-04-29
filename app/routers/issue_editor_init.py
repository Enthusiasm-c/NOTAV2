"""
Инициализация улучшенного редактора позиций для Nota V2.

Объединяет все части модуля issue_editor и регистрирует обработчики.
Этот файл служит точкой входа для подключения редактора к основному роутеру бота.
"""

from __future__ import annotations

import structlog
from aiogram import Router

# Импортируем части модуля
from app.routers.issue_editor_part1 import router

# Импортируем функции регистрации обработчиков
from app.routers.issue_editor_part3 import register_handlers as register_part3
from app.routers.issue_editor_part4 import register_handlers as register_part4
from app.routers.issue_editor_part5 import register_handlers as register_part5

logger = structlog.get_logger()

def setup_issue_editor() -> Router:
    """
    Настраивает и возвращает роутер для редактора позиций.
    
    Регистрирует все обработчики из разных частей модуля.
    
    :return: настроенный роутер aiogram
    """
    # Регистрируем обработчики из разных частей
    register_part3(router)
    register_part4(router)
    register_part5(router)
    
    logger.info("Issue editor router initialized")
    
    return router
