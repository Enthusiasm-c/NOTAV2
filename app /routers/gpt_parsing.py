__all__ = ["call_gpt_parse"]

import httpx
from ..config import settings

async def call_gpt_parse(raw_text: str) -> dict:
    """Вызывает GPT-4.0 для парсинга,
    возвращает структурированный dict"""
    headers = {"Authorization": "Bearer FAKE_KEY"}
    json = {"text": raw_text}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(settings.gpt_parsing_url, json=json, headers=headers)
            r.raise_for_status()
            return r.json()
    except Exception:
        # Mock: возвращаем пример структуры
        return {
            "supplier_name": "ООО Ромашка",
            "buyer_name": "ООО Наш Ресторан",
            "date": "2025-04-10",
            "positions": [
                {"name": "Товар А", "quantity": 5, "unit": "кг", "price": 100.0, "sum": 500.0},
                {"name": "Товар Б", "quantity": 2, "unit": "л", "price": 200.0, "sum": 400.0},
            ],
            "total_sum": 900.0,
        }
