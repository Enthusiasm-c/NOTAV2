"""
bot_runner.py
~~~~~~~~~~~~~

Точка входа Nota V2.

* Создаём объект Bot.
* Собираем Dispatcher, подключая все хендлеры (router) из app.routers.telegram_bot.
* Запускаем long-polling.
"""

import asyncio
from aiogram import Bot, Dispatcher

from app.config import settings
from app.routers.telegram_bot import router   # ← именно router, не dp


async def main() -> None:
    """
    Стартует Telegram-бот в режиме long-polling.
    """
    bot = Bot(token=settings.telegram_token)

    dp = Dispatcher()          # единый диспетчер для всего приложения
    dp.include_router(router)  # подключаем хендлеры

    # при необходимости можно добавить middleware / фильтры
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
