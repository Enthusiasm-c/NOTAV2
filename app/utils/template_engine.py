"""
Модуль для генерации форматированных сообщений в Telegram.
Используется HTML-форматирование для лучшей читаемости.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
import re
import math
import html

# Константы для форматирования
PAGE_SIZE = 5  # Количество позиций на странице при пагинации
MAX_TABLE_WIDTH = 40  # Максимальная ширина таблицы в символах

def escape_html(text: str) -> str:
    """
    Экранирует специальные символы HTML.
    """
    if not text:
        return ""
    return html.escape(text)


def render_summary(data: Dict[str, Any]) -> str:
    """
    Создает HTML-разметку для сводки по накладной.
    
    :param data: данные накладной
    :return: HTML-форматированный текст
    """
    # Подсчитываем количество позиций и проблем
    positions = data.get("positions", [])
    active_positions = [p for p in positions if not p.get("deleted", False)]
    
    total_positions = len(active_positions)
    
    if "issues" in data:
        issues = data["issues"]
    else:
        # Если issues не передан, пытаемся выделить проблемные позиции
        issues = []
        for pos in active_positions:
            if pos.get("match_id") is None or pos.get("confidence", 1.0) < 0.85:
                issues.append({"index": positions.index(pos) + 1, "original": pos})
    
    problematic_count = len(issues)
    matched_count = total_positions - problematic_count
    
    # Формируем основную информацию о накладной
    supplier = escape_html(data.get("supplier", "Unknown"))
    date = escape_html(data.get("date", "Unknown"))
    invoice_number = escape_html(data.get("number", ""))
    
    # Собираем финальный HTML
    result = f"""📄 <b>Invoice draft</b>

🏷️ <b>Supplier:</b> {supplier}
📅 <b>Date:</b> {date}{f" №{invoice_number}" if invoice_number else ""}

<b>Items parsed:</b> {total_positions}  
✅ <b>Matched:</b> {matched_count}  """
    
    if problematic_count > 0:
        result += f"❓ <b>Need review:</b> {problematic_count}"
    else:
        result += "✅ <b>All items matched!</b>"
    
    return result


def get_issue_icon(issue: Dict[str, Any]) -> str:
    """
    Возвращает иконку в зависимости от типа проблемы.
    """
    issue_type = issue.get("issue", "")
    original = issue.get("original", {})
    
    if "Not in database" in issue_type:
        return "⚠"
    elif "incorrect match" in issue_type or original.get("confidence", 1.0) < 0.85:
        return "❔"
    elif "Unit" in issue_type:
        return "🔄"
    elif original.get("ignored", False):
        return "❌"
    else:
        return "❓"


def render_issues(data: Dict[str, Any], page: int = 0) -> str:
    """
    Создает HTML-разметку для страницы со списком проблемных позиций.
    
    :param data: данные накладной с списком проблемных позиций
    :param page: номер страницы (начиная с 0)
    :return: HTML-форматированный текст
    """
    issues = data.get("issues", [])
    
    if not issues:
        return "<b>No issues to review!</b>"
    
    # Рассчитываем пагинацию
    total_pages = math.ceil(len(issues) / PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))  # Ограничиваем страницу допустимыми значениями
    
    start_idx = page * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, len(issues))
    
    current_issues = issues[start_idx:end_idx]
    
    # Формируем заголовок
    result = f"❗ <b>Items to review — page {page + 1} / {total_pages}</b>\n\n<code>"
    
    # Формируем таблицу
    # Заголовок таблицы
    result += f"{'#':<3} {'Invoice item':<20} {'Issue':<15}\n"
    
    # Строки таблицы
    for issue in current_issues:
        index = issue.get("index", 0)
        original = issue.get("original", {})
        
        # Получаем название для отображения
        item_name = original.get("name", "Unknown")
        unit = original.get("unit", "")
        if unit:
            item_name += f" {unit}"
        
        # Ограничиваем длину названия
        if len(item_name) > 20:
            item_name = item_name[:17] + "..."
        
        # Получаем тип проблемы
        issue_type = issue.get("issue", "Unknown issue")
        icon = get_issue_icon(issue)
        
        # Определяем тип проблемы для отображения
        if "Not in database" in issue_type:
            display_issue = "Not in DB"
        elif "incorrect match" in issue_type:
            display_issue = "Low confidence"
        elif "Unit" in issue_type:
            display_issue = "Unit mismatch"
        else:
            display_issue = issue_type[:15]  # Ограничиваем длину
        
        # Добавляем строку в таблицу
        result += f"{index:<3} {item_name:<20} {icon} {display_issue:<15}\n"
    
    result += "</code>"
    
    # Добавляем инструкцию
    result += "\n\nClick on an item to edit or use pagination buttons below."
    
    return result


def render_issue_edit_view(issue: Dict[str, Any]) -> str:
    """
    Создает HTML-разметку для редактирования отдельной проблемной позиции.
    
    :param issue: данные о проблемной позиции
    :return: HTML-форматированный текст
    """
    original = issue.get("original", {})
    
    # Получаем основные данные о позиции
    index = issue.get("index", 0)
    name = escape_html(original.get("name", "Unknown"))
    quantity = original.get("quantity", 0)
    unit = escape_html(original.get("unit", ""))
    price = original.get("price", 0)
    sum_val = original.get("sum", 0)
    
    # Получаем тип проблемы
    issue_type = issue.get("issue", "Unknown issue")
    icon = get_issue_icon(issue)
    
    if "Not in database" in issue_type:
        issue_description = "Product not found in database"
    elif "incorrect match" in issue_type:
        issue_description = "Possible incorrect match"
    elif "Unit" in issue_type:
        issue_description = "Unit measurement discrepancy"
    else:
        issue_description = issue_type
    
    # Формируем заголовок
    result = f"{icon} <b>Edit position #{index}</b>\n\n"
    
    # Детали позиции
    result += f"<b>Name:</b> {name}\n"
    result += f"<b>Quantity:</b> {quantity} {unit}\n"
    
    if price:
        result += f"<b>Price:</b> {price:,.2f}\n"
    
    if sum_val:
        result += f"<b>Sum:</b> {sum_val:,.2f}\n"
    
    # Информация о проблеме
    result += f"\n<b>Issue:</b> {issue_description}\n"
    
    # Если есть данные о сопоставленном товаре, добавляем их
    if product := issue.get("product"):
        result += f"\n<b>Database match:</b>\n"
        result += f"<b>→ Name:</b> {escape_html(product.name)}\n"
        result += f"<b>→ Unit:</b> {escape_html(product.unit)}\n"
    
    # Инструкция
    result += "\nSelect an action below to fix the issue:"
    
    return result


def render_product_selection(
    products: List[Dict[str, Any]], 
    query: str,
    page: int = 0,
    page_size: int = 5
) -> str:
    """
    Создает HTML-разметку для выбора товара из списка.
    
    :param products: список товаров для выбора
    :param query: поисковый запрос
    :param page: номер страницы
    :param page_size: размер страницы
    :return: HTML-форматированный текст
    """
    # Рассчитываем пагинацию
    total_pages = math.ceil(len(products) / page_size)
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(products))
    
    current_products = products[start_idx:end_idx]
    
    # Формируем заголовок
    query_html = escape_html(query)
    result = f"🔍 <b>Product selection for '{query_html}'</b>\n"
    
    if total_pages > 1:
        result += f"<i>Page {page + 1} of {total_pages}</i>\n"
    
    result += "\n<b>Select a product from the list:</b>\n\n"
    
    # Список товаров
    for i, product in enumerate(current_products, start=1):
        name = escape_html(product.get("name", "Unknown"))
        unit = escape_html(product.get("unit", ""))
        confidence = product.get("confidence", 0) * 100
        
        result += f"{i}. <b>{name}</b> ({unit})"
        
        if confidence < 100:
            result += f" <i>{confidence:.0f}% match</i>"
        
        result += "\n"
    
    if not current_products:
        result += "<i>No products found. Try a different search query or create a new product.</i>"
    
    return result


def render_final_preview(
    invoice_data: Dict[str, Any],
    original_issues: List[Dict[str, Any]],
    fixed_issues: Dict[int, Dict[str, Any]]
) -> str:
    """
    Создает HTML-разметку для финального просмотра накладной перед отправкой.
    
    :param invoice_data: данные накладной
    :param original_issues: исходный список проблем
    :param fixed_issues: информация об исправленных проблемах
    :return: HTML-форматированный текст
    """
    # Получаем основную информацию о накладной
    supplier = escape_html(invoice_data.get("supplier", "Unknown"))
    date = escape_html(invoice_data.get("date", "Unknown"))
    invoice_number = escape_html(invoice_data.get("number", ""))
    
    # Формируем заголовок
    result = f"✅ <b>Invoice ready to send</b>\n\n"
    result += f"🏷️ <b>Supplier:</b> {supplier}\n"
    result += f"📅 <b>Date:</b> {date}{f' №{invoice_number}' if invoice_number else ''}\n\n"
    
    # Обрабатываем позиции
    positions = invoice_data.get("positions", [])
    active_positions = [p for p in positions if not p.get("deleted", False)]
    
    fixed_count = len(fixed_issues)
    original_issues_count = len(original_issues)
    remaining_issues = original_issues_count - fixed_count
    
    # Добавляем статистику
    result += f"<b>Total items:</b> {len(active_positions)}\n"
    
    if fixed_count > 0:
        result += f"✅ <b>Fixed issues:</b> {fixed_count}\n"
    
    if remaining_issues > 0:
        result += f"⚠️ <b>Remaining issues:</b> {remaining_issues}\n"
    else:
        result += "✅ <b>All issues resolved!</b>\n"
    
    # Добавляем общую сумму, если она есть
    if "total_sum" in invoice_data:
        total_sum = invoice_data["total_sum"]
        result += f"\n💰 <b>Total amount:</b> {total_sum:,.2f}\n"
    else:
        # Рассчитываем сумму из позиций
        total_sum = sum(float(p.get("sum", 0)) if p.get("sum") else 0 for p in active_positions)
        result += f"\n💰 <b>Total amount:</b> {total_sum:,.2f}\n"
    
    # Добавляем инструкцию
    if remaining_issues > 0:
        result += "\n⚠️ <i>Note: Some issues remain unresolved, but you can still proceed.</i>"
    
    result += "\n\nPlease confirm to send the invoice to Syrve."
    
    return result
