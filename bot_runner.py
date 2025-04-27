from __future__ import annotations

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

from aiogram import Bot, Dispatcher
from app.config import settings
from app.routers.telegram_bot import router  # router содержит все хендлеры

# ───────────────────────  Логирование  ──────────────────────────
#
# INFO-уровень показывает старт/стоп polling’а и любые
# сообщения logger-ов aiogram’а.  DEBUG можно включить, задав
# переменную среды LOG_LEVEL=DEBUG.
#
log_level = logging.getLevelName(
    (getattr(settings, "log_level", None) or "INFO").upper()
)
logging.basicConfig(
    level=log_level,  # INFO по умолчанию
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
# ────────────────────────────────────────────────────────────────


async def main() -> None:
    """Запускает polling-loop aiogram."""
    bot = Bot(token=settings.telegram_token)
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("🚀 Nota V2 bot starting polling…")
    await dp.start_polling(bot, allowed_updates=[])   # пустой список = все стандартные
    logger.info("✅ Polling finished (graceful shutdown)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Bot stopped by user interrupt")
