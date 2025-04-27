# app/routers/gpt_ocr.py
"""
OCR-модуль Nota V2.

* При наличии OPENAI_API_KEY и корректного GPT_OCR_URL
  отправляет фото накладной в Vision GPT (Chat Completion с image_url)
  и возвращает raw-text.
* Если ключа или URL нет, либо возникает любая сетевая ошибка,
  возвращает заглушку, чтобы бот продолжал работать.

Логи:
  • DEBUG — детали запроса (есть ли ключ, какой URL);
  • INFO   — удачное завершение (`OCR done snippet=…`);
  • ERROR  — стек-трейс при любой ошибке.
"""

from __future__ import annotations

import base64
import structlog
import httpx
from aiogram import Bot

from app.config import settings

logger = structlog.get_logger()


async def ocr(file_id: str, bot: Bot) -> str:
    """Скачивает фото из Telegram и отправляет в Vision-GPT."""
    logger.info("Starting OCR", file_id=file_id)

    # ── DEBUG: показываем, что бот «видит» из .env ─────────────────────
    logger.debug("OCR key present: %s", bool(settings.openai_api_key))
    logger.debug("OCR url        : %s", settings.gpt_ocr_url)

    # 1. скачать файл из Telegram
    tg_file = await bot.get_file(file_id)
    async with bot.download_file(tg_file.file_path) as stream:
        image_bytes = await stream.read()

    # 2. если нет ключа — вернуть stub
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY missing, returning stub text")
        return "stub: supplier ООО Ромашка ... positions 1 шт"

    # 3. сформировать payload Vision-GPT
    b64img = base64.b64encode(image_bytes).decode()
    payload = {
        "model": "gpt-4o-mini",
        "temperature": 0,
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

    # 4. запрос к OpenAI / прокси
    try:
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

        logger.info("OCR done", snippet=raw_text[:120])
        return raw_text

    # 5. любая ошибка → лог + stub
    except Exception:
        logger.exception("OCR failed")        # полный стек-трейс
        return "stub: supplier ООО Ромашка ... positions 1 шт"
