"""
Main application module for Nota V2.

This module initializes the bot, routers, and database connections.
"""

import asyncio
import logging
import structlog
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.db import init_db, create_tables

# Import all necessary routers
from app.routers.telegram_bot import router as telegram_router
from app.routers.issue_editor import router as editor_router

# Import enhanced editor handlers
# from app.routers.issue_editor_handlers import setup_edit_handlers

# Configure structured logging
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
    Main function to initialize and run the bot.
    """
    # Set up standard logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting Nota V2")
    
    # Initialize database
    await init_db()
    await create_tables()
    
    # Initialize the bot
    bot = Bot(token=settings.telegram_bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Register base routers
    dp.include_router(telegram_router)
    dp.include_router(editor_router)
    
    # Register enhanced editor handlers
    setup_edit_handlers(dp)
    
    # Start the bot
    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
