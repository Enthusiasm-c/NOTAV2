"""
Тесты для модуля data_loader.
"""
import pytest
from pathlib import Path
import pandas as pd
from unittest.mock import patch, Mock

from app.core.data_loader import (
    load_data,
    get_supplier,
    get_product_alias,
    SUPPLIERS_CSV,
    PRODUCTS_CSV
)

@pytest.fixture
def mock_csv_data():
    """Фикстура с тестовыми данными CSV."""
    suppliers_data = pd.DataFrame({
        "name": ["ООО Тест", "ИП Иванов", "ООО Ромашка"],
        "id": [1, 2, 3],
        "code": ["SUP001", "SUP002", "SUP003"]
    })
    
    products_data = pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["Молоко", "Хлеб", "Сыр"],
        "code": ["MILK001", "BREAD001", "CHEESE001"],
        "measureName": ["л", "шт", "кг"],
        "is_ingredient": [True, False, True]
    })
    
    return suppliers_data, products_data

@pytest.fixture
def setup_mock_files(mock_csv_data, tmp_path):
    """Создает временные CSV файлы с тестовыми данными."""
    suppliers_data, products_data = mock_csv_data
    
    # Создаем временные файлы
    suppliers_csv = tmp_path / "base_suppliers.csv"
    products_csv = tmp_path / "base_products.csv"
    
    suppliers_data.to_csv(suppliers_csv, index=False)
    products_data.to_csv(products_csv, index=False)
    
    # Патчим пути к файлам
    with patch("app.core.data_loader.SUPPLIERS_CSV", suppliers_csv), \
         patch("app.core.data_loader.PRODUCTS_CSV", products_csv):
        yield

def test_csv_files_exist():
    """Проверяет наличие CSV файлов."""
    assert SUPPLIERS_CSV.exists(), f"Файл {SUPPLIERS_CSV} не найден"
    assert PRODUCTS_CSV.exists(), f"Файл {PRODUCTS_CSV} не найден"

def test_csv_files_have_required_columns():
    """Проверяет наличие необходимых колонок в CSV файлах."""
    suppliers_df = pd.read_csv(SUPPLIERS_CSV)
    products_df = pd.read_csv(PRODUCTS_CSV)
    
    required_supplier_cols = {"name", "id", "code"}
    required_product_cols = {"id", "name", "code", "measureName", "is_ingredient"}
    
    assert all(col in suppliers_df.columns for col in required_supplier_cols), \
        "Отсутствуют обязательные колонки в suppliers.csv"
    assert all(col in products_df.columns for col in required_product_cols), \
        "Отсутствуют обязательные колонки в products.csv"

@pytest.mark.usefixtures("setup_mock_files")
def test_load_data(mock_csv_data):
    """Тест загрузки данных из CSV."""
    load_data()
    from app.core.data_loader import SUPPLIERS, PRODUCTS
    
    assert SUPPLIERS is not None
    assert PRODUCTS is not None
    assert len(SUPPLIERS) == len(mock_csv_data[0])
    assert len(PRODUCTS) == len(mock_csv_data[1])

@pytest.mark.usefixtures("setup_mock_files")
def test_get_supplier_exact_match():
    """Тест поиска поставщика по точному совпадению."""
    supplier = get_supplier("ООО Тест")
    assert supplier is not None
    assert supplier["name"] == "ООО Тест"
    assert supplier["code"] == "SUP001"

@pytest.mark.usefixtures("setup_mock_files")
def test_get_supplier_fuzzy_match():
    """Тест поиска поставщика по частичному совпадению."""
    supplier = get_supplier("ООО Тест Компани")
    assert supplier is not None
    assert supplier["name"] == "ООО Тест"

@pytest.mark.usefixtures("setup_mock_files")
def test_get_supplier_no_match():
    """Тест отсутствия совпадений при поиске поставщика."""
    supplier = get_supplier("Несуществующий поставщик")
    assert supplier is None

@pytest.mark.usefixtures("setup_mock_files")
def test_get_product_alias_exact_match():
    """Тест поиска товара по точному совпадению."""
    product = get_product_alias("Молоко")
    assert product is not None
    assert product["name"] == "Молоко"
    assert product["code"] == "MILK001"

@pytest.mark.usefixtures("setup_mock_files")
def test_get_product_alias_fuzzy_match():
    """Тест поиска товара по частичному совпадению."""
    product = get_product_alias("Молоко 3.2%")
    assert product is not None
    assert product["name"] == "Молоко"

@pytest.mark.usefixtures("setup_mock_files")
def test_get_product_alias_no_match():
    """Тест отсутствия совпадений при поиске товара."""
    product = get_product_alias("Несуществующий товар")
    assert product is None 