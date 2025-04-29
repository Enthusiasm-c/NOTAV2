"""
Улучшенный UI-редактор спорных позиций для Nota V2.

Основные улучшения:
1. Игнорирование регистра при поиске
2. Фильтрация полуфабрикатов (s/f) из предложений
3. Механизм самообучения сопоставлений
4. Улучшенный интерфейс пользователя
"""

from __future__ import annotations

import re
import math
import structlog
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ForceReply
)

# Адаптивный импорт для разных версий aiogram
try:
    # aiogram 3.x.x
    from aiogram.filters import Text
except ImportError:
    try:
        # aiogram 3.x альтернативное расположение
        from aiogram.filters.text import Text
    except ImportError:
        # Если не найдено - создаем свою реализацию
        class Text:
            """Совместимая реализация фильтра Text."""
            def __init__(self, text=None):
                self.text = text if isinstance(text, list) else [text] if text else None
            
            def __call__(self, message):
                if hasattr(message, 'text'):
                    # Для текстовых сообщений
                    return self.text is None or message.text in self.text
                elif hasattr(message, 'data'):
                    # Для callback_query
                    return self.text is None or message.data in self.text
                return False

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from sqlalchemy import select, func, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models.product import Product
from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.product_name_lookup import ProductNameLookup
from app.models.invoice_state import InvoiceEditStates

# Импортируем модули обработки единиц измерения
try:
    from app.utils.unit_converter import normalize_unit, is_compatible_unit, convert
except ImportError:
    # Встроенная версия функций, если модуль недоступен
    def normalize_unit(unit_str: str) -> str:
        """Нормализация единиц измерения."""
        if not unit_str:
            return ""
        
        # Словарь алиасов единиц измерения
        UNIT_ALIASES = {
            # Объем
            "l": "l", "ltr": "l", "liter": "l", "liters": "l",
            "ml": "ml", "milliliter": "ml", "milliliters": "ml",
            
            # Вес
            "kg": "kg", "kilo": "kg", "kilogram": "kg",
            "g": "g", "gr": "g", "gram": "g", "grams": "g",
            
            # Штучные
            "pcs": "pcs", "pc": "pcs", "piece": "pcs", "pieces": "pcs",
            "pack": "pack", "package": "pack", "pkg": "pack",
            "box": "box", "boxes": "box",
            
            # Индонезийские алиасы
            "liter": "l", "lt": "l",
            "mililiter": "ml", "mili": "ml",
            "kilogram": "kg", "kilo": "kg",
            "gram": "g",
            "buah": "pcs", "biji": "pcs", "pcs": "pcs", "potong": "pcs",
            "paket": "pack", "pak": "pack",
            "kotak": "box", "dus": "box", "kardus": "box",
        }
        
        unit_str = unit_str.lower().strip()
        return UNIT_ALIASES.get(unit_str, unit_str)
    
    def is_compatible_unit(unit1: str, unit2: str) -> bool:
        """Проверка совместимости единиц измерения."""
        unit1 = normalize_unit(unit1)
        unit2 = normalize_unit(unit2)
        
        # Одинаковые единицы всегда совместимы
        if unit1 == unit2:
            return True
        
        # Проверка категорий
        volume_units = {"l", "ml"}
        weight_units = {"kg", "g"}
        countable_units = {"pcs", "pack", "box"}
        
        if unit1 in volume_units and unit2 in volume_units:
            return True
        if unit1 in weight_units and unit2 in weight_units:
            return True
        if unit1 in countable_units and unit2 in countable_units:
            return False  # Штучные единицы обычно несовместимы без доп. знаний
        
        return False
    
    def convert(value: float, from_unit: str, to_unit: str) -> Optional[float]:
        """Конвертация между единицами измерения."""
        from_unit = normalize_unit(from_unit)
        to_unit = normalize_unit(to_unit)
        
        # Если единицы одинаковые
        if from_unit == to_unit:
            return value
        
        # Коэффициенты конвертации
        conversion_factors = {
            ("ml", "l"): 0.001,
            ("l", "ml"): 1000,
            ("g", "kg"): 0.001,
            ("kg", "g"): 1000,
        }
        
        # Поиск коэффициента
        factor = conversion_factors.get((from_unit, to_unit))
        if factor is not None:
            return value * factor
        
        # Нет конвертации
        return None

from app.config import settings
from app.utils.change_logger import log_change, log_delete, log_save_new
from app.utils.keyboards import kb_field_selector, kb_after_edit, FieldCallback, IssueCallback

logger = structlog.get_logger()
router = Router(name="issue_editor")

# ───────────────────────── Constants ────────────────────────
# Размер страницы для пагинации
PAGE_SIZE = 5

# Префиксы для callback-данных
CB_ISSUE_PREFIX = "issue:"
CB_PAGE_PREFIX = "page:"
CB_PRODUCT_PREFIX = "product:"
CB_ACTION_PREFIX = "action:"
CB_UNIT_PREFIX = "unit:"
CB_CONVERT_PREFIX = "convert:"
CB_ADD_NEW = "add_new"
CB_ADD_ALL = "add_all_missing"
CB_SEARCH = "search"
CB_BACK = "back"
CB_CANCEL = "cancel"
CB_CONFIRM = "inv_ok"        # Для совместимости с существующим кодом
CB_REVIEW = "review"

# Для обратной совместимости
LEGACY_ISSUE_PREFIX = "issue_"
LEGACY_PAGE_PREFIX = "page_"
LEGACY_ACTION_PREFIX = "action_"

# Константы для полуфабрикатов
SEMIFINISHED_PATTERNS = [r's/f', r's/finished', r'semi.?finished', r'semi.?fabricated']
MIN_CONFIDENCE_FOR_LEARNING = 0.90  # Минимальная уверенность для автообучения


# ───────────────────────── Helpers ────────────────────────
def clean_name_for_comparison(name: str) -> str:
    """
    Подготавливает строку названия для сравнения:
    - Приводит к нижнему регистру
    - Убирает лишние пробелы
    - Убирает знаки пунктуации
    """
    if not name:
        return ""
    
    # Приводим к нижнему регистру
    name = name.lower()
    
    # Удаляем лишние пробелы
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Удаляем или заменяем знаки пунктуации
    name = re.sub(r'[.,;:\-_()]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name


def is_semifinished(name: str) -> bool:
    """
    Проверяет, является ли товар полуфабрикатом по маркерам в названии.
    
    :param name: название товара
    :return: True если это полуфабрикат, иначе False
    """
    name_lower = name.lower()
    return any(re.search(pattern, name_lower) for pattern in SEMIFINISHED_PATTERNS)


async def get_products_by_name(
    session: AsyncSession, 
    name_query: str, 
    limit: int = 20,
    exclude_semifinished: bool = True
) -> List[Dict[str, Any]]:
    """
    Ищет товары по части имени с учетом полуфабрикатов.
    
    :param session: асинхронная сессия SQLAlchemy
    :param name_query: строка поиска
    :param limit: максимальное количество результатов
    :param exclude_semifinished: исключить полуфабрикаты из результатов
    :return: список товаров
    """
    # Нормализуем запрос
    normalized_query = clean_name_for_comparison(name_query)
    
    # Поиск по базе данных
    stmt = (
        select(Product.id, Product.name, Product.unit)
        .where(func.lower(Product.name).like(f"%{normalized_query}%"))
        .order_by(Product.name)
        .limit(limit)
    )
    
    result = await session.execute(stmt)
    products = []
    
    for row in result:
        product_id, name, unit = row
        
        # Фильтрация полуфабрикатов если нужно
        if exclude_semifinished and is_semifinished(name):
            continue
        
        # Вычисляем степень соответствия
        name_normalized = clean_name_for_comparison(name)
        # Простой рейтинг соответствия на основе вхождения подстроки
        confidence = 0.85  # Базовая уверенность для точных совпадений из БД
        
        # Повышаем уверенность для более точных совпадений
        if normalized_query == name_normalized:
            confidence = 1.0
        elif normalized_query in name_normalized.split():
            confidence = 0.95
            
        products.append({
            "id": product_id,
            "name": name,
            "unit": unit,
            "confidence": confidence
        })
    
    return products


async def save_product_match(
    session: AsyncSession, 
    parsed_name: str, 
    product_id: int
) -> bool:
    """
    Сохраняет сопоставление названия товара с ID для будущего использования.
    
    :param session: асинхронная сессия SQLAlchemy
    :param parsed_name: распознанное название товара
    :param product_id: ID товара в базе данных
    :return: True если успешно, иначе False
    """
    if not parsed_name or not product_id:
        return False
    
    try:
        # Проверяем существование товара
        res = await session.execute(
            select(Product.id).where(Product.id == product_id)
        )
        if not res.scalar_one_or_none():
            logger.warning("Cannot add lookup entry - product does not exist", 
                          product_id=product_id)
            return False
        
        # Проверяем, нет ли уже такого сопоставления
        res = await session.execute(
            select(ProductNameLookup.id).where(
                ProductNameLookup.alias == parsed_name
            )
        )
        existing_id = res.scalar_one_or_none()
        
        if existing_id:
            # Обновляем существующее сопоставление
            await session.execute(
                update(ProductNameLookup)
                .where(ProductNameLookup.id == existing_id)
                .values(product_id=product_id)
            )
            logger.info("Updated existing lookup entry", 
                       lookup_id=existing_id, 
                       parsed_name=parsed_name, 
                       product_id=product_id)
        else:
            # Создаем новое сопоставление
            stmt = insert(ProductNameLookup).values(
                alias=parsed_name,
                product_id=product_id
            )
            await session.execute(stmt)
            logger.info("Added new lookup entry", 
                       parsed_name=parsed_name, 
                       product_id=product_id)
        
        # Коммитим изменения
        await session.commit()
        return True
    
    except Exception as e:
        await session.rollback()
        logger.error("Failed to save product match", 
                    error=str(e), 
                    parsed_name=parsed_name, 
                    product_id=product_id)
        return False
# ───────────────────────── UI Formatting Functions ────────────────────────

async def format_summary_message(data: Dict[str, Any]) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Форматирует сообщение со сводкой накладной.
    
    :param data: данные накладной
    :return: текст сообщения и клавиатура
    """
    # Подсчитываем позиции и проблемы
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
    
    # Получаем основную информацию о накладной
    supplier = data.get("supplier", "Unknown")
    date = data.get("date", "Unknown")
    invoice_number = data.get("number", "")
    
    # Форматируем сводку
    message = f"📄 <b>Invoice draft</b>\n\n"
    message += f"🏷️ <b>Supplier:</b> {supplier}\n"
    message += f"📅 <b>Date:</b> {date}{f' №{invoice_number}' if invoice_number else ''}\n\n"
    message += f"<b>Items parsed:</b> {total_positions}  \n"
    message += f"✅ <b>Matched:</b> {matched_count}  \n"
    
    if problematic_count > 0:
        message += f"❓ <b>Need review:</b> {problematic_count}"
    else:
        message += "✅ <b>All items matched!</b>"
    
    # Создаем клавиатуру с кнопками
    keyboard = []
    
    if problematic_count > 0:
        keyboard.append([
            InlineKeyboardButton(text="✅ Confirm", callback_data="inv_ok"),
            InlineKeyboardButton(text=f"🔍 Review ({problematic_count})", callback_data="inv_edit")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="✅ Confirm and send", callback_data="inv_ok")
        ])
    
    return message, InlineKeyboardMarkup(inline_keyboard=keyboard)


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


async def format_issues_list(
    data: Dict[str, Any], 
    page: int = 0
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Форматирует список проблемных позиций с пагинацией.
    
    :param data: данные накладной с проблемными позициями
    :param page: номер страницы (начиная с 0)
    :return: текст сообщения и клавиатура
    """
    issues = data.get("issues", [])
    
    # Рассчитываем пагинацию
    total_pages = math.ceil(len(issues) / PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    
    # Создаем заголовок
    message = f"❗ <b>Items to review — page {page+1} / {total_pages}</b>\n\n<code>"
    
    # Формируем таблицу
    # Заголовок таблицы
    message += f"{'#':<3} {'Invoice item':<20} {'Issue':<15}\n"
    
    # Получаем позиции для текущей страницы
    start_idx = page * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, len(issues))
    current_issues = issues[start_idx:end_idx]
    
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
        message += f"{index:<3} {item_name:<20} {icon} {display_issue:<15}\n"
    
    message += "</code>"
    
    # Добавляем инструкцию
    message += "\n\nClick on an item to edit or use pagination buttons below."
    
    # Создаем клавиатуру с кнопками для позиций
    buttons = []
    
    # Кнопки для каждой позиции
    for issue in current_issues:
        index = issue.get("index", 0)
        original = issue.get("original", {})
        name = original.get("name", "")[:15]
        
        issue_type = issue.get("issue", "")
        icon = get_issue_icon(issue)
                
        btn_text = f"{index}. {icon} {name}"
        buttons.append([
            InlineKeyboardButton(text=btn_text, callback_data=f"{CB_ISSUE_PREFIX}{index}")
        ])
    
    # Добавляем кнопки пагинации
    pagination_row = []
    
    if page > 0:
        pagination_row.append(
            InlineKeyboardButton(text="◀️ Prev", callback_data=f"{CB_PAGE_PREFIX}{page-1}")
        )
    
    if any("Not in database" in issue.get("issue", "") for issue in issues):
        pagination_row.append(
            InlineKeyboardButton(text="➕ Add All Missing", callback_data=CB_ADD_ALL)
        )
    
    if page < total_pages - 1:
        pagination_row.append(
            InlineKeyboardButton(text="Next ▶️", callback_data=f"{CB_PAGE_PREFIX}{page+1}")
        )
    
    if pagination_row:
        buttons.append(pagination_row)
    
    # Добавляем кнопку "Готово"
    buttons.append([
        InlineKeyboardButton(text="✅ Done", callback_data=CB_CONFIRM)
    ])
    
    return message, InlineKeyboardMarkup(inline_keyboard=buttons)


async def format_issue_edit(
    issue: Dict[str, Any]
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Форматирует сообщение для редактирования конкретной проблемной позиции.
    
    :param issue: данные о проблемной позиции
    :return: текст сообщения и клавиатура
    """
    original = issue.get("original", {})
    
    # Получаем основные данные о позиции
    index = issue.get("index", 0)
    name = original.get("name", "Unknown")
    quantity = original.get("quantity", 0)
    unit = original.get("unit", "")
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
    message = f"{icon} <b>Edit position #{index}</b>\n\n"
    
    # Детали позиции
    message += f"<b>Name:</b> {name}\n"
    message += f"<b>Quantity:</b> {quantity} {unit}\n"
    
    if price:
        message += f"<b>Price:</b> {price:,.2f}\n"
    
    if sum_val:
        message += f"<b>Sum:</b> {sum_val:,.2f}\n"
    
    # Информация о проблеме
    message += f"\n<b>Issue:</b> {issue_description}\n"
    
    # Если есть данные о сопоставленном товаре, добавляем их
    if product := issue.get("product"):
        message += f"\n<b>Database match:</b>\n"
        message += f"<b>→ Name:</b> {product.name}\n"
        message += f"<b>→ Unit:</b> {product.unit}\n"
    
    # Инструкция
    message += "\nSelect an action below to fix the issue:"
    
    # Создаем клавиатуру
    buttons = [
        # Первый ряд - основные действия
        [
            InlineKeyboardButton(text="📦 Product", callback_data=f"{CB_ACTION_PREFIX}name"),
            InlineKeyboardButton(text="🔢 Quantity", callback_data=f"{CB_ACTION_PREFIX}qty"),
            InlineKeyboardButton(text="📏 Unit", callback_data=f"{CB_ACTION_PREFIX}unit")
        ]
    ]
    
    # Добавляем дополнительные действия в зависимости от типа проблемы
    additional_row = []
    
    if "Not in database" in issue_type:
        additional_row.append(
            InlineKeyboardButton(text="✏️ Edit Name", callback_data=f"{CB_ACTION_PREFIX}edit_name")
        )
        additional_row.append(
            InlineKeyboardButton(text="➕ Create new", callback_data=f"{CB_ACTION_PREFIX}add_new")
        )
    
    if "Unit" in issue_type and product:
        additional_row.append(
            InlineKeyboardButton(text="🔄 Convert units", callback_data=f"{CB_ACTION_PREFIX}convert")
        )
    
    if additional_row:
        buttons.append(additional_row)
    
    # Добавляем кнопки удаления и возврата
    buttons.append([
        InlineKeyboardButton(text="🗑️ Delete", callback_data=f"{CB_ACTION_PREFIX}delete"),
        InlineKeyboardButton(text="◀️ Back", callback_data=CB_BACK)
    ])
    
    return message, InlineKeyboardMarkup(inline_keyboard=buttons)


async def format_product_select(
    products: List[Dict[str, Any]],
    query: str,
    page: int = 0
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Форматирует сообщение для выбора товара из списка с пагинацией.
    
    :param products: список товаров
    :param query: поисковый запрос
    :param page: номер страницы
    :return: текст сообщения и клавиатура
    """
    # Рассчитываем пагинацию
    total_pages = math.ceil(len(products) / PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    
    # Получаем товары для текущей страницы
    start_idx = page * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, len(products))
    current_products = products[start_idx:end_idx]
    
    # Форматируем сообщение
    message = f"🔍 <b>Product selection for '{query}'</b>\n"
    
    if total_pages > 1:
        message += f"<i>Page {page + 1} of {total_pages}</i>\n"
    
    message += "\n<b>Select a product from the list:</b>\n\n"
    
    for i, product in enumerate(current_products, start=1):
        name = product.get("name", "Unknown")
        unit = product.get("unit", "")
        confidence = product.get("confidence", 0) * 100
        
        message += f"{i}. <b>{name}</b> ({unit})"
        
        if confidence < 100:
            message += f" <i>{confidence:.0f}% match</i>"
        
        message += "\n"
    
    if not current_products:
        message += "<i>No products found. Try a different search query or create a new product.</i>"
    
    # Создаем клавиатуру
    buttons = []
    
    # Кнопки для каждого товара
    for product in current_products:
        product_id = product.get("id")
        name = product.get("name", "")
        unit = product.get("unit", "")
        
        if len(name) > 25:
            name = name[:22] + "..."
        
        display_text = f"{name} ({unit})"
        buttons.append([
            InlineKeyboardButton(text=display_text, callback_data=f"{CB_PRODUCT_PREFIX}{product_id}")
        ])
    
    # Кнопки пагинации
    pagination_row = []
    
    if page > 0:
        pagination_row.append(
            InlineKeyboardButton(text="◀️ Prev", callback_data=f"{CB_PAGE_PREFIX}{page-1}")
        )
    
    if page < total_pages - 1:
        pagination_row.append(
            InlineKeyboardButton(text="Next ▶️", callback_data=f"{CB_PAGE_PREFIX}{page+1}")
        )
    
    if pagination_row:
        buttons.append(pagination_row)
    
    # Кнопки поиска и создания
    buttons.append([
        InlineKeyboardButton(text="🔍 Search", callback_data=CB_SEARCH),
        InlineKeyboardButton(text="➕ New product", callback_data=CB_ADD_NEW)
    ])
    
    # Кнопка "Назад"
    buttons.append([
        InlineKeyboardButton(text="◀️ Back", callback_data=CB_BACK)
    ])
    
    return message, InlineKeyboardMarkup(inline_keyboard=buttons)


async def format_final_preview(
    invoice_data: Dict[str, Any],
    original_issues: List[Dict[str, Any]],
    fixed_issues: Dict[int, Dict[str, Any]]
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Форматирует финальный просмотр накладной перед отправкой.
    
    :param invoice_data: данные накладной
    :param original_issues: исходный список проблем
    :param fixed_issues: информация об исправленных проблемах
    :return: текст сообщения и клавиатура
    """
    # Получаем основную информацию о накладной
    supplier = invoice_data.get("supplier", "Unknown")
    date = invoice_data.get("date", "Unknown")
    invoice_number = invoice_data.get("number", "")
    
    # Обрабатываем позиции
    positions = invoice_data.get("positions", [])
    active_positions = [p for p in positions if not p.get("deleted", False)]
    
    fixed_count = len(fixed_issues)
    original_issues_count = len(original_issues)
    remaining_issues = original_issues_count - fixed_count
    
    # Формируем сообщение
    message = f"✅ <b>Invoice ready to send</b>\n\n"
    message += f"🏷️ <b>Supplier:</b> {supplier}\n"
    message += f"📅 <b>Date:</b> {date}{f' №{invoice_number}' if invoice_number else ''}\n\n"
    
    # Добавляем статистику
    message += f"<b>Total items:</b> {len(active_positions)}\n"
    
    if fixed_count > 0:
        message += f"✅ <b>Fixed issues:</b> {fixed_count}\n"
    
    if remaining_issues > 0:
        message += f"⚠️ <b>Remaining issues:</b> {remaining_issues}\n"
    else:
        message += "✅ <b>All issues resolved!</b>\n"
    
    # Добавляем общую сумму, если она есть
    if "total_sum" in invoice_data:
        total_sum = invoice_data["total_sum"]
        message += f"\n💰 <b>Total amount:</b> {total_sum:,.2f}\n"
    else:
        # Рассчитываем сумму из позиций
        total_sum = sum(float(p.get("sum", 0)) if p.get("sum") else 0 for p in active_positions)
        message += f"\n💰 <b>Total amount:</b> {total_sum:,.2f}\n"
    
    # Добавляем инструкцию
    if remaining_issues > 0:
        message += "\n⚠️ <i>Note: Some issues remain unresolved, but you can still proceed.</i>"
    
    message += "\n\nPlease confirm to send the invoice to Syrve."
    
    # Создаем клавиатуру
    buttons = [
        [InlineKeyboardButton(text="✅ Confirm and send", callback_data=CB_CONFIRM)],
        [InlineKeyboardButton(text="◀️ Back to edits", callback_data=CB_BACK)]
    ]
    
    return message, InlineKeyboardMarkup(inline_keyboard=buttons)


def format_issue_card(issue: Dict[str, Any], is_edited: bool = False) -> str:
    """
    Format an issue card with HTML markup.
    
    Args:
        issue: The issue data dictionary
        is_edited: Whether the issue has been edited
        
    Returns:
        HTML formatted card text
    """
    index = issue.get("index", 0)
    original = issue.get("original", {})
    
    name = original.get("name", "Unknown")
    quantity = original.get("quantity", 0)
    unit = original.get("unit", "")
    price = original.get("price", "")
    sum_val = original.get("sum", "")
    
    # Determine issue type and icon
    issue_type = issue.get("issue", "Unknown issue")
    
    if "Not in database" in issue_type:
        icon = "⚠"
        issue_description = "Not in database"
    elif "incorrect match" in issue_type:
        icon = "❔"
        issue_description = "Low confidence match"
    elif "Unit" in issue_type:
        icon = "🔄"
        issue_description = "Unit measurement discrepancy"
    else:
        icon = "❓"
        issue_description = issue_type
        
    # Add edit indicator if needed
    edit_prefix = "📝 " if is_edited else ""
    
    # Build the message
    message = f"{edit_prefix}<b>Row {index}:</b> {name}\n\n"
    message += f"<b>Problem:</b> {icon} {issue_description}\n"
    message += f"<b>Qty:</b> {quantity} {unit}\n"
    
    if price:
        try:
            price_float = float(price)
            message += f"<b>Price:</b> {price_float:.2f}\n"
        except (ValueError, TypeError):
            message += f"<b>Price:</b> {price or '—'}\n"
    else:
        message += "<b>Price:</b> —\n"
        
    if sum_val:
        try:
            sum_float = float(sum_val)
            message += f"<b>Sum:</b> {sum_float:.2f}\n"
        except (ValueError, TypeError):
            message += f"<b>Sum:</b> {sum_val}\n"
    else:
        # Calculate sum if possible
        if price and quantity:
            try:
                price_float = float(price)
                qty_float = float(quantity)
                message += f"<b>Sum:</b> {price_float * qty_float:.2f}\n"
            except (ValueError, TypeError):
                message += "<b>Sum:</b> —\n"
        else:
            message += "<b>Sum:</b> —\n"
    
    message += "\n<i>Select an action:</i>"
    
    return message


def format_field_prompt(field: str, current_value: str) -> str:
    """
    Format a prompt for editing a specific field.
    
    Args:
        field: The field name being edited
        current_value: The current value of the field
        
    Returns:
        HTML formatted prompt text
    """
    field_labels = {
        "name": "name",
        "qty": "quantity",
        "unit": "unit of measurement",
        "price": "price"
    }
    
    field_label = field_labels.get(field, field)
    
    message = f"<b>Enter new {field_label}:</b>\n\n"
    message += f"Current value: {current_value}\n\n"
    
    field_hints = {
        "name": "Enter product name (max 100 characters)",
        "qty": "Enter numeric quantity (e.g., 5 or 2.5)",
        "unit": "Enter unit of measurement (e.g., kg, l, pcs)",
        "price": "Enter price (numbers only)"
    }
    
    if field in field_hints:
        message += f"<i>{field_hints[field]}</i>"
        
    return message
# ───────────────────────── Handlers ───────────────────────────
@router.callback_query(Text(["inv_edit", CB_REVIEW]))
async def cb_start_review(c: CallbackQuery, state: FSMContext):
    """
    Обработчик начала просмотра проблемных позиций.
    
    Активируется при нажатии на кнопку "Review" в сводке накладной.
    """
    # Получаем данные из состояния
    data = await state.get_data()
    invoice = data.get("invoice", {})
    issues = data.get("issues", [])
    
    if not issues:
        await c.message.answer("❌ Нет проблемных позиций для просмотра.")
        await c.answer()
        return
    
    # Обновляем состояние
    await state.update_data(current_issues=issues, fixed_issues={})
    await state.set_state(InvoiceEditStates.issue_list)
    
    # Форматируем сообщение со списком проблем
    message, keyboard = await format_issues_list({"issues": issues}, page=0)
    
    # Отправляем сообщение
    try:
        await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error("Failed to edit message", error=str(e))
        await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    
    await c.answer()


# ───────────────────────── Обработчики выбора позиции ────────────────────────
@router.callback_query(lambda c: c.data and (
    c.data.startswith(CB_ISSUE_PREFIX) or c.data.startswith(LEGACY_ISSUE_PREFIX)
), InvoiceEditStates.issue_list)
async def cb_select_issue(c: CallbackQuery, state: FSMContext):
    """
    Обработчик выбора конкретной проблемной позиции из списка.
    
    Поддерживает новый (issue:X) и старый (issue_X) форматы callback_data.
    """
    # Определяем индекс позиции в зависимости от формата
    if c.data.startswith(CB_ISSUE_PREFIX):
        # Новый формат - позиция указана по индексу в накладной (1-based)
        try:
            position_index = int(c.data[len(CB_ISSUE_PREFIX):]) - 1
        except ValueError:
            await c.answer("❌ Неверный формат позиции.")
            return
    else:
        # Старый формат - позиция в массиве проблем (0-based)
        try:
            position_index = int(c.data[len(LEGACY_ISSUE_PREFIX):])
        except ValueError:
            await c.answer("❌ Неверный формат позиции.")
            return
    
    # Получаем данные из состояния
    data = await state.get_data()
    current_issues = data.get("current_issues", [])
    
    # Находим проблемную позицию
    selected_issue = None
    for issue in current_issues:
        issue_index = issue.get("index", 0) - 1  # Индекс в накладной (0-based)
        if c.data.startswith(CB_ISSUE_PREFIX) and issue_index == position_index:
            selected_issue = issue
            break
        elif c.data.startswith(LEGACY_ISSUE_PREFIX) and current_issues.index(issue) == position_index:
            selected_issue = issue
            break
    
    if not selected_issue:
        await c.answer("❌ Позиция не найдена.")
        return
    
    # Сохраняем выбранную позицию в состоянии
    await state.update_data(
        selected_issue=selected_issue,
        selected_issue_idx=current_issues.index(selected_issue)
    )
    await state.set_state(InvoiceEditStates.issue_edit)
    
    # Форматируем сообщение для редактирования
    message, keyboard = await format_issue_edit(selected_issue)
    
    # Отправляем сообщение
    try:
        await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error("Failed to edit message", error=str(e))
        await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    
    await c.answer()

# ───────────────────────── Обработчики пагинации ────────────────────────
@router.callback_query(lambda c: c.data and (
    c.data.startswith(CB_PAGE_PREFIX) or c.data.startswith(LEGACY_PAGE_PREFIX)
))
async def cb_change_page(c: CallbackQuery, state: FSMContext):
    """
    Обработчик пагинации для списков позиций и товаров.
    
    Поддерживает новый (page:X) и старый (page_X) форматы callback_data.
    """
    # Определяем номер страницы
    if c.data.startswith(CB_PAGE_PREFIX):
        page = int(c.data[len(CB_PAGE_PREFIX):])
    else:
        page = int(c.data[len(LEGACY_PAGE_PREFIX):])
    
    # Получаем текущее состояние
    current_state = await state.get_state()
    data = await state.get_data()
    
    if current_state == InvoiceEditStates.issue_list.state:
        # Пагинация в списке проблемных позиций
        current_issues = data.get("current_issues", [])
        await state.update_data(current_page=page)
        
        message, keyboard = await format_issues_list({"issues": current_issues}, page=page)
    
    elif current_state == InvoiceEditStates.product_select.state:
        # Пагинация в списке товаров
        products = data.get("products", [])
        query = data.get("search_query", "")
        await state.update_data(current_page=page)
        
        message, keyboard = await format_product_select(products, query, page=page)
    
    else:
        await c.answer("❌ Некорректное состояние для пагинации.")
        return
    
    # Отправляем сообщение
    try:
        await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error("Failed to edit message", error=str(e))
        await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    
    await c.answer()


# ───────────────────────── Обработчики действий с позицией ────────────────────────
@router.callback_query(lambda c: c.data and (
    c.data.startswith(CB_ACTION_PREFIX) or c.data.startswith(LEGACY_ACTION_PREFIX)
), InvoiceEditStates.issue_edit)
async def cb_action_with_item(c: CallbackQuery, state: FSMContext):
    """
    Обработчик выбора действия с проблемной позицией.
    
    Поддерживает новый (action:name) и старый (action_name) форматы callback_data.
    """
    # Определяем действие
    if c.data.startswith(CB_ACTION_PREFIX):
        action = c.data[len(CB_ACTION_PREFIX):]
    else:
        action = c.data[len(LEGACY_ACTION_PREFIX):]
    
    # Получаем данные из состояния
    data = await state.get_data()
    selected_issue = data.get("selected_issue", {})
    original = selected_issue.get("original", {})
    
    # Обрабатываем разные действия
    if action == "name":
        # Переход к выбору товара
        await state.set_state(InvoiceEditStates.product_select)
        
        # Получаем название для поиска
        name_query = original.get("name", "")[:3]  # Первые 3 символа для поиска
        await state.update_data(search_query=name_query)
        
        # Получаем список товаров по названию
        async with SessionLocal() as session:
            products = await get_products_by_name(session, name_query)
        
        # Сохраняем список товаров в состоянии
        await state.update_data(products=products, current_page=0)
        
        # Форматируем сообщение для выбора товара
        message, keyboard = await format_product_select(products, name_query, page=0)
        
        # Отправляем сообщение
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    
    elif action == "edit_name":
        # Переход к редактированию имени
        await state.set_state(InvoiceEditStates.field_input)
        await state.update_data(field="name")
        
        # Отправляем сообщение с запросом
        msg = format_field_prompt("name", original.get("name", ""))
        
        # Отправляем с ForceReply для получения ответа
        await c.message.edit_text(msg, parse_mode="HTML")
        await c.message.answer("Введите новое название:", reply_markup=ForceReply())
    
    elif action == "qty":
        # Переход к вводу количества
        await state.set_state(InvoiceEditStates.field_input)
        await state.update_data(field="quantity")
        
        # Отправляем сообщение с запросом
        msg = (
            f"Введите новое количество для товара <b>{original.get('name', '')}</b>.\n\n"
            f"Текущее значение: {original.get('quantity', 0)} {original.get('unit', '')}\n\n"
            f"Дробные числа вводите через точку, например: 2.5"
        )
        
        await c.message.edit_text(msg, parse_mode="HTML")
    
    elif action == "unit":
        # Переход к выбору единицы измерения
        await state.set_state(InvoiceEditStates.field_input)
        await state.update_data(field="unit")
        
        # Подготавливаем список единиц измерения
        common_units = ["kg", "g", "l", "ml", "pcs", "pack", "box"]
        
        # Если есть связанный товар, добавляем его единицу в начало
        product = selected_issue.get("product")
        if product and product.unit and product.unit not in common_units:
            common_units.insert(0, product.unit)
        
    elif action == "unit":
        # Переход к выбору единицы измерения
        await state.set_state(InvoiceEditStates.field_input)
        await state.update_data(field="unit")
        
        # Подготавливаем список единиц измерения
        common_units = ["kg", "g", "l", "ml", "pcs", "pack", "box"]
        
        # Создаем клавиатуру для выбора единиц измерения
        buttons = []
        row = []
        
        for i, unit in enumerate(common_units):
            row.append(InlineKeyboardButton(
                text=unit, 
                callback_data=f"{CB_UNIT_PREFIX}{unit}"
            ))
            
            if (i + 1) % 3 == 0 or i == len(common_units) - 1:
                buttons.append(row)
                row = []
        
        # Добавляем кнопку "Назад"
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        # Отправляем сообщение
        msg = (
            f"Выберите единицу измерения для товара <b>{original.get('name', '')}</b>.\n\n"
            f"Текущая единица: {original.get('unit', 'не указана')}"
        )
        
        await c.message.edit_text(msg, reply_markup=keyboard, parse_mode="HTML")
    
    elif action == "delete":
        # Удаление позиции
        invoice_data = data.get("invoice", {})
        positions = invoice_data.get("positions", [])
        
        issue_idx = data.get("selected_issue_idx", 0)
        issues = data.get("current_issues", [])
        
        # Определяем индекс позиции в общем списке
        position_idx = selected_issue.get("index", 0) - 1
        
        if 0 <= position_idx < len(positions):
            # Помечаем позицию как удаленную
            positions[position_idx]["deleted"] = True
            
            # Обновляем данные в состоянии
            invoice_data["positions"] = positions
            await state.update_data(invoice=invoice_data)
            
            # Добавляем в список исправленных позиций
            fixed_issues = data.get("fixed_issues", {})
            if not fixed_issues:
                fixed_issues = {}
            
            fixed_issues[position_idx] = {"action": "delete"}
            await state.update_data(fixed_issues=fixed_issues)
            
            # Логируем удаление
            try:
                invoice_id = invoice_data.get("id", 0)
                user_id = c.from_user.id if c.from_user else 0
                item_name = original.get("name", "")
                
                await log_delete(
                    invoice_id=invoice_id,
                    row_idx=position_idx,
                    user_id=user_id,
                    item_name=item_name
                )
            except Exception as e:
                logger.error("Failed to log delete action", error=str(e))
            
            # Обновляем список проблем (удаляем решенную)
            current_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
            await state.update_data(current_issues=current_issues)
            
            # Возвращаемся к списку проблем или к подтверждению
            if not current_issues:
                # Если проблем больше нет, переходим к подтверждению
                await state.set_state(InvoiceEditStates.confirm)
                
                message, keyboard = await format_final_preview(
                    invoice_data, 
                    data.get("issues", []), 
                    fixed_issues
                )
            else:
                # Если есть еще проблемы, возвращаемся к списку
                await state.set_state(InvoiceEditStates.issue_list)
                
                message, keyboard = await format_issues_list(
                    {"issues": current_issues}, 
                    page=data.get("current_page", 0)
                )
            
            # Отправляем сообщение
            try:
                await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
            except Exception as e:
                logger.error("Failed to edit message", error=str(e))
                await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
        else:
            await c.answer("❌ Ошибка при удалении позиции.")
    
    elif action == "convert":
        # Конвертация единиц измерения
        product = selected_issue.get("product")
        # Проверяем наличие продукта перед попыткой конвертации
        if not product:
            # Вместо простого сообщения об ошибке предлагаем варианты действий
            msg = (
                "❌ Нет данных о товаре для конвертации.\n\n"
                "Для конвертации единиц измерения необходимо сначала сопоставить товар с базой данных."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔍 Найти в базе", callback_data=f"{CB_ACTION_PREFIX}name"),
                    InlineKeyboardButton(text="✏️ Редактировать название", callback_data=f"{CB_ACTION_PREFIX}edit_name")
                ],
                [
                    InlineKeyboardButton(text="➕ Создать новый", callback_data=f"{CB_ACTION_PREFIX}add_new"),
                    InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)
                ]
            ])
            
            await c.message.edit_text(msg, reply_markup=keyboard, parse_mode="HTML")
            await c.answer()
            return
        
        # Получаем данные для конвертации
        invoice_unit = original.get("unit", "")
        db_unit = product.unit
        
        if not invoice_unit or not db_unit or invoice_unit == db_unit:
            await c.answer("⚠️ Нет необходимости в конвертации.")
            return
    
    # Проверяем совместимость единиц
    if not is_compatible_unit(invoice_unit, db_unit):
        msg = f"❌ Невозможно конвертировать: единицы <b>{invoice_unit}</b> и <b>{db_unit}</b> несовместимы."
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)]
        ])
        
        await c.message.edit_text(msg, reply_markup=keyboard, parse_mode="HTML")
        await c.answer()
        return
    
    # Выполняем конвертацию
    quantity = float(original.get("quantity", 0))
    converted = convert(quantity, invoice_unit, db_unit)

    if converted is None:
        await c.answer("❌ Ошибка при конвертации.")
        return

    # Обновляем данные
    invoice_data = data.get("invoice", {})
    positions = invoice_data.get("positions", [])
    position_idx = selected_issue.get("index", 0) - 1

    if 0 <= position_idx < len(positions):
        # Обновляем позицию
        positions[position_idx]["quantity"] = converted
        positions[position_idx]["unit"] = db_unit

        # Пересчитываем сумму, если есть цена
        if price := positions[position_idx].get("price"):
            try:
                price_float = float(price)
                positions[position_idx]["sum"] = converted * price_float
            except (ValueError, TypeError):
                pass

        # Обновляем данные в состоянии
        invoice_data["positions"] = positions
        await state.update_data(invoice=invoice_data)

        # Добавляем в список исправленных позиций
        fixed_issues = data.get("fixed_issues", {}) or {}
        fixed_issues[position_idx] = {
            "action":       "convert_unit",
            "from_unit":    invoice_unit,
            "to_unit":      db_unit,
            "old_quantity": quantity,
            "new_quantity": converted,
        }
        await state.update_data(fixed_issues=fixed_issues)

        # Обновляем список проблем (удаляем решённую)
        issues      = data.get("current_issues", [])
        issue_idx   = data.get("selected_issue_idx", 0)
        new_issues  = [issue for i, issue in enumerate(issues) if i != issue_idx]
        await state.update_data(current_issues=new_issues)

        # Возвращаемся к списку проблем или к подтверждению
        if not new_issues:
            await state.set_state(InvoiceEditStates.confirm)
            message, keyboard = await format_final_preview(
                invoice_data,
                data.get("issues", []),
                fixed_issues,
            )
        else:
            await state.set_state(InvoiceEditStates.issue_list)
            message, keyboard = await format_issues_list(
                {"issues": new_issues},
                page=data.get("current_page", 0),
            )

        # Добавляем информацию о конвертации
        conv_msg = (
            f"✅ Конвертация выполнена: {quantity} {invoice_unit} → "
            f"{converted} {db_unit}\n\n"
            + message
        )
        
        # Отправляем сообщение
        try:
            await c.message.edit_text(conv_msg, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(conv_msg, reply_markup=keyboard, parse_mode="HTML")
    else:
        await c.answer("❌ Ошибка при обновлении позиции.")
    
    elif action == "add_new":
        # Добавление нового товара
        invoice_data = data.get("invoice", {})
        position_idx = selected_issue.get("index", 0) - 1
        
        # Получаем данные позиции
        if "positions" in invoice_data and 0 <= position_idx < len(invoice_data["positions"]):
            # Отмечаем, что эта позиция будет добавлена как новый товар
            fixed_issues = data.get("fixed_issues", {})
            if not fixed_issues:
                fixed_issues = {}
            
            fixed_issues[position_idx] = {"action": "new_product"}
            await state.update_data(fixed_issues=fixed_issues)
            
            # Логируем создание нового товара
            try:
                invoice_id = invoice_data.get("id", 0)
                user_id = c.from_user.id if c.from_user else 0
                item_name = original.get("name", "")
                
                await log_save_new(
                    invoice_id=invoice_id,
                    row_idx=position_idx,
                    user_id=user_id,
                    item_name=item_name
                )
            except Exception as e:
                logger.error("Failed to log save_new action", error=str(e))
            
            # Обновляем список проблем (удаляем решенную)
            issues = data.get("current_issues", [])
            issue_idx = data.get("selected_issue_idx", 0)
            current_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
            await state.update_data(current_issues=current_issues)
            
            # Возвращаемся к списку проблем или к подтверждению
            if not current_issues:
                await state.set_state(InvoiceEditStates.confirm)
                
                message, keyboard = await format_final_preview(
                    invoice_data, 
                    data.get("issues", []), 
                    fixed_issues
                )
            else:
                await state.set_state(InvoiceEditStates.issue_list)
                
                message, keyboard = await format_issues_list(
                    {"issues": current_issues}, 
                    page=data.get("current_page", 0)
                )
            
            # Добавляем сообщение об успешном добавлении
            message = f"✅ Товар <b>{original.get('name', '')}</b> сохранен как новый!\n\n" + message
            
            # Отправляем сообщение
            try:
                await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
            except Exception as e:
                logger.error("Failed to edit message", error=str(e))
                await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
        else:
            await c.answer("❌ Ошибка при добавлении нового товара.")
    
    else:
        await c.answer(f"⚠️ Неизвестное действие: {action}")
    
    await c.answer()

# ───────────────────────── Обработчик выбора товара ────────────────────────
@router.callback_query(lambda c: c.data and (
    c.data.startswith(CB_PRODUCT_PREFIX) or c.data.startswith("product_")
), InvoiceEditStates.product_select)
async def cb_select_product(c: CallbackQuery, state: FSMContext):
    """
    Обработчик выбора товара из списка.
    
    Поддерживает новый (product:ID) и старый (product_ID) форматы callback_data.
    """
    # Определяем ID товара
    if c.data.startswith(CB_PRODUCT_PREFIX):
        product_id = int(c.data[len(CB_PRODUCT_PREFIX):])
    else:
        product_id = int(c.data[len("product_"):])
    
    # Получаем данные из состояния
    data = await state.get_data()
    selected_issue = data.get("selected_issue", {})
    invoice_data = data.get("invoice", {})
    positions = invoice_data.get("positions", [])
    
    # Получаем информацию о выбранном товаре
    async with SessionLocal() as session:
        stmt = select(Product).where(Product.id == product_id)
        result = await session.execute(stmt)
        product = result.scalar_one_or_none()
    
    if not product:
        await c.answer("❌ Товар не найден.")
        return
    
    # Находим позицию в списке
    issue_idx = data.get("selected_issue_idx", 0)
    issues = data.get("current_issues", [])
    
    position_idx = selected_issue.get("index", 0) - 1
    
    if 0 <= position_idx < len(positions):
        # Сохраняем оригинальное название для обучения
        original_name = positions[position_idx].get("name", "")
        
        # Обновляем позицию
        positions[position_idx]["match_id"] = product.id
        positions[position_idx]["match_name"] = product.name
        positions[position_idx]["confidence"] = 1.0  # Полная уверенность при ручном выборе
        
        # Проверяем совместимость единиц измерения
        original_unit = positions[position_idx].get("unit", "")
        if original_unit and not is_compatible_unit(original_unit, product.unit):
            positions[position_idx]["unit_issue"] = True
            positions[position_idx]["product_unit"] = product.unit
        
        # Обновляем данные в состоянии
        invoice_data["positions"] = positions
        await state.update_data(invoice=invoice_data)
        
        # Добавляем в список исправленных позиций
        fixed_issues = data.get("fixed_issues", {})
        if not fixed_issues:
            fixed_issues = {}
        
        fixed_issues[position_idx] = {
            "action": "replace_product",
            "product_id": product.id,
            "product_name": product.name,
            "original_name": original_name
        }
        await state.update_data(fixed_issues=fixed_issues)
        
        # Сохраняем сопоставление для будущего использования
        if original_name:
            try:
                await save_product_match(session, original_name, product.id)
                logger.info("Saved product match for learning", 
                           original=original_name, 
                           product_id=product.id)
            except Exception as e:
                logger.error("Failed to save product match", error=str(e))
        
        # Обновляем список проблем (удаляем решенную)
        current_issues = issues.copy()
        
        # Проверяем на другие проблемы с этой позицией (например, единицы измерения)
        unit_issue = positions[position_idx].get("unit_issue", False)
        
        if unit_issue:
            # Если есть проблема с единицей измерения, обновляем issue
            for i, issue in enumerate(current_issues):
                if issue is selected_issue:
                    issue["issue"] = "Unit measurement discrepancy"
                    issue["product"] = product
                    selected_issue = issue
                    await state.update_data(selected_issue=issue)
                    break
        else:
            # Если нет других проблем, удаляем issue
            current_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
            await state.update_data(current_issues=current_issues)
        
        # Переходим к следующему шагу
        if unit_issue:
            # Если есть проблема с единицей измерения, предлагаем исправить ее
            await state.set_state(InvoiceEditStates.issue_edit)
            
            message, keyboard = await format_issue_edit(selected_issue)
            message = f"✅ Товар заменен на <b>{product.name}</b>, но есть проблема с единицей измерения.\n\n" + message
        elif not current_issues:
            # Если проблем больше нет, переходим к подтверждению
            await state.set_state(InvoiceEditStates.confirm)
            
            message, keyboard = await format_final_preview(
                invoice_data, 
                data.get("issues", []), 
                fixed_issues
            )
        else:
            # Если есть еще проблемы, возвращаемся к списку
            await state.set_state(InvoiceEditStates.issue_list)
            
            message, keyboard = await format_issues_list(
                {"issues": current_issues}, 
                page=data.get("current_page", 0)
            )
            message = f"✅ Товар заменен на <b>{product.name}</b>\n\n" + message
        
        # Отправляем сообщение
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    else:
        await c.answer("❌ Ошибка при обновлении позиции.")
    
    await c.answer()

# ───────────────────────── Обработчики единиц измерения ────────────────────────
@router.callback_query(lambda c: c.data and (
    c.data.startswith(CB_UNIT_PREFIX) or c.data.startswith("unit_")
), InvoiceEditStates.field_input)
async def cb_select_unit(c: CallbackQuery, state: FSMContext):
    """
    Обработчик выбора единицы измерения.
    
    Поддерживает новый (unit:X) и старый (unit_X) форматы callback_data.
    """
    # Определяем единицу измерения
    if c.data.startswith(CB_UNIT_PREFIX):
        unit = c.data[len(CB_UNIT_PREFIX):]
    else:
        unit = c.data[len("unit_"):]
    
    # Получаем данные из состояния
    data = await state.get_data()
    selected_issue = data.get("selected_issue", {})
    invoice_data = data.get("invoice", {})
    positions = invoice_data.get("positions", [])
    
    # Находим позицию
    issue_idx = data.get("selected_issue_idx", 0)
    issues = data.get("current_issues", [])
    
    position_idx = selected_issue.get("index", 0) - 1
    
    if 0 <= position_idx < len(positions):
        # Сохраняем старую единицу для отчета
        old_unit = positions[position_idx].get("unit", "")
        
        # Обновляем единицу измерения
        positions[position_idx]["unit"] = unit
        
        # Проверяем необходимость конвертации
        product = selected_issue.get("product")
        if product and product.unit and unit != product.unit and is_compatible_unit(unit, product.unit):
            # Запрашиваем подтверждение о конвертации
            await state.update_data(
                conversion_from=unit,
                conversion_to=product.unit,
                position_idx=position_idx
            )
            
            # Создаем клавиатуру для подтверждения
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да", callback_data=f"{CB_CONVERT_PREFIX}yes"),
                    InlineKeyboardButton(text="❌ Нет", callback_data=f"{CB_CONVERT_PREFIX}no")
                ],
                [
                    InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)
                ]
            ])
            
            # Формируем сообщение
            quantity = positions[position_idx].get("quantity", 0)
            
            msg = (
                f"Единица измерения изменена на <b>{unit}</b>.\n\n"
                f"Товар в базе использует единицу <b>{product.unit}</b>.\n"
                f"Хотите конвертировать количество из {unit} в {product.unit}?\n\n"
                f"Текущее количество: {quantity} {unit}"
            )
            
            await c.message.edit_text(msg, reply_markup=keyboard, parse_mode="HTML")
            await c.answer()
            return
        
        # Если нет необходимости в конвертации, просто обновляем данные
        invoice_data["positions"] = positions
        await state.update_data(invoice=invoice_data)
        
        # Добавляем в список исправленных позиций
        fixed_issues = data.get("fixed_issues", {})
        if not fixed_issues:
            fixed_issues = {}
        
        fixed_issues[position_idx] = {
            "action": "change_unit",
            "old_unit": old_unit,
            "new_unit": unit
        }
        await state.update_data(fixed_issues=fixed_issues)
        
        # Получаем обновленный список проблем
        current_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
        await state.update_data(current_issues=current_issues)
        
        # Определяем следующий шаг
        if not current_issues:
            # Если проблем больше нет, переходим к подтверждению
            await state.set_state(InvoiceEditStates.confirm)
            
            message, keyboard = await format_final_preview(
                invoice_data, 
                data.get("issues", []), 
                fixed_issues
            )
        else:
            # Возвращаемся к списку проблем
            await state.set_state(InvoiceEditStates.issue_list)
            
            message, keyboard = await format_issues_list(
                {"issues": current_issues}, 
                page=data.get("current_page", 0)
            )
            message = f"✅ Единица измерения изменена на <b>{unit}</b>.\n\n" + message
        
        # Отправляем сообщение
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    else:
        await c.answer("❌ Ошибка при обновлении единицы измерения.")
    
    await c.answer()


@router.callback_query(lambda c: c.data and (
    c.data.startswith(CB_CONVERT_PREFIX) or c.data.startswith("convert_")
))
async def cb_convert_unit(c: CallbackQuery, state: FSMContext):
    """
    Обработчик подтверждения конвертации единиц измерения.
    
    Поддерживает новый (convert:yes/no) и старый (convert_yes/no) форматы callback_data.
    """
    # Определяем ответ
    is_yes = c.data.endswith("yes")
    
    # Получаем данные из состояния
    data = await state.get_data()
    invoice_data = data.get("invoice", {})
    positions = invoice_data.get("positions", [])
    
    conversion_from = data.get("conversion_from", "")
    conversion_to = data.get("conversion_to", "")
    position_idx = data.get("position_idx", -1)
    
    if 0 <= position_idx < len(positions):
        # Если пользователь подтвердил конвертацию
        if is_yes:
            quantity = positions[position_idx].get("quantity", 0)
            
            # Пытаемся конвертировать
            try:
                quantity_float = float(quantity)
                converted = convert(quantity_float, conversion_from, conversion_to)
                
                if converted is not None:
                    # Обновляем количество и единицу
                    positions[position_idx]["quantity"] = converted
                    positions[position_idx]["unit"] = conversion_to
                    
                    # Обновляем сумму, если есть цена
                    if price := positions[position_idx].get("price"):
                        try:
                            price_float = float(price)
                            positions[position_idx]["sum"] = converted * price_float
                        except (ValueError, TypeError):
                            pass
                    
                    # Добавляем в список исправленных позиций
                    fixed_issues = data.get("fixed_issues", {})
                    if not fixed_issues:
                        fixed_issues = {}
                    
                    fixed_issues[position_idx] = {
                        "action": "convert_unit",
                        "from_unit": conversion_from,
                        "to_unit": conversion_to,
                        "old_quantity": quantity,
                        "new_quantity": converted
                    }
                    
                    await state.update_data(fixed_issues=fixed_issues)
                    
                    # Формируем сообщение об успешной конвертации
                    conversion_message = f"✅ Конвертировано: {quantity} {conversion_from} → {converted} {conversion_to}"
                else:
                    # Если конвертация невозможна
                    msg = (
                        f"❌ Не удалось конвертировать из <b>{conversion_from}</b> в <b>{conversion_to}</b>.\n"
                        f"Единица измерения изменена, но количество осталось прежним."
                    )
                    
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)]
                    ])
                    
                    await c.message.edit_text(msg, reply_markup=keyboard, parse_mode="HTML")
                    await c.answer()
                    return
            except (ValueError, TypeError):
                # Ошибка при конвертации
                msg = f"❌ Ошибка при конвертации. Проверьте, что количество задано числом."
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)]
                ])
                
                await c.message.edit_text(msg, reply_markup=keyboard, parse_mode="HTML")
                await c.answer()
                return
        else:
            # Если пользователь отказался от конвертации, просто обновляем единицу
            old_unit = positions[position_idx].get("unit", "")
            positions[position_idx]["unit"] = conversion_to
            
            # Добавляем в список исправленных позиций
            fixed_issues = data.get("fixed_issues", {})
            if not fixed_issues:
                fixed_issues = {}
            
            fixed_issues[position_idx] = {
                "action": "change_unit",
                "old_unit": old_unit,
                "new_unit": conversion_to
            }
            
            await state.update_data(fixed_issues=fixed_issues)
            
            # Формируем сообщение
            conversion_message = f"✅ Единица измерения изменена на {conversion_to} (без конвертации количества)"
        
        # Обновляем данные в состоянии
        invoice_data["positions"] = positions
        await state.update_data(invoice=invoice_data)
        
        # Обновляем список проблем
        issues = data.get("current_issues", [])
        issue_idx = None
        
        for i, issue in enumerate(issues):
            if issue.get("index", 0) - 1 == position_idx:
                issue_idx = i
                break
        
        if issue_idx is not None:
            current_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
            await state.update_data(current_issues=current_issues)
        else:
            current_issues = issues
        
        # Определяем следующий шаг
        if not current_issues:
            # Если проблем больше нет, переходим к подтверждению
            await state.set_state(InvoiceEditStates.confirm)
            
            message, keyboard = await format_final_preview(
                invoice_data, 
                data.get("issues", []), 
                fixed_issues
            )
            message = f"{conversion_message}\n\n" + message
        else:
            # Возвращаемся к списку проблем
            await state.set_state(InvoiceEditStates.issue_list)
            
            message, keyboard = await format_issues_list(
                {"issues": current_issues}, 
                page=data.get("current_page", 0)
            )
            message = f"{conversion_message}\n\n" + message
        
        # Отправляем сообщение
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    else:
        await c.answer("❌ Ошибка при обновлении позиции.")
    
    await c.answer()

# ───────────────────────── Обработчики навигации ────────────────────────
@router.callback_query(lambda c: c.data and (c.data == CB_BACK or c.data == "back"))
async def cb_back(c: CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки "Назад" - возврат к предыдущему состоянию.
    """
    current_state = await state.get_state()
    data = await state.get_data()
    
    if current_state == InvoiceEditStates.issue_edit.state:
        # Возврат к списку проблем
        await state.set_state(InvoiceEditStates.issue_list)
        
        issues = data.get("current_issues", [])
        
        message, keyboard = await format_issues_list(
            {"issues": issues}, 
            page=data.get("current_page", 0)
        )
        
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    
    elif current_state == InvoiceEditStates.product_select.state:
        # Возврат к редактированию позиции
        await state.set_state(InvoiceEditStates.issue_edit)
        
        selected_issue = data.get("selected_issue", {})
        
        message, keyboard = await format_issue_edit(selected_issue)
        
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    
    elif current_state == InvoiceEditStates.field_input.state:
        # Возврат к редактированию позиции
        await state.set_state(InvoiceEditStates.issue_edit)
        
        selected_issue = data.get("selected_issue", {})
        
        message, keyboard = await format_issue_edit(selected_issue)
        
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    
    elif current_state == InvoiceEditStates.confirm.state:
        # Возврат к списку проблем
        await state.set_state(InvoiceEditStates.issue_list)
        
        issues = data.get("current_issues", [])
        
        # Если список пуст, берем оригинальный список проблем
        if not issues:
            issues = data.get("issues", [])
            await state.update_data(current_issues=issues)
        
        message, keyboard = await format_issues_list(
            {"issues": issues}, 
            page=data.get("current_page", 0)
        )
        
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    
    await c.answer()


@router.callback_query(Text("done"))
async def cb_done(c: CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки "Готово" - переход к финальному подтверждению.
    """
    # Получаем данные из состояния
    data = await state.get_data()
    invoice_data = data.get("invoice", {})
    fixed_issues = data.get("fixed_issues", {})
    
    # Переходим к подтверждению
    await state.set_state(InvoiceEditStates.confirm)
    
    # Формируем сообщение
    message, keyboard = await format_final_preview(
        invoice_data, 
        data.get("issues", []),
        fixed_issues
    )
    
    try:
        await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error("Failed to edit message", error=str(e))
        await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    
    await c.answer()


# ───────────────────────── Обработчики поиска ────────────────────────
@router.callback_query(lambda c: c.data and (c.data == CB_SEARCH or c.data == "search"), 
                        InvoiceEditStates.product_select)
async def cb_search_product(c: CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки поиска товара.
    """
    # Переходим в состояние ввода поискового запроса
    await state.update_data(field="search")
    await state.set_state(InvoiceEditStates.field_input)
    
    msg = "🔍 Введите часть названия товара для поиска:"
    
    await c.message.edit_text(msg, parse_mode="HTML")
    
    await c.answer()


# ───────────────────────── Обработчики ввода текста ────────────────────────
@router.message(InvoiceEditStates.field_input)
async def process_field_input(message: Message, state: FSMContext):
    """
    Обработчик ввода значения для поля (количество, поисковый запрос).
    """
    # Получаем данные из состояния
    data = await state.get_data()
    field = data.get("field", "")
    
    if field == "quantity":
        # Обработка ввода количества
        try:
            # Проверяем, что введено число
            quantity_text = message.text.strip().replace(",", ".")
            quantity = float(quantity_text)
            
            # Получаем данные позиции
            selected_issue = data.get("selected_issue", {})
            invoice_data = data.get("invoice", {})
            positions = invoice_data.get("positions", [])
            
            # Находим позицию в списке позиций накладной
            issue_idx = data.get("selected_issue_idx", 0)
            issues = data.get("current_issues", [])
            
            position_idx = selected_issue.get("index", 0) - 1
            
            if 0 <= position_idx < len(positions):
                # Сохраняем старое значение
                old_quantity = positions[position_idx].get("quantity", 0)
                
                # Обновляем количество
                positions[position_idx]["quantity"] = quantity
                
                # Обновляем сумму, если есть цена
                if price := positions[position_idx].get("price"):
                    try:
                        price_float = float(price)
                        positions[position_idx]["sum"] = quantity * price_float
                    except (ValueError, TypeError):
                        pass
                
                # Обновляем данные в состоянии
                invoice_data["positions"] = positions
                await state.update_data(invoice=invoice_data)
                
                # Добавляем в список исправленных позиций
                fixed_issues = data.get("fixed_issues", {})
                if not fixed_issues:
                    fixed_issues = {}
                
                fixed_issues[position_idx] = {
                    "action": "change_quantity",
                    "old_quantity": old_quantity,
                    "new_quantity": quantity
                }
                await state.update_data(fixed_issues=fixed_issues)
                
                # Удаляем сообщение пользователя (чтобы не засорять чат)
                try:
                    await message.delete()
                except Exception:
                    pass
                
                # Проверяем, есть ли другие проблемы с этой позицией
                has_other_issues = False
                for issue in issues:
                    if issue.get("index", 0) - 1 == position_idx and issues.index(issue) != issue_idx:
                        has_other_issues = True
                        selected_issue = issue
                        await state.update_data(
                            selected_issue=issue, 
                            selected_issue_idx=issues.index(issue)
                        )
                        break
                
                # Определяем следующий шаг
                current_issues = issues
                if not has_other_issues:
                    current_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
                    await state.update_data(current_issues=current_issues)
                
                if not current_issues:
                    # Если проблем больше нет, переходим к подтверждению
                    await state.set_state(InvoiceEditStates.confirm)
                    
                    message_text, keyboard = await format_final_preview(
                        invoice_data, 
                        data.get("issues", []),
                        fixed_issues
                    )
                    
                    await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")
                elif has_other_issues:
                    # Если есть другие проблемы с этой позицией
                    await state.set_state(InvoiceEditStates.issue_edit)
                    
                    message_text, keyboard = await format_issue_edit(selected_issue)
                    message_text = f"✅ Количество изменено на {quantity}.\n\n" + message_text
                    
                    await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")
                else:
                    # Если есть еще проблемы, возвращаемся к списку
                    await state.set_state(InvoiceEditStates.issue_list)
                    
                    message_text, keyboard = await format_issues_list(
                        {"issues": current_issues}, 
                        page=data.get("current_page", 0)
                    )
                    message_text = f"✅ Количество изменено на {quantity}.\n\n" + message_text
                    
                    await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await message.reply("❌ Ошибка при обновлении позиции.")
        except ValueError:
            await message.reply(
                "❌ Введите корректное число. Дробные числа вводите через точку, например: 2.5"
            )
    
    elif field == "search":
        # Обработка поискового запроса
        search_query = message.text.strip()
        
        if len(search_query) < 2:
            await message.reply("Слишком короткий запрос. Введите не менее 2 символов.")
            return
        
        # Ищем товары по запросу
        async with SessionLocal() as session:
            products = await get_products_by_name(session, search_query)
        
        # Удаляем сообщение пользователя
        try:
            await message.delete()
        except Exception:
            pass
        
        # Возвращаемся к выбору товара
        await state.set_state(InvoiceEditStates.product_select)
        
        # Сохраняем список товаров и запрос в состоянии
        await state.update_data(products=products, current_page=0, search_query=search_query)
        
        # Форматируем сообщение
        message_text, keyboard = await format_product_select(products, search_query, page=0)
        
        await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")
    
    elif field == "name":
        # Обработка ввода имени
        new_name = message.text.strip()
        
        if not new_name:
            await message.reply("❌ Имя не может быть пустым.")
            return
        
        if len(new_name) > 100:
            await message.reply("❌ Имя слишком длинное (максимум 100 символов).")
            return
        
        # Получаем данные позиции
        selected_issue = data.get("selected_issue", {})
        invoice_data = data.get("invoice", {})
        positions = invoice_data.get("positions", [])
        
        # Находим позицию
        issue_idx = data.get("selected_issue_idx", 0)
        issues = data.get("current_issues", [])
        
        position_idx = selected_issue.get("index", 0) - 1
        
        if 0 <= position_idx < len(positions):
            # Сохраняем старое имя
            old_name = positions[position_idx].get("name", "")
            
            # Обновляем имя
            positions[position_idx]["name"] = new_name
            
            # Обновляем данные в состоянии
            invoice_data["positions"] = positions
            await state.update_data(invoice=invoice_data)
            
            # Логируем изменение
            try:
                invoice_id = invoice_data.get("id", 0)
                user_id = message.from_user.id if message.from_user else 0
                
                await log_change(
                    invoice_id=invoice_id,
                    row_idx=position_idx,
                    user_id=user_id,
                    field="name",
                    old=old_name,
                    new=new_name
                )
            except Exception as e:
                logger.error("Failed to log name change", error=str(e))
            
            # Добавляем в список исправленных позиций
            fixed_issues = data.get("fixed_issues", {})
            if not fixed_issues:
                fixed_issues = {}
            
            fixed_issues[position_idx] = {
                "action": "change_name",
                "old_name": old_name,
                "new_name": new_name
            }
            await state.update_data(fixed_issues=fixed_issues)
            
            # Поиск соответствий в базе данных
            async with SessionLocal() as session:
                products = await get_products_by_name(session, new_name[:5], limit=5)
            
            # Если есть подходящие товары, предлагаем выбрать
            if products:
                await state.update_data(products=products, current_page=0, search_query=new_name[:5])
                await state.set_state(InvoiceEditStates.product_select)
                
                message_text, keyboard = await format_product_select(products, new_name[:5], page=0)
                message_text = f"✅ Имя изменено на <b>{new_name}</b>.\n\nНайдено несколько подходящих товаров:\n\n" + message_text
                
                await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")
            else:
                # Если нет соответствий, просто возвращаемся к редактированию
                await state.set_state(InvoiceEditStates.issue_edit)
                
                message_text, keyboard = await format_issue_edit(selected_issue)
                message_text = f"✅ Имя изменено на <b>{new_name}</b>.\nСоответствий в базе не найдено.\n\n" + message_text
                
                await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.reply("❌ Ошибка при обновлении имени.")
