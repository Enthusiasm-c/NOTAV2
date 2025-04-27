import asyncio
from aiogram import Bot
from app.routers.telegram_bot import dp
from app.config import settings

async def main():
    bot = Bot(token=settings.telegram_token)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
