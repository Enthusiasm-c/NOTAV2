from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()
import os
print({k: v for k, v in os.environ.items() if "TOKEN" in k or "KEY" in k or "URL" in k or "LOGIN" in k or "PASSWORD" in k or "STORE" in k})

"""
bot_runner.py
~~~~~~~~~~~~~

Точка входа Nota V2.

* Создаёт экземпляр Bot.
* Собирает единый Dispatcher, подключая router-ы из `app.routers.telegram_bot`.
* Запускает long-polling и выводит подробные логи в stdout.

Запуск:

    python bot_runner.py                # вручную
    # или через systemd-unit (см. deploy/systemd/notav2-bot.service)
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from app.config.settings import get_settings
from app.routers.telegram_bot import router as main_router
from app.routers.issue_editor import router as editor_router

# ───────────────────────  Логирование  ──────────────────────────
#
# INFO-уровень показывает старт/стоп polling'а и любые
# сообщения logger-ов aiogram'а.  DEBUG можно включить, задав
# переменную среды LOG_LEVEL=DEBUG.
#
try:
    log_level_name = get_settings().log_level if hasattr(get_settings(), "log_level") else "INFO"
    log_level = logging.getLevelName(log_level_name.upper())
except (AttributeError, ValueError):
    log_level = logging.INFO

logging.basicConfig(
    level=log_level,  # INFO по умолчанию
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
# ────────────────────────────────────────────────────────────────

async def main() -> None:
    """Запускает polling-loop aiogram."""
    # Выведем диагностику для отладки
    logger.info(f"Python версия: {sys.version}")
    logger.info(f"Telegram token: {get_settings().telegram_bot_token[:5]}...")
    logger.info(f"Log level: {log_level}")
    
    # Инициализация бота и диспетчера
    bot = Bot(token=get_settings().telegram_bot_token)
    storage = MemoryStorage()  # Хранилище для FSM
    dp = Dispatcher(storage=storage)
    
    # Подключаем все роутеры
    dp.include_router(main_router)
    dp.include_router(editor_router)  # Новый роутер для редактирования спорных позиций

    # Очистка вебхука перед запуском long polling
    logger.info("Очистка вебхука...")
    await bot.delete_webhook(drop_pending_updates=True)
    
    logger.info("🚀 Nota V2 bot starting polling…")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Закрываем сессию бота при выходе
        await bot.session.close()
    
    logger.info("✅ Polling finished (graceful shutdown)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Bot stopped by user interrupt")
    except Exception as e:
        logger.exception(f"❌ Необработанное исключение: {e}")
        sys.exit(1)
