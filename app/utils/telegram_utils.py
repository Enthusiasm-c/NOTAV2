"""
Утилиты для работы с Telegram API.
"""
import logging
from io import BytesIO
from aiogram import Bot

logger = logging.getLogger(__name__)

async def download_file(bot: Bot, file_id: str) -> bytes:
    """
    Загружает файл из Telegram по file_id.
    
    Args:
        bot: Экземпляр бота
        file_id: Идентификатор файла в Telegram
        
    Returns:
        bytes: Содержимое файла
        
    Raises:
        ValueError: Если файл не найден или пустой
    """
    logger.info("Загрузка файла с ID: %s", file_id)
    
    try:
        file = await bot.get_file(file_id)
        if not file:
            raise ValueError(f"Не удалось получить информацию о файле для ID: {file_id}")
            
        buf: BytesIO = await bot.download_file(file.file_path)
        image_bytes = buf.getvalue()
        if not image_bytes:
            raise ValueError("Получен пустой файл от Telegram API")
            
        logger.info("Файл %d байт загружен", len(image_bytes))
        return image_bytes
        
    except Exception as e:
        logger.error("Ошибка при загрузке файла: %s", str(e))
        raise ValueError(f"Ошибка при загрузке файла: {str(e)}") from e 