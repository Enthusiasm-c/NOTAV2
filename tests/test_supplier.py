"""Тесты для модели Supplier."""
import pytest

from app.models.supplier import Supplier
from app.models.invoice import Invoice

@pytest.mark.asyncio
async def test_supplier_creation(test_supplier):
    """Тест создания поставщика."""
    assert test_supplier.name == "Тестовый поставщик"
    assert test_supplier.inn == "1234567890"
    assert test_supplier.kpp == "123456789"
    assert test_supplier.address == "г. Москва, ул. Тестовая, д. 1"
    assert test_supplier.phone == "+7 (999) 123-45-67"
    assert test_supplier.email == "test@example.com"
    assert test_supplier.comment == "Тестовый комментарий"

@pytest.mark.asyncio
async def test_supplier_string_representation(test_supplier):
    """Тест строкового представления поставщика."""
    expected = f"{test_supplier.name} (ИНН: {test_supplier.inn})"
    assert str(test_supplier) == expected

@pytest.mark.asyncio
async def test_supplier_invoices_relationship(test_supplier, test_invoice):
    """Тест связи поставщика со счетами."""
    assert len(test_supplier.invoices) == 1
    invoice = test_supplier.invoices[0]
    assert invoice.number == "TEST-001"
    assert invoice.supplier_id == test_supplier.id

@pytest.mark.asyncio
async def test_supplier_validation(test_db):
    """Тест валидации данных поставщика."""
    # Тест с некорректным названием
    with pytest.raises(ValueError):
        supplier = Supplier(
            name="",  # Пустое название
            inn="1234567890",
            kpp="123456789"
        )
        test_db.add(supplier)
        await test_db.commit()

    # Тест с некорректным ИНН
    with pytest.raises(ValueError):
        supplier = Supplier(
            name="Тестовый поставщик 2",
            inn="123",  # Некорректная длина ИНН
            kpp="123456789"
        )
        test_db.add(supplier)
        await test_db.commit()

@pytest.mark.asyncio
async def test_supplier_unique_inn(test_db, test_supplier):
    """Тест уникальности ИНН поставщика."""
    # Пытаемся создать поставщика с существующим ИНН
    duplicate_supplier = Supplier(
        name="Другой поставщик",
        inn=test_supplier.inn,  # Используем существующий ИНН
        kpp="987654321"
    )
    test_db.add(duplicate_supplier)
    with pytest.raises(Exception):  # Ожидаем ошибку уникальности
        await test_db.commit()

@pytest.mark.asyncio
async def test_supplier_cascade_delete(test_db, test_supplier, test_invoice):
    """Тест каскадного удаления счетов при удалении поставщика."""
    supplier_id = test_supplier.id
    invoice_id = test_invoice.id
    
    # Удаляем поставщика
    await test_db.delete(test_supplier)
    await test_db.commit()
    
    # Проверяем, что поставщик удален
    deleted_supplier = await test_db.get(Supplier, supplier_id)
    assert deleted_supplier is None
    
    # Проверяем, что счет также удален
    deleted_invoice = await test_db.get(Invoice, invoice_id)
    assert deleted_invoice is None 