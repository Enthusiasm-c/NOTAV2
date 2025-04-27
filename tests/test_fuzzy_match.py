import asyncio
import pytest
from app.routers.fuzzy_match import fuzzy_match_product
from app.db import SessionLocal, Base, engine
from app.models.product import Product
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@pytest.mark.asyncio
async def test_fuzzy_match_product():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        p = Product(name="Молоко 2.5% л", unit="л")
        session.add(p)
        await session.commit()
        r_id, confidence = await fuzzy_match_product(session, "молоко 2,5 %")
        assert r_id == p.id
        assert confidence >= 0.85
