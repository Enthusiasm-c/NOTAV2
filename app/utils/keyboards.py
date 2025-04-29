"""
Модуль для создания клавиатур в Telegram-боте.
Содержит функции для генерации различных типов клавиатур.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
import math

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Префиксы для callback-данных
CB_ISSUE_PREFIX = "issue:"         # issue:1, issue:2... (ID строки)
CB_PAGE_PREFIX = "page:"           # page:2 (переход на страницу)
CB_PRODUCT_PREFIX = "product:"     # product:123 (ID товара)
CB_ACTION_PREFIX = "action:"       # action:name, action:qty...
CB_UNIT_PREFIX = "unit:"           # unit:kg, unit:g...
CB_CONVERT_PREFIX = "convert:"     # convert:yes, convert:no
CB_ADD_NEW = "add_new"
CB_ADD_ALL = "add_all_missing"
CB_SEARCH = "search"
CB_BACK = "back"
CB_CANCEL = "cancel"
CB_CONFIRM = "inv_ok"              # Для совместимости с существующим кодом
CB_REVIEW = "review"

# Размер страницы для пагинации
PAGE_SIZE = 5


def kb_summary(missing_count: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для сводки накладной.
    
    :param missing_count: количество проблемных позиций
    :return: клавиатура с кнопками
    """
    buttons = []
    
    if missing_count > 0:
        buttons.append([
            InlineKeyboardButton(text="✅ Confirm", callback_data=CB_CONFIRM),
            InlineKeyboardButton(text=f"🔍 Review ({missing_count})", callback_data=CB_REVIEW)
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="✅ Confirm and send", callback_data=CB_CONFIRM)
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_issues(issues: List[Dict[str, Any]], page: int = 0) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для списка проблемных позиций с пагинацией.
    
    :param issues: список проблемных позиций
    :param page: текущая страница (начиная с 0)
    :return: клавиатура с кнопками
    """
    total_pages = math.ceil(len(issues) / PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    
    buttons = []
    
    # Добавляем кнопки для каждой позиции на текущей странице
    start_idx = page * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, len(issues))
    
    for i in range(start_idx, end_idx):
        issue = issues[i]
        index = issue.get("index", i + 1)
        original = issue.get("original", {})
        name = original.get("name", "Position")
        
        # Ограничиваем длину названия для кнопки
        if len(name) > 25:
            name = name[:22] + "..."
            
        # Получаем иконку проблемы
        issue_type = issue.get("issue", "")
        
        if "Not in database" in issue_type:
            icon = "⚠"
        elif "incorrect match" in issue_type:
            icon = "❔"
        elif "Unit" in issue_type:
            icon = "🔄"
        else:
            icon = "❓"
            
        btn_text = f"{index}. {icon} {name}"
        buttons.append([
            InlineKeyboardButton(text=btn_text, callback_data=f"{CB_ISSUE_PREFIX}{index}")
        ])
    
    # Добавляем кнопки пагинации и управления
    pagination_row = []
    
    # Кнопка "Предыдущая страница"
    if page > 0:
        pagination_row.append(
            InlineKeyboardButton(text="↩ Prev", callback_data=f"{CB_PAGE_PREFIX}{page-1}")
        )
    
    # Кнопка "Добавить все отсутствующие"
    if any("Not in database" in issue.get("issue", "") for issue in issues):
        pagination_row.append(
            InlineKeyboardButton(text="➕ Add All Missing", callback_data=CB_ADD_ALL)
        )
    
    # Кнопка "Следующая страница"
    if page < total_pages - 1:
        pagination_row.append(
            InlineKeyboardButton(text="Next ↪", callback_data=f"{CB_PAGE_PREFIX}{page+1}")
        )
    
    if pagination_row:
        buttons.append(pagination_row)
    
    # Добавляем кнопку "Готово" для возврата к сводке
    buttons.append([
        InlineKeyboardButton(text="✅ Done", callback_data=CB_CONFIRM)
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_issue_edit(issue: Dict[str, Any]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для редактирования конкретной проблемной позиции.
    
    :param issue: данные о проблемной позиции
    :return: клавиатура с кнопками
    """
    issue_type = issue.get("issue", "")
    original = issue.get("original", {})
    
    buttons = []
    
    # Первый ряд - основные действия
    row1 = [
        InlineKeyboardButton(text="📦 Product", callback_data=f"{CB_ACTION_PREFIX}name"),
        InlineKeyboardButton(text="🔢 Quantity", callback_data=f"{CB_ACTION_PREFIX}qty"),
        InlineKeyboardButton(text="📏 Unit", callback_data=f"{CB_ACTION_PREFIX}unit")
    ]
    buttons.append(row1)
    
    # Второй ряд - дополнительные действия в зависимости от типа проблемы
    row2 = []
    
    if "Not in database" in issue_type:
        row2.append(
            InlineKeyboardButton(text="➕ Add as new", callback_data=f"{CB_ACTION_PREFIX}add_new")
        )
    
    if "Unit" in issue_type and "product" in issue:
        row2.append(
            InlineKeyboardButton(
                text="🔄 Convert units", 
                callback_data=f"{CB_ACTION_PREFIX}convert"
            )
        )
    
    if row2:
        buttons.append(row2)
    
    # Третий ряд - удаление и возврат
    row3 = [
        InlineKeyboardButton(text="🗑️ Delete", callback_data=f"{CB_ACTION_PREFIX}delete"),
        InlineKeyboardButton(text="◀️ Back", callback_data=CB_BACK)
    ]
    buttons.append(row3)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_product_select(
    products: List[Dict[str, Any]], 
    page: int = 0, 
    query: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора товара с пагинацией.
    
    :param products: список товаров
    :param page: текущая страница
    :param query: поисковый запрос (если есть)
    :return: клавиатура с кнопками
    """
    total_pages = math.ceil(len(products) / PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    
    buttons = []
    
    # Добавляем кнопки для каждого товара на текущей странице
    start_idx = page * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, len(products))
    
    for i in range(start_idx, end_idx):
        product = products[i]
        product_id = product.get("id")
        name = product.get("name", "")
        unit = product.get("unit", "")
        
        # Форматируем текст кнопки
        if len(name) > 25:
            name = name[:22] + "..."
        
        display_text = f"{name} ({unit})"
        buttons.append([
            InlineKeyboardButton(text=display_text, callback_data=f"{CB_PRODUCT_PREFIX}{product_id}")
        ])
    
    # Добавляем кнопки пагинации
    pagination_row = []
    
    # Кнопка "Предыдущая страница"
    if page > 0:
        pagination_row.append(
            InlineKeyboardButton(text="◀️ Prev", callback_data=f"{CB_PAGE_PREFIX}{page-1}")
        )
    
    # Информация о странице (если несколько страниц)
    if total_pages > 1:
        pagination_row.append(
            InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop")
        )
    
    # Кнопка "Следующая страница"
    if page < total_pages - 1:
        pagination_row.append(
            InlineKeyboardButton(text="Next ▶️", callback_data=f"{CB_PAGE_PREFIX}{page+1}")
        )
    
    if pagination_row:
        buttons.append(pagination_row)
    
    # Добавляем кнопки поиска и создания нового товара
    action_row = []
    action_row.append(
        InlineKeyboardButton(text="🔍 Search", callback_data=CB_SEARCH)
    )
    action_row.append(
        InlineKeyboardButton(text="➕ New product", callback_data=CB_ADD_NEW)
    )
    buttons.append(action_row)
    
    # Кнопка "Назад"
    buttons.append([
        InlineKeyboardButton(text="◀️ Back", callback_data=CB_BACK)
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_unit_select(units: List[str]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора единицы измерения.
    
    :param units: список доступных единиц измерения
    :return: клавиатура с кнопками
    """
    buttons = []
    
    # Размещаем кнопки по 3 в ряд
    row = []
    for i, unit in enumerate(units):
        row.append(
            InlineKeyboardButton(text=unit, callback_data=f"{CB_UNIT_PREFIX}{unit}")
        )
        
        if (i + 1) % 3 == 0 or i == len(units) - 1:
            buttons.append(row)
            row = []
    
    # Добавляем кнопку "Назад"
    buttons.append([
        InlineKeyboardButton(text="◀️ Back", callback_data=CB_BACK)
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_convert_confirm() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для подтверждения конвертации единиц измерения.
    
    :return: клавиатура с кнопками
    """
    buttons = [
        [
            InlineKeyboardButton(text="✅ Yes", callback_data=f"{CB_CONVERT_PREFIX}yes"),
            InlineKeyboardButton(text="❌ No", callback_data=f"{CB_CONVERT_PREFIX}no")
        ],
        [
            InlineKeyboardButton(text="◀️ Back", callback_data=CB_BACK)
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_confirm() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для финального подтверждения.
    
    :return: клавиатура с кнопками
    """
    buttons = [
        [
            InlineKeyboardButton(text="✅ Confirm and send", callback_data=CB_CONFIRM)
        ],
        [
            InlineKeyboardButton(text="◀️ Back to edits", callback_data=CB_BACK)
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_back_only() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру только с кнопкой "Назад".
    
    :return: клавиатура с кнопкой "Назад"
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️ Back", callback_data=CB_BACK)
        ]
    ])
