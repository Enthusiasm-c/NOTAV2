__all__ = ["call_gpt_ocr"]

import httpx
from ..config import settings

async def call_gpt_ocr(image_bytes: bytes) -> str:
    """Вызывает GPT-4.0 OCR API (или mock),
    возвращает raw text"""
    headers = {"Authorization": "Bearer FAKE_KEY"}
    files = {"image": ("invoice.jpg", image_bytes)}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(settings.gpt_ocr_url, files=files, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data["raw_text"]
    except Exception:
        # Mock: просто возвращаем текст "Recognized Text"
        return "Sample OCR invoice: Supplier: ООО Ромашка; Date: 2025-04-10; ..."
