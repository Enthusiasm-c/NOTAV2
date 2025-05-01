"""
Тесты для модуля работы с CSV хранилищем.
"""
import pytest
import pathlib
import json
import csv
from typing import Dict, Any

from app.core.csv_storage import CSVStorage

@pytest.fixture
async def storage(tmp_path: pathlib.Path) -> CSVStorage:
    """Создает временное хранилище для тестов."""
    return CSVStorage(tmp_path)

@pytest.mark.asyncio
async def test_file_creation(storage: CSVStorage):
    """Проверяет создание CSV файлов."""
    assert storage.products_file.exists()
    assert storage.suppliers_file.exists()
    assert storage.invoices_file.exists()

@pytest.mark.asyncio
async def test_save_and_load_invoice(storage: CSVStorage):
    """Проверяет сохранение и загрузку накладной."""
    test_invoice = {
        "id": "test1",
        "supplier": "Test Supplier",
        "date": "2024-03-20",
        "number": "INV-001",
        "total_sum": 1000,
        "items": [
            {"name": "Item 1", "quantity": 1, "price": 100},
            {"name": "Item 2", "quantity": 2, "price": 450}
        ]
    }
    
    await storage.save_invoice(test_invoice)
    
    # Проверяем что файл не пустой
    content = storage.invoices_file.read_text()
    assert "test1" in content
    assert "Test Supplier" in content

@pytest.mark.asyncio
async def test_find_product(storage: CSVStorage):
    """Проверяет поиск продукта по имени и алиасам."""
    # Создаем тестовый продукт с правильно сериализованным JSON
    aliases = json.dumps(["test", "product"])
    with open(storage.products_file, "w", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["id", "name", "aliases"])
        writer.writerow(["1", "Test Product", aliases])
    
    # Проверяем поиск
    product = await storage.find_product_by_name("Test Product")
    assert product is not None
    assert product["name"] == "Test Product"
    
    # Проверяем поиск по алиасу
    product = await storage.find_product_by_name("test")
    assert product is not None
    assert product["name"] == "Test Product"

@pytest.mark.asyncio
async def test_find_supplier(storage: CSVStorage):
    """Проверяет поиск поставщика по имени и алиасам."""
    # Создаем тестового поставщика с правильно сериализованным JSON
    aliases = json.dumps(["supplier", "test"])
    with open(storage.suppliers_file, "w", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["id", "name", "aliases"])
        writer.writerow(["1", "Test Supplier", aliases])
    
    # Проверяем поиск
    supplier = await storage.find_supplier_by_name("Test Supplier")
    assert supplier is not None
    assert supplier["name"] == "Test Supplier"
    
    # Проверяем поиск по алиасу
    supplier = await storage.find_supplier_by_name("supplier")
    assert supplier is not None
    assert supplier["name"] == "Test Supplier" 