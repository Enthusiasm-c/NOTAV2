"""
Telegram bot router for Nota V2.

This module handles all Telegram bot interactions including:
- OCR processing of invoice images
- Parsing and validation of invoice data
- User interaction for invoice review and editing
"""

from __future__ import annotations

import structlog
from typing import Dict, List, Any, Tuple

from aiogram import Bot, Router, F
from aiogram.filters.command import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# Импортируем unified_match для работы с сопоставлением товаров
from app.routers.fuzzy_match import fuzzy_match_product, find_similar_products
from app.routers.syrve_export import export_to_syrve

# Импортируем функции для создания UI
from app.utils.markdown import make_invoice_preview, make_issue_list

# Импортируем состояния FSM
from app.models.invoice_state import InvoiceStates, InvoiceEditStates

# Импортируем настройки
from app.config.settings import get_settings

# Импортируем функции работы с данными
from app.core.data_loader import get_supplier, get_product_details, load_data

# Импортируем модуль unit_converter, если он доступен
try:
    from app.utils.unit_converter import normalize_unit, is_compatible_unit
    UNIT_CONVERTER_AVAILABLE = True
except ImportError:
    UNIT_CONVERTER_AVAILABLE = False
    
    # Unit normalization dictionary
    UNIT_ALIASES: Dict[str, str] = {
        # English volume units
        "l": "l", "ltr": "l", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
        "ml": "ml", "milliliter": "ml", "milliliters": "ml", "millilitre": "ml",
        "millilitres": "ml",
        
        # English weight units
        "kg": "kg", "kilo": "kg", "kilogram": "kg", "kilograms": "kg",
        "g": "g", "gr": "g", "gram": "g", "grams": "g",
        
        # English countable units
        "pcs": "pcs", "pc": "pcs", "piece": "pcs", "pieces": "pcs",
        "pack": "pack", "package": "pack", "pkg": "pack",
        "box": "box", "boxes": "box",
        
        # Indonesian volume units
        "liter": "l", "lt": "l",
        "mililiter": "ml", "mili": "ml",
        
        # Indonesian weight units
        "kilogram": "kg", "kilo": "kg",
        "gram": "g",
        
        # Indonesian countable units
        "buah": "pcs", "biji": "pcs", "pcs": "pcs", "potong": "pcs",
        "paket": "pack", "pak": "pack",
        "kotak": "box", "dus": "box", "kardus": "box",
        
        # Common abbreviations
        "ea": "pcs",  # each
        "btl": "pcs"  # bottle/botol
    }
    
    def normalize_unit(unit_str: str) -> str:
        """Normalize unit string to standard format."""
        if not unit_str:
            return ""
        unit_str = unit_str.lower().strip()
        return UNIT_ALIASES.get(unit_str, unit_str)
    
    def is_compatible_unit(unit1: str, unit2: str) -> bool:
        """Check if two units are compatible (can be converted between each other)."""
        unit1 = normalize_unit(unit1)
        unit2 = normalize_unit(unit2)
        
        # Same normalized units are always compatible
        if unit1 == unit2:
            return True
        
        # Check unit categories
        volume_units = {"l", "ml"}
        weight_units = {"kg", "g"}
        countable_units = {"pcs", "pack", "box"}
        
        if unit1 in volume_units and unit2 in volume_units:
            return True
        if unit1 in weight_units and unit2 in weight_units:
            return True
        if unit1 in countable_units and unit2 in countable_units:
            # Countable units technically aren't directly convertible without 
            # additional knowledge (e.g., how many pieces in a pack)
            return False
        return False

logger = structlog.get_logger()
router = Router(name=__name__)

# Загружаем данные при старте модуля
load_data()

settings = get_settings()


def _safe_str(value: str | None) -> str:
    """Безопасно преобразует значение в строку и удаляет пробелы."""
    return (value or "").strip()


async def _run_pipeline(file_id: str, bot: Bot) -> dict:
    """Фото в Telegram → структурированный словарь (OCR+Parsing)."""
    try:
        # Пытаемся использовать оптимизированный объединенный вызов
        try:
            from app.routers.gpt_combined import ocr_and_parse
            _, parsed_data = await ocr_and_parse(file_id, bot)
            logger.info(
                "Combined OCR+Parsing completed successfully",
                positions_count=len(parsed_data.get("positions", []))
            )
            return parsed_data
        except ImportError:
            # Если модуль недоступен, используем отдельные вызовы
            raise RuntimeError("gpt_combined.py должен быть в проекте!")
    except Exception as exc:
        logger.exception("Pipeline failed", exc_info=exc)
        raise


def calculate_total_sum(positions: list) -> float:
    """Безопасно вычисляет общую сумму из всех позиций."""
    total = 0.0
    for pos in positions:
        # Пропускаем удаленные позиции
        if pos.get("deleted", False):
            continue
        try:
            pos_sum = float(pos.get("sum", 0)) if pos.get("sum") else 0
            total += pos_sum
        except (ValueError, TypeError):
            logger.warning(
                "Invalid sum value",
                position=pos.get("name"),
                sum=pos.get("sum")
            )
    return total


async def _check_supplier(supplier_name: str) -> List[Dict[str, Any]]:
    """Проверяет поставщика на наличие в базе."""
    issues = []
    if not supplier_name:
        issues.append({
            "type": "supplier_missing",
            "message": "❌ Не указан поставщик"
        })
    else:
        supplier = get_supplier(supplier_name)
        if not supplier:
            issues.append({
                "type": "supplier_not_found",
                "message": f"❓ Поставщик не найден: {supplier_name}"
            })
    return issues


async def _check_product(name: str, i: int) -> Tuple[List[Dict[str, Any]], str | None]:
    """Проверяет товар на наличие в базе и уверенность сопоставления."""
    issues = []
    product_id, confidence = await fuzzy_match_product(name)
    if not product_id:
        issues.append({
            "type": "product_not_found",
            "message": f"❓ Позиция {i}: товар не найден: {name}"
        })
    elif confidence < 0.9:  # Если уверенность низкая
        similar = await find_similar_products(name, limit=3)
        suggestions = ", ".join(_safe_str(p.get("name")) for p in similar)
        msg = (
            f"⚠️ Позиция {i}: низкая уверенность в сопоставлении товара: {name}\n"
            f"Возможные варианты: {suggestions}"
        )
        issues.append({
            "type": "product_low_confidence",
            "message": msg
        })
    return issues, product_id


def _check_quantity(qty: float, i: int) -> List[Dict[str, Any]]:
    """Проверяет количество товара."""
    issues = []
    if not qty or qty <= 0:
        issues.append({
            "type": "position_no_quantity",
            "message": f"❌ Позиция {i}: не указано количество"
        })
    return issues


def _check_unit(unit: str, product_id: str | None, i: int) -> List[Dict[str, Any]]:
    """Проверяет единицы измерения товара."""
    issues = []
    if not unit:
        issues.append({
            "type": "position_no_unit",
            "message": f"❌ Позиция {i}: не указаны единицы измерения"
        })
    elif product_id:
        product = get_product_details(product_id)
        if product and UNIT_CONVERTER_AVAILABLE:
            product_unit = _safe_str(product.get("measureName"))
            if not is_compatible_unit(unit, product_unit):
                msg = (
                    f"⚠️ Позиция {i}: несовместимые единицы измерения: "
                    f"{unit} vs {product_unit}"
                )
                issues.append({
                    "type": "unit_mismatch",
                    "message": msg
                })
    return issues


def _check_total_sum(total: float, positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Проверяет общую сумму накладной."""
    issues = []
    if not total or total <= 0:
        issues.append({
            "type": "no_total",
            "message": "❌ Не указана общая сумма"
        })
    else:
        positions_sum = calculate_total_sum(positions)
        if abs(total - positions_sum) > 0.01:  # Допускаем погрешность в 1 копейку
            msg = (
                f"⚠️ Сумма позиций ({positions_sum:.2f}) "
                f"не совпадает с общей суммой ({total:.2f})"
            )
            issues.append({
                "type": "sum_mismatch",
                "message": msg
            })
    return issues


async def analyze_invoice_issues(data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    """Анализирует накладную на наличие проблем."""
    issues = []
    
    # Проверяем наличие поставщика
    supplier_name = _safe_str(data.get("supplier"))
    issues.extend(await _check_supplier(supplier_name))
    
    # Проверяем позиции
    positions = data.get("positions", [])
    if not positions:
        issues.append({
            "type": "no_positions",
            "message": "❌ Нет позиций в накладной"
        })
    else:
        for i, pos in enumerate(positions, 1):
            name = _safe_str(pos.get("name"))
            if not name:
                issues.append({
                    "type": "position_no_name",
                    "message": f"❌ Позиция {i}: не указано название"
                })
                continue
            
            # Проверяем товар в базе
            product_issues, product_id = await _check_product(name, i)
            issues.extend(product_issues)
            
            # Проверяем количество
            qty = pos.get("quantity")
            issues.extend(_check_quantity(qty, i))
            
            # Проверяем единицы измерения
            unit = _safe_str(pos.get("unit"))
            issues.extend(_check_unit(unit, product_id, i))
    
    # Проверяем общую сумму
    total = data.get("total_sum")
    issues.extend(_check_total_sum(total, positions))
    
    # Формируем общее сообщение
    if not issues:
        message = "✅ Проблем не обнаружено"
    else:
        message = "❗️ Обнаружены проблемы:\n" + "\n".join(i["message"] for i in issues)
    
    return issues, message


@router.message(CommandStart())
async def cmd_start(m: Message):
    """Обработчик команды /start"""
    await m.answer(
        "👋 Добро пожаловать! Пришлите мне фото накладной, "
        "и я распознаю товары и загружу их в Syrve."
    )


@router.message(F.photo)
async def handle_photo(m: Message, state: FSMContext, bot: Bot):
    """Обработчик получения фото накладной"""
    # Устанавливаем состояние OCR
    await state.set_state(InvoiceStates.ocr)
    
    # Отправляем уведомление о начале обработки
    await m.answer("⏳ Обработка накладной...")
    
    # Получаем file_id фото с максимальным разрешением
    file_id = m.photo[-1].file_id

    try:
        # Запускаем пайплайн OCR+Parsing
        data = await _run_pipeline(file_id, bot)
        
        # Анализируем проблемы в распознанной накладной
        issues, parser_comment = await analyze_invoice_issues(data)
        
        # Сохраняем данные в состоянии
        await state.update_data(
            invoice=data,
            issues=issues,
            parser_comment=parser_comment
        )
        
        # Переходим к отображению предварительного просмотра накладной
        await state.set_state(InvoiceStates.preview)
        
        # Формируем сообщение с подробным выводом проблемных позиций
        message = make_invoice_preview(data, issues, show_all_issues=True)
        
        # Создаем клавиатуру для действий
        keyboard = []
        
        # Добавляем кнопки в зависимости от наличия проблемных позиций
        if issues:
            keyboard.append([
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="inv_ok"),
                InlineKeyboardButton(text="✏️ Исправить", callback_data="inv_edit")
            ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    text="✅ Подтвердить и отправить",
                    callback_data="inv_ok"
                )
            ])
        
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        # Отправляем сообщение с результатами распознавания
        await m.answer(message, reply_markup=kb, parse_mode="Markdown")
        
    except Exception as exc:
        logger.exception("Ошибка обработки фото", exc_info=exc)
        await m.answer(
            "❌ Не удалось распознать документ. Пожалуйста, попробуйте снова."
        )
    finally:
        # Возвращаемся к начальному состоянию, если была ошибка
        if await state.get_state() == InvoiceStates.ocr.state:
            await state.set_state(InvoiceStates.upload)


@router.callback_query(F.data == "inv_ok")
async def cb_confirm_invoice(c: CallbackQuery, state: FSMContext):
    """Обработчик подтверждения накладной"""
    # Получаем данные из состояния
    data = (await state.get_data()).get("invoice", {})
    issues = (await state.get_data()).get("issues", [])
    fixed_issues = (await state.get_data()).get("fixed_issues", {})
    
    if not data:
        await c.message.answer("❌ Данные накладной отсутствуют. Попробуйте снова.")
        await c.answer()
        return
    
    # Устанавливаем состояние экспорта
    await state.set_state(InvoiceStates.exporting)
    
    # Фильтруем удаленные позиции перед экспортом
    positions = data.get("positions", [])
    active_positions = [p for p in positions if not p.get("deleted", False)]
    data["positions"] = active_positions
    
    # Экспортируем в Syrve
    await c.message.answer("⏳ Экспорт в Syrve...")
    
    try:
        success, message = await export_to_syrve(data)
        
        if success:
            # Подготавливаем итоговое сообщение об успешном экспорте
            total_items = len(active_positions)
            
            # Получаем актуальный список проблем (исключая исправленные)
            fixed_indices = set(fixed_issues.keys() if fixed_issues else set())
            remaining_issues = [
                issue for issue in issues 
                if issue.get("index") - 1 not in fixed_indices
            ]
            
            fixed_count = len(fixed_issues) if fixed_issues else 0
            remaining_count = len(remaining_issues)
            
            if remaining_count > 0:
                msg = (
                    f"✅ *Накладная обработана с предупреждениями!*\n\n"
                    f"• Всего позиций: {total_items}\n"
                    f"• Исправлено: {fixed_count}\n"
                    f"• Осталось проблем: {remaining_count}\n\n"
                    f"Все данные загружены в Syrve несмотря на предупреждения."
                )
            else:
                msg = (
                    f"✅ *Накладная успешно обработана!*\n\n"
                    f"• Всего позиций: {total_items}\n"
                    f"• Все позиции корректно сопоставлены\n\n"
                    f"Данные успешно загружены в Syrve."
                )
            
            # Устанавливаем состояние завершения
            await state.set_state(InvoiceStates.complete)
            
            # Отправляем итоговое сообщение
            await c.message.answer(msg, parse_mode="Markdown")
        else:
            # Ошибка при экспорте
            await c.message.answer(f"❌ Ошибка при экспорте в Syrve:\n{message}")
            # Возвращаемся к состоянию предварительного просмотра
            await state.set_state(InvoiceStates.preview)
    except Exception as e:
        logger.exception("Ошибка экспорта", error=str(e))
        await c.message.answer("❌ Произошла ошибка при обработке накладной.")
        # Возвращаемся к состоянию предварительного просмотра
        await state.set_state(InvoiceStates.preview)
    
    # Отвечаем на callback для скрытия часиков
    await c.answer()


@router.callback_query(F.data == "inv_edit")
async def cb_edit_invoice(c: CallbackQuery, state: FSMContext):
    """Обработчик для перехода к редактированию накладной."""
    # Получаем данные из состояния
    data = (await state.get_data()).get("invoice", {})
    issues = (await state.get_data()).get("issues", [])
    
    if not issues:
        await c.message.answer("✅ Нет позиций для исправления.")
        await c.answer()
        return
    
    # Обновляем данные в состоянии для редактора
    await state.update_data(current_issues=issues, fixed_issues={})
    
    # Переходим к состоянию списка проблем в редакторе
    await state.set_state(InvoiceEditStates.issue_list)
    
    # Форматируем сообщение со списком проблем
    message = make_issue_list(issues)
    
    # Создаем клавиатуру для списка проблем
    keyboard = []
    
    for i, issue in enumerate(issues, 1):
        index = issue.get("index", 0)
        original = issue.get("original", {})
        name = original.get("name", "")[:20]
        
        # Выбираем иконку в зависимости от типа проблемы
        if "Not in database" in issue.get("issue", ""):
            icon = "⚠"
        elif "incorrect match" in issue.get("issue", ""):
            icon = "❔"
        elif "Unit" in issue.get("issue", ""):
            icon = "🔄"
        else:
            icon = "❓"
        
        btn_text = f"{index}. {icon} {name}"
        keyboard.append([
            InlineKeyboardButton(text=btn_text, callback_data=f"issue:{index}")
        ])
    
    # Добавляем кнопку "Готово"
    keyboard.append([
        InlineKeyboardButton(text="✅ Готово", callback_data="inv_ok")
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    # Отправляем сообщение со списком проблем
    await c.message.answer(message, reply_markup=kb, parse_mode="Markdown")
    await c.answer()
