"""
UI-редактор спорных позиций для Nota V2.

Модуль отвечает за интерактивное редактирование проблемных
позиций накладной через чат Telegram:
* Выбор проблемных позиций из списка
* Редактирование наименования, количества, единиц измерения
* Удаление позиций
* Добавление новых позиций
* Выбор из списка похожих товаров

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

# Адаптивный импорт Text для разных версий aiogram
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

# Адаптивный импорт функций unit_converter
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

# ───────────────────────── FSM States ────────────────────────
class InvoiceEditStates(StatesGroup):
    """Состояния FSM для редактирования накладной."""
    invoice_preview = State()     # А. Превью накладной
    issue_list = State()          # B. Список проблем
    issue_edit = State()          # C. Редактор строки
    field_input = State()         # D. Ввод значения поля (текст/цифра)
    product_select = State()      # E. Выбор товара из списка
    new_product = State()         # F. Добавление нового товара
    confirm = State()             # G. Финальное подтверждение


# ───────────────────────── Callback Data Prefixes ────────────────────────
# Префиксы для callback-данных (нажатие на кнопки)
CB_ISSUE_PREFIX = "issue_"         # issue_1, issue_2...
CB_ACTION_PREFIX = "action_"       # action_name, action_qty...
CB_PRODUCT_PREFIX = "product_"     # product_123 (id)
CB_PAGE_PREFIX = "page_"           # page_2 (пагинация)
CB_UNIT_PREFIX = "unit_"           # unit_kg, unit_g...
CB_CANCEL = "cancel"
CB_BACK = "back"
CB_DONE = "done"
CB_SEARCH = "search"
CB_ADD_NEW = "add_new"
CB_ADD_POSITION = "add_position"


# ───────────────────────── Helpers ────────────────────────
def make_issue_list_keyboard(issues: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Создает клавиатуру со списком проблемных позиций."""
    keyboard = []
    
    # Для каждой проблемной позиции - отдельная кнопка с эмодзи
    for i, issue in enumerate(issues):
        # Получаем исходные данные
        original = issue.get("original", {})
        item_name = original.get("name", "").split(' ')[0]  # Берем только название без единиц
        item_name = item_name[:15] + "..." if len(item_name) > 15 else item_name
        
        # Определяем эмодзи в зависимости от типа проблемы
        issue_type = issue.get("issue", "Проблема")
        if "Not in database" in issue_type:
            emoji = "🔴"  # Красный для отсутствующих в базе
        elif "incorrect match" in issue_type:
            emoji = "🟡"  # Желтый для возможных ошибок сопоставления
        elif "Unit" in issue_type:
            emoji = "🟠"  # Оранжевый для проблем с единицами измерения
        else:
            emoji = "⚠️"  # Общее предупреждение для остальных проблем
        
        btn_text = f"{i+1}. {emoji} {item_name}"
        keyboard.append([InlineKeyboardButton(
            text=btn_text, 
            callback_data=f"{CB_ISSUE_PREFIX}{i}"
        )])
    
    # Добавляем кнопку для создания новой позиции
    keyboard.append([InlineKeyboardButton(
        text="➕ Добавить позицию", 
        callback_data=CB_ADD_POSITION
    )])
    
    # Кнопки "Готово" и "Отмена"
    keyboard.append([
        InlineKeyboardButton(text="✅ Готово", callback_data=CB_DONE),
        InlineKeyboardButton(text="❌ Отмена", callback_data=CB_CANCEL)
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def make_item_edit_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для редактирования позиции с обновленными иконками."""
    keyboard = [
        # Первый ряд кнопок - основные действия
        [
            InlineKeyboardButton(text="📦 Товар", callback_data=f"{CB_ACTION_PREFIX}name"),
            InlineKeyboardButton(text="🔢 Кол-во", callback_data=f"{CB_ACTION_PREFIX}qty"),
            InlineKeyboardButton(text="📏 Ед.изм", callback_data=f"{CB_ACTION_PREFIX}unit"),
        ],
        # Второй ряд - удаление и возврат
        [
            InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"{CB_ACTION_PREFIX}delete"),
            InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def make_product_select_keyboard(
    products: List[Tuple], 
    page: int = 0, 
    page_size: int = 5
) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора товара с пагинацией."""
    keyboard = []
    
    # Определяем диапазон для текущей страницы
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(products))
    
    # Добавляем кнопки для товаров текущей страницы
    for i in range(start_idx, end_idx):
        product_id, name, unit = products[i]
        # Ограничиваем длину имени для кнопки
        display_name = f"{name} ({unit})"
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."
            
        keyboard.append([InlineKeyboardButton(
            text=display_name,
            callback_data=f"{CB_PRODUCT_PREFIX}{product_id}"
        )])
    
    # Добавляем кнопки пагинации, если нужно
    pagination_buttons = []
    
    # Кнопка "Предыдущая страница"
    if page > 0:
        pagination_buttons.append(InlineKeyboardButton(
            text="◀️ Пред.", 
            callback_data=f"{CB_PAGE_PREFIX}{page-1}"
        ))
    
    # Кнопка "Следующая страница"
    if end_idx < len(products):
        pagination_buttons.append(InlineKeyboardButton(
            text="След. ▶️", 
            callback_data=f"{CB_PAGE_PREFIX}{page+1}"
        ))
    
    if pagination_buttons:
        keyboard.append(pagination_buttons)
    
    # Добавляем кнопки поиска и добавления нового товара
    keyboard.append([
        InlineKeyboardButton(text="🔍 Поиск", callback_data=CB_SEARCH),
        InlineKeyboardButton(text="➕ Новый товар", callback_data=CB_ADD_NEW)
    ])
    
    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def make_unit_select_keyboard(units: List[str]) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора единицы измерения."""
    keyboard = []
    
    # Размещаем кнопки по 3 в ряд
    row = []
    for i, unit in enumerate(units):
        row.append(InlineKeyboardButton(
            text=unit,
            callback_data=f"{CB_UNIT_PREFIX}{unit}"
        ))
        
        if (i + 1) % 3 == 0 or i == len(units) - 1:
            keyboard.append(row)
            row = []
    
    # Добавляем кнопку "Назад"
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def make_confirm_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для финального подтверждения с обновленными кнопками."""
    keyboard = [
        [InlineKeyboardButton(text="✅ Подтвердить и отправить", callback_data="inv_ok")],
        [InlineKeyboardButton(text="◀️ Вернуться к правкам", callback_data=CB_BACK)]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def get_products_by_name(
    session: AsyncSession, 
    name_query: str, 
    limit: int = 20
) -> List[Tuple]:
    """
    Ищет товары по части имени.
    
    Возвращает: список кортежей (id, name, unit)
    """
    stmt = (
        select(Product.id, Product.name, Product.unit)
        .where(func.lower(Product.name).like(f"%{name_query.lower()}%"))
        .order_by(Product.name)
        .limit(limit)
    )
    
    result = await session.execute(stmt)
    return result.all()


async def format_issue_for_edit(issue: Dict[str, Any]) -> str:
    """
    Форматирует информацию о проблемной позиции для редактирования.
    """
    original = issue.get("original", {})
    
    name = original.get("name", "Неизвестный товар")
    quantity = original.get("quantity", 0)
    unit = original.get("unit", "")
    price = original.get("price", 0)
    sum_val = original.get("sum", 0)
    
    # Тип проблемы
    issue_type = issue.get("issue", "Неизвестная проблема")
    
    # Определяем эмодзи в зависимости от типа проблемы
    if "Not in database" in issue_type:
        emoji = "🔴"
        issue_description = "Товар не найден в базе"
    elif "incorrect match" in issue_type:
        emoji = "🟡"
        issue_description = "Возможно неверное сопоставление"
    elif "Unit" in issue_type:
        emoji = "🟠"
        issue_description = "Несоответствие единиц измерения"
    else:
        emoji = "⚠️"
        issue_description = issue_type
    
    # Форматируем детали позиции
    formatted = f"{emoji} *Редактирование позиции*\n\n"
    formatted += f"*Наименование:* {name}\n"
    formatted += f"*Количество:* {quantity} {unit}\n"
    
    if price:
        formatted += f"*Цена:* {price:,.2f}\n"
    
    if sum_val:
        formatted += f"*Сумма:* {sum_val:,.2f}\n"
    
    # Добавляем информацию о проблеме
    formatted += f"\n*Проблема:* {issue_description}\n"
    
    # Если есть информация о товаре в базе, добавляем ее
    if product := issue.get("product"):
        formatted += f"\n*В базе данных:*\n"
        formatted += f"*→ Наименование:* {product.name}\n"
        formatted += f"*→ Единица измерения:* {product.unit}\n"
    
    # Добавляем инструкцию по действиям
    formatted += f"\nВыберите действие для исправления проблемы:"
    
    return formatted


# Функция для форматирования финального вида накладной с использованием нового markdown модуля
async def format_final_invoice(
    invoice_data: Dict[str, Any], 
    original_issues: List[Dict[str, Any]],
    fixed_issues: Dict[int, Dict[str, Any]]
) -> str:
    """
    Форматирует финальный вид накладной с использованием улучшенного markdown.
    
    Интегрирует функцию make_final_preview из utils.markdown для создания красивой сводки.
    """
    try:
        from app.utils.markdown import make_final_preview
        # Используем новую функцию форматирования
        return make_final_preview(invoice_data, original_issues, fixed_issues)
    except ImportError:
        # Если модуль недоступен, используем старый формат
        result = f"📄 *Supplier:* \"{invoice_data.get('supplier', 'Unknown')}\"  \n"
        result += f"🗓️ *Date:* {invoice_data.get('date', 'Unknown')}"
        
        if invoice_number := invoice_data.get('number'):
            result += f"  № {invoice_number}"
        
        result += "\n\n"
        
        # Собираем все позиции с отметками об исправлениях
        positions = invoice_data.get("positions", [])
        total_sum = 0
        fixed_count = len(fixed_issues)
        
        result += f"📋 *Позиции ({len(positions)} шт.):*\n"
        
        for i, pos in enumerate(positions):
            # Пропускаем удаленные позиции
            if pos.get("deleted", False):
                continue
                
            # Проверяем, была ли позиция в списке проблемных
            is_issue = any(i == issue.get("index", 0) - 1 for issue in original_issues)
            was_fixed = i in fixed_issues
            
            name = pos.get("name", "")
            quantity = pos.get("quantity", 0)
            unit = pos.get("unit", "")
            price = pos.get("price", 0)
            sum_val = pos.get("sum", 0) if pos.get("sum") else (price * float(quantity) if price else 0)
            
            # Добавляем соответствующую отметку
            if was_fixed:
                prefix = "✅ "  # Исправлено
            elif is_issue:
                prefix = "⚠️ "  # Проблема не исправлена
            else:
                prefix = "• "   # Обычная позиция
            
            # Форматируем строку позиции
            pos_str = f"{prefix}{name}, {quantity} {unit}"
            if price:
                pos_str += f" по {price:,.2f}"
            if sum_val:
                pos_str += f" = {sum_val:,.2f}"
            
            result += f"{pos_str}\n"
            
            # Увеличиваем общую сумму
            try:
                total_sum += float(sum_val)
            except (ValueError, TypeError):
                pass
        
        # Добавляем итоговую сумму
        result += f"\n💰 *Итоговая сумма:* {total_sum:,.2f}\n"
        
        # Добавляем статистику по исправлениям
        if fixed_count > 0:
            result += f"\n✅ Исправлено позиций: {fixed_count}"
        
        remaining_issues = len(original_issues) - fixed_count
        if remaining_issues > 0:
            result += f"\n⚠️ Осталось проблем: {remaining_issues}"
        
        return result

# Дополнение файла issue_editor.py - обработчики событий

# ───────────────────────── handlers ─────────────────────────
router = Router(name="issue_editor")

@router.callback_query(Text("inv_edit"))
async def cb_start_fix(c: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Fix Issues' - начало процесса редактирования."""
    # Получаем данные из состояния
    data = await state.get_data()
    invoice = data.get("invoice", {})
    issues = data.get("issues", [])
    
    if not issues:
        await c.message.answer("❌ Нет проблемных позиций для исправления.")
        await c.answer()
        return
    
    # Обновляем состояние
    await state.update_data(current_issues=issues, fixed_issues={})
    await state.set_state(InvoiceEditStates.issue_list)
    
    # Пытаемся использовать новый формат отображения списка проблем
    try:
        from app.utils.markdown import make_issue_list
        message = make_issue_list(issues)
    except ImportError:
        # Используем старый формат при отсутствии модуля
        message = "Выберите позицию для исправления:\n\n"
        for i, issue in enumerate(issues):
            original = issue.get("original", {})
            name = original.get("name", "Позиция")
            quantity = original.get("quantity", 0)
            unit = original.get("unit", "")
            
            issue_type = issue.get("issue", "Проблема")
            
            message += f"{i+1}. *{name}*, {quantity} {unit} - {issue_type}\n"
    
    keyboard = make_issue_list_keyboard(issues)
    
    # Отправляем сообщение с клавиатурой
    await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
    await c.answer()


# ───────────────────────── Выбор проблемной позиции ────────────────────────
@router.callback_query(lambda c: c.data.startswith(CB_ISSUE_PREFIX), InvoiceEditStates.issue_list)
async def cb_select_issue(c: CallbackQuery, state: FSMContext):
    """Обработчик выбора проблемной позиции из списка."""
    issue_idx = int(c.data[len(CB_ISSUE_PREFIX):])
    
    # Получаем данные из состояния
    data = await state.get_data()
    issues = data.get("current_issues", [])
    
    if issue_idx >= len(issues):
        await c.answer("❌ Позиция не найдена.")
        return
    
    selected_issue = issues[issue_idx]
    
    # Сохраняем выбранную позицию в состоянии
    await state.update_data(selected_issue=selected_issue, selected_issue_idx=issue_idx)
    await state.set_state(InvoiceEditStates.issue_edit)
    
    # Форматируем сообщение с деталями позиции
    message = await format_issue_for_edit(selected_issue)
    
    # Отправляем сообщение с клавиатурой для редактирования
    keyboard = make_item_edit_keyboard()
    await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
    await c.answer()


# ───────────────────────── Действия с позицией ────────────────────────
@router.callback_query(lambda c: c.data.startswith(CB_ACTION_PREFIX), InvoiceEditStates.issue_edit)
async def cb_action_with_item(c: CallbackQuery, state: FSMContext):
    """Обработчик выбора действия с позицией (изменение товара, количества и т.д.)."""
    action = c.data[len(CB_ACTION_PREFIX):]
    
    # Получаем данные из состояния
    data = await state.get_data()
    selected_issue = data.get("selected_issue", {})
    original = selected_issue.get("original", {})
    
    # Обрабатываем разные действия
    if action == "name":
        # Переход к выбору товара
        await state.set_state(InvoiceEditStates.product_select)
        
        # Получаем список товаров по первым буквам имени
        name_query = original.get("name", "")[:3]  # Берем первые 3 символа для поиска
        
        async with SessionLocal() as session:
            products = await get_products_by_name(session, name_query)
        
        # Сохраняем список товаров в состоянии
        await state.update_data(products=products, current_page=0)
        
        # Отправляем сообщение с клавиатурой выбора товара
        keyboard = make_product_select_keyboard(products)
        await c.message.edit_text(
            f"Выберите товар для позиции *{original.get('name', '')}*:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    elif action == "qty":
        # Переход к вводу количества
        await state.set_state(InvoiceEditStates.field_input)
        await state.update_data(field="quantity")
        
        # Отправляем сообщение с запросом ввода количества
        await c.message.edit_text(
            f"Введите новое количество для *{original.get('name', '')}*.\n"
            f"Текущее значение: {original.get('quantity', 0)} {original.get('unit', '')}\n\n"
            f"Дробные числа вводите через точку, например: 2.5",
            parse_mode="Markdown"
        )
    
    elif action == "unit":
        # Переход к выбору единицы измерения
        await state.set_state(InvoiceEditStates.field_input)
        await state.update_data(field="unit")
        
        # Подготавливаем список доступных единиц измерения
        common_units = ["kg", "g", "l", "ml", "pcs", "pack", "box"]
        
        # Если есть связанный товар, добавляем его единицу в начало списка
        product = selected_issue.get("product")
        if product and product.unit:
            if product.unit not in common_units:
                common_units.insert(0, product.unit)
        
        # Создаем клавиатуру для выбора единицы измерения
        keyboard = make_unit_select_keyboard(common_units)
        
        await c.message.edit_text(
            f"Выберите единицу измерения для *{original.get('name', '')}*.\n"
            f"Текущая единица: {original.get('unit', 'не указана')}\n",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    elif action == "delete":
        # Помечаем позицию как удаленную
        invoice_data = data.get("invoice", {})
        positions = invoice_data.get("positions", [])
        
        issue_idx = data.get("selected_issue_idx", 0)
        issues = data.get("current_issues", [])
        
        # Находим индекс позиции в общем списке позиций
        position_idx = issues[issue_idx].get("index", 0) - 1
        
        if 0 <= position_idx < len(positions):
            # Помечаем позицию как удаленную
            positions[position_idx]["deleted"] = True
            
            # Обновляем данные в состоянии
            invoice_data["positions"] = positions
            await state.update_data(invoice=invoice_data)
            
            # Добавляем в список исправленных позиций
            fixed_issues = data.get("fixed_issues", {})
            fixed_issues[position_idx] = {"action": "delete"}
            await state.update_data(fixed_issues=fixed_issues)
            
            # Возвращаемся к списку проблем
            await state.set_state(InvoiceEditStates.issue_list)
            
            # Обновляем список проблем (удаляем решенную)
            current_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
            await state.update_data(current_issues=current_issues)
            
            # Если проблем больше нет, переходим к подтверждению
            if not current_issues:
                await state.set_state(InvoiceEditStates.confirm)
                
                # Формируем сообщение с итоговым списком
                message = await format_final_invoice(
                    invoice_data, 
                    data.get("issues", []),
                    fixed_issues
                )
                
                keyboard = make_confirm_keyboard()
                await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
            else:
                # Показываем обновленный список проблем
                try:
                    from app.utils.markdown import make_issue_list
                    message = make_issue_list(current_issues)
                except ImportError:
                    message = "Позиция удалена. Выберите следующую позицию для исправления:\n\n"
                    for i, issue in enumerate(current_issues):
                        original = issue.get("original", {})
                        name = original.get("name", "Позиция")
                        quantity = original.get("quantity", 0)
                        unit = original.get("unit", "")
                        
                        issue_type = issue.get("issue", "Проблема")
                        
                        message += f"{i+1}. *{name}*, {quantity} {unit} - {issue_type}\n"
                
                keyboard = make_issue_list_keyboard(current_issues)
                await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await c.answer("❌ Ошибка при удалении позиции.")
    
    await c.answer()


# ───────────────────────── Выбор товара из списка ────────────────────────
@router.callback_query(lambda c: c.data.startswith(CB_PRODUCT_PREFIX), InvoiceEditStates.product_select)
async def cb_select_product(c: CallbackQuery, state: FSMContext):
    """Обработчик выбора товара из списка."""
    product_id = int(c.data[len(CB_PRODUCT_PREFIX):])
    
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
    
    # Находим позицию в списке позиций накладной
    issue_idx = data.get("selected_issue_idx", 0)
    issues = data.get("current_issues", [])
    
    position_idx = issues[issue_idx].get("index", 0) - 1
    
    if 0 <= position_idx < len(positions):
        # Обновляем позицию
        positions[position_idx]["match_id"] = product.id
        positions[position_idx]["match_name"] = product.name
        positions[position_idx]["confidence"] = 1.0  # Ручной выбор - 100% уверенность
        
        # Проверяем совместимость единиц измерения
        original_unit = positions[position_idx].get("unit", "")
        if original_unit and not is_compatible_unit(original_unit, product.unit):
            # Если единицы несовместимы, предлагаем обновить
            positions[position_idx]["unit_issue"] = True
            positions[position_idx]["product_unit"] = product.unit
        
        # Обновляем данные в состоянии
        invoice_data["positions"] = positions
        await state.update_data(invoice=invoice_data)
        
        # Добавляем в список исправленных позиций
        fixed_issues = data.get("fixed_issues", {})
        fixed_issues[position_idx] = {
            "action": "replace_product",
            "product_id": product.id,
            "product_name": product.name
        }
        await state.update_data(fixed_issues=fixed_issues)
        
        # Возвращаемся к списку проблем
        await state.set_state(InvoiceEditStates.issue_list)
        
        # Обновляем список проблем (удаляем решенную)
        current_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
        await state.update_data(current_issues=current_issues)
        
        # Если проблем больше нет, переходим к подтверждению
        if not current_issues:
            await state.set_state(InvoiceEditStates.confirm)
            
            # Формируем сообщение с итоговым списком
            message = await format_final_invoice(
                invoice_data, 
                data.get("issues", []),
                fixed_issues
            )
            
            keyboard = make_confirm_keyboard()
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
        else:
            # Показываем обновленный список проблем
            try:
                from app.utils.markdown import make_issue_list
                message = f"✅ Товар заменен на *{product.name}*.\n\n" + make_issue_list(current_issues)
            except ImportError:
                message = f"✅ Товар заменен на *{product.name}*. Выберите следующую позицию:\n\n"
                for i, issue in enumerate(current_issues):
                    original = issue.get("original", {})
                    name = original.get("name", "Позиция")
                    quantity = original.get("quantity", 0)
                    unit = original.get("unit", "")
                    
                    issue_type = issue.get("issue", "Проблема")
                    
                    message += f"{i+1}. *{name}*, {quantity} {unit} - {issue_type}\n"
            
            keyboard = make_issue_list_keyboard(current_issues)
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await c.answer("❌ Ошибка при обновлении позиции.")
    
    await c.answer()


# ───────────────────────── Пагинация в списке товаров ────────────────────────
@router.callback_query(lambda c: c.data.startswith(CB_PAGE_PREFIX), InvoiceEditStates.product_select)
async def cb_change_page(c: CallbackQuery, state: FSMContext):
    """Обработчик пагинации в списке товаров."""
    page = int(c.data[len(CB_PAGE_PREFIX):])
    
    # Получаем данные из состояния
    data = await state.get_data()
    products = data.get("products", [])
    
    # Обновляем текущую страницу
    await state.update_data(current_page=page)
    
    # Создаем клавиатуру для текущей страницы
    keyboard = make_product_select_keyboard(products, page)
    
    selected_issue = data.get("selected_issue", {})
    original = selected_issue.get("original", {})
    
    await c.message.edit_text(
        f"Выберите товар для позиции *{original.get('name', '')}* (стр. {page+1}):",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    await c.answer()


# ───────────────────────── Поиск товара по названию ────────────────────────
@router.callback_query(Text(CB_SEARCH), InvoiceEditStates.product_select)
async def cb_search_product(c: CallbackQuery, state: FSMContext):
    """Обработчик кнопки поиска товара."""
    # Переходим в состояние ввода поискового запроса
    await state.update_data(field="search")
    await state.set_state(InvoiceEditStates.field_input)
    
    await c.message.edit_text(
        "🔍 Введите часть названия товара для поиска:",
        parse_mode="Markdown"
    )
    
    await c.answer()


# ───────────────────────── Выбор единицы измерения ────────────────────────
@router.callback_query(lambda c: c.data.startswith(CB_UNIT_PREFIX), InvoiceEditStates.field_input)
async def cb_select_unit(c: CallbackQuery, state: FSMContext):
    """Обработчик выбора единицы измерения."""
    unit = c.data[len(CB_UNIT_PREFIX):]
    
    # Получаем данные из состояния
    data = await state.get_data()
    selected_issue = data.get("selected_issue", {})
    invoice_data = data.get("invoice", {})
    positions = invoice_data.get("positions", [])
    
    # Находим позицию в списке позиций накладной
    issue_idx = data.get("selected_issue_idx", 0)
    issues = data.get("current_issues", [])
    
    position_idx = issues[issue_idx].get("index", 0) - 1
    
    if 0 <= position_idx < len(positions):
        # Старая единица измерения
        old_unit = positions[position_idx].get("unit", "")
        
        # Обновляем единицу измерения
        positions[position_idx]["unit"] = unit
        
        # Проверяем необходимость конвертации количества
        product = selected_issue.get("product")
        if product and is_compatible_unit(unit, product.unit) and unit != product.unit:
            # Запрашиваем пользователя о конвертации
            await state.update_data(
                conversion_from=unit,
                conversion_to=product.unit,
                position_idx=position_idx
            )
            
            # Просим подтвердить конвертацию
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да", callback_data="convert_yes"),
                    InlineKeyboardButton(text="❌ Нет", callback_data="convert_no")
                ]
            ])
            
            quantity = positions[position_idx].get("quantity", 0)
            
            await c.message.edit_text(
                f"Единица измерения изменена на *{unit}*.\n\n"
                f"Товар в базе использует единицу *{product.unit}*.\n"
                f"Хотите конвертировать количество из {unit} в {product.unit}?\n\n"
                f"Текущее количество: {quantity} {unit}",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            await c.answer()
            return
        
        # Обновляем данные в состоянии
        invoice_data["positions"] = positions
        await state.update_data(invoice=invoice_data)
        
        # Добавляем в список исправленных позиций
        fixed_issues = data.get("fixed_issues", {})
        fixed_issues[position_idx] = {
            "action": "change_unit",
            "old_unit": old_unit,
            "new_unit": unit
        }
        await state.update_data(fixed_issues=fixed_issues)
        
        # Возвращаемся к списку проблем
        await state.set_state(InvoiceEditStates.issue_list)
        
        # Обновляем список проблем (удаляем решенную)
        current_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
        await state.update_data(current_issues=current_issues)
        
        # Если проблем больше нет, переходим к подтверждению
        if not current_issues:
            await state.set_state(InvoiceEditStates.confirm)
            
            # Формируем сообщение с итоговым списком
            message = await format_final_invoice(
                invoice_data, 
                data.get("issues", []),
                fixed_issues
            )
            
            keyboard = make_confirm_keyboard()
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
        else:
            # Показываем обновленный список проблем
            try:
                from app.utils.markdown import make_issue_list
                message = f"✅ Единица измерения изменена на *{unit}*.\n\n" + make_issue_list(current_issues)
            except ImportError:
                message = f"✅ Единица измерения изменена на *{unit}*. Выберите следующую позицию:\n\n"
                for i, issue in enumerate(current_issues):
                    original = issue.get("original", {})
                    name = original.get("name", "Позиция")
                    quantity = original.get("quantity", 0)
                    unit = original.get("unit", "")
                    
                    issue_type = issue.get("issue", "Проблема")
                    
                    message += f"{i+1}. *{name}*, {quantity} {unit} - {issue_type}\n"
            
            keyboard = make_issue_list_keyboard(current_issues)
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await c.answer("❌ Ошибка при обновлении единицы измерения.")
    
    await c.answer()

# ───────────────────────── Конвертация единиц измерения ────────────────────────
@router.callback_query(Text("convert_yes"))
async def cb_convert_yes(c: CallbackQuery, state: FSMContext):
    """Обработчик подтверждения конвертации единиц измерения."""
    # Получаем данные из состояния
    data = await state.get_data()
    invoice_data = data.get("invoice", {})
    positions = invoice_data.get("positions", [])
    
    conversion_from = data.get("conversion_from", "")
    conversion_to = data.get("conversion_to", "")
    position_idx = data.get("position_idx", -1)
    
    if 0 <= position_idx < len(positions):
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
                
                # Обновляем данные в состоянии
                invoice_data["positions"] = positions
                await state.update_data(invoice=invoice_data)
                
                # Добавляем в список исправленных позиций
                fixed_issues = data.get("fixed_issues", {})
                fixed_issues[position_idx] = {
                    "action": "convert_unit",
                    "from_unit": conversion_from,
                    "to_unit": conversion_to,
                    "old_quantity": quantity,
                    "new_quantity": converted
                }
                await state.update_data(fixed_issues=fixed_issues)
                
                # Возвращаемся к списку проблем
                await state.set_state(InvoiceEditStates.issue_list)
                
                # Обновляем список проблем (удаляем решенную)
                issues = data.get("current_issues", [])
                issue_idx = data.get("selected_issue_idx", 0)
                current_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
                await state.update_data(current_issues=current_issues)
                
                # Если проблем больше нет, переходим к подтверждению
                if not current_issues:
                    await state.set_state(InvoiceEditStates.confirm)
                    
                    # Формируем сообщение с итоговым списком
                    message = await format_final_invoice(
                        invoice_data, 
                        data.get("issues", []),
                        fixed_issues
                    )
                    
                    keyboard = make_confirm_keyboard()
                    await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
                else:
                    # Показываем обновленный список проблем
                    try:
                        from app.utils.markdown import make_issue_list
                        message = (
                            f"✅ Конвертировано: {quantity} {conversion_from} → "
                            f"{converted} {conversion_to}.\n\n" + make_issue_list(current_issues)
                        )
                    except ImportError:
                        message = (
                            f"✅ Конвертировано: {quantity} {conversion_from} → "
                            f"{converted} {conversion_to}. Выберите следующую позицию:\n\n"
                        )
                        for i, issue in enumerate(current_issues):
                            original = issue.get("original", {})
                            name = original.get("name", "Позиция")
                            quantity = original.get("quantity", 0)
                            unit = original.get("unit", "")
                            
                            issue_type = issue.get("issue", "Проблема")
                            
                            message += f"{i+1}. *{name}*, {quantity} {unit} - {issue_type}\n"
                    
                    keyboard = make_issue_list_keyboard(current_issues)
                    await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
            else:
                # Если конвертация невозможна
                await c.message.edit_text(
                    f"❌ Не удалось конвертировать из {conversion_from} в {conversion_to}.\n"
                    f"Вернитесь к списку проблем и попробуйте исправить вручную.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)]
                    ]),
                    parse_mode="Markdown"
                )
        except (ValueError, TypeError):
            await c.message.edit_text(
                "❌ Ошибка при конвертации. Проверьте, что количество задано числом.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)]
                ]),
                parse_mode="Markdown"
            )
    else:
        await c.answer("❌ Ошибка при обновлении позиции.")
    
    await c.answer()


@router.callback_query(Text("convert_no"))
async def cb_convert_no(c: CallbackQuery, state: FSMContext):
    """Обработчик отказа от конвертации единиц измерения."""
    # Получаем данные из состояния
    data = await state.get_data()
    invoice_data = data.get("invoice", {})
    positions = invoice_data.get("positions", [])
    
    conversion_to = data.get("conversion_to", "")
    position_idx = data.get("position_idx", -1)
    
    if 0 <= position_idx < len(positions):
        # Обновляем только единицу измерения, без конвертации количества
        old_unit = positions[position_idx].get("unit", "")
        positions[position_idx]["unit"] = conversion_to
        
        # Обновляем данные в состоянии
        invoice_data["positions"] = positions
        await state.update_data(invoice=invoice_data)
        
        # Добавляем в список исправленных позиций
        fixed_issues = data.get("fixed_issues", {})
        fixed_issues[position_idx] = {
            "action": "change_unit",
            "old_unit": old_unit,
            "new_unit": conversion_to
        }
        await state.update_data(fixed_issues=fixed_issues)
        
        # Возвращаемся к списку проблем
        await state.set_state(InvoiceEditStates.issue_list)
        
        # Обновляем список проблем (удаляем решенную)
        issues = data.get("current_issues", [])
        issue_idx = data.get("selected_issue_idx", 0)
        current_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
        await state.update_data(current_issues=current_issues)
        
        # Если проблем больше нет, переходим к подтверждению
        if not current_issues:
            await state.set_state(InvoiceEditStates.confirm)
            
            # Формируем сообщение с итоговым списком
            message = await format_final_invoice(
                invoice_data, 
                data.get("issues", []),
                fixed_issues
            )
            
            keyboard = make_confirm_keyboard()
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
        else:
            # Показываем обновленный список проблем
            try:
                from app.utils.markdown import make_issue_list
                message = f"✅ Единица измерения изменена на *{conversion_to}* (без конвертации количества).\n\n" + make_issue_list(current_issues)
            except ImportError:
                message = f"✅ Единица измерения изменена на *{conversion_to}* (без конвертации количества). Выберите следующую позицию:\n\n"
                for i, issue in enumerate(current_issues):
                    original = issue.get("original", {})
                    name = original.get("name", "Позиция")
                    quantity = original.get("quantity", 0)
                    unit = original.get("unit", "")
                    
                    issue_type = issue.get("issue", "Проблема")
                    
                    message += f"{i+1}. *{name}*, {quantity} {unit} - {issue_type}\n"
            
            keyboard = make_issue_list_keyboard(current_issues)
            await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await c.answer("❌ Ошибка при обновлении позиции.")
    
    await c.answer()


# ───────────────────────── Обработка текстового ввода ────────────────────────
@router.message(InvoiceEditStates.field_input)
async def process_field_input(message: Message, state: FSMContext):
    """Обработчик ввода значения для поля (количество, поисковый запрос)."""
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
            
            position_idx = issues[issue_idx].get("index", 0) - 1
            
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
                fixed_issues[position_idx] = {
                    "action": "change_quantity",
                    "old_quantity": old_quantity,
                    "new_quantity": quantity
                }
                await state.update_data(fixed_issues=fixed_issues)
                
                # Удаляем сообщение пользователя (чтобы не засорять чат)
                await message.delete()
                
                # Возвращаемся к списку проблем
                await state.set_state(InvoiceEditStates.issue_list)
                
                # Обновляем список проблем (удаляем решенную)
                current_issues = [issue for i, issue in enumerate(issues) if i != issue_idx]
                await state.update_data(current_issues=current_issues)
                
                # Если проблем больше нет, переходим к подтверждению
                if not current_issues:
                    await state.set_state(InvoiceEditStates.confirm)
                    
                    # Формируем сообщение с итоговым списком
                    final_message = await format_final_invoice(
                        invoice_data, 
                        data.get("issues", []),
                        fixed_issues
                    )
                    
                    keyboard = make_confirm_keyboard()
                    await message.answer(final_message, reply_markup=keyboard, parse_mode="Markdown")
                else:
                    # Показываем обновленный список проблем
                    try:
                        from app.utils.markdown import make_issue_list
                        update_message = f"✅ Количество изменено на *{quantity}*.\n\n" + make_issue_list(current_issues)
                    except ImportError:
                        update_message = f"✅ Количество изменено на *{quantity}*. Выберите следующую позицию:\n\n"
                        for i, issue in enumerate(current_issues):
                            original = issue.get("original", {})
                            name = original.get("name", "Позиция")
                            quantity = original.get("quantity", 0)
                            unit = original.get("unit", "")
                            
                            issue_type = issue.get("issue", "Проблема")
                            
                            update_message += f"{i+1}. *{name}*, {quantity} {unit} - {issue_type}\n"
                    
                    keyboard = make_issue_list_keyboard(current_issues)
                    await message.answer(update_message, reply_markup=keyboard, parse_mode="Markdown")
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
        await message.delete()
        
        # Возвращаемся к выбору товара
        await state.set_state(InvoiceEditStates.product_select)
        
        # Сохраняем список товаров в состоянии
        await state.update_data(products=products, current_page=0)
        
        if products:
            # Отправляем сообщение с клавиатурой выбора товара
            keyboard = make_product_select_keyboard(products)
            await message.answer(
                f"🔍 Результаты поиска по запросу *{search_query}* ({len(products)} товаров):",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            # Если ничего не найдено
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Новый поиск", callback_data=CB_SEARCH)],
                [InlineKeyboardButton(text="➕ Новый товар", callback_data=CB_ADD_NEW)],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)]
            ])
            
            await message.answer(
                f"🔍 По запросу *{search_query}* ничего не найдено.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )


# ───────────────────────── Кнопка "Назад" ────────────────────────
@router.callback_query(Text(CB_BACK))
async def cb_back(c: CallbackQuery, state: FSMContext):
    """Обработчик кнопки "Назад" - возврат к предыдущему состоянию."""
    current_state = await state.get_state()
    
    if current_state == InvoiceEditStates.issue_edit.state:
        # Возврат к списку проблем
        await state.set_state(InvoiceEditStates.issue_list)
        
        # Получаем данные из состояния
        data = await state.get_data()
        issues = data.get("current_issues", [])
        
        # Показываем список проблемных позиций
        try:
            from app.utils.markdown import make_issue_list
            message = make_issue_list(issues)
        except ImportError:
            message = "Выберите позицию для исправления:\n\n"
            for i, issue in enumerate(issues):
                original = issue.get("original", {})
                name = original.get("name", "Позиция")
                quantity = original.get("quantity", 0)
                unit = original.get("unit", "")
                
                issue_type = issue.get("issue", "Проблема")
                
                message += f"{i+1}. *{name}*, {quantity} {unit} - {issue_type}\n"
        
        keyboard = make_issue_list_keyboard(issues)
        await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
    
    elif current_state == InvoiceEditStates.product_select.state:
        # Возврат к редактированию позиции
        await state.set_state(InvoiceEditStates.issue_edit)
        
        # Получаем данные из состояния
        data = await state.get_data()
        selected_issue = data.get("selected_issue", {})
        
        # Форматируем сообщение с деталями позиции
        message = await format_issue_for_edit(selected_issue)
        
        # Отправляем сообщение с клавиатурой для редактирования
        keyboard = make_item_edit_keyboard()
        await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
    
    elif current_state == InvoiceEditStates.field_input.state:
        # Возврат к редактированию позиции
        await state.set_state(InvoiceEditStates.issue_edit)
        
        # Получаем данные из состояния
        data = await state.get_data()
        selected_issue = data.get("selected_issue", {})
        
        # Форматируем сообщение с деталями позиции
        message = await format_issue_for_edit(selected_issue)
        
        # Отправляем сообщение с клавиатурой для редактирования
        keyboard = make_item_edit_keyboard()
        await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
    
    elif current_state == InvoiceEditStates.confirm.state:
        # Возврат к списку проблем
        await state.set_state(InvoiceEditStates.issue_list)
        
        # Получаем данные из состояния
        data = await state.get_data()
        issues = data.get("current_issues", [])
        
        # Если список пуст, берем оригинальный список проблем
        if not issues:
            issues = data.get("issues", [])
            await state.update_data(current_issues=issues)
        
        # Показываем список проблемных позиций
        try:
            from app.utils.markdown import make_issue_list
            message = make_issue_list(issues)
        except ImportError:
            message = "Выберите позицию для исправления:\n\n"
            for i, issue in enumerate(issues):
                original = issue.get("original", {})
                name = original.get("name", "Позиция")
                quantity = original.get("quantity", 0)
                unit = original.get("unit", "")
                
                issue_type = issue.get("issue", "Проблема")
                
                message += f"{i+1}. *{name}*, {quantity} {unit} - {issue_type}\n"
        
        keyboard = make_issue_list_keyboard(issues)
        await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
    
    await c.answer()


# ───────────────────────── Кнопка "Отмена" ────────────────────────
@router.callback_query(Text(CB_CANCEL))
async def cb_cancel(c: CallbackQuery, state: FSMContext):
    """Обработчик кнопки "Отмена" - отмена всех изменений."""
    # Возвращаем оригинальное сообщение
    # (это можно сделать, возвращая тот же callback_data, что и в начале)
    await c.message.edit_text(
        "❌ Редактирование отменено. Все изменения отменены.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Назад к накладной", callback_data="inv_edit")]
        ])
    )
    
    await c.answer()


# ───────────────────────── Кнопка "Готово" ────────────────────────
@router.callback_query(Text(CB_DONE))
async def cb_done(c: CallbackQuery, state: FSMContext):
    """Обработчик кнопки "Готово" - переход к финальному подтверждению."""
    # Получаем данные из состояния
    data = await state.get_data()
    invoice_data = data.get("invoice", {})
    fixed_issues = data.get("fixed_issues", {})
    
    # Переходим к подтверждению
    await state.set_state(InvoiceEditStates.confirm)
    
    # Формируем сообщение с итоговым списком
    message = await format_final_invoice(
        invoice_data, 
        data.get("issues", []),
        fixed_issues
    )
    
    keyboard = make_confirm_keyboard()
    await c.message.edit_text(message, reply_markup=keyboard, parse_mode="Markdown")
    
    await c.answer()


# ───────────────────────── Кнопка "Добавить позицию" ────────────────────────
@router.callback_query(Text(CB_ADD_POSITION))
async def cb_add_position(c: CallbackQuery, state: FSMContext):
    """Обработчик кнопки "Добавить позицию" - создание новой позиции."""
    # Реализация добавления новой позиции
    # (эта функциональность может быть добавлена в будущем)
    await c.answer("Функция добавления новой позиции в разработке.")


# ───────────────────────── Добавление нового товара ────────────────────────
@router.callback_query(Text(CB_ADD_NEW))
async def cb_add_new_product(c: CallbackQuery, state: FSMContext):
    """Обработчик кнопки "Добавить новый товар" - создание нового товара."""
    # Реализация добавления нового товара
    # (эта функциональность может быть добавлена в будущем)
    await c.answer("Функция добавления нового товара в разработке.")
