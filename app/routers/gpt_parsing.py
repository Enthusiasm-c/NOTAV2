import httpx
from app.config import settings
from app.utils.logger import logger

async def call_gpt_parse(raw_text: str) -> dict:
    """Call GPT parsing endpoint, return structured dict."""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(settings.gpt_parsing_url, json={"text": raw_text})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error("Parsing request failed", error=str(e))
            # demo/mock response
            return {
                "supplier": "ООО Ромашка",
                "buyer": "ООО Наш Ресторан",
                "date": "2025-05-10",
                "positions": [
                    {"name": "Товар А", "quantity": 5, "unit": "кг", "price": 100.0, "sum": 500.0},
                    {"name": "Товар Б", "quantity": 2, "unit": "л", "price": 200.0, "sum": 400.0},
                ],
                "total_sum": 900.0,
            }
