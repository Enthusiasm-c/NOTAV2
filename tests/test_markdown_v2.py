"""Тесты для функций форматирования Markdown V2."""
import pytest
import re
from app.utils.markdown_v2 import (
    md2_escape,
    format_bold,
    format_italic,
    format_code,
    format_list_item,
    _MD_V2_SPECIAL
)

def test_md2_escape_basic():
    """Тест базового экранирования."""
    assert md2_escape("Test*Bold*") == "Test\\*Bold\\*"
    assert md2_escape("Price: 100.50") == "Price\\: 100\\.50"
    assert md2_escape(None) == "—"
    assert md2_escape("") == "—"

def test_md2_escape_all_special():
    """Тест экранирования всех специальных символов."""
    test_str = "".join(_MD_V2_SPECIAL)
    escaped = md2_escape(test_str)
    
    # Проверяем, что все специальные символы экранированы
    assert not re.search(rf'[{re.escape(_MD_V2_SPECIAL)}](?!\\)', escaped), \
        "Найдены неэкранированные специальные символы"

def test_md2_escape_numbers():
    """Тест экранирования чисел и знаков."""
    assert md2_escape("-100.50") == "\\-100\\.50"
    assert md2_escape("+100.50") == "\\+100\\.50"
    assert md2_escape("1.") == "1\\."

def test_md2_escape_complex():
    """Тест сложных случаев."""
    complex_str = "1. Product [v2.0] (new) *special* price: -50.00!"
    escaped = md2_escape(complex_str)
    expected = "1\\. Product \\[v2\\.0\\] \\(new\\) \\*special\\* price\\: \\-50\\.00\\!"
    assert escaped == expected

def test_format_bold():
    """Тест форматирования жирным."""
    assert format_bold("test") == "*test*"
    assert format_bold("test*bold") == "*test\\*bold*"

def test_format_italic():
    """Тест форматирования курсивом."""
    assert format_italic("test") == "_test_"
    assert format_italic("test_italic") == "_test\\_italic_"

def test_format_code():
    """Тест форматирования кодом."""
    assert format_code("test") == "`test`"
    assert format_code("test`code") == "`test\\`code`"

def test_format_list_item():
    """Тест форматирования элемента списка."""
    assert format_list_item(1, "test") == "1\\. test"
    assert format_list_item(2, "test*bold") == "2\\. test\\*bold" 