"""
Форматирование сообщений для Telegram бота.

Модуль отвечает за форматирование сообщений в удобочитаемый вид
с использованием Markdown V2.
"""
from __future__ import annotations

import re
from typing import Dict, Any, List, Optional
from datetime import datetime

import structlog

logger = structlog.get_logger()

# Константы для эмодзи-статусов
STATUS_EMOJIS = {
    "ok": "✅",
    "not_found": "🔍",
    "unit_mismatch": "📏",
    "sum_mismatch": "💵",
    "other": "❓"
}

# Приоритеты проблем (меньше = важнее)
ISSUE_PRIORITIES = {
    "product_not_found": 1,
    "product_low_confidence": 1,
    "unit_mismatch": 2,
    "unit_missing_in_product": 2,
    "sum_mismatch": 3,
    "position_no_quantity": 4,
    "position_no_unit": 4,
    "position_no_name": 4,
}

def escape_markdown(text: str) -> str:
    """
    Экранирует специальные символы Markdown V2.
    
    Args:
        text: Исходный текст
        
    Returns:
        str: Экранированный текст
    """
    if not text:
        return "—"
    
    # Символы, которые нужно экранировать в Markdown V2
    special_chars = r'_*[]()~`>#+-=|{}.!'
    result = ""
    text = str(text)
    
    # Обрабатываем отрицательные числа
    if text.startswith("-"):
        result = "\\-" + text[1:]
    else:
        result = text
    
    # Экранируем остальные специальные символы
    for c in special_chars:
        if c != "-" and c in result:  # Минус уже обработан
            result = result.replace(c, f"\\{c}")
    
    return result

def format_number(value: float | None) -> str:
    """
    Форматирует число без разделителей.
    
    Args:
        value: Число для форматирования
        
    Returns:
        str: Отформатированное число или "—"
    """
    if value is None:
        return "—"
    try:
        # Форматируем число и экранируем точку и минус
        num_str = f"{float(value):.2f}".rstrip('0').rstrip('.')
        return escape_markdown(num_str)
    except (ValueError, TypeError):
        return "—"

def format_date(date_str: str) -> str:
    """
    Форматирует дату в читаемый вид.
    
    Args:
        date_str: Строка с датой
        
    Returns:
        str: Отформатированная дата или "—"
    """
    if not date_str:
        return "—"
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.strftime("%d.%m.%Y")
    except ValueError:
        return escape_markdown(date_str)

def get_status_emoji(issues: List[Dict[str, Any]]) -> str:
    """
    Определяет эмодзи-статус позиции по списку проблем.
    
    Args:
        issues: Список проблем
        
    Returns:
        str: Эмодзи-статус
    """
    if not issues:
        return STATUS_EMOJIS["ok"]
    
    # Находим проблему с наивысшим приоритетом
    min_priority = min(
        (ISSUE_PRIORITIES.get(issue["type"], 99) for issue in issues),
        default=99
    )
    
    if min_priority == 1:
        return STATUS_EMOJIS["not_found"]
    elif min_priority == 2:
        return STATUS_EMOJIS["unit_mismatch"]
    elif min_priority == 3:
        return STATUS_EMOJIS["sum_mismatch"]
    else:
        return STATUS_EMOJIS["other"]

def format_position(pos: Dict[str, Any], idx: int, issues: List[Dict[str, Any]]) -> str:
    """
    Форматирует одну позицию накладной.
    
    Args:
        pos: Данные позиции
        idx: Номер позиции
        issues: Список проблем
        
    Returns:
        str: Отформатированная строка позиции
    """
    name = escape_markdown(pos.get("name", ""))
    qty = format_number(pos.get("quantity"))
    unit = escape_markdown(pos.get("unit", ""))
    price = format_number(pos.get("price"))
    total = format_number(pos.get("sum"))
    
    status = get_status_emoji(issues)
    
    return (
        f"{idx}\\. {status} {name}\n"
        f"     {qty} {unit} × {price} = {total}"
    )

def build_message(data: Dict[str, Any], issues: List[Dict[str, Any]]) -> str:
    """
    Строит полное сообщение о накладной.
    
    Args:
        data: Данные накладной
        issues: Список проблем
        
    Returns:
        str: Отформатированное сообщение
    """
    # Если нет позиций, возвращаем специальное сообщение
    positions = data.get("positions", [])
    if not positions:
        return "😕 Не удалось распознать ни одной позиции…"
    
    # Форматируем заголовок
    supplier = escape_markdown(data.get("supplier", ""))
    date = format_date(data.get("date", ""))
    invoice_no = escape_markdown(data.get("number", ""))
    
    header = f"📑 {supplier} • {date}"
    if invoice_no:
        header += f" • № {invoice_no}"
    
    # Считаем статистику
    ok_positions = len([p for p in positions if not any(
        i for i in issues if i.get("index") == positions.index(p) + 1
    )])
    warn_positions = len(positions) - ok_positions
    
    stats = f"✅ {ok_positions} позиций подтверждено"
    if warn_positions > 0:
        stats += f" • ⚠️ {warn_positions} требует внимания"
    
    # Форматируем позиции
    formatted_positions = []
    for i, pos in enumerate(positions, 1):
        pos_issues = [
            issue for issue in issues 
            if issue.get("index") == i
        ]
        formatted_positions.append(format_position(pos, i, pos_issues))
    
    # Добавляем комментарий парсера, если есть
    parser_comment = data.get("parser_comment", "").strip()
    comment_block = f"\n\nℹ️ {escape_markdown(parser_comment)}" if parser_comment else ""
    
    # Собираем сообщение
    message = f"{header}\n{stats}\n\n"
    message += "\n\n".join(formatted_positions)
    message += comment_block
    
    # Проверяем длину сообщения
    if len(message) > 4093:  # Оставляем место для "..."
        # Находим последний полный абзац
        last_paragraph = message[:4090].rfind("\n\n")
        if last_paragraph > 0:
            message = message[:last_paragraph].rstrip() + "\n\n..."
        else:
            message = message[:4090].rstrip() + "..."
    
    return message 