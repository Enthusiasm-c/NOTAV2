"""
Тесты для проверки корректной обработки None значений в analyze_invoice_issues.
"""
import pytest
from typing import Dict, Any

from app.routers.telegram_bot import analyze_invoice_issues, _safe_str

@pytest.mark.asyncio
async def test_none_values():
    """Проверяем, что функция корректно обрабатывает None значения."""
    # Тестовые данные с None значениями
    test_data: Dict[str, Any] = {
        "supplier": None,
        "positions": [
            {
                "name": None,
                "unit": None,
                "quantity": None,
                "price": None,
                "sum": None
            },
            {
                "name": "Test Product",
                "unit": None,
                "quantity": 1,
                "price": 100,
                "sum": 100
            }
        ],
        "total_sum": None
    }
    
    # Проверяем, что функция не выбрасывает исключений
    issues, message = await analyze_invoice_issues(test_data)
    
    # Проверяем, что все проблемы обнаружены
    assert any("Не указан поставщик" in i["message"] for i in issues)
    assert any("не указано название" in i["message"] for i in issues)
    assert any("не указаны единицы измерения" in i["message"] for i in issues)
    assert any("Не указана общая сумма" in i["message"] for i in issues)
    
    # Проверяем, что функция вернула сообщение
    assert message.startswith("❗️ Обнаружены проблемы")

def test_safe_str():
    """Проверяем работу функции безопасного преобразования строк."""
    assert _safe_str(None) == ""
    assert _safe_str("") == ""
    assert _safe_str(" test ") == "test"
    assert _safe_str("  ") == ""
    assert _safe_str(123) == "123"  # Проверяем преобразование чисел
    
@pytest.mark.asyncio
async def test_empty_positions():
    """Проверяем обработку пустого списка позиций."""
    test_data = {
        "supplier": "Test Supplier",
        "positions": [],
        "total_sum": 0
    }
    
    issues, message = await analyze_invoice_issues(test_data)
    assert any("Нет позиций в накладной" in i["message"] for i in issues)

@pytest.mark.asyncio
async def test_invalid_numbers():
    """Проверяем обработку некорректных числовых значений."""
    test_data = {
        "supplier": "Test Supplier",
        "positions": [
            {
                "name": "Test Product",
                "unit": "шт",
                "quantity": "not a number",  # Некорректное значение
                "price": None,
                "sum": "invalid"
            }
        ],
        "total_sum": "NaN"
    }
    
    issues, message = await analyze_invoice_issues(test_data)
    assert len(issues) > 0  # Должны быть обнаружены проблемы с числовыми значениями 