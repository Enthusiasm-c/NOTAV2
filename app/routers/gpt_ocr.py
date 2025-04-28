"""
OCR module for Nota V2
──────────────────
* Downloads photo from Telegram.
* Sends base64-encoded image to OpenAI Vision (gpt-4o by default).
* Returns raw-text or raises an exception — so the bot can show
  a clear error, not a "stub".

If-fallbacks "return stub" are removed: now with any network / JSON error
you will see a stack-trace in journalctl.

Requires:
    OPENAI_API_KEY          — mandatory
    GPT_OCR_URL             — default is https://api.openai.com/v1/chat/completions
    
Note: This module now uses the optimized combined OCR+Parsing module internally.
"""

from __future__ import annotations

import base64
import httpx
import structlog
from aiogram import Bot
from aiogram.types import File
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.config import settings
from app.routers.gpt_combined import ocr_and_parse

logger = structlog.get_logger()


# ───────── app/routers/gpt_ocr.py ─────────────────────────────────────────
async def _tg_download(bot: Bot, file_id: str) -> bytes:
    """
    Download file from Telegram and return bytes.

    aiogram-3:
        tg_file = await bot.get_file(file_id)
        stream  = await bot.download_file(tg_file.file_path)   # coroutine → BytesIO
    """
    tg_file = await bot.get_file(file_id)
    stream  = await bot.download_file(tg_file.file_path)  # <-- await, without async with
    return stream.read()                                  # BytesIO → bytes


@retry(
    # Retry only on 5xx and network errors
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.NetworkError)),
    wait=wait_exponential_jitter(initial=1, max=30),  # 1s, 2s, 4s... + jitter
    stop=stop_after_attempt(6),                       # ≤ 6 attempts
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        f"OCR API call failed, retrying in {retry_state.next_action.sleep} seconds "
        f"(attempt {retry_state.attempt_number}/{6})",
        error=str(retry_state.outcome.exception())
    ),
)
async def _call_openai_vision(image_bytes: bytes) -> str:
    """
    Legacy function for direct OpenAI Vision API calls.
    Kept for compatibility and as a fallback.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set – OCR is not possible")

    b64img = base64.b64encode(image_bytes).decode()
    payload = {
        "model": "gpt-4o",
        "temperature": 0,
        "max_tokens": 4096,
        # response_format — ask for text only
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
                            "Do OCR. Return clean text without comments, "
                            "markup or JSON."
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

    async with httpx.AsyncClient(timeout=60) as client:  # Increased timeout
        resp = await client.post(settings.gpt_ocr_url, json=payload, headers=headers)
        resp.raise_for_status()  # Will raise HTTPStatusError for 4xx/5xx responses
        data = resp.json()

    try:
        raw_text = (
            data["choices"][0]["message"]["content"].strip()
        )
    except (KeyError, ValueError) as exc:
        logger.error("OCR JSON structure unexpected", body=data)
        raise RuntimeError("OpenAI returned invalid response") from exc

    logger.info("OCR done", snippet=raw_text[:120])
    return raw_text


async def ocr(file_id: str, bot: Bot) -> str:
    """
    Main call: telegram-file-id → raw text.
    
    Now uses the optimized combined OCR+Parsing module internally,
    but still returns only the raw text for compatibility.

    Exceptions are not "swallowed" — let them bubble up to the handler,
    so they can be logged by both the Telegram bot and systemd-journal.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set – OCR is not possible")

    logger.info("OCR start", file_id=file_id)
    
    try:
        # Use the combined OCR+Parsing module
        raw_text, _ = await ocr_and_parse(file_id, bot)
        return raw_text
    except Exception as e:
        logger.error("Combined OCR failed, fallback to direct OCR", error=str(e))
        # Fallback to direct OCR if combined fails
        image_bytes = await _tg_download(bot, file_id)
        return await _call_openai_vision(image_bytes)
