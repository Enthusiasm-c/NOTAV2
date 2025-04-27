from rapidfuzz import process, fuzz
from sqlalchemy import select
from app.models.product import Product

async def fuzzy_match_product(session, parsed_name: str, threshold=0.85):
    """Fuzzy matches product names in db, returns product_id and confidence."""
    result = await session.execute(select(Product.id, Product.name, Product.unit))
    products = result.fetchall()
    candidates = [(row.id, row.name) for row in products]
    if not candidates:
        return None, 0.0
    match = process.extractOne(parsed_name, [c[1] for c in candidates], scorer=fuzz.ratio)
    if match and match[1] / 100.0 >= threshold:
        idx = [c[1] for c in candidates].index(match[0])
        product_id = candidates[idx][0]
        return product_id, match[1] / 100.0
    return None, 0.0
