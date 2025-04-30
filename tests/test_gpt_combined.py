"""
Тесты для оптимизированного модуля OCR+Parsing.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock, Mock
import json
import base64
import httpx

from app.routers.gpt_combined import (
    _split_api_response,
    _call_combined_api,
    ocr_and_parse,
    process_invoice
)


# Тестовые данные
@pytest.fixture
def sample_api_response():
    """Пример ответа от API в формате RAW TEXT + PARSED DATA."""
    return """
RAW TEXT:
INVOICE
Supplier: Test Company Ltd
Date: 2025-04-25
Item 1   10 pcs   $5   $50
Item 2   5 kg     $10  $50
Total: $100

PARSED DATA:
```json
{
  "supplier": "Test Company Ltd",
  "buyer": "Restaurant",
  "date": "2025-04-25",
  "positions": [
    {
      "name": "Item 1",
      "quantity": 10,
      "unit": "pcs",
      "price": 5,
      "sum": 50
    },
    {
      "name": "Item 2",
      "quantity": 5,
      "unit": "kg",
      "price": 10,
      "sum": 50
    }
  ],
  "total_sum": 100
}
```
"""


@pytest.fixture
def sample_parsed_data():
    """Пример структурированных данных из JSON."""
    return {
        "supplier": "Test Company Ltd",
        "buyer": "Restaurant",
        "date": "2025-04-25",
        "positions": [
            {
                "name": "Item 1",
                "quantity": 10,
                "unit": "pcs",
                "price": 5,
                "sum": 50
            },
            {
                "name": "Item 2",
                "quantity": 5,
                "unit": "kg",
                "price": 10,
                "sum": 50
            }
        ],
        "total_sum": 100
    }


@pytest.fixture
def sample_raw_text():
    """Пример распознанного текста."""
    return """
INVOICE
Supplier: Test Company Ltd
Date: 2025-04-25
Item 1   10 pcs   $5   $50
Item 2   5 kg     $10  $50
Total: $100
"""


@pytest.fixture
def sample_image_bytes():
    """Тестовое изображение (просто байты для теста)."""
    return b'test_image_bytes'


@pytest.fixture
def mock_bot():
    """Мок для бота Telegram."""
    bot = AsyncMock()
    file_mock = AsyncMock()
    file_mock.file_path = "test_file_path"
    bot.get_file.return_value = file_mock
    
    stream_mock = MagicMock()
    stream_mock.read.return_value = b'test_image_bytes'
    bot.download_file.return_value = stream_mock
    
    return bot


@pytest.fixture
def mock_httpx_response(sample_api_response):
    """Мок для ответа httpx."""
    response = MagicMock(spec=httpx.Response)
    response.raise_for_status = Mock()
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": sample_api_response
                }
            }
        ]
    }
    return response


@pytest.fixture
def mock_httpx_client(mock_httpx_response):
    """Мок для клиента httpx."""
    client = AsyncMock()
    client.__aenter__.return_value.post.return_value = mock_httpx_response
    return client


# Тесты функций
def test_split_api_response_with_markers(sample_api_response, sample_raw_text, sample_parsed_data):
    """Тест разделения ответа API с маркерами."""
    raw_text, json_str = _split_api_response(sample_api_response)
    
    # Проверяем, что текст извлечен корректно
    assert raw_text.strip() == sample_raw_text.strip()
    
    # Проверяем, что JSON получен
    assert json_str is not None
    
    # Проверяем, что JSON валиден и содержит ожидаемые данные
    parsed_data = json.loads(json_str)
    assert parsed_data == sample_parsed_data


def test_split_api_response_without_markers():
    """Тест разделения ответа API без маркеров."""
    # Ответ без маркеров, но с JSON
    content = """
    Это просто текст.
    
    {
      "supplier": "Company",
      "positions": []
    }
    """
    
    raw_text, json_str = _split_api_response(content)
    
    # Проверяем, что текст извлечен
    assert "Это просто текст" in raw_text
    
    # Проверяем, что JSON получен
    assert json_str is not None
    assert "supplier" in json_str
    
    # Проверяем, что JSON валиден
    parsed_data = json.loads(json_str)
    assert parsed_data["supplier"] == "Company"


def test_split_api_response_only_text():
    """Тест разделения ответа API с только текстом."""
    content = "Это просто текст без JSON."
    
    raw_text, json_str = _split_api_response(content)
    
    # Проверяем, что весь контент интерпретирован как текст
    assert raw_text == content
    
    # Проверяем, что JSON не найден
    assert json_str is None


@pytest.mark.asyncio
@patch('httpx.AsyncClient', autospec=True)
async def test_call_combined_api(mock_client, mock_httpx_response, sample_image_bytes, 
                               sample_raw_text, sample_parsed_data):
    """Тест вызова объединенного API."""
    mock_client.return_value.__aenter__.return_value.post.return_value = mock_httpx_response
    
    # Патчим настройки
    with patch('app.routers.gpt_combined.settings') as mock_settings:
        mock_settings.openai_api_key = "test_key"
        mock_settings.gpt_ocr_url = "https://api.test.com"
        
        raw_text, parsed_data = await _call_combined_api(sample_image_bytes)
    
    # Проверяем результаты
    assert raw_text.strip() == sample_raw_text.strip()
    assert parsed_data == sample_parsed_data
    
    # Проверяем, что вызван правильный метод
    mock_client.return_value.__aenter__.return_value.post.assert_called_once()


@patch('app.routers.gpt_combined.download_file')
@patch('app.routers.gpt_combined._call_combined_api')
async def test_process_invoice(mock_call_api, mock_download, mock_bot, 
                              sample_image_bytes, sample_raw_text, sample_parsed_data):
    """Тест основной функции process_invoice."""
    # Настраиваем моки
    mock_download.return_value = sample_image_bytes
    mock_call_api.return_value = (sample_raw_text, sample_parsed_data)
    # Патчим настройки
    with patch('app.routers.gpt_combined.get_settings') as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test_key"
        mock_get_settings.return_value = mock_settings
        # Вызываем тестируемую функцию
        raw_text, parsed_data = await process_invoice("test_file_id", mock_bot)
    # Проверяем результаты
    assert raw_text == sample_raw_text
    assert parsed_data == sample_parsed_data
    # Проверяем вызовы
    mock_download.assert_called_once_with(mock_bot, "test_file_id")
    mock_call_api.assert_called_once_with(sample_image_bytes)


@pytest.mark.asyncio
@patch('app.routers.gpt_combined.process_invoice')
async def test_ocr_and_parse(mock_process, mock_bot, sample_raw_text, sample_parsed_data):
    """Тест публичного API ocr_and_parse."""
    # Настраиваем мок
    mock_process.return_value = (sample_raw_text, sample_parsed_data)
    
    # Вызываем тестируемую функцию
    raw_text, parsed_data = await ocr_and_parse("test_file_id", mock_bot)
    
    # Проверяем результаты
    assert raw_text == sample_raw_text
    assert parsed_data == sample_parsed_data
    
    # Проверяем вызов
    mock_process.assert_called_once_with("test_file_id", mock_bot)


@pytest.mark.asyncio
@patch('app.routers.gpt_combined.process_invoice')
async def test_ocr_and_parse_with_error(mock_process, mock_bot):
    """Тест обработки ошибок в ocr_and_parse."""
    # Настраиваем мок на выброс исключения
    mock_process.side_effect = RuntimeError("Test error")
    
    # Вызываем тестируемую функцию
    raw_text, parsed_data = await ocr_and_parse("test_file_id", mock_bot)
    
    # Проверяем, что вернулись заглушки вместо ошибки
    assert "[OCR FAILED" in raw_text
    assert "Test error" in raw_text
    assert "MOCK" in parsed_data["supplier"]
    
    # Проверяем вызов
    mock_process.assert_called_once_with("test_file_id", mock_bot)
