"""Тесты для модели Product."""
import pytest
from decimal import Decimal

from app.models.product import Product
from app.models.product_name_lookup import ProductNameLookup

@pytest.mark.asyncio
async def test_product_creation(test_product):
    """Тест создания товара."""
    assert test_product.name == "Тестовый товар"
    assert test_product.code == "TEST001"
    assert test_product.unit == "шт"
    assert test_product.price == Decimal("100.50")
    assert test_product.comment == "Тестовый комментарий"

@pytest.mark.asyncio
async def test_product_string_representation(test_product):
    """Тест строкового представления товара."""
    expected = f"{test_product.name} ({test_product.code})"
    assert str(test_product) == expected

@pytest.mark.asyncio
async def test_product_name_lookup_relationship(test_product, test_product_name_lookup):
    """Тест связи товара с записями поиска по названию."""
    assert len(test_product.name_lookups) == 1
    lookup = test_product.name_lookups[0]
    assert lookup.alias == "тестовый товар"
    assert lookup.product_id == test_product.id

@pytest.mark.asyncio
async def test_product_validation(test_db):
    """Тест валидации данных товара."""
    # Тест с некорректным названием
    with pytest.raises(ValueError):
        product = Product(
            name="",  # Пустое название
            code="TEST002",
            unit="шт",
            price=Decimal("100.50")
        )
        test_db.add(product)
        await test_db.commit()

    # Тест с некорректной ценой
    with pytest.raises(ValueError):
        product = Product(
            name="Тестовый товар 2",
            code="TEST003",
            unit="шт",
            price=Decimal("-100.50")  # Отрицательная цена
        )
        test_db.add(product)
        await test_db.commit()

@pytest.mark.asyncio
async def test_product_unique_code(test_db, test_product):
    """Тест уникальности кода товара."""
    # Пытаемся создать товар с существующим кодом
    duplicate_product = Product(
        name="Другой товар",
        code=test_product.code,  # Используем существующий код
        unit="шт",
        price=Decimal("200.00")
    )
    test_db.add(duplicate_product)
    with pytest.raises(Exception):  # Ожидаем ошибку уникальности
        await test_db.commit()

@pytest.mark.asyncio
async def test_product_cascade_delete(test_db, test_product, test_product_name_lookup):
    """Тест каскадного удаления записей поиска при удалении товара."""
    product_id = test_product.id
    lookup_id = test_product_name_lookup.id
    
    # Удаляем товар
    await test_db.delete(test_product)
    await test_db.commit()
    
    # Проверяем, что товар удален
    deleted_product = await test_db.get(Product, product_id)
    assert deleted_product is None
    
    # Проверяем, что запись поиска также удалена
    deleted_lookup = await test_db.get(ProductNameLookup, lookup_id)
    assert deleted_lookup is None 