"""
Форматирование сводки накладной в Markdown для Telegram.

Модуль содержит функции для создания красивой и информативной
сводки накладной, которая отображается в чате Telegram.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional, Tuple
import re
from datetime import datetime

# Максимальное количество символов в строке товара перед обрезкой
MAX_ITEM_LENGTH = 60

def format_date(date_str: str) -> str:
    """
    Форматирует дату в читаемый вид DD MMM YYYY.
    
    Args:
        date_str: Строка с датой в формате YYYY-MM-DD
        
    Returns:
        str: Отформатированная дата
    """
    try:
        # Пытаемся распарсить дату в разных форматах
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            try:
                dt = datetime.strptime(date_str, "%d-%m-%Y")
            except ValueError:
                return date_str  # Возвращаем как есть, если не удалось распарсить
        
        # Форматируем дату в нужный вид
        return dt.strftime("%d %b %Y").replace(" ", "-")
    except Exception:
        return date_str

def format_number(number: Any) -> str:
    """
    Форматирует число с разделителями тысяч.
    
    Args:
        number: Число для форматирования
        
    Returns:
        str: Отформатированное число
    """
    try:
        if isinstance(number, str):
            # Попытка преобразовать строку в число
            try:
                number = float(number.replace(',', '.'))
            except ValueError:
                return number
        
        # Форматируем число с разделителями тысяч
        return f"{number:,.2f}".replace(',', ' ')
    except Exception:
        return str(number)

def get_issue_emoji(issue_type: str) -> str:
    """
    Возвращает эмодзи в зависимости от типа проблемы.
    
    Args:
        issue_type: Строка с типом проблемы
        
    Returns:
        str: Эмодзи для данного типа проблемы
    """
    if "Not in database" in issue_type:
        return "🔴"  # Красный для отсутствующих в базе
    elif "incorrect match" in issue_type:
        return "🟡"  # Желтый для возможных ошибок сопоставления
    elif "Unit" in issue_type:
        return "🟠"  # Оранжевый для проблем с единицами измерения
    else:
        return "⚠️"  # Общее предупреждение для остальных проблем

def truncate_text(text: str, max_length: int = MAX_ITEM_LENGTH) -> str:
    """
    Обрезает текст, если он длиннее max_length.
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        
    Returns:
        str: Обрезанный текст с многоточием или исходный текст
    """
    if len(text) > max_length:
        return text[:max_length-3] + "..."
    return text

def escape_markdown(text: str | None) -> str:
    if not text:                         # ловим None или ""
        return ""
    markdown_chars = r"\_*[]()~>`|#"+ "!"
    return "".join(f"\\{c}" if c in markdown_chars else c for c in text)

def make_invoice_preview(
    data: Dict[str, Any], 
    issues: List[Dict[str, Any]], 
    fixed_issues: Dict[int, Dict[str, Any]] = None,
    show_all_issues: bool = False,
) -> str:
    """
    Создает красивую сводку накладной в формате MarkdownV2.
    
    Args:
        data: Данные накладной
        issues: Список проблемных позиций
        fixed_issues: Словарь с исправленными позициями
        show_all_issues: Показать все проблемы или только верхний уровень
        
    Returns:
        str: Отформатированная сводка в MarkdownV2
    """
    fixed_issues = fixed_issues or {}
    
    # Получаем основные данные
    supplier = escape_markdown(data.get('supplier', 'Неизвестный поставщик'))
    date_str = format_date(data.get('date', ''))
    invoice_number = escape_markdown(data.get('number', ''))
    
    # Получаем позиции и отфильтровываем удаленные
    positions = [p for p in data.get('positions', []) if not p.get('deleted', False)]
    
    # Считаем статистику
    total_positions = len(positions)
    problem_count = len(issues)
    fixed_count = len(fixed_issues)
    valid_count = total_positions - problem_count
    
    # Форматируем хедер
    header = f"📦  *{supplier}* • {date_str}"
    if invoice_number:
        header += f" № {invoice_number}"
    
    # Статус-бар
    status_bar = "────────────────────────────────────────\n"
    status_bar += f"✅ {valid_count} позиций подтверждено\n"
    if problem_count > 0:
        status_bar += f"⚠️ {problem_count} позиций требуют внимания"
        if not show_all_issues:
            status_bar += " \\(нажмите, чтобы раскрыть\\)"
    
    # Список проблемных позиций
    issues_block = ""
    if problem_count > 0 and show_all_issues:
        issues_block = "\n────────────────────────────────────────\n"
        issues_block += "🚩 *Проблемные позиции:*\n\n"
        
        for i, issue in enumerate(issues):
            emoji = get_issue_emoji(issue.get('issue', ''))
            original = issue.get('original', {})
            name = escape_markdown(original.get('name', 'Позиция'))
            qty = original.get('quantity', '')
            unit = original.get('unit', '')
            price = format_number(original.get('price', 0))
            
            # Кратко об ошибке
            issue_text = issue.get('issue', '')
            if "Not in database" in issue_text:
                issue_info = "Товар не найден в базе"
            elif "incorrect match" in issue_text:
                issue_info = "Возможно неверное сопоставление"
            elif "Unit" in issue_text:
                issue_info = "Несоответствие единиц измерения"
            else:
                issue_info = issue_text
            
            # Ограничиваем длину строки
            name_display = truncate_text(name)
            
            issues_block += f"{i+1}\\. {emoji} *{name_display}*\n"
            issues_block += f"   {qty} {unit} × {price}\n"
            issues_block += f"   __{issue_info}__\n\n"

def make_issue_list(issues: List[Dict[str, Any]]) -> str:
    """
    Создает список проблемных позиций для выбора.
    
    Args:
        issues: Список проблемных позиций
        
    Returns:
        str: Отформатированный список проблем
    """
    if not issues:
        return "✅ Все позиции проверены и готовы к отправке."
    
    result = "*Выберите позицию для исправления:*\n\n"
    
    for i, issue in enumerate(issues):
        emoji = get_issue_emoji(issue.get('issue', ''))
        original = issue.get('original', {})
        name = escape_markdown(original.get('name', 'Позиция'))
        qty = original.get('quantity', '')
        unit = original.get('unit', '')
        
        # Ограничиваем длину строки
        name_display = truncate_text(name, 30)  # Короче для кнопок
        
        result += f"{i+1}\\. {emoji} *{name_display}* \\- {qty} {unit}\n"
    
    return result

def make_final_preview(
    data: Dict[str, Any], 
    original_issues: List[Dict[str, Any]],
    fixed_issues: Dict[int, Dict[str, Any]]
) -> str:
    """
    Создает финальный вид накладной с отметкой исправленных позиций.
    
    Args:
        data: Данные накладной
        original_issues: Первоначальный список проблемных позиций
        fixed_issues: Словарь с исправленными позициями
        
    Returns:
        str: Отформатированная сводка для финального подтверждения
    """
    # Проверяем, остались ли неисправленные позиции
    fixed_indices = set(fixed_issues.keys())
    remaining_issues = [
        issue for i, issue in enumerate(original_issues) 
        if issue.get("index") - 1 not in fixed_indices
    ]
    
    # Генерируем превью с флагом показа всех проблем, если остались неисправленные
    return make_invoice_preview(
        data, 
        remaining_issues, 
        fixed_issues,
        show_all_issues=len(remaining_issues) > 0
    )
