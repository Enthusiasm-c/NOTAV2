"""
Тесты для модуля редактирования спорных позиций в накладных.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, User, Chat, InlineKeyboardMarkup

from app.routers.issue_editor import (
    cb_start_fix, cb_select_issue, cb_action_with_item, cb_select_product,
    make_issue_list_keyboard, make_item_edit_keyboard, format_issue_for_edit,
    format_final_invoice, InvoiceEditStates
)


# Фикстуры для тестирования
@pytest.fixture
def state_data():
    """Базовые данные состояния FSM для тестов."""
    return {
        "invoice": {
            "supplier": "Test Supplier",
            "date": "2025-04-20",
            "positions": [
                {
                    "name": "Apple",
                    "quantity": 5,
                    "unit": "kg",
                    "price": 10.0,
                    "sum": 50.0,
                    "match_id": 1,
                    "confidence": 0.95
                },
                {
                    "name": "Banana",
                    "quantity": 2,
                    "unit": "pack",
                    "price": 20.0,
                    "sum": 40.0,
                    "match_id": None,
                    "confidence": 0.0
                },
                {
                    "name": "Carrot",
                    "quantity": 3,
                    "unit": "pcs",
                    "price": 5.0,
                    "sum": 15.0,
                    "match_id": 3,
                    "confidence": 0.85
                }
            ]
        },
        "issues": [
            {
                "index": 2,
                "invoice_item": "Banana pack",
                "db_item": "—",
                "issue": "❌ Not in database",
                "original": {
                    "name": "Banana",
                    "quantity": 2,
                    "unit": "pack",
                    "price": 20.0,
                    "sum": 40.0
                }
            },
            {
                "index": 3,
                "invoice_item": "Carrot *pcs*",
                "db_item": "Carrot *kg*",
                "issue": "Units incompatible",
                "original": {
                    "name": "Carrot",
                    "quantity": 3,
                    "unit": "pcs",
                    "price": 5.0,
                    "sum": 15.0
                },
                "product": MagicMock(name="Carrot", unit="kg", id=3)
            }
        ],
        "current_issues": [
            {
                "index": 2,
                "invoice_item": "Banana pack",
                "db_item": "—",
                "issue": "❌ Not in database",
                "original": {
                    "name": "Banana",
                    "quantity": 2,
                    "unit": "pack",
                    "price": 20.0,
                    "sum": 40.0
                }
            },
            {
                "index": 3,
                "invoice_item": "Carrot *pcs*",
                "db_item": "Carrot *kg*",
                "issue": "Units incompatible",
                "original": {
                    "name": "Carrot",
                    "quantity": 3,
                    "unit": "pcs",
                    "price": 5.0,
                    "sum": 15.0
                },
                "product": MagicMock(name="Carrot", unit="kg", id=3)
            }
        ],
        "fixed_issues": {},
        "selected_issue_idx": 0,
        "selected_issue": {
            "index": 2,
            "invoice_item": "Banana pack",
            "db_item": "—",
            "issue": "❌ Not in database",
            "original": {
                "name": "Banana",
                "quantity": 2,
                "unit": "pack",
                "price": 20.0,
                "sum": 40.0
            }
        }
    }


@pytest.fixture
def callback_query():
    """Фикстура для имитации callback_query."""
    query = AsyncMock(spec=CallbackQuery)
    query.message = AsyncMock(spec=Message)
    query.data = "test_data"
    query.from_user = AsyncMock(spec=User)
    query.from_user.id = 12345
    query.message.chat = AsyncMock(spec=Chat)
    query.message.chat.id = 12345
    return query


@pytest.fixture
def message():
    """Фикстура для имитации сообщения."""
    msg = AsyncMock(spec=Message)
    msg.from_user = AsyncMock(spec=User)
    msg.from_user.id = 12345
    msg.chat = AsyncMock(spec=Chat)
    msg.chat.id = 12345
    msg.text = "Test message"
    return msg


@pytest.fixture
async def state(state_data):
    """Фикстура для имитации FSMContext."""
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key="test:12345")
    await state.set_state(InvoiceEditStates.issue_list)
    await state.set_data(state_data)
    return state


# Тесты для хелперов
def test_make_issue_list_keyboard():
    """Тест создания клавиатуры списка проблем."""
    issues = [
        {"invoice_item": "Item 1", "issue": "Not in database"},
        {"invoice_item": "Item 2", "issue": "Unit mismatch"}
    ]
    
    keyboard = make_issue_list_keyboard(issues)
    
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert len(keyboard.inline_keyboard) == 4  # 2 проблемы + кнопка добавления + кнопки готово/отмена


def test_make_item_edit_keyboard():
    """Тест создания клавиатуры редактирования позиции."""
    keyboard = make_item_edit_keyboard()
    
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert len(keyboard.inline_keyboard) == 2  # 2 ряда кнопок
    assert len(keyboard.inline_keyboard[0]) == 3  # 3 кнопки в первом ряду
    assert len(keyboard.inline_keyboard[1]) == 2  # 2 кнопки во втором ряду


@pytest.mark.asyncio
async def test_format_issue_for_edit():
    """Тест форматирования информации о проблемной позиции."""
    issue = {
        "issue": "Not in database",
        "original": {
            "name": "Test Item",
            "quantity": 5,
            "unit": "kg",
            "price": 10.0,
            "sum": 50.0
        },
        "product": MagicMock(name="Database Item", unit="kg")
    }
    
    result = await format_issue_for_edit(issue)
    
    assert isinstance(result, str)
    assert "Test Item" in result
    assert "5 kg" in result
    assert "10.0" in result
    assert "50.0" in result
    assert "Not in database" in result


@pytest.mark.asyncio
async def test_format_final_invoice():
    """Тест форматирования финального вида накладной."""
    invoice_data = {
        "supplier": "Test Supplier",
        "date": "2025-04-20",
        "positions": [
            {
                "name": "Item 1",
                "quantity": 5,
                "unit": "kg",
                "price": 10.0,
                "sum": 50.0
            },
            {
                "name": "Item 2",
                "quantity": 2,
                "unit": "pcs",
                "price": 20.0,
                "sum": 40.0
            }
        ]
    }
    
    original_issues = [
        {"index": 2, "original": {"name": "Item 2"}},
    ]
    
    fixed_issues = {
        1: {"action": "change_unit", "old_unit": "box", "new_unit": "pcs"}
    }
    
    result = await format_final_invoice(invoice_data, original_issues, fixed_issues)
    
    assert isinstance(result, str)
    assert "Test Supplier" in result
    assert "2025-04-20" in result
    assert "Item 1" in result
    assert "Item 2" in result
    assert "90.0" in result  # Total sum
    assert "Исправлено позиций: 1" in result


# Тесты для колбэков
@pytest.mark.asyncio
async def test_cb_start_fix(callback_query, state):
    """Тест начала процесса исправления накладной."""
    callback_query.data = "inv_edit"
    
    await cb_start_fix(callback_query, state)
    
    # Проверяем, что состояние изменилось
    assert await state.get_state() == InvoiceEditStates.issue_list
    
    # Проверяем, что был вызов редактирования сообщения
    callback_query.message.edit_text.assert_called_once()
    callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_cb_select_issue(callback_query, state):
    """Тест выбора проблемной позиции из списка."""
    callback_query.data = "issue_0"  # Выбираем первую проблему
    
    await cb_select_issue(callback_query, state)
    
    # Проверяем, что состояние изменилось
    assert await state.get_state() == InvoiceEditStates.issue_edit
    
    # Проверяем, что был вызов редактирования сообщения
    callback_query.message.edit_text.assert_called_once()
    callback_query.answer.assert_called_once()


@pytest.mark.asyncio
@patch('app.routers.issue_editor.get_products_by_name')
async def test_cb_action_with_item_name(mock_get_products, callback_query, state):
    """Тест выбора действия изменения наименования товара."""
    mock_get_products.return_value = [
        (1, "Banana", "kg"),
        (2, "Banana Yellow", "pack")
    ]
    
    callback_query.data = "action_name"
    
    await cb_action_with_item(callback_query, state)
    
    # Проверяем, что состояние изменилось
    assert await state.get_state() == InvoiceEditStates.product_select
    
    # Проверяем, что был вызов редактирования сообщения
    callback_query.message.edit_text.assert_called_once()
    callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_cb_action_with_item_qty(callback_query, state):
    """Тест выбора действия изменения количества."""
    callback_query.data = "action_qty"
    
    await cb_action_with_item(callback_query, state)
    
    # Проверяем, что состояние изменилось
    assert await state.get_state() == InvoiceEditStates.field_input
    
    # Проверяем, что был вызов редактирования сообщения
    callback_query.message.edit_text.assert_called_once()
    assert "новое количество" in callback_query.message.edit_text.call_args[0][0].lower()
    callback_query.answer.assert_called_once()


@pytest.mark.asyncio
@patch('app.routers.issue_editor.get_product_details')
@patch('app.routers.issue_editor.SessionLocal')
async def test_cb_select_product(mock_session_local, mock_get_product, callback_query, state):
    """Тест выбора товара из списка."""
    # Настраиваем моки
    session_instance = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = session_instance
    
    product = MagicMock()
    product.id = 2
    product.name = "Banana Yellow"
    product.unit = "pack"
    mock_get_product.return_value = product
    
    callback_query.data = "product_2"
    
    await cb_select_product(callback_query, state)
    
    # Проверяем, что состояние изменилось
    assert await state.get_state() == InvoiceEditStates.issue_list
    
    # Проверяем, что был вызов редактирования сообщения
    callback_query.message.edit_text.assert_called_once()
    callback_query.answer.assert_called_once()
    
    # Проверяем, что данные обновились
    updated_data = await state.get_data()
    assert 2 in updated_data["fixed_issues"]
    assert updated_data["fixed_issues"][2]["action"] == "replace_product"
    assert updated_data["fixed_issues"][2]["product_id"] == 2


@pytest.mark.asyncio
async def test_process_field_input_quantity(message, state):
    """Тест ввода нового количества."""
    # Устанавливаем состояние и поле для редактирования
    await state.update_data(field="quantity")
    await state.set_state(InvoiceEditStates.field_input)
    
    # Устанавливаем текст сообщения
    message.text = "3.5"
    
    # Импортируем функцию здесь, чтобы не мешать другим тестам
    from app.routers.issue_editor import process_field_input
    
    await process_field_input(message, state)
    
    # Проверяем, что данные обновились
    updated_data = await state.get_data()
    assert 1 in updated_data["fixed_issues"]
    assert updated_data["fixed_issues"][1]["action"] == "change_quantity"
    assert updated_data["fixed_issues"][1]["new_quantity"] == 3.5
