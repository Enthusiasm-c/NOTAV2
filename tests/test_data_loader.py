"""
Тесты для модуля data_loader.
"""
import pytest
import pathlib
from typing import Dict, Any

from app.core.data_loader import (
    load_data_async,
    get_product_alias,
    get_supplier,
    save_invoice,
    storage
)

@pytest.fixture(autouse=True)
async def setup_test_data(tmp_path):
    """Создает тестовые данные."""
    # Используем временную директорию для тестов
    storage.data_dir = tmp_path
    storage.products_file = tmp_path / "products.csv"
    storage.suppliers_file = tmp_path / "suppliers.csv"
    storage.invoices_file = tmp_path / "invoices.csv"
    
    # Создаем тестовые продукты
    with open(storage.products_file, "w", newline="") as f:
        f.write('id,name,aliases\n')
        f.write('1,Молоко,"[""молоко 3.2%"", ""молоко пастеризованное""]"\n')
        f.write('2,Хлеб,"[""хлеб белый"", ""батон""]"\n')
    
    # Создаем тестовых поставщиков
    with open(storage.suppliers_file, "w", newline="") as f:
        f.write('id,name,aliases\n')
        f.write('1,ООО Молочный завод,"[""молзавод"", ""молокозавод""]"\n')
        f.write('2,ИП Иванов,"[""иванов"", ""хлебозавод""]"\n')
    
    # Загружаем данные
    await load_data_async()
    
    yield
    
    # Очищаем данные после тестов
    import shutil
    shutil.rmtree(tmp_path)

@pytest.mark.asyncio
async def test_load_data():
    """Проверяет загрузку данных."""
    # Проверяем что данные загружены
    product = get_product_alias("молоко 3.2%")
    assert product == "Молоко"
    
    supplier = get_supplier("молзавод")
    assert supplier == "ООО Молочный завод"

@pytest.mark.asyncio
async def test_product_alias_search():
    """Проверяет поиск продуктов по алиасам."""
    assert get_product_alias("молоко") == "Молоко"
    assert get_product_alias("молоко 3.2%") == "Молоко"
    assert get_product_alias("батон") == "Хлеб"
    assert get_product_alias("несуществующий") is None

@pytest.mark.asyncio
async def test_supplier_search():
    """Проверяет поиск поставщиков по алиасам."""
    assert get_supplier("молзавод") == "ООО Молочный завод"
    assert get_supplier("иванов") == "ИП Иванов"
    assert get_supplier("несуществующий") is None

@pytest.mark.asyncio
async def test_save_invoice():
    """Проверяет сохранение накладной."""
    test_invoice = {
        "id": "INV-001",
        "supplier": "ООО Молочный завод",
        "date": "2024-03-20",
        "number": "123",
        "total_sum": 1000,
        "items": [
            {"name": "Молоко", "quantity": 10, "price": 100}
        ]
    }
    
    await save_invoice(test_invoice)
    
    # Проверяем что файл содержит данные
    content = storage.invoices_file.read_text()
    assert "INV-001" in content
    assert "ООО Молочный завод" in content 