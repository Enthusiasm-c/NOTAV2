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
from .markdown_v2 import md2_escape, format_list_item

logger = structlog.get_logger()

# Константы для эмодзи-статусов
STATUS_EMOJIS = {
    "ok": "✅",
    "not_found": "🔍",
    "unit_mismatch": "📏",
    "sum_mismatch": "💵",
    "other": "❓"
}

# Специальные символы Markdown V2
_MD_V2_SPECIAL = r'_*[]()~`>#+-=|{}.!'

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

def escape_markdown(text: str | None) -> str:
    """
    Экранирует специальные символы Markdown V2.
    
    Args:
        text: Исходный текст
        
    Returns:
        str: Экранированный текст
    """
    if not text:
        return "—"
    
    text = str(text)
    result = ""
    i = 0
    
    while i < len(text):
        # Проверяем, является ли текущий символ эмодзи
        if i + 1 < len(text) and 0x1F300 <= ord(text[i]) <= 0x1F9FF:
            result += text[i]
            i += 1
            continue
            
        # Проверяем, не экранирован ли уже символ
        if i > 0 and text[i-1] == '\\':
            result += text[i]
            i += 1
            continue
            
        # Экранируем специальный символ
        if text[i] in _MD_V2_SPECIAL:
            result += "\\" + text[i]
        else:
            result += text[i]
        i += 1
    
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
        # Форматируем число без лишних нулей после точки
        num_str = f"{float(value):.2f}".rstrip('0').rstrip('.')
        # Экранируем все специальные символы, включая минус и точку
        return md2_escape(num_str)
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
        return md2_escape(date_str)

def get_status_emoji(issues: List[Dict[str, Any]]) -> str:
    """
    Определяет эмодзи-статус для позиции на основе проблем.
    
    Args:
        issues: Список проблем
        
    Returns:
        str: Эмодзи-статус
    """
    if not issues:
        return STATUS_EMOJIS["ok"]
    
    # Определяем тип проблемы с наивысшим приоритетом
    issue_types = [issue.get("type", "unknown_issue") for issue in issues]
    
    if "product_not_found" in issue_types:
        return STATUS_EMOJIS["not_found"]
    elif "unit_mismatch" in issue_types:
        return STATUS_EMOJIS["unit_mismatch"]
    elif "sum_mismatch" in issue_types:
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
    name = md2_escape(pos.get("name", ""))
    qty = format_number(pos.get("quantity"))
    unit = md2_escape(pos.get("unit", ""))
    price = format_number(pos.get("price"))
    total = format_number(pos.get("sum"))
    
    status = get_status_emoji(issues)
    
    return format_list_item(idx, f"{status} {name}") + f"\n     {qty} {unit} × {price} = {total}"

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
    supplier = md2_escape(data.get("supplier", ""))
    date = format_date(data.get("date", ""))
    invoice_no = md2_escape(data.get("number", ""))
    
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
    
    # Собираем части сообщения
    message_parts = []
    message_parts.append(header)
    message_parts.append(stats)
    message_parts.extend(formatted_positions)
    
    # Добавляем комментарий парсера, если есть
    parser_comment = data.get("parser_comment", "").strip()
    if parser_comment:
        message_parts.append(f"ℹ️ {md2_escape(parser_comment)}")
    
    # Собираем сообщение с правильными отступами
    message = header + "\n"  # Заголовок
    message += stats  # Статистика
    
    # Добавляем позиции с отступами
    if formatted_positions:
        message += "\n\n" + "\n\n".join(formatted_positions)
    
    # Добавляем комментарий с отступом
    if parser_comment:
        message += "\n\nℹ️ " + md2_escape(parser_comment)
    
    # Проверяем длину сообщения и обрезаем при необходимости
    if len(message) > 4000:
        # Находим последний полный абзац
        parts = message[:4000].split("\n\n")
        message = "\n\n".join(parts[:-1])
        
        # Добавляем многоточие как обычный текст
        message += "\n\n..."
    
    return message 