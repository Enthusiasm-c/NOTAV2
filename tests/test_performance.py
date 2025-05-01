"""Тесты производительности для проверки скорости работы с базой данных."""
import pytest
import time
from decimal import Decimal
from datetime import date

from app.models.supplier import Supplier
from app.models.product import Product
from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.product_name_lookup import ProductNameLookup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

@pytest.mark.asyncio
async def test_bulk_insert_performance(test_db):
    """Тест производительности массового добавления данных."""
    # Подготовка данных
    suppliers = [
        Supplier(
            name=f"Поставщик {i}",
            inn=f"123456789{i}",
            kpp=f"12345678{i}"
        )
        for i in range(100)
    ]
    
    products = [
        Product(
            name=f"Товар {i}",
            code=f"TEST{i:03d}",
            unit="шт",
            price=Decimal("100.50")
        )
        for i in range(1000)
    ]
    
    # Измеряем время добавления поставщиков
    start_time = time.time()
    for supplier in suppliers:
        test_db.add(supplier)
    await test_db.commit()
    supplier_time = time.time() - start_time
    
    # Измеряем время добавления товаров
    start_time = time.time()
    for product in products:
        test_db.add(product)
    await test_db.commit()
    product_time = time.time() - start_time
    
    # Проверяем, что время добавления не превышает разумные пределы
    assert supplier_time < 1.0  # Менее 1 секунды для 100 поставщиков
    assert product_time < 5.0   # Менее 5 секунд для 1000 товаров

@pytest.mark.asyncio
async def test_search_performance(test_db):
    """Тест производительности поиска."""
    # Создаем тестовые данные
    product = Product(
        name="Тестовый товар",
        code="TEST001",
        unit="шт",
        price=Decimal("100.50")
    )
    test_db.add(product)
    await test_db.commit()
    
    # Создаем множество алиасов
    aliases = [f"тестовый товар {i}" for i in range(100)]
    lookups = [
        ProductNameLookup(
            alias=alias,
            product_id=product.id
        )
        for alias in aliases
    ]
    
    for lookup in lookups:
        test_db.add(lookup)
    await test_db.commit()
    
    # Измеряем время поиска
    start_time = time.time()
    for alias in aliases:
        result = await test_db.query(ProductNameLookup).filter(
            ProductNameLookup.alias.ilike(f"%{alias}%")
        ).first()
        assert result is not None
    search_time = time.time() - start_time
    
    # Проверяем, что время поиска не превышает разумные пределы
    assert search_time < 2.0  # Менее 2 секунд для 100 поисковых запросов

@pytest.mark.asyncio
async def test_invoice_calculation_performance(test_db):
    """Тест производительности расчета сумм в счетах."""
    # Создаем поставщика
    supplier = Supplier(
        name="Тестовый поставщик",
        inn="1234567890",
        kpp="123456789"
    )
    test_db.add(supplier)
    await test_db.commit()
    
    # Создаем товары
    products = [
        Product(
            name=f"Товар {i}",
            code=f"TEST{i:03d}",
            unit="шт",
            price=Decimal("100.50")
        )
        for i in range(100)
    ]
    for product in products:
        test_db.add(product)
    await test_db.commit()
    
    # Создаем счет с большим количеством позиций
    invoice = Invoice(
        number="TEST-001",
        date=date(2024, 3, 20),
        supplier_id=supplier.id
    )
    test_db.add(invoice)
    await test_db.commit()
    
    # Создаем позиции счета
    items = [
        InvoiceItem(
            invoice_id=invoice.id,
            product_id=product.id,
            name=product.name,
            quantity=Decimal("10"),
            unit="шт",
            price=product.price
        )
        for product in products
    ]
    
    # Измеряем время добавления позиций
    start_time = time.time()
    for item in items:
        test_db.add(item)
    await test_db.commit()
    insert_time = time.time() - start_time
    
    # Измеряем время расчета общей суммы
    start_time = time.time()
    total_amount = sum(item.quantity * item.price for item in invoice.items)
    calculation_time = time.time() - start_time
    
    # Проверяем, что время операций не превышает разумные пределы
    assert insert_time < 3.0  # Менее 3 секунд для добавления 100 позиций
    assert calculation_time < 0.1  # Менее 100 мс для расчета суммы

@pytest.mark.asyncio
async def test_concurrent_operations_performance(test_db):
    """Тест производительности при параллельных операциях."""
    # Создаем тестовые данные
    suppliers = [
        Supplier(
            name=f"Поставщик {i}",
            inn=f"123456789{i}",
            kpp=f"12345678{i}"
        )
        for i in range(10)
    ]
    
    products = [
        Product(
            name=f"Товар {i}",
            code=f"TEST{i:03d}",
            unit="шт",
            price=Decimal("100.50")
        )
        for i in range(100)
    ]
    
    # Добавляем поставщиков и товары
    for supplier in suppliers:
        test_db.add(supplier)
    for product in products:
        test_db.add(product)
    await test_db.commit()
    
    # Создаем счета для каждого поставщика
    invoices = []
    for supplier in suppliers:
        invoice = Invoice(
            number=f"TEST-{supplier.id:03d}",
            date=date(2024, 3, 20),
            supplier_id=supplier.id
        )
        test_db.add(invoice)
        invoices.append(invoice)
    await test_db.commit()
    
    # Измеряем время создания позиций для всех счетов
    start_time = time.time()
    for invoice in invoices:
        for product in products[:10]:  # По 10 товаров в каждом счете
            item = InvoiceItem(
                invoice_id=invoice.id,
                product_id=product.id,
                name=product.name,
                quantity=Decimal("10"),
                unit="шт",
                price=product.price
            )
            test_db.add(item)
    await test_db.commit()
    concurrent_time = time.time() - start_time
    
    # Проверяем, что время операций не превышает разумные пределы
    assert concurrent_time < 5.0  # Менее 5 секунд для создания 1000 позиций 

@pytest.mark.asyncio
async def test_index_performance(test_db):
    """Тест производительности индексов."""
    # Создаем большое количество товаров с разными кодами
    products = [
        Product(
            name=f"Товар {i}",
            code=f"TEST{i:06d}",  # Уникальный код для каждого товара
            unit="шт",
            price=Decimal("100.50")
        )
        for i in range(10000)
    ]
    
    # Добавляем товары
    for product in products:
        test_db.add(product)
    await test_db.commit()
    
    # Измеряем время поиска по индексированному полю (code)
    start_time = time.time()
    for i in range(100):
        code = f"TEST{i:06d}"
        result = await test_db.query(Product).filter(Product.code == code).first()
        assert result is not None
    indexed_search_time = time.time() - start_time
    
    # Измеряем время поиска по неиндексированному полю (name)
    start_time = time.time()
    for i in range(100):
        name = f"Товар {i}"
        result = await test_db.query(Product).filter(Product.name == name).first()
        assert result is not None
    non_indexed_search_time = time.time() - start_time
    
    # Проверяем, что поиск по индексированному полю быстрее
    assert indexed_search_time < non_indexed_search_time
    assert indexed_search_time < 1.0  # Менее 1 секунды для 100 поисков

@pytest.mark.asyncio
async def test_complex_query_performance(test_db: AsyncSession):
    """Тест производительности сложных запросов."""
    # Создаем поставщиков
    suppliers = [
        Supplier(
            name=f"Поставщик {i}",
            inn=f"123456789{i:03d}",
            kpp=f"123456789"  # Фиксированный KPP из 9 цифр
        )
        for i in range(100)
    ]
    
    for supplier in suppliers:
        test_db.add(supplier)
    await test_db.commit()
    
    # Создаем товары
    products = [
        Product(
            name=f"Товар {i}",
            code=f"TEST{i:06d}",
            unit="шт",
            price=Decimal("100.50")
        )
        for i in range(1000)
    ]
    
    for product in products:
        test_db.add(product)
    await test_db.commit()
    
    # Создаем накладные
    for i in range(100):
        invoice = Invoice(
            supplier_id=suppliers[i % len(suppliers)].id,
            number=f"INV-{i:06d}",
            date=date.today()
        )
        test_db.add(invoice)
        
        # Добавляем позиции в накладную
        for j in range(10):
            product = products[(i * 10 + j) % len(products)]
            item = InvoiceItem(
                invoice=invoice,
                product=product,
                name=product.name,
                quantity=Decimal("1.000"),
                unit=product.unit,
                price=product.price,
                sum=product.price
            )
            test_db.add(item)
    
    await test_db.commit()
    
    # Измеряем время выполнения сложного запроса
    start_time = time.time()
    
    # Сложный запрос с джойнами и агрегацией
    query = select(
        Invoice.number,
        Supplier.name.label("supplier_name"),
        Invoice.date,
        func.count(InvoiceItem.id).label("items_count"),
        func.sum(InvoiceItem.sum).label("total_sum")
    ).join(
        Supplier, Invoice.supplier_id == Supplier.id
    ).join(
        InvoiceItem, Invoice.id == InvoiceItem.invoice_id
    ).group_by(
        Invoice.id,
        Invoice.number,
        Supplier.name,
        Invoice.date
    ).order_by(
        Invoice.date.desc()
    )
    
    result = await test_db.execute(query)
    invoices = result.fetchall()
    
    execution_time = time.time() - start_time
    assert execution_time < 1.0  # Запрос должен выполняться менее 1 секунды
    assert len(invoices) > 0

@pytest.mark.asyncio
async def test_memory_usage_performance(test_db: AsyncSession):
    """Тест производительности с точки зрения использования памяти."""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    # Создаем большое количество товаров
    products = [
        Product(
            name=f"Товар {i}",
            code=f"PERF{i:06d}",  # Используем другой префикс для тестов производительности
            unit="шт",
            price=Decimal("100.50")
        )
        for i in range(50000)
    ]
    
    # Добавляем товары порциями
    batch_size = 1000
    for i in range(0, len(products), batch_size):
        batch = products[i:i + batch_size]
        for product in batch:
            test_db.add(product)
        await test_db.commit()
    
    # Проверяем использование памяти
    final_memory = process.memory_info().rss
    memory_increase = (final_memory - initial_memory) / 1024 / 1024  # В МБ
    
    # Проверяем, что увеличение памяти не превышает разумных пределов
    assert memory_increase < 500  # Менее 500 МБ дополнительной памяти

@pytest.mark.asyncio
async def test_transaction_performance(test_db: AsyncSession):
    """Тест производительности транзакций."""
    # Создаем товары
    products = [
        Product(
            name=f"Товар {i}",
            code=f"TRANS{i:06d}",  # Используем другой префикс для тестов транзакций
            unit="шт",
            price=Decimal("100.50")
        )
        for i in range(1000)
    ]
    
    # Измеряем время выполнения в одной транзакции
    start_time = time.time()
    for product in products:
        test_db.add(product)
    await test_db.commit()
    
    transaction_time = time.time() - start_time
    assert transaction_time < 5.0  # Менее 5 секунд для 1000 записей 