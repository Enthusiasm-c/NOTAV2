"""
Тесты для функции download_file.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram import Bot
from app.utils.telegram_utils import download_file

@pytest.fixture
def mock_bot():
    """Фикстура для мока бота."""
    bot = AsyncMock(spec=Bot)
    file_mock = AsyncMock()
    file_mock.file_path = "test/path/image.jpg"
    bot.get_file.return_value = file_mock
    return bot

@pytest.mark.asyncio
async def test_download_file_success(mock_bot):
    """Тест успешной загрузки файла."""
    # Подготавливаем тестовые данные
    test_bytes = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00'  # Валидный JPEG заголовок
    mock_bot.download_file.return_value = test_bytes
    
    # Вызываем функцию
    result = await download_file(mock_bot, "test_file_id")
    
    # Проверяем результат
    assert result == test_bytes
    assert len(result) > 0
    mock_bot.get_file.assert_called_once_with("test_file_id")
    mock_bot.download_file.assert_called_once_with("test/path/image.jpg")

@pytest.mark.asyncio
async def test_download_file_empty_response(mock_bot):
    """Тест обработки пустого ответа."""
    mock_bot.download_file.return_value = b''
    
    with pytest.raises(ValueError, match="Получен пустой файл от Telegram API"):
        await download_file(mock_bot, "test_file_id")

@pytest.mark.asyncio
async def test_download_file_no_file_info(mock_bot):
    """Тест обработки отсутствия информации о файле."""
    mock_bot.get_file.return_value = None
    
    with pytest.raises(ValueError, match="Не удалось получить информацию о файле"):
        await download_file(mock_bot, "test_file_id")

@pytest.mark.asyncio
async def test_download_file_api_error(mock_bot):
    """Тест обработки ошибки API."""
    mock_bot.download_file.side_effect = Exception("API Error")
    
    with pytest.raises(ValueError, match="Ошибка при загрузке файла"):
        await download_file(mock_bot, "test_file_id") 