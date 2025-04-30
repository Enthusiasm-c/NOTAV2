"""Тесты для модели InvoiceItem."""
import pytest
from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import IntegrityError

from app.models.invoice_item import InvoiceItem

@pytest.mark.asyncio
async def test_invoice_item_creation(test_invoice_item):
    """Тест создания позиции счета."""
    assert test_invoice_item.name == "Тестовый товар"
    assert test_invoice_item.quantity == Decimal("10")
    assert test_invoice_item.unit == "шт"
    assert test_invoice_item.price == Decimal("100.50")
    assert test_invoice_item.comment == "Тестовый комментарий"

@pytest.mark.asyncio
async def test_invoice_item_string_representation(test_invoice_item):
    """Тест строкового представления позиции счета."""
    expected = f"{test_invoice_item.name} - {test_invoice_item.quantity} {test_invoice_item.unit}"
    assert str(test_invoice_item) == expected

@pytest.mark.asyncio
async def test_invoice_item_invoice_relationship(test_invoice_item, test_invoice):
    """Тест связи позиции счета со счетом."""
    assert test_invoice_item.invoice_id == test_invoice.id
    assert test_invoice_item.invoice.number == "TEST-001"
    assert test_invoice_item.invoice.date == test_invoice.date

@pytest.mark.asyncio
async def test_invoice_item_product_relationship(test_invoice_item, test_product):
    """Тест связи позиции счета с товаром."""
    assert test_invoice_item.product_id == test_product.id
    assert test_invoice_item.product.name == "Тестовый товар"
    assert test_invoice_item.product.code == "TEST001"
    assert test_invoice_item.product.unit == "шт"

@pytest.mark.asyncio
async def test_invoice_item_validation(test_db, test_invoice, test_product):
    """Тест валидации данных позиции счета."""
    # Тест с некорректным названием
    with pytest.raises(ValueError):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="",  # Пустое название
            quantity=Decimal("10"),
            unit="шт",
            price=Decimal("100.50")
        )
        test_db.add(item)
        await test_db.commit()

    # Тест с некорректным количеством
    with pytest.raises(ValueError):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="Тестовый товар",
            quantity=Decimal("-10"),  # Отрицательное количество
            unit="шт",
            price=Decimal("100.50")
        )
        test_db.add(item)
        await test_db.commit()

    # Тест с некорректной ценой
    with pytest.raises(ValueError):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="Тестовый товар",
            quantity=Decimal("10"),
            unit="шт",
            price=Decimal("-100.50")  # Отрицательная цена
        )
        test_db.add(item)
        await test_db.commit()

@pytest.mark.asyncio
async def test_invoice_item_total_amount(test_invoice_item):
    """Тест расчета общей суммы позиции."""
    total = test_invoice_item.quantity * test_invoice_item.price
    expected_total = Decimal("10") * Decimal("100.50")
    assert total == expected_total

@pytest.mark.asyncio
async def test_invoice_item_unit_validation(test_db, test_invoice, test_product):
    """Тест валидации единиц измерения."""
    # Тест с пустой единицей измерения
    with pytest.raises(ValueError):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="Тестовый товар",
            quantity=Decimal("10"),
            unit="",  # Пустая единица измерения
            price=Decimal("100.50")
        )
        test_db.add(item)
        await test_db.commit()

    # Тест с недопустимой единицей измерения
    with pytest.raises(ValueError):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="Тестовый товар",
            quantity=Decimal("10"),
            unit="invalid_unit",  # Недопустимая единица измерения
            price=Decimal("100.50")
        )
        test_db.add(item)
        await test_db.commit()

@pytest.mark.asyncio
async def test_invoice_item_quantity_precision(test_db, test_invoice, test_product):
    """Тест точности количества."""
    # Тест с количеством, имеющим слишком много знаков после запятой
    with pytest.raises(ValueError):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="Тестовый товар",
            quantity=Decimal("10.123"),  # Слишком много знаков после запятой
            unit="шт",
            price=Decimal("100.50")
        )
        test_db.add(item)
        await test_db.commit()

@pytest.mark.asyncio
async def test_invoice_item_price_precision(test_db, test_invoice, test_product):
    """Тест точности цены."""
    # Тест с ценой, имеющей слишком много знаков после запятой
    with pytest.raises(ValueError):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="Тестовый товар",
            quantity=Decimal("10"),
            unit="шт",
            price=Decimal("100.123")  # Слишком много знаков после запятой
        )
        test_db.add(item)
        await test_db.commit()

@pytest.mark.asyncio
async def test_invoice_item_total_amount_precision(test_invoice_item):
    """Тест точности расчета общей суммы."""
    # Проверяем, что общая сумма округляется до 2 знаков после запятой
    total = test_invoice_item.quantity * test_invoice_item.price
    assert total.quantize(Decimal("0.01")) == Decimal("1005.00")

@pytest.mark.asyncio
async def test_invoice_item_update(test_db, test_invoice_item):
    """Тест обновления позиции счета."""
    # Обновляем данные позиции
    test_invoice_item.name = "Обновленный товар"
    test_invoice_item.quantity = Decimal("20")
    test_invoice_item.price = Decimal("200.00")
    await test_db.commit()
    await test_db.refresh(test_invoice_item)

    # Проверяем обновленные данные
    assert test_invoice_item.name == "Обновленный товар"
    assert test_invoice_item.quantity == Decimal("20")
    assert test_invoice_item.price == Decimal("200.00")
    assert test_invoice_item.quantity * test_invoice_item.price == Decimal("4000.00")

@pytest.mark.asyncio
async def test_invoice_item_edge_cases(test_db, test_invoice, test_product):
    """Тест граничных случаев для позиции счета."""
    # Тест с нулевым количеством
    with pytest.raises(ValueError):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="Тестовый товар",
            quantity=Decimal("0"),
            unit="шт",
            price=Decimal("100.50")
        )
        test_db.add(item)
        await test_db.commit()

    # Тест с нулевой ценой
    with pytest.raises(ValueError):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="Тестовый товар",
            quantity=Decimal("10"),
            unit="шт",
            price=Decimal("0")
        )
        test_db.add(item)
        await test_db.commit()

    # Тест с очень большим количеством
    with pytest.raises(ValueError):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="Тестовый товар",
            quantity=Decimal("999999999.99"),
            unit="шт",
            price=Decimal("100.50")
        )
        test_db.add(item)
        await test_db.commit()

@pytest.mark.asyncio
async def test_invoice_item_invalid_decimal(test_db, test_invoice, test_product):
    """Тест обработки некорректных десятичных чисел."""
    # Тест с некорректным форматом количества
    with pytest.raises(InvalidOperation):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="Тестовый товар",
            quantity=Decimal("invalid"),
            unit="шт",
            price=Decimal("100.50")
        )
        test_db.add(item)
        await test_db.commit()

    # Тест с некорректным форматом цены
    with pytest.raises(InvalidOperation):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="Тестовый товар",
            quantity=Decimal("10"),
            unit="шт",
            price=Decimal("invalid")
        )
        test_db.add(item)
        await test_db.commit()

@pytest.mark.asyncio
async def test_invoice_item_foreign_key_constraints(test_db, test_invoice, test_product):
    """Тест ограничений внешних ключей."""
    # Тест с несуществующим счетом
    with pytest.raises(IntegrityError):
        item = InvoiceItem(
            invoice_id=999999,  # Несуществующий ID счета
            product_id=test_product.id,
            name="Тестовый товар",
            quantity=Decimal("10"),
            unit="шт",
            price=Decimal("100.50")
        )
        test_db.add(item)
        await test_db.commit()

    # Тест с несуществующим товаром
    with pytest.raises(IntegrityError):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=999999,  # Несуществующий ID товара
            name="Тестовый товар",
            quantity=Decimal("10"),
            unit="шт",
            price=Decimal("100.50")
        )
        test_db.add(item)
        await test_db.commit()

@pytest.mark.asyncio
async def test_invoice_item_name_length(test_db, test_invoice, test_product):
    """Тест длины названия позиции."""
    # Тест с названием, превышающим максимальную длину
    with pytest.raises(ValueError):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="n" * 256,  # Название длиннее 255 символов
            quantity=Decimal("10"),
            unit="шт",
            price=Decimal("100.50")
        )
        test_db.add(item)
        await test_db.commit()

@pytest.mark.asyncio
async def test_invoice_item_comment_length(test_db, test_invoice, test_product):
    """Тест длины комментария."""
    # Тест с комментарием, превышающим максимальную длину
    with pytest.raises(ValueError):
        item = InvoiceItem(
            invoice_id=test_invoice.id,
            product_id=test_product.id,
            name="Тестовый товар",
            quantity=Decimal("10"),
            unit="шт",
            price=Decimal("100.50"),
            comment="c" * 1001  # Комментарий длиннее 1000 символов
        )
        test_db.add(item)
        await test_db.commit() 