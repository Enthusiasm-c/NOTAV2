"""
Тесты для модуля редактирования спорных позиций в накладных.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.types import InlineKeyboardMarkup

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, User, Chat

from app.routers.issue_editor.formatters import (
    get_issue_icon, format_issues_list, format_issue_edit, format_product_select
)
from app.routers.issue_editor.utils import (
    clean_name_for_comparison, is_semifinished, get_products_by_name, save_product_match
)
from app.routers.issue_editor.handlers import (
    cb_back, cb_change_page, cb_select_unit, cb_search_product, process_field_input, cb_select_issue, cb_action_with_item, cb_select_product
)
from app.routers.issue_editor.formatters import format_field_prompt
from app.routers.issue_editor.formatters import format_summary_message
from app.models.invoice_state import InvoiceEditStates


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


@pytest.fixture
def sample_issue() -> Dict[str, Any]:
    """Создает тестовую проблему для накладной."""
    return {
        "index": 1,
        "invoice_item": "Test Product (pcs)",
        "db_item": "Test Product (pcs)",
        "issue": "Not in database",
        "original": {
            "name": "Test Product",
            "quantity": 10.0,
            "unit": "pcs",
            "price": 100.0
        }
    }

@pytest.fixture
def sample_issues() -> List[Dict[str, Any]]:
    """Создает список тестовых проблем."""
    return [
        {
            "index": 1,
            "invoice_item": "Product 1 (pcs)",
            "db_item": "—",
            "issue": "Not in database",
            "original": {
                "name": "Product 1",
                "quantity": 10.0,
                "unit": "pcs",
                "price": 100.0
            }
        },
        {
            "index": 2,
            "invoice_item": "Product 2 (kg)",
            "db_item": "Product 2 (g)",
            "issue": "Unit conversion needed",
            "original": {
                "name": "Product 2",
                "quantity": 1.0,
                "unit": "kg",
                "price": 50.0
            }
        }
    ]


# Тесты для колбэков
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


def test_clean_name_for_comparison():
    """Тестирует очистку названия для сравнения."""
    test_cases = [
        ("Test Product", "test product"),
        ("Test-Product", "test product"),
        ("Test_Product", "test product"),
        ("Test.Product", "test product"),
        ("Test  Product", "test product"),
        ("Test Product!", "test product"),
        ("Test Product?", "test product"),
        ("Test Product...", "test product"),
    ]
    
    for input_name, expected in test_cases:
        assert clean_name_for_comparison(input_name) == expected


def test_is_semifinished():
    """Тестирует определение полуфабрикатов."""
    semifinished_names = [
        "Полуфабрикат",
        "Полуфабрикат мясной",
        "Полуфабрикат куриный",
        "П/ф",
        "П/ф мясной",
        "П/ф куриный"
    ]
    
    regular_names = [
        "Курица",
        "Мясо",
        "Рыба",
        "Овощи",
        "Фрукты"
    ]
    
    for name in semifinished_names:
        assert is_semifinished(name) is True
    
    for name in regular_names:
        assert is_semifinished(name) is False


@pytest.mark.asyncio
async def test_get_products_by_name(session: AsyncSession):
    """Тестирует поиск товаров по названию."""
    # Создаем тестовые товары
    products = [
        {"name": "Test Product 1", "unit": "pcs"},
        {"name": "Test Product 2", "unit": "kg"},
        {"name": "Another Product", "unit": "g"}
    ]
    
    for product_data in products:
        product = Product(**product_data)
        session.add(product)
    await session.commit()
    
    # Тестируем поиск
    results = await get_products_by_name(session, "Test Product", limit=2)
    assert len(results) == 2
    assert all("Test Product" in p["name"] for p in results)
    
    # Тестируем поиск с порогом схожести
    results = await get_products_by_name(session, "Test", threshold=0.9)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_save_product_match(session: AsyncSession):
    """Тестирует сохранение сопоставления товара."""
    # Создаем тестовый товар
    product = Product(name="Test Product", unit="pcs")
    session.add(product)
    await session.commit()
    
    # Тестируем сохранение сопоставления
    success = await save_product_match(session, "Test Product Alias", product.id)
    assert success is True
    
    # Проверяем, что сопоставление создано
    lookup = await session.execute(
        select(ProductNameLookup).where(ProductNameLookup.alias == "Test Product Alias")
    )
    assert lookup.scalar_one_or_none() is not None


def test_get_issue_icon(sample_issue: Dict[str, Any]):
    """Тестирует получение иконки для проблемы."""
    # Тестируем разные типы проблем
    test_cases = [
        ("Not in database", "🔴"),
        ("Unit conversion needed", "🟠"),
        ("Possible incorrect match", "🟡"),
        ("Unknown issue", "⚠️")
    ]
    
    for issue_type, expected_icon in test_cases:
        sample_issue["issue"] = issue_type
        assert get_issue_icon(sample_issue) == expected_icon


@pytest.mark.asyncio
async def test_format_issues_list(sample_issues: List[Dict[str, Any]]):
    """Тестирует форматирование списка проблем."""
    message, keyboard = await format_issues_list({"issues": sample_issues})
    
    assert isinstance(message, str)
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert "Product 1" in message
    assert "Product 2" in message
    assert len(keyboard.inline_keyboard) == len(sample_issues) + 1  # +1 для кнопки "Готово"


@pytest.mark.asyncio
async def test_format_issue_edit(sample_issue: Dict[str, Any]):
    """Тестирует форматирование редактирования проблемы."""
    message, keyboard = await format_issue_edit(sample_issue)
    
    assert isinstance(message, str)
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert "Test Product" in message
    assert len(keyboard.inline_keyboard) > 0


@pytest.mark.asyncio
async def test_format_product_select(session: AsyncSession):
    """Тестирует форматирование выбора товара."""
    # Создаем тестовые товары
    products = [
        {"name": "Test Product 1", "unit": "pcs"},
        {"name": "Test Product 2", "unit": "kg"}
    ]
    
    for product_data in products:
        product = Product(**product_data)
        session.add(product)
    await session.commit()
    
    message, keyboard = await format_product_select(
        [{"id": p.id, "name": p.name, "unit": p.unit} for p in products],
        "Test",
        page=0
    )
    
    assert isinstance(message, str)
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert "Test Product 1" in message
    assert "Test Product 2" in message


def test_format_field_prompt():
    """Тестирует форматирование подсказки для поля."""
    test_cases = [
        ("name", "Test", "Введите новое название товара:\nТекущее значение: Test"),
        ("quantity", "10", "Введите новое количество:\nТекущее значение: 10"),
        ("unit", "pcs", "Введите новую единицу измерения:\nТекущее значение: pcs"),
        ("price", "100", "Введите новую цену:\nТекущее значение: 100")
    ]
    
    for field, current_value, expected in test_cases:
        assert format_field_prompt(field, current_value) == expected


@pytest.mark.asyncio
async def test_cb_back(callback_query, state):
    """Тест возврата к предыдущему состоянию."""
    # Устанавливаем начальное состояние
    await state.set_state(InvoiceEditStates.issue_edit)
    await state.update_data(previous_state=InvoiceEditStates.issue_list)
    
    callback_query.data = "back"
    
    await cb_back(callback_query, state)
    
    # Проверяем, что вернулись к предыдущему состоянию
    assert await state.get_state() == InvoiceEditStates.issue_list
    callback_query.message.edit_text.assert_called_once()
    callback_query.answer.assert_called_once()

@pytest.mark.asyncio
async def test_cb_change_page(callback_query, state):
    """Тест переключения страницы в списке проблем."""
    callback_query.data = "page_1"  # Переход на вторую страницу
    
    await cb_change_page(callback_query, state)
    
    # Проверяем, что сообщение обновилось
    callback_query.message.edit_text.assert_called_once()
    callback_query.answer.assert_called_once()

@pytest.mark.asyncio
async def test_cb_select_unit(callback_query, state):
    """Тест выбора единицы измерения."""
    callback_query.data = "unit_kg"
    
    await cb_select_unit(callback_query, state)
    
    # Проверяем, что состояние изменилось
    assert await state.get_state() == InvoiceEditStates.issue_list
    
    # Проверяем, что данные обновились
    updated_data = await state.get_data()
    assert 1 in updated_data["fixed_issues"]
    assert updated_data["fixed_issues"][1]["action"] == "change_unit"
    assert updated_data["fixed_issues"][1]["new_unit"] == "kg"

@pytest.mark.asyncio
async def test_cb_search_product(callback_query, state):
    """Тест поиска товара."""
    callback_query.data = "search"
    
    await cb_search_product(callback_query, state)
    
    # Проверяем, что состояние изменилось
    assert await state.get_state() == InvoiceEditStates.field_input
    
    # Проверяем, что было запрошено введение поискового запроса
    callback_query.message.edit_text.assert_called_once()
    assert "поисковый запрос" in callback_query.message.edit_text.call_args[0][0].lower()

@pytest.mark.asyncio
async def test_process_field_input_invalid_quantity(message, state):
    """Тест обработки некорректного ввода количества."""
    # Устанавливаем состояние и поле для редактирования
    await state.update_data(field="quantity")
    await state.set_state(InvoiceEditStates.field_input)
    
    # Устанавливаем некорректный текст сообщения
    message.text = "invalid"
    
    await process_field_input(message, state)
    
    # Проверяем, что данные не обновились
    updated_data = await state.get_data()
    assert "fixed_issues" not in updated_data or 1 not in updated_data["fixed_issues"]
    
    # Проверяем, что было отправлено сообщение об ошибке
    message.answer.assert_called_once()
    assert "ошибка" in message.answer.call_args[0][0].lower()

@pytest.mark.asyncio
async def test_process_field_input_price(message, state):
    """Тест ввода новой цены."""
    # Устанавливаем состояние и поле для редактирования
    await state.update_data(field="price")
    await state.set_state(InvoiceEditStates.field_input)
    
    # Устанавливаем текст сообщения
    message.text = "150.50"
    
    await process_field_input(message, state)
    
    # Проверяем, что данные обновились
    updated_data = await state.get_data()
    assert 1 in updated_data["fixed_issues"]
    assert updated_data["fixed_issues"][1]["action"] == "change_price"
    assert updated_data["fixed_issues"][1]["new_price"] == 150.50
