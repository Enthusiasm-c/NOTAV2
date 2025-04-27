# app/routers/fuzzy_match.py
"""
Поиск товара по не-чёткому названию.

Алгоритм:
1. Сначала пытаемся найти точное соответствие в таблице `invoice_name_lookup`
   (ранее подтверждённая пара «распознанное название → product_id»).
   Если нашли — возвращаем (product_id, 1.0).

2. Если lookup не сработал — загружаем список (id, name) всех товаров
   из таблицы `products` и ищем ближайшее совпадение через RapidFuzz
   (`fuzz.ratio`).  Порог совпадения берём из settings.fuzzy_threshold
   (по умолчанию 0.85).

Возвращаем кортеж `(product_id | None, confidence 0–1)`.
"""

from __future__ import annotations

from typing import Tuple, Optional

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.invoice_name_lookup import InvoiceNameLookup
from app.models.product import Product


async def fuzzy_match_product(
    session: AsyncSession,
    parsed_name: str,
    threshold: float | None = None,
) -> Tuple[Optional[int], float]:
    """
    Поиск товара по распознанному названию.

    :param session: асинхронная сессия SQLAlchemy
    :param parsed_name: строка из OCR/Parsing
    :param threshold: кастомный порог RapidFuzz (0–1); если None → settings
    :return: (product_id | None, confidence 0–1)
    """

    threshold = threshold or settings.fuzzy_threshold

    # ───────────────────────── 1. lookup по памяти ────────────────────────
    res = await session.execute(
        select(InvoiceNameLookup.product_id).where(
            InvoiceNameLookup.parsed_name == parsed_name
        )
    )
    product_id = res.scalar_one_or_none()
    if product_id is not None:
        return product_id, 1.0

    # ──────────────────────── 2. RapidFuzz по каталогу ────────────────────
    rows = await session.execute(select(Product.id, Product.name))
    candidates = list(rows)  # [(id, name), …]

    if not candidates:  # пустой каталог
        return None, 0.0

    names = [name for _, name in candidates]
    match = process.extractOne(parsed_name, names, scorer=fuzz.ratio)

    if match:
        matched_name, score_raw = match  # score_raw 0–100
        confidence = score_raw / 100.0
        if confidence >= threshold:
            # Находим product_id по имени
            product_id = next(pid for pid, name in candidates if name == matched_name)
            return product_id, confidence

    # ничего не подошло с нужным порогом
    return None, 0.0
