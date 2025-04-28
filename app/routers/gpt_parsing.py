"""
Invoice-parser for Nota V2.

• Takes raw-text (OCR result) and transforms it
  into a structure {supplier, buyer, date, positions[], total_sum}.
• If the GPT_PARSING_URL environment variable is empty — returns mock-JSON,
  to make the bot work offline and in CI.
• Works through OpenAI ChatCompletion (or compatible proxy) asynchronously.

Note: This module now uses the optimized combined OCR+Parsing module internally
when possible.
"""

from __future__ import annotations

import json
import structlog
import httpx
import asyncio
import random
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.config import settings
from app.routers.gpt_combined import ocr_and_parse

logger = structlog.get_logger()


# --------------------------------------------------------------------------- #
#  MOCK-result, used when GPT_PARSING_URL is not set or in case of
#  network error.  dict() ↦ return a copy — so that someone doesn't accidentally mutate
#  the global object between calls.
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
#  PUBLIC API
# --------------------------------------------------------------------------- #
async def parse(raw_text: str, file_id: str = None, bot = None) -> dict[str, object]:
    """
    Returns a structured JSON dictionary or mock data.
    
    If file_id and bot are provided, uses the optimized combined OCR+Parsing.
    Otherwise, performs only parsing on the provided raw_text.
    """
    logger.info("Start parsing", snippet=raw_text[:80])

    # ── offline / CI mode ─────────────────────────────────────────────────
    if not settings.gpt_parsing_url:
        logger.warning("gpt_parsing_url not set – return mock result")
        return dict(_MOCK_RESULT)
    
    # If file_id and bot are provided, use the combined OCR+Parsing
    if file_id and bot:
        try:
            # Get both raw text and parsed data in one call
            _, parsed_data = await ocr_and_parse(file_id, bot)
            logger.info("Combined OCR+Parsing successful", 
                       positions=len(parsed_data.get("positions", [])))
            return parsed_data
        except Exception as e:
            logger.error("Combined OCR+Parsing failed, fallback to parsing-only", error=str(e))
            # Fallback to parsing-only if combined fails
    
    # Standard parsing-only path
    try:
        # Call OpenAI with retry logic
        parsed = await call_openai_with_retry(raw_text)
        logger.info("Parsing OK", positions=len(parsed.get("positions", [])))
        return parsed
    except Exception as exc:
        logger.error("Parsing failed, return mock", error=str(exc))
        # Return mock with a clear indication it's a mock due to error
        mock_data = dict(_MOCK_RESULT)
        mock_data["supplier"] = f"[MOCK - API ERROR] {mock_data['supplier']}"
        return mock_data


@retry(
    # Retry on 5xx and network errors
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
async def call_openai_with_retry(raw_text: str) -> dict[str, object]:
    """Call OpenAI API with retry logic for handling temporary failures."""
    # ── prepare OpenAI (or proxy) request ─────────────────────────────────
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.openai_api_key:
        headers["Authorization"] = f"Bearer {settings.openai_api_key}"

    payload = {
        "model": "gpt-4o-mini",
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a parser that extracts invoice data from plain text. "
                    "Return STRICTLY valid JSON with the following top-level keys:\n"
                    "supplier, buyer, date, positions (array of {name, quantity, unit, price, sum}), "
                    "total_sum.\nDo not wrap the JSON in markdown or natural language."
                ),
            },
            {"role": "user", "content": raw_text},
        ],
    }

    # ── HTTP request ─────────────────────────────────────────────────────────
    async with httpx.AsyncClient(timeout=60) as client:  # Increased timeout
        resp = await client.post(
            settings.gpt_parsing_url, json=payload, headers=headers
        )
        resp.raise_for_status()  # Will raise HTTPStatusError for 4xx/5xx responses
        data = resp.json()

    # OpenAI-compatible parsing: content contains JSON string
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )

    parsed: dict[str, object] = json.loads(content)
    return parsed
