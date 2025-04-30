"""
Форматтеры для модуля issue_editor.

Этот модуль содержит функции для форматирования сообщений и клавиатур.
"""

from typing import Dict, Any, List, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.config.issue_editor_constants import (
    CB_ISSUE_PREFIX,
    CB_PAGE_PREFIX,
    CB_PRODUCT_PREFIX,
    CB_ACTION_PREFIX,
    CB_UNIT_PREFIX,
    CB_CONVERT_PREFIX,
    CB_BACK,
    CB_SEARCH,
    PAGE_SIZE
)
from .constants import CB_CANCEL

def get_issue_icon(issue: Dict[str, Any]) -> str:
    """
    Возвращает иконку для типа проблемы.
    
    Args:
        issue: словарь с данными о проблеме
        
    Returns:
        str: эмодзи-иконка
    """
    issue_type = issue.get("type", "")
    if issue_type == "product":
        return "🔍"
    elif issue_type == "unit":
        return "📏"
    elif issue_type == "quantity":
        return "🔢"
    elif issue_type == "price":
        return "💰"
    return "❓"

async def format_summary_message(data: Dict[str, Any]) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Форматирует сообщение с итоговой информацией.
    
    Args:
        data: словарь с данными накладной
        
    Returns:
        Tuple[str, InlineKeyboardMarkup]: (текст сообщения, клавиатура)
    """
    text = "📋 *Итоговая информация*\n\n"
    
    # Добавляем информацию о поставщике
    text += f"*Поставщик:* {data.get('supplier', 'Не указан')}\n"
    text += f"*Дата:* {data.get('date', 'Не указана')}\n"
    text += f"*Номер:* {data.get('number', 'Не указан')}\n\n"
    
    # Добавляем список позиций
    text += "*Позиции:*\n"
    for pos in data.get("positions", []):
        if not pos.get("deleted", False):
            text += f"• {pos.get('name', 'Без названия')} - "
            text += f"{pos.get('quantity', 0)} {pos.get('unit', 'шт')} - "
            text += f"{pos.get('price', 0)} ₽\n"
    
    # Добавляем общую сумму
    text += f"\n*Итого:* {data.get('total_sum', 0)} ₽"
    
    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="inv_ok"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data="inv_edit")
        ]
    ])
    
    return text, keyboard

async def format_issues_list(
    data: Dict[str, Any], 
    page: int = 0
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Форматирует список проблем для редактирования.
    
    Args:
        data: словарь с данными накладной
        page: номер страницы
        
    Returns:
        Tuple[str, InlineKeyboardMarkup]: (текст сообщения, клавиатура)
    """
    issues = data.get("issues", [])
    total_pages = (len(issues) + PAGE_SIZE - 1) // PAGE_SIZE
    
    text = "📝 *Список проблем для редактирования*\n\n"
    
    # Добавляем проблемы для текущей страницы
    start_idx = page * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, len(issues))
    
    for i, issue in enumerate(issues[start_idx:end_idx], start=start_idx + 1):
        icon = get_issue_icon(issue)
        text += f"{i}. {icon} {issue.get('description', 'Без описания')}\n"
    
    # Добавляем информацию о страницах
    if total_pages > 1:
        text += f"\nСтраница {page + 1} из {total_pages}"
    
    # Создаем клавиатуру
    keyboard = []
    
    # Кнопки для проблем
    for i, issue in enumerate(issues[start_idx:end_idx], start=start_idx + 1):
        keyboard.append([
            InlineKeyboardButton(
                text=f"{i}. {issue.get('description', '')[:30]}...",
                callback_data=f"{CB_ISSUE_PREFIX}{i-1}"
            )
        ])
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"{CB_PAGE_PREFIX}{page-1}")
        )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="➡️", callback_data=f"{CB_PAGE_PREFIX}{page+1}")
        )
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопки действий
    keyboard.append([
        InlineKeyboardButton(text="🔍 Поиск", callback_data=CB_SEARCH),
        InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)
    ])
    
    return text, InlineKeyboardMarkup(inline_keyboard=keyboard)

async def format_issue_edit(
    issue: Dict[str, Any]
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Форматирует форму редактирования проблемы.
    
    Args:
        issue: словарь с данными о проблеме
        
    Returns:
        Tuple[str, InlineKeyboardMarkup]: (текст сообщения, клавиатура)
    """
    text = "✏️ *Редактирование*\n\n"
    
    # Добавляем описание проблемы
    text += f"*Проблема:* {issue.get('description', 'Без описания')}\n\n"
    
    # Добавляем текущие значения
    text += "*Текущие значения:*\n"
    for field, value in issue.get("current_values", {}).items():
        text += f"• {field}: {value}\n"
    
    # Создаем клавиатуру
    keyboard = []
    
    # Кнопки для редактирования полей
    for field in issue.get("editable_fields", []):
        keyboard.append([
            InlineKeyboardButton(
                text=f"✏️ {field}",
                callback_data=f"{CB_ACTION_PREFIX}{field}"
            )
        ])
    
    # Кнопки навигации
    keyboard.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK),
        InlineKeyboardButton(text="❌ Отмена", callback_data=CB_CANCEL)
    ])
    
    return text, InlineKeyboardMarkup(inline_keyboard=keyboard)

async def format_product_select(
    products: List[Dict[str, Any]],
    query: str,
    page: int = 0
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Форматирует список товаров для выбора.
    
    Args:
        products: список товаров
        query: поисковый запрос
        page: номер страницы
        
    Returns:
        Tuple[str, InlineKeyboardMarkup]: (текст сообщения, клавиатура)
    """
    text = f"🔍 *Поиск товаров: {query}*\n\n"
    
    if not products:
        text += "Товары не найдены"
    else:
        for i, product in enumerate(products, 1):
            text += f"{i}. {product['name']} ({product['unit']})\n"
    
    # Создаем клавиатуру
    keyboard = []
    
    # Кнопки для выбора товаров
    for i, product in enumerate(products, 1):
        keyboard.append([
            InlineKeyboardButton(
                text=f"{i}. {product['name'][:30]}...",
                callback_data=f"{CB_PRODUCT_PREFIX}{product['id']}"
            )
        ])
    
    # Кнопки навигации
    keyboard.append([
        InlineKeyboardButton(text="🔍 Новый поиск", callback_data=CB_SEARCH),
        InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)
    ])
    
    return text, InlineKeyboardMarkup(inline_keyboard=keyboard)

def format_field_prompt(field: str, current_value: str) -> str:
    """
    Форматирует подсказку для ввода значения поля.
    
    Args:
        field: название поля
        current_value: текущее значение
        
    Returns:
        str: текст подсказки
    """
    return (
        f"✏️ Введите новое значение для поля *{field}*\n\n"
        f"Текущее значение: {current_value}\n\n"
        "Или выберите из списка:"
    ) 