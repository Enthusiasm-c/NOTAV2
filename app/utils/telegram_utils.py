"""
Заглушка для download_file для тестов и устранения ошибок импорта.
"""
import logging
from aiogram import Bot

logger = logging.getLogger(__name__)

async def download_file(bot: Bot, file_id: str) -> bytes:
    """Загружает файл из Telegram по file_id."""
    logger.info(f"Загрузка файла с ID: {file_id}")
    
    try:
        file = await bot.get_file(file_id)
        if not file:
            raise ValueError(f"Не удалось получить информацию о файле для ID: {file_id}")
            
        file_stream = await bot.download_file(file.file_path)
        if not file_stream:
            raise ValueError("Получен пустой файл от Telegram API")
            
        image_bytes = await file_stream.read()
        if not image_bytes:
            raise ValueError("Не удалось прочитать содержимое файла")
            
        logger.info(f"Успешно загружен файл размером {len(image_bytes)} байт")
        return image_bytes
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла: {str(e)}")
        raise ValueError(f"Ошибка при загрузке файла: {str(e)}") from e 