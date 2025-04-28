#!/usr/bin/env python
"""
Скрипт для создания всех таблиц в базе данных.
Использует SQLAlchemy, минуя Alembic.
"""

import asyncio
from app.models import Base
from app.db import engine

async def create_all_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Все таблицы созданы")

if __name__ == "__main__":
    asyncio.run(create_all_tables())
