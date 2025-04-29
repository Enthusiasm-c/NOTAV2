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
    InlineKeyboardButton
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

logger = structlog.get_logger()
router = Router(name="issue_editor")

# ───────────────────────── FSM States ────────────────────────
class InvoiceEditStates(StatesGroup):
    """Состояния FSM для редактирования накладной."""
    summary = State()            # А. Сводка накладной
    issue_list = State()         # B. Список проблемных позиций
    issue_edit = State()         # C. Редактор конкретной позиции
    field_input = State()        # D. Ввод значения поля
    product_select = State()     # E. Выбор товара из списка
    confirm = State()            # F. Финальное подтверждение
    bulk_add = State()           # G. Массовое добавление товаров


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
        if not product:
            await c.answer("❌ Нет данных о товаре для конвертации.")
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
            fixed_issues = data.get("fixed_issues", {})
            if not fixed_issues:
                fixed_issues = {}
            
            fixed_issues[position_idx] = {
                "action": "convert_unit",
                "from_unit": invoice_unit,
                "to_unit": db_unit,
                "old_quantity": quantity,
                "new_quantity": converted
            }
            await state.update_data(fixed_issues=fixed_issues)
            
            # Обновляем список проблем (удаляем решенную)
            issues = data.get("current_issues", [])
            issue_idx = data.get("selected_issue_idx", 0)
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
            
            # Добавляем информацию о конвертации
            conv_msg = f"✅ Конвертация выполнена: {quantity} {invoice_unit} → {converted} {db_unit}\n\n" + message
            
            # Отправляем сообщение
            try:
                await c.message.edit_text(conv_msg, reply_markup=keyboard, parse_mode="HTML")
            except Exception as e:
                logger.error("Failed to edit message", error=str(e))
                await c.message.answer(conv_msg, reply_markup=keyboard, parse_mode="HTML")
        else:
            await c.answer("❌ Ошибка при обновлении позиции.")
