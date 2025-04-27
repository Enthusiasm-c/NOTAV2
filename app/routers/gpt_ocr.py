import httpx
from app.config import settings
from app.utils.logger import logger

async def call_gpt_ocr(image_bytes: bytes) -> str:
    """Call GPT-OCR Vision endpoint, return recognized raw text."""
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            r = await client.post(settings.gpt_ocr_url, files={"image": ("invoice.jpg", image_bytes)})
            r.raise_for_status()
            return r.json()["raw_text"]
        except Exception as e:
            logger.error("OCR request failed", error=str(e))
            return "Ошибка OCR"  # fallback for demo/mock
