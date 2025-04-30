"""
Обработчики для модуля issue_editor.

Этот модуль содержит обработчики для различных действий в issue_editor.
"""

import structlog
from typing import Dict, Any, Optional
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.models.invoice_state import InvoiceEditStates
from app.config.issue_editor_constants import (
    CB_ISSUE_PREFIX,
    CB_PAGE_PREFIX,
    CB_PRODUCT_PREFIX,
    CB_ACTION_PREFIX,
    CB_UNIT_PREFIX,
    CB_CONVERT_PREFIX,
    CB_BACK,
    CB_CANCEL,
    CB_CONFIRM,
    CB_REVIEW,
    CB_SEARCH
)
from .formatters import (
    format_summary_message,
    format_issues_list,
    format_issue_edit,
    format_product_select,
    format_field_prompt
)
from .utils import get_products_by_name, save_product_match

logger = structlog.get_logger()
router = Router(name="issue_editor_handlers")

@router.callback_query(F.data == CB_BACK)
async def cb_back(c: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Назад'."""
    current_state = await state.get_state()
    data = await state.get_data()
    
    if current_state == InvoiceEditStates.issue_list:
        # Возвращаемся к итоговой информации
        text, keyboard = await format_summary_message(data)
        await c.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(None)
    elif current_state == InvoiceEditStates.issue_edit:
        # Возвращаемся к списку проблем
        text, keyboard = await format_issues_list(data)
        await c.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(InvoiceEditStates.issue_list)
    elif current_state == InvoiceEditStates.product_select:
        # Возвращаемся к редактированию проблемы
        issue = data.get("current_issue", {})
        text, keyboard = await format_issue_edit(issue)
        await c.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(InvoiceEditStates.issue_edit)
    elif current_state == InvoiceEditStates.field_input:
        # Возвращаемся к редактированию проблемы
        issue = data.get("current_issue", {})
        text, keyboard = await format_issue_edit(issue)
        await c.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(InvoiceEditStates.issue_edit)

@router.callback_query((F.data == "inv_edit") | (F.data == CB_REVIEW))
async def cb_start_review(c: CallbackQuery, state: FSMContext):
    """Обработчик начала редактирования."""
    data = await state.get_data()
    
    # Форматируем список проблем
    text, keyboard = await format_issues_list(data)
    
    # Обновляем сообщение
    await c.message.edit_text(text, reply_markup=keyboard)
    
    # Устанавливаем состояние
    await state.set_state(InvoiceEditStates.issue_list)

@router.callback_query((F.data.startswith(CB_ISSUE_PREFIX)) & (F.state == InvoiceEditStates.issue_list))
async def cb_select_issue(c: CallbackQuery, state: FSMContext):
    """Обработчик выбора проблемы для редактирования."""
    data = await state.get_data()
    issues = data.get("issues", [])
    
    # Получаем индекс проблемы из callback_data
    try:
        issue_idx = int(c.data[len(CB_ISSUE_PREFIX):])
        if issue_idx < 0 or issue_idx >= len(issues):
            raise ValueError("Invalid issue index")
    except ValueError:
        logger.error("Invalid issue index in callback", callback_data=c.data)
        await c.answer("Ошибка: неверный индекс проблемы")
        return
    
    # Получаем проблему
    issue = issues[issue_idx]
    
    # Сохраняем текущую проблему в состоянии
    await state.update_data(current_issue=issue)
    
    # Форматируем форму редактирования
    text, keyboard = await format_issue_edit(issue)
    
    # Обновляем сообщение
    await c.message.edit_text(text, reply_markup=keyboard)
    
    # Устанавливаем состояние
    await state.set_state(InvoiceEditStates.issue_edit)

@router.callback_query(lambda c: c.data and c.data.startswith(CB_PAGE_PREFIX))
async def cb_change_page(c: CallbackQuery, state: FSMContext):
    """Обработчик смены страницы."""
    data = await state.get_data()
    
    # Получаем номер страницы из callback_data
    try:
        page = int(c.data[len(CB_PAGE_PREFIX):])
        if page < 0:
            raise ValueError("Invalid page number")
    except ValueError:
        logger.error("Invalid page number in callback", callback_data=c.data)
        await c.answer("Ошибка: неверный номер страницы")
        return
    
    # Форматируем список проблем
    text, keyboard = await format_issues_list(data, page)
    
    # Обновляем сообщение
    await c.message.edit_text(text, reply_markup=keyboard)

@router.callback_query((F.data.startswith(CB_PRODUCT_PREFIX)) & (F.state == InvoiceEditStates.product_select))
async def cb_select_product(c: CallbackQuery, state: FSMContext):
    """Обработчик выбора товара."""
    data = await state.get_data()
    current_issue = data.get("current_issue", {})
    
    # Получаем ID товара из callback_data
    try:
        product_id = int(c.data[len(CB_PRODUCT_PREFIX):])
    except ValueError:
        logger.error("Invalid product ID in callback", callback_data=c.data)
        await c.answer("Ошибка: неверный ID товара")
        return
    
    # Обновляем проблему
    current_issue["product_id"] = product_id
    current_issue["resolved"] = True
    
    # Сохраняем обновленную проблему
    issues = data.get("issues", [])
    for i, issue in enumerate(issues):
        if issue.get("id") == current_issue.get("id"):
            issues[i] = current_issue
            break
    
    await state.update_data(issues=issues, current_issue=current_issue)
    
    # Возвращаемся к списку проблем
    text, keyboard = await format_issues_list(data)
    await c.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(InvoiceEditStates.issue_list)

@router.callback_query((F.data.startswith(CB_ACTION_PREFIX)) & (F.state == InvoiceEditStates.issue_edit))
async def cb_action_with_item(c: CallbackQuery, state: FSMContext):
    """Обработчик действий с элементом."""
    data = await state.get_data()
    current_issue = data.get("current_issue", {})
    
    # Получаем название поля из callback_data
    field = c.data[len(CB_ACTION_PREFIX):]
    
    if field == "product":
        # Переходим к выбору товара
        await state.set_state(InvoiceEditStates.product_select)
        await c.message.edit_text(
            "🔍 Введите название товара для поиска:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)]
            ])
        )
    elif field in ["unit", "quantity", "price"]:
        # Переходим к вводу значения поля
        current_value = current_issue.get("current_values", {}).get(field, "")
        text = format_field_prompt(field, current_value)
        
        # Создаем клавиатуру с кнопками для единиц измерения
        keyboard = []
        if field == "unit":
            for unit in ["шт", "кг", "л"]:
                keyboard.append([
                    InlineKeyboardButton(
                        text=unit,
                        callback_data=f"{CB_UNIT_PREFIX}{unit}"
                    )
                ])
        
        keyboard.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)
        ])
        
        await c.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await state.set_state(InvoiceEditStates.field_input)
        await state.update_data(current_field=field)

@router.callback_query((F.data.startswith(CB_UNIT_PREFIX)) & (F.state == InvoiceEditStates.field_input))
async def cb_select_unit(c: CallbackQuery, state: FSMContext):
    """Обработчик выбора единицы измерения."""
    data = await state.get_data()
    current_issue = data.get("current_issue", {})
    current_field = data.get("current_field")
    
    if current_field != "unit":
        await c.answer("Ошибка: неверное поле для единицы измерения")
        return
    
    # Получаем единицу измерения из callback_data
    unit = c.data[len(CB_UNIT_PREFIX):]
    
    # Обновляем значение
    if "current_values" not in current_issue:
        current_issue["current_values"] = {}
    current_issue["current_values"]["unit"] = unit
    current_issue["resolved"] = True
    
    # Сохраняем обновленную проблему
    issues = data.get("issues", [])
    for i, issue in enumerate(issues):
        if issue.get("id") == current_issue.get("id"):
            issues[i] = current_issue
            break
    
    await state.update_data(issues=issues, current_issue=current_issue)
    
    # Возвращаемся к списку проблем
    text, keyboard = await format_issues_list(data)
    await c.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(InvoiceEditStates.issue_list)

@router.callback_query((F.data == CB_SEARCH) & (F.state == InvoiceEditStates.product_select))
async def cb_search_product(c: CallbackQuery, state: FSMContext):
    """Обработчик поиска товаров."""
    await c.message.edit_text(
        "🔍 Введите название товара для поиска:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)]
        ])
    )

@router.message(F.state == InvoiceEditStates.field_input)
async def process_field_input(message: Message, state: FSMContext):
    """Обработчик ввода значения поля."""
    data = await state.get_data()
    current_issue = data.get("current_issue", {})
    current_field = data.get("current_field")
    
    if not current_field:
        await message.answer("Ошибка: не выбрано поле для редактирования")
        return
    
    try:
        # Преобразуем значение в нужный тип
        if current_field == "quantity":
            value = float(message.text.replace(",", "."))
        elif current_field == "price":
            value = float(message.text.replace(",", "."))
        else:
            value = message.text
        
        # Обновляем значение
        if "current_values" not in current_issue:
            current_issue["current_values"] = {}
        current_issue["current_values"][current_field] = value
        current_issue["resolved"] = True
        
        # Сохраняем обновленную проблему
        issues = data.get("issues", [])
        for i, issue in enumerate(issues):
            if issue.get("id") == current_issue.get("id"):
                issues[i] = current_issue
                break
        
        await state.update_data(issues=issues, current_issue=current_issue)
        
        # Возвращаемся к списку проблем
        text, keyboard = await format_issues_list(data)
        await message.answer(text, reply_markup=keyboard)
        await state.set_state(InvoiceEditStates.issue_list)
        
    except ValueError:
        await message.answer(
            "❌ Ошибка: введите корректное числовое значение",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)]
            ])
        ) 