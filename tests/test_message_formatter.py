"""Тесты для форматирования сообщений."""
import pytest
import re
from pathlib import Path
from app.utils.message_formatter import (
    escape_markdown,
    format_number,
    format_date,
    get_status_emoji,
    format_position,
    build_message,
    _MD_V2_SPECIAL
)
from tests.data.sample_invoices import TEST_INVOICES, TEST_ISSUES

# Путь к директории с эталонными файлами
GOLDEN_DIR = Path(__file__).parent / "data" / "golden"

def read_golden_file(name: str) -> str:
    """Читает эталонный файл."""
    with open(GOLDEN_DIR / f"invoice_{name}.txt", "r", encoding="utf-8") as f:
        return f.read().strip()

def test_escape_markdown():
    """Тест экранирования символов Markdown."""
    # Базовые тесты
    assert escape_markdown("Test*Bold*") == "Test\\*Bold\\*"
    assert escape_markdown("Price: 100.50") == "Price\\: 100\\.50"
    assert escape_markdown(None) == "—"
    assert escape_markdown("") == "—"
    
    # Тест на все специальные символы
    test_str = "".join(_MD_V2_SPECIAL)
    escaped = escape_markdown(test_str)
    
    # Проверяем, что все специальные символы экранированы
    assert not re.search(rf'[{re.escape(_MD_V2_SPECIAL)}](?!\\)', escaped), \
        "Найдены неэкранированные специальные символы"
    
    # Тест на числа и знаки
    assert escape_markdown("-100.50") == "\\-100\\.50"
    assert escape_markdown("+100.50") == "\\+100\\.50"
    
    # Тест на сложные случаи
    complex_str = "1. Product [v2.0] (new) *special* price: -50.00!"
    escaped_complex = escape_markdown(complex_str)
    assert escaped_complex == "1\\. Product \\[v2\\.0\\] \\(new\\) \\*special\\* price\\: \\-50\\.00\\!"

def test_format_number():
    """Тест форматирования чисел."""
    # Базовые тесты
    assert format_number(100.50) == "100\\.5"
    assert format_number(100.00) == "100"
    assert format_number(None) == "—"
    assert format_number("not a number") == "—"
    
    # Тест отрицательных чисел
    assert format_number(-100.50) == "\\-100\\.5"
    assert format_number(-0.50) == "\\-0\\.5"
    
    # Тест больших чисел
    assert format_number(1000000.00) == "1000000"
    assert format_number(1000000.50) == "1000000\\.5"
    
    # Тест малых чисел
    assert format_number(0.01) == "0\\.01"
    assert format_number(0.00) == "0"

def test_format_date():
    """Тест форматирования даты."""
    assert format_date("2024-03-15") == "15.03.2024"
    assert format_date("invalid date") == "invalid date"
    assert format_date("") == "—"
    assert format_date(None) == "—"

def test_get_status_emoji():
    """Тест определения эмодзи-статуса."""
    assert get_status_emoji([]) == "✅"
    assert get_status_emoji([{"type": "product_not_found"}]) == "🔍"
    assert get_status_emoji([{"type": "unit_mismatch"}]) == "📏"
    assert get_status_emoji([{"type": "sum_mismatch"}]) == "💵"
    assert get_status_emoji([{"type": "unknown_issue"}]) == "❓"

def test_format_position():
    """Тест форматирования позиции."""
    # Базовый тест
    pos = {
        "name": "Test Product",
        "quantity": 2.0,
        "unit": "pcs",
        "price": 100.50,
        "sum": 201.00
    }
    expected = "1\\. ✅ Test Product\n     2 pcs × 100\\.5 = 201"
    assert format_position(pos, 1, []) == expected
    
    # Тест со специальными символами
    pos_special = {
        "name": "Product [v2.0] (new)",
        "quantity": -2.0,
        "unit": "pcs.",
        "price": -100.50,
        "sum": -201.00
    }
    expected_special = (
        "1\\. ✅ Product \\[v2\\.0\\] \\(new\\)\n"
        "     \\-2 pcs\\. × \\-100\\.5 = \\-201"
    )
    assert format_position(pos_special, 1, []) == expected_special

@pytest.mark.parametrize("case", [
    "ok",
    "not_found",
    "empty",
    "multiple_issues"
])
def test_build_message_golden(case):
    """Тест построения сообщения с использованием эталонных файлов."""
    invoice = TEST_INVOICES[case]
    issues = TEST_ISSUES[case]
    expected = read_golden_file(case)
    result = build_message(invoice, issues)
    assert result == expected

def test_build_message_with_issues():
    """Тест построения сообщения с проблемами."""
    issues = [
        {
            "type": "product_not_found",
            "index": 1,
            "message": "Товар не найден"
        },
        {
            "type": "sum_mismatch",
            "index": 2,
            "message": "Неверная сумма"
        }
    ]
    message = build_message(TEST_INVOICES["not_found"], issues)
    assert "📑" in message
    assert "✅ 0 позиций подтверждено • ⚠️ 2 требует внимания" in message
    assert "🔍" in message  # Для первой позиции
    assert "💵" in message  # Для второй позиции

def test_message_length_limit():
    """Тест ограничения длины сообщения."""
    message = build_message(TEST_INVOICES["long_values"], [])
    assert len(message) <= 4096
    assert message.endswith("...") 