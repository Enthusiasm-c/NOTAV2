"""
Утилиты для работы с Telegram Markdown V2.

Модуль предоставляет функции для безопасного форматирования текста
в формате Markdown V2 для Telegram Bot API.
"""
from __future__ import annotations
import re
from typing import Optional

# Специальные символы, которые нужно экранировать в Markdown V2
_MD_V2_SPECIAL = r'_*[]()~`>#+-=|{}.!'

def md2_escape(text: str | None) -> str:
    """
    Экранирует специальные символы Markdown V2.
    
    Args:
        text: Исходный текст или None
        
    Returns:
        str: Экранированный текст или "—" для None/пустой строки
        
    Examples:
        >>> md2_escape("Text with *bold*")
        'Text with \\*bold\\*'
        >>> md2_escape("1. List item")
        '1\\. List item'
        >>> md2_escape("Price: -100.50")
        'Price\\: \\-100\\.50'
    """
    if not text:
        return "—"
    
    text = str(text)
    return re.sub(rf'([{re.escape(_MD_V2_SPECIAL)}])', r'\\\1', text)

def format_bold(text: str) -> str:
    """Форматирует текст жирным шрифтом."""
    return f"*{md2_escape(text)}*"

def format_italic(text: str) -> str:
    """Форматирует текст курсивом."""
    return f"_{md2_escape(text)}_"

def format_code(text: str) -> str:
    """Форматирует текст как код."""
    return f"`{md2_escape(text)}`"

def format_list_item(idx: int, text: str) -> str:
    """
    Форматирует элемент списка с номером.
    
    Args:
        idx: Номер элемента
        text: Текст элемента
        
    Returns:
        str: Отформатированная строка вида "1. Текст"
    """
    return f"{idx}\\. {md2_escape(text)}" 