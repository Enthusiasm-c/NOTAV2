"""Интеграционные тесты для проверки взаимодействия моделей."""
import pytest
from decimal import Decimal
from datetime import date

from app.models.supplier import Supplier
from app.models.product import Product
from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.product_name_lookup import ProductNameLookup

@pytest.mark.asyncio
async def test_full_invoice_creation_flow(test_db):
    """Тест полного процесса создания счета."""
    # Создаем поставщика
    supplier = Supplier(
        name="Тестовый поставщик",
        inn="1234567890",
        kpp="123456789",
        address="г. Москва, ул. Тестовая, д. 1",
        phone="+7 (999) 123-45-67",
        email="test@example.com"
    )
    test_db.add(supplier)
    await test_db.commit()

    # Создаем товары
    products = [
        Product(
            name="Товар 1",
            code="TEST001",
            unit="шт",
            price=Decimal("100.50")
        ),
        Product(
            name="Товар 2",
            code="TEST002",
            unit="шт",
            price=Decimal("200.75")
        )
    ]
    for product in products:
        test_db.add(product)
    await test_db.commit()

    # Создаем записи поиска для товаров
    lookups = [
        ProductNameLookup(
            alias="товар один",
            product_id=products[0].id
        ),
        ProductNameLookup(
            alias="товар два",
            product_id=products[1].id
        )
    ]
    for lookup in lookups:
        test_db.add(lookup)
    await test_db.commit()

    # Создаем счет
    invoice = Invoice(
        number="TEST-001",
        date=date(2024, 3, 20),
        supplier_id=supplier.id,
        comment="Тестовый счет"
    )
    test_db.add(invoice)
    await test_db.commit()

    # Создаем позиции счета
    items = [
        InvoiceItem(
            invoice_id=invoice.id,
            product_id=products[0].id,
            name="Товар 1",
            quantity=Decimal("10"),
            unit="шт",
            price=Decimal("100.50")
        ),
        InvoiceItem(
            invoice_id=invoice.id,
            product_id=products[1].id,
            name="Товар 2",
            quantity=Decimal("5"),
            unit="шт",
            price=Decimal("200.75")
        )
    ]
    for item in items:
        test_db.add(item)
    await test_db.commit()

    # Проверяем созданные данные
    assert len(invoice.items) == 2
    assert invoice.supplier.name == "Тестовый поставщик"
    
    total_amount = sum(item.quantity * item.price for item in invoice.items)
    expected_total = Decimal("10") * Decimal("100.50") + Decimal("5") * Decimal("200.75")
    assert total_amount == expected_total

@pytest.mark.asyncio
async def test_product_search_by_alias(test_db):
    """Тест поиска товаров по алиасам."""
    # Создаем товар
    product = Product(
        name="Тестовый товар",
        code="TEST001",
        unit="шт",
        price=Decimal("100.50")
    )
    test_db.add(product)
    await test_db.commit()

    # Создаем несколько алиасов для товара
    aliases = [
        "тестовый товар",
        "тест товар",
        "товар тест",
        "тест"
    ]
    for alias in aliases:
        lookup = ProductNameLookup(
            alias=alias,
            product_id=product.id
        )
        test_db.add(lookup)
    await test_db.commit()

    # Проверяем поиск по разным алиасам
    for alias in aliases:
        result = await test_db.query(ProductNameLookup).filter(
            ProductNameLookup.alias.ilike(f"%{alias}%")
        ).first()
        assert result is not None
        assert result.product_id == product.id

@pytest.mark.asyncio
async def test_cascade_delete_flow(test_db):
    """Тест каскадного удаления связанных данных."""
    # Создаем поставщика
    supplier = Supplier(
        name="Тестовый поставщик",
        inn="1234567890",
        kpp="123456789"
    )
    test_db.add(supplier)
    await test_db.commit()

    # Создаем товар
    product = Product(
        name="Тестовый товар",
        code="TEST001",
        unit="шт",
        price=Decimal("100.50")
    )
    test_db.add(product)
    await test_db.commit()

    # Создаем запись поиска
    lookup = ProductNameLookup(
        alias="тестовый товар",
        product_id=product.id
    )
    test_db.add(lookup)
    await test_db.commit()

    # Создаем счет
    invoice = Invoice(
        number="TEST-001",
        date=date(2024, 3, 20),
        supplier_id=supplier.id
    )
    test_db.add(invoice)
    await test_db.commit()

    # Создаем позицию счета
    item = InvoiceItem(
        invoice_id=invoice.id,
        product_id=product.id,
        name="Тестовый товар",
        quantity=Decimal("10"),
        unit="шт",
        price=Decimal("100.50")
    )
    test_db.add(item)
    await test_db.commit()

    # Удаляем поставщика
    await test_db.delete(supplier)
    await test_db.commit()

    # Проверяем, что все связанные данные удалены
    assert await test_db.get(Invoice, invoice.id) is None
    assert await test_db.get(InvoiceItem, item.id) is None

    # Удаляем товар
    await test_db.delete(product)
    await test_db.commit()

    # Проверяем, что запись поиска удалена
    assert await test_db.get(ProductNameLookup, lookup.id) is None 