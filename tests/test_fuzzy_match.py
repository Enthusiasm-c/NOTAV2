"""
Тесты для модуля нечеткого поиска.
"""

import pytest
from app.routers.fuzzy_match import fuzzy_match_product, find_similar_products
from app.core.data_loader import load_data


@pytest.fixture(autouse=True)
def setup_test_data():
    """Загружаем тестовые данные перед каждым тестом."""
    load_data()

@pytest.mark.asyncio
async def test_fuzzy_match_rasp():
    """Проверяем, что для строки 'Rasp' возвращается корректный product_id с высокой уверенностью."""
    product_id, confidence = await fuzzy_match_product("Rasp")
    
    assert product_id is not None, "Product ID should not be None"
    assert confidence > 0.7, f"Confidence should be > 0.7, got {confidence}"

@pytest.mark.asyncio
async def test_fuzzy_match_empty():
    """Проверяем обработку пустой строки."""
    product_id, confidence = await fuzzy_match_product("")
    
    assert product_id is None, "Product ID should be None for empty string"
    assert confidence == 0.0, "Confidence should be 0.0 for empty string"

@pytest.mark.asyncio
async def test_fuzzy_match_threshold():
    """Проверяем работу с пользовательским порогом уверенности."""
    product_id, confidence = await fuzzy_match_product("Rasp", threshold=0.9)
    
    if confidence >= 0.9:
        assert product_id is not None, "Product ID should not be None when confidence >= threshold"
    else:
        assert product_id is None, "Product ID should be None when confidence < threshold"

@pytest.mark.asyncio
async def test_find_similar_products():
    """Проверяем поиск похожих товаров."""
    products = await find_similar_products("Rasp")
    
    assert len(products) > 0, "Should find at least one similar product"
    assert all(isinstance(p["confidence"], float) for p in products), "All products should have confidence score"
    assert all(p["confidence"] > 0.7 for p in products), "All products should have confidence > 0.7"
