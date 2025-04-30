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
    file = await bot.get_file(file_id)
    file_stream = await bot.download_file(file.file_path)
    # Асинхронный поток
    if hasattr(file_stream, 'read') and callable(file_stream.read):
        try:
            # Пробуем асинхронный read
            return await file_stream.read()
        except TypeError:
            # Если read не асинхронный, пробуем обычный
            return file_stream.read()
    # Уже байты
    if isinstance(file_stream, bytes):
        return file_stream
    raise TypeError("Не удалось получить байты из file_stream") 