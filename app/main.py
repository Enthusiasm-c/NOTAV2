"""
Основной модуль запуска Nota V2 с улучшенным редактором позиций.

Настраивает и запускает aiogram-роутеры, включая улучшенный редактор позиций.
"""

import asyncio
import logging
import structlog
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.db import init_db, create_tables

# Импортируем все необходимые роутеры
from app.routers.telegram_bot import router as telegram_router
from app.routers.issue_editor_init import setup_issue_editor

# Настраиваем логирование
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()


async def main():
    """
    Основная функция запуска приложения.
    """
    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting Nota V2")
    
    # Инициализируем базу данных
    await init_db()
    await create_tables()
    
    # Инициализируем бота с FSM хранилищем
    bot = Bot(token=settings.telegram_bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем роутеры
    dp.include_router(telegram_router)
    
    # Настраиваем и подключаем улучшенный редактор позиций
    issue_editor_router = setup_issue_editor()
    dp.include_router(issue_editor_router)
    
    # Настраиваем остальные компоненты
    # ... (Дополнительные роутеры)
    
    logger.info("Bot started")
    
    # Запускаем поллинг
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
