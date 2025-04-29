"""
Улучшенный UI-редактор спорных позиций для Nota V2 (часть 1).

Содержит:
- Импорты и конфигурацию
- FSM-состояния
- Константы
- Базовые вспомогательные функции

Построен на aiogram FSM (Finite State Machine).
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

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models.product import Product
from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem

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

# Импортируем модули шаблонизации и клавиатур
try:
    from app.utils.template_engine import (
        render_summary, render_issues, render_issue_edit_view,
        render_product_selection, render_final_preview
    )
    from app.utils.keyboards import (
        kb_summary, kb_issues, kb_issue_edit, kb_product_select,
        kb_unit_select, kb_convert_confirm, kb_confirm, kb_back_only,
        CB_ISSUE_PREFIX, CB_PAGE_PREFIX, CB_PRODUCT_PREFIX, CB_ACTION_PREFIX,
        CB_UNIT_PREFIX, CB_CONVERT_PREFIX, CB_ADD_NEW, CB_ADD_ALL, CB_SEARCH,
        CB_BACK, CB_CANCEL, CB_CONFIRM, CB_REVIEW
    )
    TEMPLATE_ENGINE_AVAILABLE = True
except ImportError:
    TEMPLATE_ENGINE_AVAILABLE = False
    # Обрабатываем случай отсутствия новых модулей (будут использоваться старые функции)

# Импортируем модуль самообучения
try:
    from app.utils.lookup_manager import add_lookup_entry, process_fixed_issues
    LOOKUP_MANAGER_AVAILABLE = True
except ImportError:
    LOOKUP_MANAGER_AVAILABLE = False

# Импортируем улучшенный модуль нечеткого поиска
try:
    from app.routers.fuzzy_match import (
        fuzzy_match_product as improved_fuzzy_match_product,
        get_product_suggestions
    )
    IMPROVED_FUZZY_MATCH_AVAILABLE = True
except ImportError:
    try:
        from app.routers.fuzzy_match import fuzzy_match_product
        IMPROVED_FUZZY_MATCH_AVAILABLE = False
    except ImportError:
        # Заглушка, если ни один модуль не найден
        async def fuzzy_match_product(session, name, threshold=None):
            return None, 0.0
        IMPROVED_FUZZY_MATCH_AVAILABLE = False

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

# Префиксы для callback-данных (совместимые с keyboards.py)
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


# ───────────────────────── Helpers ────────────────────────
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
    if IMPROVED_FUZZY_MATCH_AVAILABLE:
        # Используем улучшенный поиск товаров с фильтрацией полуфабрикатов
        return await get_product_suggestions(
            session, 
            name_query, 
            limit=limit,
            exclude_semifinished=exclude_semifinished
        )
    else:
        # Обычный поиск по базе данных
        semifinished_patterns = [r's/f', r's/finished', r'semi.?finished', r'semi.?fabricated']
        
        stmt = (
            select(Product.id, Product.name, Product.unit)
            .where(func.lower(Product.name).like(f"%{name_query.lower()}%"))
            .order_by(Product.name)
            .limit(limit)
        )
        
        result = await session.execute(stmt)
        products = []
        
        for row in result:
            product_id, name, unit = row
            
            # Фильтрация полуфабрикатов если нужно
            if exclude_semifinished:
                if any(re.search(pattern, name.lower()) for pattern in semifinished_patterns):
                    continue
            
            products.append({
                "id": product_id,
                "name": name,
                "unit": unit,
                "confidence": 1.0  # Точное соответствие из базы
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
    if LOOKUP_MANAGER_AVAILABLE:
        return await add_lookup_entry(session, parsed_name, product_id)
    else:
        # Простая реализация без отдельного модуля
        from app.models.product_name_lookup import ProductNameLookup
        
        try:
            # Проверяем наличие записи
            stmt = select(ProductNameLookup).where(ProductNameLookup.alias == parsed_name)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                # Обновляем существующую запись
                existing.product_id = product_id
            else:
                # Создаем новую запись
                new_lookup = ProductNameLookup(
                    alias=parsed_name,
                    product_id=product_id
                )
                session.add(new_lookup)
            
            await session.commit()
            return True
        except Exception as e:
            logger.error("Failed to save product match", error=str(e))
            await session.rollback()
            return False

# Импорт других частей модуля
from app.routers.issue_editor_part2 import (
    format_summary_message, format_issues_list, format_issue_edit,
    format_product_select, format_final_preview
)
from app.routers.issue_editor_part3 import cb_start_review, cb_select_issue, cb_change_page
from app.routers.issue_editor_part4 import cb_action_with_item, cb_select_product
from app.routers.issue_editor_part5 import (
    cb_select_unit, cb_convert_unit, cb_back, cb_done, 
    process_field_input, cb_search_product
)
"""
Улучшенный UI-редактор спорных позиций для Nota V2 (часть 2).

Содержит:
- Функции форматирования сообщений для Telegram
- Создание HTML/Markdown разметки
- Поддержка шаблонизатора

Обеспечивает форматирование для всех типов сообщений в UI-редакторе.
"""

from __future__ import annotations

import re
import math
import html
from typing import Any, Dict, List, Optional, Tuple

from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)

import structlog

# Импортируем константы из части 1
from app.routers.issue_editor_part1 import (
    TEMPLATE_ENGINE_AVAILABLE, PAGE_SIZE,
    CB_ISSUE_PREFIX, CB_PAGE_PREFIX, CB_PRODUCT_PREFIX, CB_ACTION_PREFIX,
    CB_UNIT_PREFIX, CB_BACK, CB_CONFIRM, CB_REVIEW, CB_SEARCH, CB_ADD_NEW, CB_ADD_ALL
)

logger = structlog.get_logger()

# Проверяем наличие шаблонизатора
if TEMPLATE_ENGINE_AVAILABLE:
    try:
        from app.utils.template_engine import (
            render_summary, render_issues, render_issue_edit_view,
            render_product_selection, render_final_preview
        )
        from app.utils.keyboards import (
            kb_summary, kb_issues, kb_issue_edit, kb_product_select,
            kb_unit_select, kb_convert_confirm, kb_confirm, kb_back_only
        )
    except ImportError:
        TEMPLATE_ENGINE_AVAILABLE = False


# ───────────────────────── UI Formatting Functions ────────────────────────

async def format_summary_message(data: Dict[str, Any]) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Форматирует сообщение со сводкой накладной.
    
    :param data: данные накладной
    :return: текст сообщения и клавиатура
    """
    if TEMPLATE_ENGINE_AVAILABLE:
        # Используем новый движок шаблонов
        message = render_summary(data)
        
        # Подсчитываем проблемные позиции
        positions = data.get("positions", [])
        active_positions = [p for p in positions if not p.get("deleted", False)]
        issues = data.get("issues", [])
        
        keyboard = kb_summary(len(issues))
    else:
        # Старый формат
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
        
        supplier = data.get("supplier", "Unknown")
        date = data.get("date", "Unknown")
        invoice_number = data.get("number", "")
        
        message = f"📄 *Invoice draft*\n\n"
        message += f"🏷️ *Supplier:* {supplier}\n"
        message += f"📅 *Date:* {date}{f' №{invoice_number}' if invoice_number else ''}\n\n"
        message += f"*Items parsed:* {total_positions}  \n"
        message += f"✅ *Matched:* {matched_count}  \n"
        
        if problematic_count > 0:
            message += f"❓ *Need review:* {problematic_count}"
        else:
            message += "✅ *All items matched!*"
        
        # Создаем клавиатуру
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
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    return message, keyboard


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
    
    if TEMPLATE_ENGINE_AVAILABLE:
        # Используем новый движок шаблонов
        message = render_issues(data, page)
        keyboard = kb_issues(issues, page)
    else:
        # Старый формат
        total_pages = math.ceil(len(issues) / PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        
        message = f"❗ *Items to review — page {page+1} / {total_pages}*\n\n"
        
        # Получаем позиции для текущей страницы
        start_idx = page * PAGE_SIZE
        end_idx = min(start_idx + PAGE_SIZE, len(issues))
        current_issues = issues[start_idx:end_idx]
        
        # Форматируем таблицу
        message += "```\n#  Invoice item             Issue\n"
        
        for issue in current_issues:
            index = issue.get("index", 0)
            original = issue.get("original", {})
            
            name = original.get("name", "Unknown")
            if len(name) > 20:
                name = name[:17] + "..."
                
            unit = original.get("unit", "")
            if unit:
                name = f"{name} {unit}"
                if len(name) > 20:
                    name = name[:17] + "..."
            
            issue_type = issue.get("issue", "Unknown issue")
            
            # Определяем иконку в зависимости от типа проблемы
            if "Not in database" in issue_type:
                icon = "⚠"
                issue_display = "Not in DB"
            elif "incorrect match" in issue_type:
                icon = "❔"
                issue_display = "Low confidence"
            elif "Unit" in issue_type:
                icon = "🔄"
                issue_display = "Unit mismatch"
            else:
                icon = "❓"
                issue_display = issue_type[:15]
                
            message += f"{index:<2} {name:<20} {icon} {issue_display}\n"
        
        message += "```\n"
        
        # Добавляем инструкцию
        message += "\nНажмите на позицию для редактирования или используйте кнопки пагинации."
        
        # Создаем клавиатуру
        buttons = []
        
        # Кнопки для каждой позиции
        for issue in current_issues:
            index = issue.get("index", 0)
            original = issue.get("original", {})
            name = original.get("name", "")[:15]
            
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
                InlineKeyboardButton(text=btn_text, callback_data=f"issue_{index-1}")
            ])
        
        # Кнопки пагинации
        pagination_row = []
        
        if page > 0:
            pagination_row.append(
                InlineKeyboardButton(text="◀️ Prev", callback_data=f"page_{page-1}")
            )
        
        if any("Not in database" in issue.get("issue", "") for issue in issues):
            pagination_row.append(
                InlineKeyboardButton(text="➕ Add All Missing", callback_data="add_all_missing")
            )
        
        if page < total_pages - 1:
            pagination_row.append(
                InlineKeyboardButton(text="Next ▶️", callback_data=f"page_{page+1}")
            )
        
        if pagination_row:
            buttons.append(pagination_row)
        
        # Кнопка "Готово"
        buttons.append([
            InlineKeyboardButton(text="✅ Done", callback_data="inv_ok")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    return message, keyboard


async def format_issue_edit(
    issue: Dict[str, Any]
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Форматирует сообщение для редактирования конкретной проблемной позиции.
    
    :param issue: данные о проблемной позиции
    :return: текст сообщения и клавиатура
    """
    if TEMPLATE_ENGINE_AVAILABLE:
        # Используем новый движок шаблонов
        message = render_issue_edit_view(issue)
        keyboard = kb_issue_edit(issue)
    else:
        # Старый формат
        original = issue.get("original", {})
        
        index = issue.get("index", 0)
        name = original.get("name", "Unknown")
        quantity = original.get("quantity", 0)
        unit = original.get("unit", "")
        price = original.get("price", 0)
        sum_val = original.get("sum", 0)
        
        issue_type = issue.get("issue", "Unknown issue")
        
        # Определяем иконку и описание проблемы
        if "Not in database" in issue_type:
            icon = "⚠"
            issue_description = "Товар не найден в базе данных"
        elif "incorrect match" in issue_type:
            icon = "❔"
            issue_description = "Возможно неверное сопоставление"
        elif "Unit" in issue_type:
            icon = "🔄"
            issue_description = "Несоответствие единиц измерения"
        else:
            icon = "❓"
            issue_description = issue_type
        
        # Форматируем сообщение
        message = f"{icon} *Редактирование позиции #{index}*\n\n"
        message += f"*Наименование:* {name}\n"
        message += f"*Количество:* {quantity} {unit}\n"
        
        if price:
            message += f"*Цена:* {price:,.2f}\n"
        
        if sum_val:
            message += f"*Сумма:* {sum_val:,.2f}\n"
        
        # Добавляем информацию о проблеме
        message += f"\n*Проблема:* {issue_description}\n"
        
        # Если есть информация о товаре в базе, добавляем ее
        product = issue.get("product")
        if product:
            message += f"\n*В базе данных:*\n"
            message += f"*→ Наименование:* {product.name}\n"
            message += f"*→ Единица измерения:* {product.unit}\n"
        
        # Добавляем инструкцию
        message += f"\nВыберите действие для исправления проблемы:"
        
        # Создаем клавиатуру
        buttons = [
            # Первый ряд - основные действия
            [
                InlineKeyboardButton(text="📦 Товар", callback_data="action_name"),
                InlineKeyboardButton(text="🔢 Кол-во", callback_data="action_qty"),
                InlineKeyboardButton(text="📏 Ед.изм", callback_data="action_unit")
            ]
        ]
        
        # Добавляем дополнительные действия в зависимости от типа проблемы
        additional_row = []
        
        if "Not in database" in issue_type:
            additional_row.append(
                InlineKeyboardButton(text="➕ Создать", callback_data="action_add_new")
            )
        
        if "Unit" in issue_type and product:
            additional_row.append(
                InlineKeyboardButton(text="🔄 Конвертировать", callback_data="action_convert")
            )
        
        if additional_row:
            buttons.append(additional_row)
        
        # Добавляем кнопки удаления и возврата
        buttons.append([
            InlineKeyboardButton(text="🗑️ Удалить", callback_data="action_delete"),
            InlineKeyboardButton(text="◀️ Назад", callback_data="back")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    return message, keyboard


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
    if TEMPLATE_ENGINE_AVAILABLE:
        # Используем новый движок шаблонов
        message = render_product_selection(products, query, page)
        keyboard = kb_product_select(products, page, query)
    else:
        # Старый формат
        # Рассчитываем пагинацию
        total_pages = math.ceil(len(products) / PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        
        # Получаем товары для текущей страницы
        start_idx = page * PAGE_SIZE
        end_idx = min(start_idx + PAGE_SIZE, len(products))
        current_products = products[start_idx:end_idx]
        
        # Форматируем сообщение
        message = f"🔍 *Выбор товара для '{query}'*\n"
        
        if total_pages > 1:
            message += f"_Страница {page+1} из {total_pages}_\n"
        
        message += "\n*Выберите товар из списка:*\n\n"
        
        for i, product in enumerate(current_products, start=1):
            name = product.get("name", "Unknown")
            unit = product.get("unit", "")
            confidence = product.get("confidence", 0) * 100
            
            message += f"{i}. *{name}* ({unit})"
            
            if confidence < 100:
                message += f" _{confidence:.0f}% совпадение_"
            
            message += "\n"
        
        if not current_products:
            message += "_Товары не найдены. Попробуйте изменить поисковый запрос или создать новый товар._"
        
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
                InlineKeyboardButton(text=display_text, callback_data=f"product_{product_id}")
            ])
        
        # Кнопки пагинации
        pagination_row = []
        
        if page > 0:
            pagination_row.append(
                InlineKeyboardButton(text="◀️ Prev", callback_data=f"page_{page-1}")
            )
        
        if page < total_pages - 1:
            pagination_row.append(
                InlineKeyboardButton(text="Next ▶️", callback_data=f"page_{page+1}")
            )
        
        if pagination_row:
            buttons.append(pagination_row)
        
        # Кнопки поиска и создания
        buttons.append([
            InlineKeyboardButton(text="🔍 Поиск", callback_data="search"),
            InlineKeyboardButton(text="➕ Новый товар", callback_data="add_new")
        ])
        
        # Кнопка "Назад"
        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="back")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    return message, keyboard


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
    if TEMPLATE_ENGINE_AVAILABLE:
        # Используем новый движок шаблонов
        message = render_final_preview(invoice_data, original_issues, fixed_issues)
        keyboard = kb_confirm()
    else:
        # Старый формат
        supplier = invoice_data.get("supplier", "Unknown")
        date = invoice_data.get("date", "Unknown")
        invoice_number = invoice_data.get("number", "")
        
        # Обрабатываем позиции
        positions = invoice_data.get("positions", [])
        active_positions = [p for p in positions if not p.get("deleted", False)]
        
        fixed_count = len(fixed_issues)
        original_issues_count = len(original_issues)
        remaining_issues = original_issues_count - fixed_count
        
        # Форматируем сообщение
        message = f"✅ *Накладная готова к отправке*\n\n"
        message += f"🏷️ *Supplier:* {supplier}\n"
        message += f"📅 *Date:* {date}{f' №{invoice_number}' if invoice_number else ''}\n\n"
        
        # Добавляем статистику
        message += f"*Всего позиций:* {len(active_positions)}\n"
        
        if fixed_count > 0:
            message += f"✅ *Исправлено:* {fixed_count}\n"
        
        if remaining_issues > 0:
            message += f"⚠️ *Осталось проблем:* {remaining_issues}\n"
        else:
            message += "✅ *Все проблемы решены!*\n"
        
        # Добавляем общую сумму, если она есть
        if "total_sum" in invoice_data:
            total_sum = invoice_data["total_sum"]
            message += f"\n💰 *Общая сумма:* {total_sum:,.2f}\n"
        else:
            # Рассчитываем сумму из позиций
            total_sum = sum(float(p.get("sum", 0)) if p.get("sum") else 0 for p in active_positions)
            message += f"\n💰 *Общая сумма:* {total_sum:,.2f}\n"
        
        # Добавляем инструкцию
        if remaining_issues > 0:
            message += "\n⚠️ _Примечание: Некоторые проблемы остались нерешенными, но вы можете продолжить._"
        
        message += "\n\nНажмите кнопку для отправки накладной в Syrve."
        
        # Создаем клавиатуру
        buttons = [
            [InlineKeyboardButton(text="✅ Подтвердить и отправить", callback_data="inv_ok")],
            [InlineKeyboardButton(text="◀️ Вернуться к правкам", callback_data="back")]
        ]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    return message, keyboard

"""
Улучшенный UI-редактор спорных позиций для Nota V2 (часть 3).

Содержит:
- Обработчики начала просмотра проблем
- Обработчики выбора позиций
- Обработчики пагинации

Отвечает за первый этап взаимодействия с пользователем.
"""

from __future__ import annotations

import structlog
from typing import Any, Dict, List, Optional, Tuple

from aiogram import Router, F
from aiogram.filters import Text
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

# Импортируем из первой части
from app.routers.issue_editor_part1 import (
    TEMPLATE_ENGINE_AVAILABLE, InvoiceEditStates,
    CB_ISSUE_PREFIX, CB_PAGE_PREFIX, LEGACY_ISSUE_PREFIX, LEGACY_PAGE_PREFIX
)

# Импортируем из второй части
from app.routers.issue_editor_part2 import (
    format_issues_list, format_issue_edit
)

logger = structlog.get_logger()

# ───────────────────────── Handlers ───────────────────────────
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
    
    parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
    
    # Отправляем сообщение
    try:
        await c.message.edit_text(message, reply_markup=keyboard, parse_mode=parse_mode)
    except Exception as e:
        logger.error("Failed to edit message", error=str(e))
        await c.message.answer(message, reply_markup=keyboard, parse_mode=parse_mode)
    
    await c.answer()


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
    
    parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
    
    # Отправляем сообщение
    try:
        await c.message.edit_text(message, reply_markup=keyboard, parse_mode=parse_mode)
    except Exception as e:
        logger.error("Failed to edit message", error=str(e))
        await c.message.answer(message, reply_markup=keyboard, parse_mode=parse_mode)
    
    await c.answer()


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
    
    parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
    
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
        
        # Импортируем функцию форматирования списка товаров
        from app.routers.issue_editor_part2 import format_product_select
        message, keyboard = await format_product_select(products, query, page=page)
    
    else:
        await c.answer("❌ Некорректное состояние для пагинации.")
        return
    
    # Отправляем сообщение
    try:
        await c.message.edit_text(message, reply_markup=keyboard, parse_mode=parse_mode)
    except Exception as e:
        logger.error("Failed to edit message", error=str(e))
        await c.message.answer(message, reply_markup=keyboard, parse_mode=parse_mode)
    
    await c.answer()


# Регистрация обработчиков в роутере
def register_handlers(router: Router):
    """
    Регистрирует обработчики в роутере.
    
    :param router: роутер aiogram
    """
    # Обработчик начала просмотра
    router.callback_query.register(
        cb_start_review,
        Text(["inv_edit", "review"])
    )
    
    # Обработчик выбора позиции
    router.callback_query.register(
        cb_select_issue,
        lambda c: c.data and (
            c.data.startswith(CB_ISSUE_PREFIX) or c.data.startswith(LEGACY_ISSUE_PREFIX)
        ),
        state=InvoiceEditStates.issue_list
    )
    
    # Обработчик пагинации
    router.callback_query.register(
        cb_change_page,
        lambda c: c.data and (
            c.data.startswith(CB_PAGE_PREFIX) or c.data.startswith(LEGACY_PAGE_PREFIX)
        )
    )

"""
Улучшенный UI-редактор спорных позиций для Nota V2 (часть 4).

Содержит:
- Обработчики действий с позициями (изменение, удаление)
- Обработчики выбора товаров из списка
- Сохранение изменений в базу данных

Отвечает за основной этап работы с позициями.
"""

from __future__ import annotations

import structlog
from typing import Any, Dict, List, Optional, Tuple

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from sqlalchemy import select

# Импортируем из первой части
from app.routers.issue_editor_part1 import (
    TEMPLATE_ENGINE_AVAILABLE, InvoiceEditStates, SessionLocal,
    CB_ACTION_PREFIX, CB_PRODUCT_PREFIX, LEGACY_ACTION_PREFIX,
    Product, save_product_match, normalize_unit, is_compatible_unit, convert
)

# Импортируем из второй части
from app.routers.issue_editor_part2 import (
    format_issues_list, format_issue_edit, format_final_preview,
    format_product_select
)

logger = structlog.get_logger()

# ───────────────────────── Обработчики действий с позицией ────────────────────────
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
    
    parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
    
    # Обрабатываем разные действия
    if action == "name":
        # Переход к выбору товара
        await state.set_state(InvoiceEditStates.product_select)
        
        # Получаем название для поиска
        name_query = original.get("name", "")[:3]  # Первые 3 символа для поиска
        await state.update_data(search_query=name_query)
        
        # Получаем список товаров по названию
        async with SessionLocal() as session:
            from app.routers.issue_editor_part1 import get_products_by_name
            products = await get_products_by_name(session, name_query)
        
        # Сохраняем список товаров в состоянии
        await state.update_data(products=products, current_page=0)
        
        # Форматируем сообщение для выбора товара
        message, keyboard = await format_product_select(products, name_query, page=0)
        
        # Отправляем сообщение
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode=parse_mode)
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode=parse_mode)
    
    elif action == "qty":
        # Переход к вводу количества
        await state.set_state(InvoiceEditStates.field_input)
        await state.update_data(field="quantity")
        
        # Отправляем сообщение с запросом
        msg = (
            f"Введите новое количество для товара <b>{original.get('name', '')}</b>.\n\n"
            f"Текущее значение: {original.get('quantity', 0)} {original.get('unit', '')}\n\n"
            f"Дробные числа вводите через точку, например: 2.5"
        ) if TEMPLATE_ENGINE_AVAILABLE else (
            f"Введите новое количество для товара *{original.get('name', '')}*.\n\n"
            f"Текущее значение: {original.get('quantity', 0)} {original.get('unit', '')}\n\n"
            f"Дробные числа вводите через точку, например: 2.5"
        )
        
        await c.message.edit_text(msg, parse_mode=parse_mode)
    
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
        
        # Создаем клавиатуру для выбора
        if TEMPLATE_ENGINE_AVAILABLE:
            from app.utils.keyboards import kb_unit_select
            keyboard = kb_unit_select(common_units)
        else:
            buttons = []
            row = []
            
            for i, unit in enumerate(common_units):
                row.append(InlineKeyboardButton(text=unit, callback_data=f"unit_{unit}"))
                
                if (i + 1) % 3 == 0 or i == len(common_units) - 1:
                    buttons.append(row)
                    row = []
            
            buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back")])
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        # Отправляем сообщение
        msg = (
            f"Выберите единицу измерения для товара <b>{original.get('name', '')}</b>.\n\n"
            f"Текущая единица: {original.get('unit', 'не указана')}"
        ) if TEMPLATE_ENGINE_AVAILABLE else (
            f"Выберите единицу измерения для товара *{original.get('name', '')}*.\n\n"
            f"Текущая единица: {original.get('unit', 'не указана')}"
        )
        
        await c.message.edit_text(msg, reply_markup=keyboard, parse_mode=parse_mode)
    
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
                await c.message.edit_text(message, reply_markup=keyboard, parse_mode=parse_mode)
            except Exception as e:
                logger.error("Failed to edit message", error=str(e))
                await c.message.answer(message, reply_markup=keyboard, parse_mode=parse_mode)
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
            msg = (
                f"❌ Невозможно конвертировать: единицы <b>{invoice_unit}</b> и <b>{db_unit}</b> несовместимы."
            ) if TEMPLATE_ENGINE_AVAILABLE else (
                f"❌ Невозможно конвертировать: единицы *{invoice_unit}* и *{db_unit}* несовместимы."
            )
            
            if TEMPLATE_ENGINE_AVAILABLE:
                from app.utils.keyboards import kb_back_only
                keyboard = kb_back_only()
            else:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
                ])
            
            await c.message.edit_text(msg, reply_markup=keyboard, parse_mode=parse_mode)
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
            conv_msg = (
                f"✅ Конвертация выполнена: {quantity} {invoice_unit} → {converted} {db_unit}\n\n" + message
            )
            
            # Отправляем сообщение
            try:
                await c.message.edit_text(conv_msg, reply_markup=keyboard, parse_mode=parse_mode)
            except Exception as e:
                logger.error("Failed to edit message", error=str(e))
                await c.message.answer(conv_msg, reply_markup=keyboard, parse_mode=parse_mode)
        else:
            await c.answer("❌ Ошибка при обновлении позиции.")
    
    elif action == "add_new":
        # Добавление нового товара
        await c.answer("⚠️ Функция добавления нового товара находится в разработке.")
    
    else:
        await c.answer(f"⚠️ Неизвестное действие: {action}")
    
    await c.answer()


# ───────────────────────── Обработчик выбора товара ────────────────────────
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
        current_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
        await state.update_data(current_issues=current_issues)
        
        parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
        
        # Переходим к следующему шагу
        if not current_issues:
            # Если проблем больше нет, переходим к подтверждению
            await state.set_state(InvoiceEditStates.confirm)
            
            message, keyboard = await format_final_preview(
                invoice_data, 
                data.get("issues", []), 
                fixed_issues
            )
        else:
            # Возвращаемся к списку проблем или к редактированию текущей позиции
            # (в зависимости от наличия других проблем с этой позицией)
            unit_issue = positions[position_idx].get("unit_issue", False)
            
            if unit_issue:
                # Если есть проблема с единицей измерения, предлагаем исправить ее
                selected_issue["product"] = product
                await state.update_data(selected_issue=selected_issue)
                await state.set_state(InvoiceEditStates.issue_edit)
                
                message, keyboard = await format_issue_edit(selected_issue)
                message = f"✅ Товар заменен на <b>{product.name}</b>, но есть проблема с единицей измерения.\n\n" + message if TEMPLATE_ENGINE_AVAILABLE else f"✅ Товар заменен на *{product.name}*, но есть проблема с единицей измерения.\n\n" + message
            else:
                # Если нет других проблем, возвращаемся к списку
                await state.set_state(InvoiceEditStates.issue_list)
                
                message, keyboard = await format_issues_list(
                    {"issues": current_issues}, 
                    page=data.get("current_page", 0)
                )
                message = f"✅ Товар заменен на <b>{product.name}</b>\n\n" + message if TEMPLATE_ENGINE_AVAILABLE else f"✅ Товар заменен на *{product.name}*\n\n" + message
        
        # Отправляем сообщение
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode=parse_mode)
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode=parse_mode)
    else:
        await c.answer("❌ Ошибка при обновлении позиции.")
    
    await c.answer()


# Регистрация обработчиков в роутере
def register_handlers(router: Router):
    """
    Регистрирует обработчики в роутере.
    
    :param router: роутер aiogram
    """
    # Обработчик действий с позицией
    router.callback_query.register(
        cb_action_with_item,
        lambda c: c.data and (
            c.data.startswith(CB_ACTION_PREFIX) or c.data.startswith(LEGACY_ACTION_PREFIX)
        ),
        state=InvoiceEditStates.issue_edit
    )
    
    # Обработчик выбора товара
    router.callback_query.register(
        cb_select_product,
        lambda c: c.data and (
            c.data.startswith(CB_PRODUCT_PREFIX) or c.data.startswith("product_")
        ),
        state=InvoiceEditStates.product_select
    )

"""
Улучшенный UI-редактор спорных позиций для Nota V2 (часть 5).

Содержит:
- Обработчики выбора единиц измерения
- Обработчики конвертации 
- Функции возврата и отмены редактирования
- Обработчики текстового ввода

Отвечает за завершающие этапы взаимодействия с пользователем.
"""

from __future__ import annotations

import structlog
from typing import Any, Dict, List, Optional, Tuple

from aiogram import Router, F
from aiogram.filters import Text
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Импортируем из первой части
from app.routers.issue_editor_part1 import (
    TEMPLATE_ENGINE_AVAILABLE, InvoiceEditStates, SessionLocal,
    CB_UNIT_PREFIX, CB_CONVERT_PREFIX, CB_BACK, CB_CONFIRM, CB_SEARCH,
    normalize_unit, is_compatible_unit, convert, get_products_by_name
)

# Импортируем из второй части
from app.routers.issue_editor_part2 import (
    format_issues_list, format_issue_edit, format_final_preview,
    format_product_select
)

logger = structlog.get_logger()

# ───────────────────────── Обработчики единиц измерения ────────────────────────
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
            if TEMPLATE_ENGINE_AVAILABLE:
                from app.utils.keyboards import kb_convert_confirm
                keyboard = kb_convert_confirm()
            else:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Да", callback_data="convert:yes"),
                        InlineKeyboardButton(text="❌ Нет", callback_data="convert:no")
                    ],
                    [
                        InlineKeyboardButton(text="◀️ Назад", callback_data="back")
                    ]
                ])
            
            # Формируем сообщение
            quantity = positions[position_idx].get("quantity", 0)
            parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
            
            msg = (
                f"Единица измерения изменена на <b>{unit}</b>.\n\n"
                f"Товар в базе использует единицу <b>{product.unit}</b>.\n"
                f"Хотите конвертировать количество из {unit} в {product.unit}?\n\n"
                f"Текущее количество: {quantity} {unit}"
            ) if TEMPLATE_ENGINE_AVAILABLE else (
                f"Единица измерения изменена на *{unit}*.\n\n"
                f"Товар в базе использует единицу *{product.unit}*.\n"
                f"Хотите конвертировать количество из {unit} в {product.unit}?\n\n"
                f"Текущее количество: {quantity} {unit}"
            )
            
            await c.message.edit_text(msg, reply_markup=keyboard, parse_mode=parse_mode)
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
        parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
        
        if not current_issues:
            # Если проблем больше нет, переходим к подтверждению
            await state.set_state(InvoiceEditStates.confirm)
            
            message, keyboard = await format_final_preview(
                invoice_data, 
                data.get("issues", []), 
                fixed_issues
            )
        else:
            # Возвращаемся к редактированию текущей позиции или к списку проблем
            # Проверяем, есть ли еще проблемы у этой позиции
            has_other_issues = False
            for issue in current_issues:
                if issue.get("index", 0) - 1 == position_idx:
                    has_other_issues = True
                    selected_issue = issue
                    await state.update_data(selected_issue=issue)
                    break
            
            if has_other_issues:
                # Если есть еще проблемы с этой позицией, продолжаем ее редактирование
                await state.set_state(InvoiceEditStates.issue_edit)
                
                message, keyboard = await format_issue_edit(selected_issue)
                message = f"✅ Единица измерения изменена на <b>{unit}</b>.\n\n" + message if TEMPLATE_ENGINE_AVAILABLE else f"✅ Единица измерения изменена на *{unit}*.\n\n" + message
            else:
                # Если больше нет проблем с этой позицией, возвращаемся к списку
                await state.set_state(InvoiceEditStates.issue_list)
                
                message, keyboard = await format_issues_list(
                    {"issues": current_issues}, 
                    page=data.get("current_page", 0)
                )
                message = f"✅ Единица измерения изменена на <b>{unit}</b>.\n\n" + message if TEMPLATE_ENGINE_AVAILABLE else f"✅ Единица измерения изменена на *{unit}*.\n\n" + message
        
        # Отправляем сообщение
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode=parse_mode)
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode=parse_mode)
    else:
        await c.answer("❌ Ошибка при обновлении единицы измерения.")
    
    await c.answer()


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
                    parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
                    
                    msg = (
                        f"❌ Не удалось конвертировать из <b>{conversion_from}</b> в <b>{conversion_to}</b>.\n"
                        f"Единица измерения изменена, но количество осталось прежним."
                    ) if TEMPLATE_ENGINE_AVAILABLE else (
                        f"❌ Не удалось конвертировать из *{conversion_from}* в *{conversion_to}*.\n"
                        f"Единица измерения изменена, но количество осталось прежним."
                    )
                    
                    if TEMPLATE_ENGINE_AVAILABLE:
                        from app.utils.keyboards import kb_back_only
                        keyboard = kb_back_only()
                    else:
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
                        ])
                    
                    await c.message.edit_text(msg, reply_markup=keyboard, parse_mode=parse_mode)
                    await c.answer()
                    return
            except (ValueError, TypeError):
                # Ошибка при конвертации
                parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
                
                msg = (
                    f"❌ Ошибка при конвертации. Проверьте, что количество задано числом."
                ) if TEMPLATE_ENGINE_AVAILABLE else (
                    f"❌ Ошибка при конвертации. Проверьте, что количество задано числом."
                )
                
                if TEMPLATE_ENGINE_AVAILABLE:
                    from app.utils.keyboards import kb_back_only
                    keyboard = kb_back_only()
                else:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
                    ])
                
                await c.message.edit_text(msg, reply_markup=keyboard, parse_mode=parse_mode)
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
        parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
        
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
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode=parse_mode)
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode=parse_mode)
    else:
        await c.answer("❌ Ошибка при обновлении позиции.")
    
    await c.answer()


# ───────────────────────── Обработчики навигации ────────────────────────
async def cb_back(c: CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки "Назад" - возврат к предыдущему состоянию.
    """
    current_state = await state.get_state()
    data = await state.get_data()
    
    parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
    
    if current_state == InvoiceEditStates.issue_edit.state:
        # Возврат к списку проблем
        await state.set_state(InvoiceEditStates.issue_list)
        
        issues = data.get("current_issues", [])
        
        message, keyboard = await format_issues_list(
            {"issues": issues}, 
            page=data.get("current_page", 0)
        )
        
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode=parse_mode)
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode=parse_mode)
    
    elif current_state == InvoiceEditStates.product_select.state:
        # Возврат к редактированию позиции
        await state.set_state(InvoiceEditStates.issue_edit)
        
        selected_issue = data.get("selected_issue", {})
        
        message, keyboard = await format_issue_edit(selected_issue)
        
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode=parse_mode)
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode=parse_mode)
    
    elif current_state == InvoiceEditStates.field_input.state:
        # Возврат к редактированию позиции
        await state.set_state(InvoiceEditStates.issue_edit)
        
        selected_issue = data.get("selected_issue", {})
        
        message, keyboard = await format_issue_edit(selected_issue)
        
        try:
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode=parse_mode)
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode=parse_mode)
    
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
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode=parse_mode)
        except Exception as e:
            logger.error("Failed to edit message", error=str(e))
            await c.message.answer(message, reply_markup=keyboard, parse_mode=parse_mode)
    
    await c.answer()


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
    
    parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
    
    try:
        await c.message.edit_text(message, reply_markup=keyboard, parse_mode=parse_mode)
    except Exception as e:
        logger.error("Failed to edit message", error=str(e))
        await c.message.answer(message, reply_markup=keyboard, parse_mode=parse_mode)
    
    await c.answer()


# ───────────────────────── Обработчики ввода текста ────────────────────────
async def process_field_input(message: Message, state: FSMContext):
    """
    Обработчик ввода значения для поля (количество, поисковый запрос).
    """
    # Получаем данные из состояния
    data = await state.get_data()
    field = data.get("field", "")
    
    parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
    
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
                
                # Обновляем список проблем
                has_other_issues = False
                for i, issue in enumerate(issues):
                    if i != issue_idx and issue.get("index", 0) - 1 == position_idx:
                        has_other_issues = True
                        selected_issue = issue
                        await state.update_data(selected_issue=issue, selected_issue_idx=i)
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
                    
                    await message.answer(message_text, reply_markup=keyboard, parse_mode=parse_mode)
                elif has_other_issues:
                    # Если есть другие проблемы с этой позицией
                    await state.set_state(InvoiceEditStates.issue_edit)
                    
                    message_text, keyboard = await format_issue_edit(selected_issue)
                    message_text = f"✅ Количество изменено на {quantity}.\n\n" + message_text
                    
                    await message.answer(message_text, reply_markup=keyboard, parse_mode=parse_mode)
                else:
                    # Если есть еще проблемы, возвращаемся к списку
                    await state.set_state(InvoiceEditStates.issue_list)
                    
                    message_text, keyboard = await format_issues_list(
                        {"issues": current_issues}, 
                        page=data.get("current_page", 0)
                    )
                    message_text = f"✅ Количество изменено на {quantity}.\n\n" + message_text
                    
                    await message.answer(message_text, reply_markup=keyboard, parse_mode=parse_mode)
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
        
        await message.answer(message_text, reply_markup=keyboard, parse_mode=parse_mode)


async def cb_search_product(c: CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки поиска товара.
    """
    # Переходим в состояние ввода поискового запроса
    await state.update_data(field="search")
    await state.set_state(InvoiceEditStates.field_input)
    
    parse_mode = "HTML" if TEMPLATE_ENGINE_AVAILABLE else "Markdown"
    
    msg = "🔍 Введите часть названия товара для поиска:"
    
    await c.message.edit_text(msg, parse_mode=parse_mode)
    
    await c.answer()


# Регистрация обработчиков в роутере
def register_handlers(router: Router):
    """
    Регистрирует обработчики в роутере.
    
    :param router: роутер aiogram
    """
    # Обработчик выбора единицы измерения
    router.callback_query.register(
        cb_select_unit,
        lambda c: c.data and (
            c.data.startswith(CB_UNIT_PREFIX) or c.data.startswith("unit_")
        ),
        state=InvoiceEditStates.field_input
    )
    
    # Обработчик конвертации единиц
    router.callback_query.register(
        cb_convert_unit,
        lambda c: c.data and (
            c.data.startswith(CB_CONVERT_PREFIX) or c.data.startswith("convert_")
        )
    )
    
    # Обработчик кнопки "Назад"
    router.callback_query.register(
        cb_back,
        lambda c: c.data and c.data == CB_BACK or c.data == "back"
    )
    
    # Обработчик кнопки "Готово"
    router.callback_query.register(
        cb_done,
        lambda c: c.data and c.data == "done"
    )
    
    # Обработчик кнопки поиска
    router.callback_query.register(
        cb_search_product,
        lambda c: c.data and c.data == CB_SEARCH or c.data == "search",
        state=InvoiceEditStates.product_select
    )
    
    # Обработчик текстового ввода
    router.message.register(
        process_field_input,
        state=InvoiceEditStates.field_input
    )
