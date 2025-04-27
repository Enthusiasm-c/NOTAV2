__all__ = ["fuzzy_match_product"]

from rapidfuzz import fuzz, process
from sqlalchemy import select
from ..models.product import Product

async def fuzzy_match_product(session, parsed_name: str, threshold: float = 0.9):
    """Fuzzy-сопоставление parsed_name с продуктами.
    Возвращает (product_id, confidence), если найдено;
    иначе None"""
    result = await session.execute(select(Product.id, Product.name))
    products = result.all()
    candidates = [(row.id, row.name) for row in products]
    # Используем rapidfuzz для сравнения
    matches = process.extract(
        parsed_name,
        [c[1] for c in candidates],
        scorer=fuzz.ratio,
        limit=1,
    )
    if matches:
        best_name, confidence, idx = matches[0]
        if confidence / 100.0 >= threshold:
            product_id = candidates[idx][0]
            return product_id, confidence / 100.0
    return None, 0.0
