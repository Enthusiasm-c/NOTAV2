"""
Заглушка для download_file для тестов и устранения ошибок импорта.
"""
import structlog

logger = structlog.get_logger()

async def download_file(file_id: str, bot) -> bytes:
    logger.warning("download_file called (stub)", file_id=file_id)
    return b""  # Возвращаем пустые байты для тестов 