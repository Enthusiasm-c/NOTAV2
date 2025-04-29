"""
Улучшенный UI-редактор спорных позиций для Nota V2.

Основные улучшения:
1. Отображение детальной информации о проблемных позициях сразу
2. Интерактивное редактирование с предложением товаров из базы
3. Конвертация единиц измерения
4. Массовое добавление отсутствующих товаров
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
from aiogram.filters import Text
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
from app.utils.unit_converter import normalize_unit, is_compatible_unit, convert
from app.config import settings
from app.utils.change_logger import log_change, log_delete, log_save_new
from app.utils.keyboards import kb_field_selector, kb_after_edit, FieldCallback, IssueCallback

logger = structlog.get_logger()
router = Router(name="issue_editor")

# ───────────────────────── Константы ────────────────────────
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

# Константы для полуфабрикатов
SEMIFINISHED_PATTERNS = [r's/f', r's/finished', r'semi.?finished', r'semi.?fabricated']
MIN_CONFIDENCE_FOR_LEARNING = 0.90  # Минимальная уверенность для автообучения

# ───────────────────────── Вспомогательные функции ────────────────────────
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
    limit: int = 3,
    threshold: float = 0.7,
    exclude_semifinished: bool = True
) -> List[Dict[str, Any]]:
    """
    Ищет товары по части имени с учетом полуфабрикатов.
    
    :param session: асинхронная сессия SQLAlchemy
    :param name_query: строка поиска
    :param limit: максимальное количество результатов (по умолчанию 3)
    :param threshold: минимальный порог схожести (по умолчанию 0.7)
    :param exclude_semifinished: исключить полуфабрикаты из результатов
    :return: список товаров
    """
    if not name_query:
        return []
    
    # Нормализуем запрос
    normalized_query = clean_name_for_comparison(name_query)
    
    # Пытаемся использовать функцию find_similar_products из fuzzy_match
    try:
        from app.routers.fuzzy_match import find_similar_products
        products = await find_similar_products(
            session, 
            normalized_query, 
            limit=limit, 
            threshold=threshold
        )
        
        # Фильтруем полуфабрикаты если нужно
        if exclude_semifinished:
            products = [p for p in products if not is_semifinished(p["name"])]
        
        return products
    except ImportError:
        logger.warning("fuzzy_match module not found, using fallback search")
    
    # Резервный путь: используем прямой SQL запрос
    stmt = (
        select(Product.id, Product.name, Product.unit)
        .where(func.lower(Product.name).like(f"%{normalized_query}%"))
        .order_by(Product.name)
        .limit(limit * 2)  # Запрашиваем больше для фильтрации
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
        
        # Используем более точное вычисление схожести
        try:
            from rapidfuzz import fuzz
            score = fuzz.token_sort_ratio(normalized_query, name_normalized) / 100.0
        except ImportError:
            # Простой расчет соответствия, если rapidfuzz не установлен
            if normalized_query == name_normalized:
                score = 1.0
            elif normalized_query in name_normalized.split():
                score = 0.85
            elif normalized_query in name_normalized:
                score = 0.75
            else:
                score = 0.65
        
        # Отфильтровываем результаты ниже порога схожести
        if score < threshold:
            continue
            
        products.append({
            "id": product_id,
            "name": name,
            "unit": unit,
            "confidence": score
        })
    
    # Сортируем по убыванию уверенности
    products.sort(key=lambda p: p["confidence"], reverse=True)
    
    # Ограничиваем количество результатов
    return products[:limit]


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

# ───────────────────────── Функции форматирования UI ────────────────────────

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
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="inv_ok"),
            InlineKeyboardButton(text=f"🔍 Исправить ({problematic_count})", callback_data="inv_edit")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="✅ Подтвердить и отправить", callback_data="inv_ok")
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
    message = f"❗ <b>Позиции требующие внимания — страница {page+1} / {total_pages}</b>\n\n<code>"
    
    # Формируем таблицу с новым дизайном
    # Заголовок таблицы с 4 колонками: №, Наименование, Кол-во/Ед., Цена
    message += f"{'№':<3} {'Наименование':<20} {'Кол-во/Ед.':<12} {'Цена':<8}\n"
    message += f"{'-'*3} {'-'*20} {'-'*12} {'-'*8}\n"
    
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
        
        # Ограничиваем длину названия
        if len(item_name) > 20:
            item_name = item_name[:17] + "..."
        
        # Форматируем столбец количества и единицы измерения
        quantity = original.get("quantity", 0)
        unit = original.get("unit", "")
        qty_unit = f"{quantity} {unit}".strip()
        
        # Форматируем столбец цены
        price = original.get("price", "")
        price_display = ""
        if price:
            try:
                price_float = float(price)
                price_display = f"{price_float:,.2f}"
            except (ValueError, TypeError):
                price_display = str(price)
        
        # Получаем иконку проблемы
        icon = get_issue_icon(issue)
        
        # Добавляем строку в таблицу
        message += f"{index:<3} {item_name:<20} {qty_unit:<12} {price_display:<8} {icon}\n"
    
    message += "</code>"
    
    # Добавляем инструкцию
    message += "\n\nНажмите на позицию для редактирования или используйте кнопки пагинации."
    
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
            InlineKeyboardButton(text="◀️ Пред", callback_data=f"{CB_PAGE_PREFIX}{page-1}")
        )
    
    if any("Not in database" in issue.get("issue", "") for issue in issues):
        pagination_row.append(
            InlineKeyboardButton(text="➕ Добавить все", callback_data=CB_ADD_ALL)
        )
    
    if page < total_pages - 1:
        pagination_row.append(
            InlineKeyboardButton(text="След ▶️", callback_data=f"{CB_PAGE_PREFIX}{page+1}")
        )
    
    if pagination_row:
        buttons.append(pagination_row)
    
    # Добавляем кнопку "Готово"
    buttons.append([
        InlineKeyboardButton(text="✅ Готово", callback_data=CB_CONFIRM)
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
        issue_description = "Товар не найден в базе данных"
    elif "incorrect match" in issue_type:
        issue_description = "Возможно некорректное сопоставление"
    elif "Unit" in issue_type:
        issue_description = "Несоответствие единиц измерения"
    else:
        issue_description = issue_type
    
    # Формируем заголовок
    message = f"{icon} <b>Редактирование позиции #{index}</b>\n\n"
    
    # Детали позиции
    message += f"<b>Название:</b> {name}\n"
    message += f"<b>Количество:</b> {quantity} {unit}\n"
    
    if price:
        try:
            price_float = float(price)
            message += f"<b>Цена:</b> {price_float:,.2f}\n"
        except (ValueError, TypeError):
            message += f"<b>Цена:</b> {price}\n"
    
    if sum_val:
        try:
            sum_float = float(sum_val)
            message += f"<b>Сумма:</b> {sum_float:,.2f}\n"
        except (ValueError, TypeError):
            message += f"<b>Сумма:</b> {sum_val}\n"
    
    # Информация о проблеме
    message += f"\n<b>Проблема:</b> {issue_description}\n"
    
    # Если есть данные о сопоставленном товаре, добавляем их
    if "product" in issue:
        product = issue["product"]
        message += f"\n<b>Сопоставление в базе:</b>\n"
        message += f"<b>→ Название:</b> {product.name}\n"
        message += f"<b>→ Единица:</b> {product.unit}\n"
    
    # Инструкция
    message += "\nВыберите действие для исправления проблемы:"
    
    # Создаем клавиатуру
    buttons = []
    
    # Первый ряд - основные действия
    buttons.append([
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"{CB_ACTION_PREFIX}edit_name")
    ])
    
    buttons.append([
        InlineKeyboardButton(text="📦 Товар", callback_data=f"{CB_ACTION_PREFIX}name"),
        InlineKeyboardButton(text="🔢 Количество", callback_data=f"{CB_ACTION_PREFIX}qty"),
        InlineKeyboardButton(text="📏 Единица", callback_data=f"{CB_ACTION_PREFIX}unit")
    ])
    
    # Добавляем дополнительные действия в зависимости от типа проблемы
    additional_row = []
    
    if "Not in database" in issue_type:
        additional_row.append(
            InlineKeyboardButton(text="➕ Создать новый", callback_data=f"{CB_ACTION_PREFIX}add_new")
        )
    
    if "Unit" in issue_type and "product" in issue:
        additional_row.append(
            InlineKeyboardButton(text="🔄 Конвертировать", callback_data=f"{CB_ACTION_PREFIX}convert")
        )
    
    if additional_row:
        buttons.append(additional_row)
    
    # Добавляем кнопки удаления и возврата
    buttons.append([
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"{CB_ACTION_PREFIX}delete"),
        InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)
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
    message = f"🔍 <b>Выбор товара для '{query}'</b>\n"
    
    if total_pages > 1:
        message += f"<i>Страница {page + 1} из {total_pages}</i>\n"
    
    message += "\n<b>Выберите товар из списка:</b>\n\n"
    
    for i, product in enumerate(current_products, start=1):
        name = product.get("name", "Unknown")
        unit = product.get("unit", "")
        confidence = product.get("confidence", 0) * 100
        
        message += f"{i}. <b>{name}</b> ({unit})"
        
        if confidence < 100:
            message += f" <i>{confidence:.0f}% соответствие</i>"
        
        message += "\n"
    
    if not current_products:
        message += "<i>Товары не найдены. Попробуйте изменить запрос или создайте новый товар.</i>"
    
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
            InlineKeyboardButton(text="◀️ Пред", callback_data=f"{CB_PAGE_PREFIX}{page-1}")
        )
    
    if page < total_pages - 1:
        pagination_row.append(
            InlineKeyboardButton(text="След ▶️", callback_data=f"{CB_PAGE_PREFIX}{page+1}")
        )
    
    if pagination_row:
        buttons.append(pagination_row)
    
    # Кнопки поиска и создания
    buttons.append([
        InlineKeyboardButton(text="🔍 Поиск", callback_data=CB_SEARCH),
        InlineKeyboardButton(text="➕ Новый товар", callback_data=CB_ADD_NEW)
    ])
    
    # Кнопка "Назад"
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)
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
    message = f"✅ <b>Накладная готова к отправке</b>\n\n"
    message += f"🏷️ <b>Поставщик:</b> {supplier}\n"
    message += f"📅 <b>Дата:</b> {date}{f' №{invoice_number}' if invoice_number else ''}\n\n"
    
    # Добавляем статистику
    message += f"<b>Всего позиций:</b> {len(active_positions)}\n"
    
    if fixed_count > 0:
        message += f"✅ <b>Исправлено проблем:</b> {fixed_count}\n"
    
    if remaining_issues > 0:
        message += f"⚠️ <b>Осталось проблем:</b> {remaining_issues}\n"
    else:
        message += "✅ <b>Все проблемы решены!</b>\n"
    
    # Добавляем инструкцию
    if remaining_issues > 0:
        message += "\n⚠️ <i>Примечание: Некоторые проблемы остались неразрешенными, но вы все равно можете продолжить.</i>"
    
    message += "\n\nПожалуйста, подтвердите для отправки накладной в Syrve."
    
    # Создаем клавиатуру
    buttons = [
        [InlineKeyboardButton(text="✅ Подтвердить и отправить", callback_data=CB_CONFIRM)],
        [InlineKeyboardButton(text="◀️ Вернуться к правкам", callback_data=CB_BACK)]
    ]
    
    return message, InlineKeyboardMarkup(inline_keyboard=buttons)


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
        "name": "названия",
        "qty": "количества",
        "unit": "единицы измерения",
        "price": "цены"
    }
    
    field_label = field_labels.get(field, field)
    
    message = f"<b>Введите новое значение {field_label}:</b>\n\n"
    message += f"Текущее значение: {current_value}\n\n"
    
    field_hints = {
        "name": "Введите название товара (максимум 100 символов)",
        "qty": "Введите числовое количество (например, 5 или 2.5)",
        "unit": "Введите единицу измерения (например, кг, л, шт)",
        "price": "Введите цену (только числа)"
    }
    
    if field in field_hints:
        message += f"<i>{field_hints[field]}</i>"
        
    return message

# ───────────────────────── Обработчики навигации ────────────────────────
@router.callback_query(Text(CB_BACK))
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


# ───────────────────────── Обработчики выбора позиции ────────────────────────
@router.callback_query(Text(["inv_edit", CB_REVIEW]))
async def cb_start_review(c: CallbackQuery, state: FSMContext):
    """
    Обработчик начала просмотра проблемных позиций.
    
    Активируется при нажатии на кнопку "Исправить" в сводке накладной.
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


@router.callback_query(lambda c: c.data and c.data.startswith(CB_ISSUE_PREFIX), InvoiceEditStates.issue_list)
async def cb_select_issue(c: CallbackQuery, state: FSMContext):
    """
    Обработчик выбора конкретной проблемной позиции из списка.
    """
    # Определяем индекс позиции из callback_data
    try:
        position_index = int(c.data[len(CB_ISSUE_PREFIX):]) - 1
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
        if issue_index == position_index:
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
@router.callback_query(lambda c: c.data and c.data.startswith(CB_PAGE_PREFIX))
async def cb_change_page(c: CallbackQuery, state: FSMContext):
    """
    Обработчик пагинации для списков позиций и товаров.
    """
    # Определяем номер страницы
    page = int(c.data[len(CB_PAGE_PREFIX):])
    
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


# ───────────────────────── Обработчик выбора продукта ────────────────────────
@router.callback_query(lambda c: c.data and c.data.startswith(CB_PRODUCT_PREFIX), InvoiceEditStates.product_select)
async def cb_select_product(c: CallbackQuery, state: FSMContext):
    """
    Обработчик выбора конкретного продукта из списка.
    """
    # Получаем ID продукта из callback_data
    product_id = int(c.data[len(CB_PRODUCT_PREFIX):])
    
    # Получаем данные из состояния
    data = await state.get_data()
    selected_issue = data.get("selected_issue", {})
    invoice_data = data.get("invoice", {})
    positions = invoice_data.get("positions", [])
    
    # Находим индексы
    issue_idx = data.get("selected_issue_idx", 0)
    issues = data.get("current_issues", [])
    position_idx = selected_issue.get("index", 0) - 1
    
    if 0 <= position_idx < len(positions):
        # Получаем информацию о выбранном продукте
        products = data.get("products", [])
        selected_product = None
        
        for product in products:
            if product.get("id") == product_id:
                selected_product = product
                break
        
        if not selected_product:
            await c.answer("❌ Выбранный продукт не найден.")
            return
        
        # Обновляем данные позиции
        position = positions[position_idx]
        
        # Сохраняем старые значения для логирования
        old_name = position.get("name", "")
        
        # Обновляем сопоставление
        position["match_id"] = product_id
        position["confidence"] = 1.0  # Установлено пользователем вручную
        
        # Сохраняем изменения в базе данных - добавляем в таблицу сопоставлений
        try:
            async with SessionLocal() as session:
                success = await save_product_match(
                    session, 
                    old_name,  # Исходное название из накладной
                    product_id  # ID выбранного продукта
                )
                
                if success:
                    logger.info("Product match saved to lookup table", 
                               name=old_name, product_id=product_id)
                else:
                    logger.warning("Failed to save product match", 
                                  name=old_name, product_id=product_id)
        except Exception as e:
            logger.error("Error saving product match", error=str(e))
        
        # Обновляем данные накладной в состоянии
        invoice_data["positions"] = positions
        await state.update_data(invoice=invoice_data)
        
        # Добавляем в список исправленных позиций
        fixed_issues = data.get("fixed_issues", {}) or {}
        fixed_issues[position_idx] = {
            "action": "match_product",
            "product_id": product_id,
            "product_name": selected_product.get("name")
        }
        await state.update_data(fixed_issues=fixed_issues)
        
        # Логируем изменение
        try:
            invoice_id = invoice_data.get("id", 0)
            user_id = c.from_user.id if c.from_user else 0
            
            await log_change(
                invoice_id=invoice_id,
                row_idx=position_idx,
                user_id=user_id,
                field="match_id",
                old=None,
                new=product_id
            )
        except Exception as e:
            logger.error("Failed to log product match", error=str(e))
        
        # Проверяем необходимость конвертации единиц
        position_unit = normalize_unit(position.get("unit", ""))
        product_unit = normalize_unit(selected_product.get("unit", ""))
        
        if position_unit and product_unit and position_unit != product_unit:
            # Есть несоответствие единиц, предлагаем конвертацию
            await state.update_data(
                product_match_unit_mismatch=True,
                from_unit=position_unit,
                to_unit=product_unit,
                product_name=selected_product.get("name")
            )
            
            # Создаем клавиатуру для выбора действия
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔄 Конвертировать единицы", 
                                        callback_data=f"{CB_CONVERT_PREFIX}auto"),
                    InlineKeyboardButton(text="✅ Оставить как есть", 
                                        callback_data=f"{CB_CONVERT_PREFIX}skip")
                ]
            ])
            
            # Отправляем сообщение
            await c.message.answer(
                f"⚠️ <b>Обнаружено несоответствие единиц измерения</b>\n\n"
                f"Товар <b>{selected_product.get('name')}</b> в базе данных имеет "
                f"единицу измерения <b>{product_unit}</b>, но в накладной указано <b>{position_unit}</b>.\n\n"
                f"Хотите автоматически конвертировать единицы?",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await c.answer()
            return
        
        # Обновляем список проблем (удаляем исправленную)
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
        
        # Добавляем информацию о сопоставлении
        message = (
            f"✅ Товар успешно сопоставлен с <b>{selected_product.get('name')}</b>.\n\n"
            + message
        )
        
        # Отправляем сообщение
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    else:
        await c.answer("❌ Ошибка при обновлении позиции.")
    
    await c.answer()

# ───────────────────────── Обработчики действий с позицией ────────────────────────
@router.callback_query(lambda c: c.data and c.data.startswith(CB_ACTION_PREFIX), InvoiceEditStates.issue_edit)
async def cb_action_with_item(c: CallbackQuery, state: FSMContext):
    """
    Обработчик выбора действия с проблемной позицией.
    """
    # Определяем действие
    action = c.data[len(CB_ACTION_PREFIX):]
    
    # Получаем данные из состояния
    data = await state.get_data()
    selected_issue = data.get("selected_issue", {})
    original = selected_issue.get("original", {})
    
    # Обрабатываем разные действия
    if action == "name":
        # Переход к выбору товара
        await state.set_state(InvoiceEditStates.product_select)
        
        # Получаем название для поиска
        name_query = original.get("name", "")[:5]  # Первые 5 символов для поиска
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
        msg = format_field_prompt("qty", f"{original.get('quantity', 0)} {original.get('unit', '')}")
        
        # Отправляем с ForceReply для получения ответа
        await c.message.edit_text(msg, parse_mode="HTML")
        await c.message.answer("Введите новое количество:", reply_markup=ForceReply())
    
    elif action == "unit":
        # Переход к выбору единицы измерения
        await state.set_state(InvoiceEditStates.field_input)
        await state.update_data(field="unit")
        
        # Отправляем сообщение с запросом
        msg = format_field_prompt("unit", original.get("unit", ""))
        
        # Отправляем с ForceReply для получения ответа
        await c.message.edit_text(msg, parse_mode="HTML")
        await c.message.answer("Введите новую единицу измерения:", reply_markup=ForceReply())
    
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
            fixed_issues = data.get("fixed_issues", {}) or {}
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
    
    elif action == "add_new":
        # Добавление нового товара
        invoice_data = data.get("invoice", {})
        position_idx = selected_issue.get("index", 0) - 1
        
        # Получаем данные позиции
        if "positions" in invoice_data and 0 <= position_idx < len(invoice_data["positions"]):
            # Отмечаем, что эта позиция будет добавлена как новый товар
            fixed_issues = data.get("fixed_issues", {}) or {}
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
            
            # Вернуться к списку проблем или к финальному подтверждению
            if not current_issues:
                await state.set_state(InvoiceEditStates.confirm)
                
                message, keyboard = await format_final_preview(
                    invoice_data,
                    data.get("issues", []),
                    fixed_issues,
                )
            else:
                await state.set_state(InvoiceEditStates.issue_list)
                
                message, keyboard = await format_issues_list(
                    {"issues": current_issues},
                    page=data.get("current_page", 0),
                )
            
            # Сообщение об успешном добавлении товара
            message = (
                f"✅ Товар <b>{original.get('name', '')}</b> сохранён как новый!\n\n"
                + message
            )
            
            # Отправляем сообщение
            try:
                await c.message.edit_text(
                    message,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Failed to edit message", error=str(e))
                await c.message.answer(
                    message,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        else:
            await c.answer("❌ Ошибка при добавлении нового товара.")
    
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
                "action": "convert_unit",
                "from_unit": invoice_unit,
                "to_unit": db_unit,
                "old_quantity": quantity,
                "new_quantity": converted,
            }
            await state.update_data(fixed_issues=fixed_issues)

            # Обновляем список проблем (удаляем решённую)
            issues = data.get("current_issues", [])
            issue_idx = data.get("selected_issue_idx", 0)
            new_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
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
    
    else:
        await c.answer(f"⚠️ Неизвестное действие: {action}")
    
    # Отвечаем на callback, чтобы убрать часики у сообщения
    await c.answer()


# ───────────────────────── Обработчики выбора единицы и конвертации ────────────────────────
@router.callback_query(lambda c: c.data and c.data.startswith(CB_UNIT_PREFIX), InvoiceEditStates.field_input)
async def cb_select_unit(c: CallbackQuery, state: FSMContext):
    """
    Обработчик выбора единицы измерения.
    """
    # Определяем единицу измерения
    unit = c.data[len(CB_UNIT_PREFIX):]
    
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
        fixed_issues = data.get("fixed_issues", {}) or {}
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


@router.callback_query(lambda c: c.data and c.data.startswith(CB_CONVERT_PREFIX))
async def cb_convert_unit(c: CallbackQuery, state: FSMContext):
    """
    Обработчик подтверждения конвертации единиц измерения.
    """
    # Определяем ответ
    action = c.data[len(CB_CONVERT_PREFIX):]
    is_auto = action == "auto"
    is_yes = action == "yes" or is_auto
    is_skip = action == "skip" or action == "no"
    
    # Получаем данные из состояния
    data = await state.get_data()
    invoice_data = data.get("invoice", {})
    positions = invoice_data.get("positions", [])
    
    # Для автоматической конвертации после сопоставления
    if is_auto:
        # Используем данные из автоматического сопоставления
        from_unit = data.get("from_unit", "")
        to_unit = data.get("to_unit", "")
        
        # Находим позицию по match_id
        position_idx = None
        product_id = None
        
        for i, pos in enumerate(positions):
            if pos.get("match_id") and pos.get("unit") == from_unit:
                # Это наша позиция
                position_idx = i
                product_id = pos.get("match_id")
                break
        
        if position_idx is None:
            await c.answer("❌ Не удалось найти позицию для конвертации.")
            return
    else:
        # Для ручной конвертации используем сохраненные значения
        from_unit = data.get("conversion_from", "")
        to_unit = data.get("conversion_to", "")
        position_idx = data.get("position_idx", -1)
    
    if 0 <= position_idx < len(positions):
        # Если пользователь подтвердил конвертацию
        if is_yes:
            quantity = positions[position_idx].get("quantity", 0)
            
            # Пытаемся конвертировать
            try:
                quantity_float = float(quantity)
                converted = convert(quantity_float, from_unit, to_unit)
                
                if converted is not None:
                    # Обновляем количество и единицу
                    positions[position_idx]["quantity"] = converted
                    positions[position_idx]["unit"] = to_unit
                    
                    # Обновляем сумму, если есть цена
                    if price := positions[position_idx].get("price"):
                        try:
                            price_float = float(price)
                            positions[position_idx]["sum"] = converted * price_float
                        except (ValueError, TypeError):
                            pass
                    
                    # Добавляем в список исправленных позиций
                    fixed_issues = data.get("fixed_issues", {}) or {}
                    fixed_issues[position_idx] = {
                        "action": "convert_unit",
                        "from_unit": from_unit,
                        "to_unit": to_unit,
                        "old_quantity": quantity,
                        "new_quantity": converted
                    }
                    
                    await state.update_data(fixed_issues=fixed_issues)
                    
                    # Логируем конвертацию
                    try:
                        invoice_id = invoice_data.get("id", 0)
                        user_id = c.from_user.id if c.from_user else 0
                        
                        await log_change(
                            invoice_id=invoice_id,
                            row_idx=position_idx,
                            user_id=user_id,
                            field="convert_unit",
                            old=f"{quantity} {from_unit}",
                            new=f"{converted} {to_unit}"
                        )
                    except Exception as e:
                        logger.error("Failed to log unit conversion", error=str(e))
                    
                    # Формируем сообщение об успешной конвертации
                    conversion_message = f"✅ Конвертировано: {quantity} {from_unit} → {converted} {to_unit}"
                else:
                    # Если конвертация невозможна
                    msg = (
                        f"❌ Не удалось конвертировать из <b>{from_unit}</b> в <b>{to_unit}</b>.\n"
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
        elif is_skip:
            # Если пользователь отказался от конвертации
            conversion_message = f"✅ Единицы не конвертированы, оставлено как есть."
        else:
            await c.answer("❌ Неизвестное действие.")
            return
        
        # Обновляем данные в состоянии
        invoice_data["positions"] = positions
        await state.update_data(invoice=invoice_data)
        
        # Обновляем список проблем
        issues = data.get("current_issues", [])
        issue_idx = None
        
        # Находим индекс проблемы в списке
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
                data.get("fixed_issues", {})
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

# ───────────────────────── Массовые операции и подтверждение ────────────────────────
@router.callback_query(Text(CB_ADD_ALL))
async def cb_add_all_missing(c: CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки "Добавить все отсутствующие товары".
    """
    # Получаем данные из состояния
    data = await state.get_data()
    invoice_data = data.get("invoice", {})
    positions = invoice_data.get("positions", [])
    issues = data.get("current_issues", [])
    
    # Находим все позиции, отсутствующие в базе
    missing_positions = []
    for issue in issues:
        if "Not in database" in issue.get("issue", ""):
            position_idx = issue.get("index", 0) - 1
            if 0 <= position_idx < len(positions):
                missing_positions.append((position_idx, issue))
    
    if not missing_positions:
        await c.answer("❌ Нет отсутствующих в базе товаров.")
        return
    
    # Отмечаем все отсутствующие позиции как "новый товар"
    fixed_issues = data.get("fixed_issues", {}) or {}
    
    for position_idx, issue in missing_positions:
        fixed_issues[position_idx] = {"action": "new_product"}
        
        # Логируем создание нового товара
        try:
            invoice_id = invoice_data.get("id", 0)
            user_id = c.from_user.id if c.from_user else 0
            item_name = positions[position_idx].get("name", "")
            
            await log_save_new(
                invoice_id=invoice_id,
                row_idx=position_idx,
                user_id=user_id,
                item_name=item_name
            )
        except Exception as e:
            logger.error("Failed to log add_all_missing action", error=str(e))
    
    # Обновляем данные в состоянии
    await state.update_data(fixed_issues=fixed_issues)
    
    # Обновляем список проблем (удаляем все решенные)
    remaining_issues = []
    for issue in issues:
        if "Not in database" not in issue.get("issue", ""):
            remaining_issues.append(issue)
    
    await state.update_data(current_issues=remaining_issues)
    
    # Определяем следующий шаг
    if not remaining_issues:
        # Если проблем больше нет, переходим к подтверждению
        await state.set_state(InvoiceEditStates.confirm)
        
        message, keyboard = await format_final_preview(
            invoice_data, 
            data.get("issues", []), 
            fixed_issues
        )
        
        # Добавляем информацию о групповом добавлении
        message = (
            f"✅ Добавлено {len(missing_positions)} новых товаров.\n\n"
            + message
        )
    else:
        # Возвращаемся к списку проблем
        await state.set_state(InvoiceEditStates.issue_list)
        
        message, keyboard = await format_issues_list(
            {"issues": remaining_issues}, 
            page=0
        )
        
        # Добавляем информацию о групповом добавлении
        message = (
            f"✅ Добавлено {len(missing_positions)} новых товаров.\n\n"
            + message
        )
    
    # Отправляем сообщение
    try:
        await c.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error("Failed to edit message", error=str(e))
        await c.message.answer(message, reply_markup=keyboard, parse_mode="HTML")
    
    await c.answer()


@router.callback_query(Text([CB_CONFIRM, "done"]))
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


# ───────────────────────── Обработчики поиска товара ────────────────────────
@router.callback_query(Text(CB_SEARCH), InvoiceEditStates.product_select)
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
                
                # Логируем изменение
                try:
                    invoice_id = invoice_data.get("id", 0)
                    user_id = message.from_user.id if message.from_user else 0
                    
                    await log_change(
                        invoice_id=invoice_id,
                        row_idx=position_idx,
                        user_id=user_id,
                        field="quantity",
                        old=old_quantity,
                        new=quantity
                    )
                except Exception as e:
                    logger.error("Failed to log quantity change", error=str(e))
                
                # Добавляем в список исправленных позиций
                fixed_issues = data.get("fixed_issues", {}) or {}
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
            fixed_issues = data.get("fixed_issues", {}) or {}
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
    
    elif field == "unit":
        # Обработка ввода единицы измерения
        new_unit = message.text.strip()
        
        if not new_unit:
            await message.reply("❌ Единица измерения не может быть пустой.")
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
            # Сохраняем старую единицу измерения
            old_unit = positions[position_idx].get("unit", "")
            
            # Обновляем единицу измерения
            positions[position_idx]["unit"] = new_unit
            
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
                    field="unit",
                    old=old_unit,
                    new=new_unit
                )
            except Exception as e:
                logger.error("Failed to log unit change", error=str(e))
            
            # Добавляем в список исправленных позиций
            fixed_issues = data.get("fixed_issues", {}) or {}
            fixed_issues[position_idx] = {
                "action": "change_unit",
                "old_unit": old_unit,
                "new_unit": new_unit
            }
            await state.update_data(fixed_issues=fixed_issues)
            
            # Проверяем необходимость конвертации (если есть сопоставленный товар)
            product = selected_issue.get("product")
            
            if product and product.unit and new_unit != product.unit:
                # Предложение конвертации
                # Создаем клавиатуру для выбора действия
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🔄 Конвертировать", 
                                            callback_data=f"{CB_CONVERT_PREFIX}yes"),
                        InlineKeyboardButton(text="✅ Оставить как есть", 
                                            callback_data=f"{CB_CONVERT_PREFIX}no")
                    ]
                ])
                
                # Сохраняем данные для конвертации
                await state.update_data(
                    conversion_from=new_unit,
                    conversion_to=product.unit,
                    position_idx=position_idx
                )
                
                # Формируем сообщение
                msg = (
                    f"✅ Единица измерения изменена на <b>{new_unit}</b>.\n\n"
                    f"⚠️ Эта единица отличается от единицы товара в базе данных (<b>{product.unit}</b>).\n"
                    f"Хотите автоматически конвертировать количество из {new_unit} в {product.unit}?"
                )
                
                await message.answer(msg, reply_markup=keyboard, parse_mode="HTML")
                return
                
            # Если нет необходимости в конвертации, возвращаемся к редактированию
            await state.set_state(InvoiceEditStates.issue_edit)
            
            message_text, keyboard = await format_issue_edit(selected_issue)
            message_text = f"✅ Единица измерения изменена на <b>{new_unit}</b>.\n\n" + message_text
            
            await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.reply("❌ Ошибка при обновлении единицы измерения.")
    else:
        await message.reply(f"❌ Неизвестное поле для редактирования: {field}")
