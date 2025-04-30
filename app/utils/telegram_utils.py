"""
Заглушка для download_file для тестов и устранения ошибок импорта.
"""
import structlog
from aiogram import Bot

logger = structlog.get_logger()

async def download_file(bot: Bot, file_id: str) -> bytes:
    """
    Скачивает файл из Telegram по file_id и возвращает его содержимое в виде байтов.
    """
    logger.warning("download_file called (stub)", file_id=file_id)
    file = await bot.get_file(file_id)
    file_stream = await bot.download_file(file.file_path)
    if hasattr(file_stream, 'read'):
        # Если это поток, читаем байты
        return await file_stream.read()
    return file_stream  # Если это уже байты 