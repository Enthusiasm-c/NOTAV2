# app/routers/gpt_ocr.py
"""
OCR-модуль Nota V2
──────────────────
* Загружает фото из Telegram.
* Отправляет base64-картинку в OpenAI Vision (gpt-4o-mini по-умолчанию).
* Возвращает raw-text или возбуждает исключение — чтобы бот показал
  понятную ошибку, а не «заглушку».

Ифы-фоллбэки «вернуть stub» убраны: теперь при любой сетевой / JSON-ошибке
вы увидите stack-trace в journalctl.

Требует:
    OPENAI_API_KEY          — обязательный
    GPT_OCR_URL             — по-умолчанию https://api.openai.com/v1/chat/completions
"""

from __future__ import annotations

import base64
import httpx
import structlog
from aiogram import Bot
from aiogram.types import File

from app.config import settings

logger = structlog.get_logger()


async def _tg_download(bot: Bot, file_id: str) -> bytes:
    """Скачиваем файл из Telegram, возвращаем bytes."""
    tg_file: File = await bot.get_file(file_id)
    async with bot.download_file(tg_file.file_path) as stream:
        return await stream.read()


async def ocr(file_id: str, bot: Bot) -> str:
    """
    Основной вызов: telegram-file-id → raw text.

    Исключения не «глотаются» — пусть всплывают до хендлера,
    чтобы их логировал и Telegram-бот, и systemd-journal.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY не задан — OCR невозможен")

    logger.info("OCR start", file_id=file_id)
    image_bytes = await _tg_download(bot, file_id)

    b64img = base64.b64encode(image_bytes).decode()
    payload = {
        "model": "gpt-4o-mini",
        "temperature": 0,
        "max_tokens": 4096,
        # response_format — просим только текст
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64img}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Сделай OCR. Верни чистый текст без комментариев, "
                            "языка разметки или JSON."
                        ),
                    },
                ],
            }
        ],
    }

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(settings.gpt_ocr_url, json=payload, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPStatusError as err:
        logger.error(
            "OCR HTTP error",
            status=err.response.status_code,
            body=err.response.text[:300],
        )
        raise
    except Exception as exc:
        logger.exception("OCR transport error", exc_info=exc)
        raise

    try:
        raw_text = (
            resp.json()["choices"][0]["message"]["content"].strip()
        )
    except (KeyError, ValueError) as exc:
        logger.error("OCR JSON structure unexpected", body=resp.text[:400])
        raise RuntimeError("OpenAI вернул некорректный ответ") from exc

    logger.info("OCR done", snippet=raw_text[:120])
    return raw_text
