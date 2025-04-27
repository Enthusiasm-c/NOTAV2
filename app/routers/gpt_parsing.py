# app/routers/gpt_parsing.py
"""
Invoice-parser for Nota V2.

• Берёт raw-text (результат OCR) и преобразует его
  в структуру {supplier, buyer, date, positions[], total_sum}.
• Если переменная окружения GPT_PARSING_URL пустая — возвращает mock-JSON,
  чтобы бот работал оффлайн и в CI.
• Работает через OpenAI ChatCompletion (или совместимый прокси) асинхронно.
"""

from __future__ import annotations

import json
import structlog
import httpx

from app.config import settings

logger = structlog.get_logger()


# --------------------------------------------------------------------------- #
#  MOCK-результат, используемый при отсут­ствии GPT_PARSING_URL или в случае
#  ошибки сети.  dict() ↦ возвращаем копию — чтобы кто-то случайно не мутировал
#  глобальный объект между вызовами.
# --------------------------------------------------------------------------- #
_MOCK_RESULT: dict[str, object] = {
    "supplier": "ООО Ромашка",
    "buyer": "ООО Ресторан",
    "date": "2025-01-01",
    "positions": [
        {"name": "Товар А", "quantity": 5, "unit": "кг", "price": 100.0, "sum": 500.0},
        {"name": "Товар Б", "quantity": 2, "unit": "л", "price": 200.0, "sum": 400.0},
    ],
    "total_sum": 900.0,
}


# --------------------------------------------------------------------------- #
#  PUBLIC API
# --------------------------------------------------------------------------- #
async def parse(raw_text: str) -> dict[str, object]:
    """Возвращает структурированный JSON-словарь или mock-данные."""
    logger.info("Start parsing", snippet=raw_text[:80])

    # ── offline / CI режим ─────────────────────────────────────────────────
    if not settings.gpt_parsing_url:
        logger.warning("gpt_parsing_url not set – return mock result")
        return dict(_MOCK_RESULT)

    # ── собираем request к OpenAI (или прокси) ─────────────────────────────
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

    # ── HTTP-запрос ─────────────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                settings.gpt_parsing_url, json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()

        # OpenAI-совместимый разбор: content содержит JSON-строку
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        parsed: dict[str, object] = json.loads(content)
        logger.info("Parsing OK", positions=len(parsed.get("positions", [])))
        return parsed

    # ── сетевые / форматные ошибки → лог и mock ────────────────────────────
    except Exception as exc:
        logger.error("Parsing failed, return mock", error=str(exc))
        return dict(_MOCK_RESULT)
