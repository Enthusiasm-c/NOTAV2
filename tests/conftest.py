"""
Конфигурация тестов для NOTA V2.
"""

import os
import pytest
import pandas as pd
from pathlib import Path

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Настраивает тестовое окружение."""
    # Создаем временную директорию для тестовых данных
    test_data_dir = Path("tests/data")
    test_data_dir.mkdir(exist_ok=True)
    
    # Создаем тестовые CSV файлы
    products_df = pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["Raspberry", "Apple", "Orange"],
        "code": ["R001", "A001", "O001"],
        "measureName": ["kg", "kg", "kg"],
        "is_ingredient": [True, True, True]
    })
    
    suppliers_df = pd.DataFrame({
        "id": [1, 2],
        "name": ["Supplier A", "Supplier B"],
        "code": ["SA001", "SB001"]
    })
    
    # Сохраняем тестовые данные
    products_df.to_csv(test_data_dir / "test_products.csv", index=False)
    suppliers_df.to_csv(test_data_dir / "test_suppliers.csv", index=False)
    
    # Устанавливаем переменные окружения для тестов
    os.environ["PRODUCTS_CSV"] = str(test_data_dir / "test_products.csv")
    os.environ["SUPPLIERS_CSV"] = str(test_data_dir / "test_suppliers.csv")
    
    yield
    
    # Очищаем после тестов
    try:
        (test_data_dir / "test_products.csv").unlink()
        (test_data_dir / "test_suppliers.csv").unlink()
    except FileNotFoundError:
        pass 