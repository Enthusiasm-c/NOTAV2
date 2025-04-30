from datetime import datetime, date
from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.supplier import Supplier
from app.models.product import Product
from app.models.product_name_lookup import ProductNameLookup

@pytest.fixture
async def sample_supplier(session: AsyncSession) -> Supplier:
    """Создает тестового поставщика."""
    supplier = Supplier(
        name="Test Supplier",
        inn="1234567890",
        address="Test Address",
        phone="+1234567890",
        email="test@supplier.com"
    )
    session.add(supplier)
    await session.commit()
    return supplier

@pytest.fixture
async def sample_product(session: AsyncSession) -> Product:
    """Создает тестовый товар."""
    product = Product(
        name="Test Product",
        unit="pcs",
        price=100.0
    )
    session.add(product)
    await session.commit()
    return product

@pytest.fixture
async def sample_invoice(session: AsyncSession, sample_supplier: Supplier) -> Invoice:
    """Создает тестовую накладную."""
    invoice = Invoice(
        number="INV-001",
        date=datetime.now(),
        supplier_id=sample_supplier.id,
        comment="Test invoice"
    )
    session.add(invoice)
    await session.commit()
    return invoice

@pytest.fixture
async def sample_invoice_item(
    session: AsyncSession,
    sample_invoice: Invoice,
    sample_product: Product
) -> InvoiceItem:
    """Создает тестовый элемент накладной."""
    item = InvoiceItem(
        invoice_id=sample_invoice.id,
        product_id=sample_product.id,
        name="Test Item",
        quantity=10.0,
        unit="pcs",
        price=100.0
    )
    session.add(item)
    await session.commit()
    return item

@pytest.fixture
async def sample_product_name_lookup(
    session: AsyncSession,
    sample_product: Product
) -> ProductNameLookup:
    """Создает тестовую запись сопоставления названий товаров."""
    lookup = ProductNameLookup(
        alias="Test Product Alias",
        product_id=sample_product.id,
        comment="Test lookup entry"
    )
    session.add(lookup)
    await session.commit()
    return lookup

@pytest.mark.asyncio
async def test_invoice_creation(session: AsyncSession, sample_invoice: Invoice):
    """Тестирует создание накладной."""
    assert sample_invoice.id is not None
    assert sample_invoice.number == "INV-001"
    assert isinstance(sample_invoice.date, datetime)
    assert isinstance(sample_invoice.comment, str)
    assert sample_invoice.comment == "Test invoice"
    assert sample_invoice.supplier.name == "Test Supplier"

@pytest.mark.asyncio
async def test_invoice_supplier_relationship(
    session: AsyncSession,
    sample_invoice: Invoice,
    sample_supplier: Supplier
):
    """Тестирует связь накладной с поставщиком."""
    assert sample_invoice.supplier_id == sample_supplier.id
    assert sample_invoice.supplier.name == "Test Supplier"
    assert sample_invoice.supplier.inn == "1234567890"
    assert sample_invoice.supplier.address == "Test Address"
    assert sample_invoice.supplier.phone == "+1234567890"
    assert sample_invoice.supplier.email == "test@supplier.com"

@pytest.mark.asyncio
async def test_invoice_items_relationship(
    session: AsyncSession,
    sample_invoice: Invoice,
    sample_invoice_item: InvoiceItem
):
    """Тестирует связь накладной с элементами."""
    assert len(sample_invoice.items) == 1
    item = sample_invoice.items[0]
    assert isinstance(item.name, str)
    assert isinstance(item.quantity, float)
    assert isinstance(item.unit, str)
    assert isinstance(item.price, float)
    assert item.name == "Test Item"
    assert item.quantity == 10.0
    assert item.unit == "pcs"
    assert item.price == 100.0

@pytest.mark.asyncio
async def test_invoice_item_product_relationship(
    session: AsyncSession,
    sample_invoice_item: InvoiceItem,
    sample_product: Product
):
    """Тестирует связь элемента накладной с товаром."""
    assert sample_invoice_item.product_id == sample_product.id
    assert sample_invoice_item.product.name == "Test Product"
    assert sample_invoice_item.product.unit == "pcs"
    assert float(sample_invoice_item.product.price) == 100.0

@pytest.mark.asyncio
async def test_invoice_str_representation(sample_invoice: Invoice):
    """Тестирует строковое представление накладной."""
    expected = f"Накладная INV-001 от {sample_invoice.date.strftime('%d.%m.%Y')}"
    assert str(sample_invoice) == expected
    assert isinstance(sample_invoice.date, datetime)
    assert sample_invoice.date.strftime('%d.%m.%Y') in str(sample_invoice)

@pytest.mark.asyncio
async def test_invoice_item_str_representation(sample_invoice_item: InvoiceItem):
    """Тестирует строковое представление элемента накладной."""
    expected = f"{sample_invoice_item.name} - {sample_invoice_item.quantity} {sample_invoice_item.unit}"
    assert str(sample_invoice_item) == expected
    assert isinstance(sample_invoice_item.name, str)
    assert isinstance(sample_invoice_item.quantity, float)
    assert isinstance(sample_invoice_item.unit, str)

@pytest.mark.asyncio
async def test_product_name_lookup_creation(
    session: AsyncSession,
    sample_product_name_lookup: ProductNameLookup
):
    """Тестирует создание записи сопоставления названий товаров."""
    assert sample_product_name_lookup.id is not None
    assert isinstance(sample_product_name_lookup.alias, str)
    assert isinstance(sample_product_name_lookup.comment, str)
    assert sample_product_name_lookup.alias == "Test Product Alias"
    assert sample_product_name_lookup.comment == "Test lookup entry"

@pytest.mark.asyncio
async def test_product_name_lookup_product_relationship(
    session: AsyncSession,
    sample_product_name_lookup: ProductNameLookup,
    sample_product: Product
):
    """Тестирует связь записи сопоставления с товаром."""
    assert sample_product_name_lookup.product_id == sample_product.id
    assert isinstance(sample_product_name_lookup.product.name, str)
    assert isinstance(sample_product_name_lookup.product.unit, str)
    assert isinstance(sample_product_name_lookup.product.price, float)
    assert sample_product_name_lookup.product.name == "Test Product"
    assert sample_product_name_lookup.product.unit == "pcs"
    assert sample_product_name_lookup.product.price == 100.0

@pytest.mark.asyncio
async def test_product_name_lookup_str_representation(
    sample_product_name_lookup: ProductNameLookup
):
    """Тестирует строковое представление записи сопоставления."""
    expected = f"{sample_product_name_lookup.alias} -> {sample_product_name_lookup.product.name}"
    assert str(sample_product_name_lookup) == expected
    assert isinstance(sample_product_name_lookup.alias, str)
    assert isinstance(sample_product_name_lookup.product.name, str)
    assert " -> " in str(sample_product_name_lookup)

@pytest.mark.asyncio
async def test_product_name_lookup_unique_alias(
    session: AsyncSession,
    sample_product: Product
):
    """Тестирует уникальность алиаса в записях сопоставления."""
    # Создаем первую запись
    lookup1 = ProductNameLookup(
        alias="Unique Alias",
        product_id=sample_product.id
    )
    session.add(lookup1)
    await session.commit()
    
    # Пытаемся создать вторую запись с тем же алиасом
    lookup2 = ProductNameLookup(
        alias="Unique Alias",
        product_id=sample_product.id
    )
    session.add(lookup2)
    
    # Должно вызвать исключение из-за нарушения уникальности
    with pytest.raises(IntegrityError):
        await session.commit()

@pytest.mark.asyncio
async def test_invoice_total_amount(test_invoice, test_invoice_item):
    """Тест расчета общей суммы счета."""
    total = sum(item.quantity * item.price for item in test_invoice.items)
    expected_total = Decimal("10") * Decimal("100.50")
    assert total == expected_total

@pytest.mark.asyncio
async def test_invoice_validation(test_db, test_supplier):
    """Тест валидации данных счета."""
    # Тест с некорректным номером
    with pytest.raises(ValueError):
        invoice = Invoice(
            number="",  # Пустой номер
            date=date(2024, 3, 20),
            supplier_id=test_supplier.id
        )
        test_db.add(invoice)
        await test_db.commit()

    # Тест с некорректной датой
    with pytest.raises(ValueError):
        invoice = Invoice(
            number="TEST-002",
            date=None,  # Отсутствующая дата
            supplier_id=test_supplier.id
        )
        test_db.add(invoice)
        await test_db.commit()

@pytest.mark.asyncio
async def test_invoice_cascade_delete(test_db, test_invoice, test_invoice_item):
    """Тест каскадного удаления позиций при удалении счета."""
    invoice_id = test_invoice.id
    item_id = test_invoice_item.id
    
    # Удаляем счет
    await test_db.delete(test_invoice)
    await test_db.commit()
    
    # Проверяем, что счет удален
    deleted_invoice = await test_db.get(Invoice, invoice_id)
    assert deleted_invoice is None
    
    # Проверяем, что позиция также удалена
    deleted_item = await test_db.get(InvoiceItem, item_id)
    assert deleted_item is None 