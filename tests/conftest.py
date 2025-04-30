"""Фикстуры для тестов."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.base import Base
from app.config.database import SessionLocal
from app.models.supplier import Supplier
from app.models.invoice import Invoice

# Используем in-memory SQLite для тестов
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Создает новый event loop для тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    """Создает тестовую базу данных."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Создает тестовую сессию базы данных."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
def override_get_db(test_db: AsyncSession):
    """Переопределяет зависимость get_db для тестов."""
    async def _override_get_db():
        yield test_db
    
    return _override_get_db

@pytest.fixture
async def test_supplier(test_db: AsyncSession) -> Supplier:
    """Создает тестового поставщика."""
    supplier = Supplier(
        name="Тестовый поставщик",
        inn="1234567890",
        kpp="123456789",
        address="г. Москва, ул. Тестовая, д. 1",
        phone="+7 (999) 123-45-67",
        email="test@example.com",
        comment="Тестовый комментарий"
    )
    test_db.add(supplier)
    await test_db.commit()
    await test_db.refresh(supplier)
    return supplier

@pytest.fixture
async def test_invoice(test_db: AsyncSession, test_supplier: Supplier) -> Invoice:
    """Создает тестовый счет."""
    invoice = Invoice(
        number="TEST-001",
        supplier_id=test_supplier.id,
        comment="Тестовый счет"
    )
    test_db.add(invoice)
    await test_db.commit()
    await test_db.refresh(invoice)
    return invoice 