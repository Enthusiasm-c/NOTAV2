"""
Telegram bot router for Nota V2.

This module handles all Telegram bot interactions including:
- OCR processing of invoice images
- Parsing and validation of invoice data
- User interaction for invoice review and editing
"""

from __future__ import annotations

import structlog
from typing import Dict, List, Any, Optional, Tuple

from aiogram import Bot, Router, F
from aiogram.filters import CommandStart

from aiogram.filters import CommandStart
# Адаптивный импорт для разных версий aiogram
try:
    # aiogram 3.x.x
    from aiogram.filters import Text
except ImportError:
    # Если не найдено - создаем свою реализацию
    class Text:
        """Совместимая реализация фильтра Text."""
        def __init__(self, text=None):
            self.text = text if isinstance(text, list) else [text] if text else None
        
        def __call__(self, message):
            if hasattr(message, 'text'):
                return self.text is None or message.text in self.text
            elif hasattr(message, 'data'):
                return self.text is None or message.data in self.text
            return False
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)

# Импортируем модуль OCR и парсинга
from app.routers.gpt_combined import ocr_and_parse

# Импортируем unified_match для работы с сопоставлением товаров
from app.routers.fuzzy_match import fuzzy_match_product, find_similar_products

# Импортируем модуль unit_converter, если он доступен
try:
    from app.utils.unit_converter import normalize_unit, is_compatible_unit, convert
    UNIT_CONVERTER_AVAILABLE = True
except ImportError:
    UNIT_CONVERTER_AVAILABLE = False
    # Встроенные функции для работы с единицами измерения
    # (копия из unit_converter для обеспечения прямой работоспособности)
    
    # Unit normalization dictionary
    UNIT_ALIASES: Dict[str, str] = {
        # English volume units
        "l": "l", "ltr": "l", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
        "ml": "ml", "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml",
        
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
        "btl": "pcs",  # bottle/botol
    }
    
    def normalize_unit(unit_str: str) -> str:
        """
        Normalize unit string to standard format.
        """
        if not unit_str:
            return ""
        
        unit_str = unit_str.lower().strip()
        return UNIT_ALIASES.get(unit_str, unit_str)
    
    def is_compatible_unit(unit1: str, unit2: str) -> bool:
        """
        Check if two units are compatible (can be converted between each other).
        """
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

# Импортируем функции для создания UI
from app.utils.markdown import make_invoice_preview, make_issue_list

# Импортируем экспорт в Syrve
from app.routers.syrve_export import export_to_syrve

# Импортируем состояния FSM
from app.models.invoice_state import InvoiceStates, InvoiceEditStates

# Импортируем сессию для работы с БД
from app.config.database import get_engine_and_session
_, SessionLocal = get_engine_and_session()

# Импортируем настройки
from app.config import settings

logger = structlog.get_logger()
router = Router(name=__name__)

# --------------------------------------------------------------------------- #
#                             Вспомогательные функции                         #
# --------------------------------------------------------------------------- #

async def _run_pipeline(file_id: str, bot: Bot) -> dict:
    """Фото в Telegram → структурированный словарь (OCR+Parsing)."""
    try:
        # Пытаемся использовать оптимизированный объединенный вызов
        try:
            from app.routers.gpt_combined import ocr_and_parse
            _, parsed_data = await ocr_and_parse(file_id, bot)
            logger.info("Combined OCR+Parsing completed successfully",
                       positions_count=len(parsed_data.get("positions", [])))
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
            logger.warning("Invalid sum value", position=pos.get("name"), sum=pos.get("sum"))
    return total


async def get_product_details(session, product_id):
    """Получает детали продукта из базы данных"""
    if not product_id:
        return None
    
    from sqlalchemy import select
    from app.models.product import Product
    
    res = await session.execute(select(Product).where(Product.id == product_id))
    return res.scalar_one_or_none()


async def analyze_invoice_issues(data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    """
    Анализирует проблемы в накладной, сопоставляя товары с базой данных.
    
    Args:
        data: Данные накладной после OCR и парсинга
        
    Returns:
        Tuple[List[Dict], str]: (список проблем, комментарий)
    """
    issues = []
    unit_mismatches = 0
    unknown_items = 0
    wrong_matches = 0
    
    # Получаем только активные позиции (не удаленные)
    positions = [p for p in data.get("positions", []) if not p.get("deleted", False)]
    
    # Словарь для хранения информации о продуктах
    products_info = {}
    
    # Выполняем fuzzy-matching для каждой позиции и получаем информацию о продуктах
    async with SessionLocal() as session:
        for i, position in enumerate(positions):
            if not position.get("name"):
                continue
                
            # Нормализуем единицы измерения
            if "unit" in position and position["unit"]:
                position["unit"] = normalize_unit(position["unit"])
                
            # Выполняем fuzzy-matching
            product_id, confidence = await fuzzy_match_product(
                session, position["name"], settings.fuzzy_threshold
            )
            
            position["match_id"] = product_id
            position["confidence"] = confidence
            
            # Получаем информацию о продукте, если есть совпадение
            if product_id:
                product = await get_product_details(session, product_id)
                if product:
                    products_info[product_id] = product
                    
                    # Проверяем соответствие единиц измерения
                    invoice_unit = normalize_unit(position.get("unit", ""))
                    db_unit = normalize_unit(product.unit)
                    
                    if invoice_unit and db_unit and invoice_unit != db_unit:
                        if is_compatible_unit(invoice_unit, db_unit):
                            issues.append({
                                "index": i+1,
                                "invoice_item": f"{position.get('name', '')} ({invoice_unit})",
                                "db_item": f"{product.name} ({db_unit})",
                                "issue": "Unit conversion needed",
                                "original": position,
                                "product": product
                            })
                            unit_mismatches += 1
                        else:
                            issues.append({
                                "index": i+1,
                                "invoice_item": f"{position.get('name', '')} ({invoice_unit})",
                                "db_item": f"{product.name} ({db_unit})",
                                "issue": "Units incompatible",
                                "original": position,
                                "product": product
                            })
                            unit_mismatches += 1
                    
                    # Проверяем возможные ошибки сопоставления (низкая уверенность)
                    if confidence < 0.90 and position.get("name", "").lower() != product.name.lower():
                        issues.append({
                            "index": i+1,
                            "invoice_item": f"{position.get('name', '')}",
                            "db_item": f"{product.name}",
                            "issue": "Possible incorrect match",
                            "original": position,
                            "product": product
                        })
                        wrong_matches += 1
            else:
                # Нет совпадения в базе данных
                issues.append({
                    "index": i+1,
                    "invoice_item": f"{position.get('name', '')} ({position.get('unit', '')})",
                    "db_item": "—",
                    "issue": "Not in database",
                    "original": position
                })
                unknown_items += 1
    
    # Генерируем комментарий
    comments = []
    if unknown_items:
        comments.append(f"{unknown_items} unknown items")
    if unit_mismatches:
        comments.append(f"{unit_mismatches} unit measurement discrepancies")
    if wrong_matches:
        comments.append(f"{wrong_matches} potential incorrect matches")
    
    if comments:
        parser_comment = f"Found {', '.join(comments)}. See details below."
    else:
        parser_comment = "All items processed successfully."
    
    # Возвращаем результаты анализа
    return issues, parser_comment


# --------------------------------------------------------------------------- #
#                             Обработчики команд                              #
# --------------------------------------------------------------------------- #

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
    processing_msg = await m.answer("⏳ Обработка накладной...")
    
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
                InlineKeyboardButton(text="✅ Подтвердить и отправить", callback_data="inv_ok")
            ])
        
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        # Отправляем сообщение с результатами распознавания
        await m.answer(message, reply_markup=kb, parse_mode="Markdown")
        
    except Exception as exc:
        logger.exception("Ошибка обработки фото", exc_info=exc)
        await m.answer("❌ Не удалось распознать документ. Пожалуйста, попробуйте снова.")
    finally:
        # Возвращаемся к начальному состоянию, если была ошибка
        if await state.get_state() == InvoiceStates.ocr.state:
            await state.set_state(InvoiceStates.upload)


# --------------------------------------------------------------------------- #
#                       Обработчики основных callback'ов                      #
# --------------------------------------------------------------------------- #

@router.callback_query(Text("inv_ok"))
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
    status_msg = await c.message.answer("⏳ Экспорт в Syrve...")
    
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


@router.callback_query(Text("inv_edit"))
async def cb_edit_invoice(c: CallbackQuery, state: FSMContext):
    """
    Обработчик для перехода к редактированию накладной.
    
    Переводит FSM в состояние списка проблем InvoiceEditStates.issue_list
    и передает управление модулю issue_editor.py
    """
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
    # Эта клавиатура будет обработана модулем issue_editor.py
    keyboard = []
    
    for i, issue in enumerate(issues):
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
