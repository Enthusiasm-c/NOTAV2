import base64
import structlog
import httpx
from aiogram import Bot
from app.config import settings

logger = structlog.get_logger()

async def ocr(file_id: str, bot: Bot) -> str:
    """Скачивает фото из Telegram и отправляет в OpenAI Vision GPT."""
    logger.info("Starting OCR", file_id=file_id)

    # 1. скачать файл
    tg_file = await bot.get_file(file_id)
    async with bot.download_file(tg_file.file_path) as stream:
        image_bytes = await stream.read()

    # 2. если нет ключа — мок-ответ
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY missing, returning stub text")
        return "stub: supplier ООО Ромашка ... positions 1 шт"

    # 3. подготовить payload Vision-GPT
    b64img = base64.b64encode(image_bytes).decode()
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64img}"},
                    }
                ],
            }
        ],
    }

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    # 4. запрос
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(settings.gpt_ocr_url, json=payload, headers=headers)
        r.raise_for_status()

    raw_text = (
        r.json()
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )

    logger.info("OCR done", snippet=raw_text[:80])
    return raw_text
