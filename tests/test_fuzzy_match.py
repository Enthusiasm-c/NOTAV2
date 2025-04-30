"""
Тесты для модуля нечеткого поиска.
"""

import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.routers.fuzzy_match import fuzzy_match_product, find_similar_products
from app.config.database import get_engine_and_session, Base
from app.models.product import Product


@pytest.mark.asyncio
async def test_fuzzy_match_product():
    engine, SessionLocal = get_engine_and_session()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        p = Product(name="Молоко 2.5% л", unit="л")
        session.add(p)
        await session.commit()
        r_id, confidence = await fuzzy_match_product(session, "молоко 2,5 %")
        assert r_id == p.id
        assert confidence >= 0.85
