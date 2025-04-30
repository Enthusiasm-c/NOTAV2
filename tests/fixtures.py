"""Фикстуры для тестов."""

import asyncio
from typing import AsyncGenerator, Dict, List

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from tests.test_utils import create_test_data

# URL для тестовой базы данных
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Создаем движок для тестовой базы данных
test_engine = create_async_engine(TEST_DATABASE_URL, echo=True)

# Создаем фабрику сессий для тестовой базы данных
TestSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Создает новый event loop для тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Создает тестовую базу данных."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Создает сессию для тестовой базы данных."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_data(test_db) -> Dict[str, List]:
    """Создает тестовые данные."""
    return await create_test_data(test_db)


@pytest.fixture
async def test_supplier(test_db) -> AsyncGenerator[AsyncSession, None]:
    """Создает тестового поставщика."""
    from tests.test_utils import create_test_supplier

    supplier = await create_test_supplier(test_db)
    yield supplier
    await test_db.delete(supplier)
    await test_db.commit()


@pytest.fixture
async def test_product(test_db) -> AsyncGenerator[AsyncSession, None]:
    """Создает тестовый продукт."""
    from tests.test_utils import create_test_product

    product = await create_test_product(test_db)
    yield product
    await test_db.delete(product)
    await test_db.commit()


@pytest.fixture
async def test_product_alias(test_db, test_product) -> AsyncGenerator[AsyncSession, None]:
    """Создает тестовый алиас продукта."""
    from tests.test_utils import create_test_product_alias

    product_alias = await create_test_product_alias(
        test_db, product_id=test_product.id
    )
    yield product_alias
    await test_db.delete(product_alias)
    await test_db.commit()


@pytest.fixture
async def test_invoice(test_db, test_supplier) -> AsyncGenerator[AsyncSession, None]:
    """Создает тестовую накладную."""
    from tests.test_utils import create_test_invoice

    invoice = await create_test_invoice(
        test_db, supplier_id=test_supplier.id
    )
    yield invoice
    await test_db.delete(invoice)
    await test_db.commit()


@pytest.fixture
async def test_invoice_item(
    test_db, test_invoice, test_product
) -> AsyncGenerator[AsyncSession, None]:
    """Создает тестовую позицию накладной."""
    from tests.test_utils import create_test_invoice_item

    invoice_item = await create_test_invoice_item(
        test_db,
        invoice_id=test_invoice.id,
        product_id=test_product.id,
    )
    yield invoice_item
    await test_db.delete(invoice_item)
    await test_db.commit() 