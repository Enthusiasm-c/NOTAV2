"""
Оптимизированный модуль для NOTA V2, объединяющий OCR и парсинг в один API-запрос.

Преимущества:
- Сокращение количества API-запросов в 2 раза
- Уменьшение времени обработки накладной примерно вдвое
- Снижение стоимости API-запросов
"""

from __future__ import annotations

import base64
import json
import httpx
import structlog
from typing import Dict, Any, Tuple, Optional
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from aiogram import Bot

from app.config.settings import get_settings
from app.utils.telegram_utils import download_file

logger = structlog.get_logger()


# --------------------------------------------------------------------------- #
#  Базовые служебные функции
# --------------------------------------------------------------------------- #
@retry(
    # Retry only on 5xx and network errors
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.NetworkError)),
    wait=wait_exponential_jitter(initial=1, max=30),  # 1s, 2s, 4s... + jitter
    stop=stop_after_attempt(6),                       # ≤ 6 attempts
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        f"API call failed, retrying in {retry_state.next_action.sleep} seconds "
        f"(attempt {retry_state.attempt_number}/{6})",
        error=str(retry_state.outcome.exception())
    ),
)
async def _call_combined_api(image_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """
    Выполняет объединенный API-запрос OCR + парсинг.
    
    Args:
        image_bytes: Изображение в виде байтов
        
    Returns:
        Tuple[str, Dict[str, Any]]: (распознанный текст, структурированные данные)
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    b64img = base64.b64encode(image_bytes).decode()
    # Сохраняем картинку для отладки
    debug_path = "debug_ocr_image.jpg"
    with open(debug_path, "wb") as f:
        f.write(image_bytes)
    logger.info(f"[DEBUG] Картинка для OCR сохранена: {debug_path}")
    payload = _build_payload(b64img)

    # Для логирования — копия payload без base64
    safe_payload = _build_payload('[OMITTED]')
    logger.info("OpenAI payload", payload=safe_payload)

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(settings.gpt_ocr_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("OpenAI API HTTP error", status_code=e.response.status_code, payload=safe_payload, response_text=e.response.text[:500])
        raise
    except Exception as e:
        logger.error("OpenAI API error", error=str(e), payload=safe_payload)
        raise

    try:
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        
        # Разделяем результат на raw_text и parsed_data
        raw_text, parsed_json = _split_api_response(content)
        
        # Проверяем валидность JSON
        if parsed_json:
            # Преобразуем JSON-строку в словарь
            parsed_data = json.loads(parsed_json)
        else:
            # Если JSON не получен, выполняем повторную попытку парсинга
            # через отдельный вызов API для парсинга
            logger.warning("JSON parsing failed in combined response, fallback to separate parsing")
            
            # Проверяем, что есть сырой текст
            if not raw_text:
                raise ValueError("Failed to extract both raw text and JSON from API response")
                
            # Используем существующую функцию parse из gpt_parsing
            # Но импортируем её прямо здесь, чтобы избежать циклического импорта
            from app.routers.gpt_parsing import call_openai_with_retry
            parsed_data = await call_openai_with_retry(raw_text)
        
        logger.info("Combined API call successful", 
                   raw_text_length=len(raw_text), 
                   parsed_data_keys=list(parsed_data.keys()))
        
        return raw_text, parsed_data
    except Exception as e:
        logger.error("Failed to process combined API response", error=str(e), content=content[:500])
        raise RuntimeError(f"Failed to process API response: {str(e)}") from e


def _split_api_response(content: str) -> Tuple[str, Optional[str]]:
    """
    Разделяет ответ API на сырой текст и JSON.
    
    Args:
        content: Полный ответ от API
        
    Returns:
        Tuple[str, Optional[str]]: (raw_text, json_str)
    """
    # Ищем маркеры разделов
    raw_text_marker = "RAW TEXT:"
    parsed_data_marker = "PARSED DATA:"
    json_start_marker = "```json"
    json_end_marker = "```"
    
    raw_text = ""
    json_str = None
    
    # Извлекаем сырой текст
    if raw_text_marker in content:
        # Находим начало сырого текста
        raw_text_start = content.find(raw_text_marker) + len(raw_text_marker)
        
        # Находим конец сырого текста (начало следующей секции)
        raw_text_end = content.find(parsed_data_marker, raw_text_start)
        if raw_text_end == -1:  # Если секции PARSED DATA нет
            raw_text = content[raw_text_start:].strip()
        else:
            raw_text = content[raw_text_start:raw_text_end].strip()
    else:
        # Если маркер не найден, проверяем, есть ли JSON в содержимом
        json_start = content.find('{')
        json_end = content.rfind('}')
        
        if json_start != -1 and json_end != -1 and json_start < json_end:
            # Предполагаем, что всё до JSON - это сырой текст
            raw_text = content[:json_start].strip()
            # Возможно, это прямой JSON без маркеров
            json_str = content[json_start:json_end+1]
            return raw_text, json_str
        else:
            # Если JSON не найден, считаем всё сырым текстом
            raw_text = content.strip()
    
    # Извлекаем JSON
    if json_start_marker in content:
        # Находим начало JSON (после маркера)
        json_content_start = content.find(json_start_marker) + len(json_start_marker)
        
        # Находим конец JSON
        json_content_end = content.find(json_end_marker, json_content_start)
        if json_content_end != -1:
            json_str = content[json_content_start:json_content_end].strip()
    elif parsed_data_marker in content:
        # Если есть маркер PARSED DATA, но нет маркера JSON
        # Пытаемся найти JSON напрямую
        parsed_data_start = content.find(parsed_data_marker) + len(parsed_data_marker)
        json_start = content.find('{', parsed_data_start)
        json_end = content.rfind('}')
        
        if json_start != -1 and json_end != -1 and json_start < json_end:
            json_str = content[json_start:json_end+1]
    
    # Возвращаем результаты
    return raw_text, json_str


def _build_payload(image_b64: str) -> dict:
    """
    Формирует payload для OpenAI API (безопасно для логирования, если не включать base64).
    """
    return {
        "model": "gpt-4o",
        "temperature": 0,
        "max_tokens": 4096,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an OCR system that can extract structured data from invoice images. "
                    "You'll first extract the raw text from the image, then parse it into structured JSON. "
                    "Follow these steps:\n"
                    "1. Transcribe all text from the image accurately.\n"
                    "2. Parse the transcribed text to extract invoice details.\n"
                    "3. Return BOTH the raw text and structured data in this format:\n\n"
                    "RAW TEXT:\n[transcribed text goes here]\n\n"
                    "PARSED DATA:\n```json\n{\n"
                    "  \"supplier\": \"[supplier name]\",\n"
                    "  \"buyer\": \"[buyer name]\",\n"
                    "  \"date\": \"[YYYY-MM-DD]\",\n"
                    "  \"number\": \"[invoice number if available]\",\n"
                    "  \"positions\": [\n"
                    "    {\n"
                    "      \"name\": \"[item name]\",\n"
                    "      \"quantity\": [numeric value],\n"
                    "      \"unit\": \"[unit of measure]\",\n"
                    "      \"price\": [unit price],\n"
                    "      \"sum\": [total price]\n"
                    "    },\n"
                    "    ...\n"
                    "  ],\n"
                    "  \"total_sum\": [total invoice amount]\n"
                    "}\n```"
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,[OMITTED]"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract all text from this invoice image and parse the data into structured JSON."
                        ),
                    },
                ],
            }
        ],
    }


# --------------------------------------------------------------------------- #
#  MOCK-result для случаев ошибок
# --------------------------------------------------------------------------- #
_MOCK_RESULT: dict[str, object] = {
    "supplier": "[MOCK DATA] ООО Ромашка",
    "buyer": "ООО Ресторан",
    "date": "2025-01-01",
    "positions": [
        {"name": "[MOCK] Товар А", "quantity": 5, "unit": "кг", "price": 100.0, "sum": 500.0},
        {"name": "[MOCK] Товар Б", "quantity": 2, "unit": "л", "price": 200.0, "sum": 400.0},
    ],
    "total_sum": 900.0,
}


# --------------------------------------------------------------------------- #
#  Публичное API
# --------------------------------------------------------------------------- #
async def process_invoice(file_id: str, bot: Bot) -> Tuple[str, Dict[str, Any]]:
    """
    Основная функция обработки накладной (оптимизированная).
    
    Args:
        file_id: Идентификатор файла в Telegram
        bot: Экземпляр бота Aiogram
        
    Returns:
        Tuple[str, Dict[str, Any]]: (распознанный текст, структурированные данные)
        
    Raises:
        Exception: При ошибке в процессе обработки
    """
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set – using mock result")
        return "OCR MOCK (API KEY NOT SET)", dict(_MOCK_RESULT)

    logger.info("Starting combined OCR+Parsing process", file_id=file_id)
    
    try:
        # Скачиваем изображение с Telegram
        image_bytes = await download_file(bot, file_id)
        
        # Выполняем объединенный запрос
        raw_text, parsed_data = await _call_combined_api(image_bytes)
        
        logger.info("Combined OCR+Parsing successful", 
                   text_length=len(raw_text), 
                   positions_count=len(parsed_data.get("positions", [])))
        
        return raw_text, parsed_data
    except Exception as e:
        logger.exception("Combined OCR+Parsing failed", error=str(e))
        raise


async def ocr_and_parse(file_id: str, bot: Bot) -> Tuple[str, Dict[str, Any]]:
    """
    Публичный API для процессинга накладной в один запрос.
    
    Args:
        file_id: Идентификатор файла в Telegram
        bot: Экземпляр бота Aiogram
        
    Returns:
        Tuple[str, Dict[str, Any]]: (распознанный текст, структурированные данные)
    """
    try:
        return await process_invoice(file_id, bot)
    except Exception as e:
        logger.exception("Failed to process invoice", error=str(e))
        # Если произошла ошибка, возвращаем заглушки для обоих значений
        mock_text = f"[OCR FAILED: {str(e)[:100]}]"
        mock_data = dict(_MOCK_RESULT)
        mock_data["supplier"] = f"[MOCK DUE TO ERROR] {mock_data['supplier']}"
        return mock_text, mock_data
