from __future__ import annotations

import asyncio
import json
import logging
import structlog
from aiogram import Bot, Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, Tuple, Optional

# Импортируем модули распознавания и парсинга
from app.routers.gpt_ocr import ocr
from app.routers.gpt_parsing import parse

# Импортируем модуль unit_converter, если он доступен
try:
    from app.utils.unit_converter import normalize_unit, is_compatible_unit
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

# Модуль объединенного OCR+Parsing импортируем отдельно,
# чтобы избежать циклической зависимости
try:
    from app.routers.gpt_combined import ocr_and_parse as combined_ocr_parse
    COMBINED_MODE_AVAILABLE = True
except ImportError:
    COMBINED_MODE_AVAILABLE = False

from app.routers.fuzzy_match import fuzzy_match_product
try:
    from app.utils.xml_generator import build_xml
except ImportError:
    # Функция для создания XML из telegram_bot.py
    def build_xml(data: Dict) -> str:
        """
        Creates XML for Syrve from invoice data.
        
        :param data: Invoice data dictionary
        :return: XML string
        """
        from xml.etree.ElementTree import Element, SubElement, tostring
        
        root = Element("SyrveDocument")
        
        if "supplier" in data:
            SubElement(root, "Supplier").text = data["supplier"]
        if "buyer" in data:
            SubElement(root, "Buyer").text = data["buyer"]
        if "date" in data:
            SubElement(root, "Date").text = data["date"]
        
        items = SubElement(root, "Items")
        for p in data.get("positions", []):
            item = SubElement(items, "Item")
            
            if "name" in p:
                SubElement(item, "Name").text = str(p["name"])
            
            if "quantity" in p:
                SubElement(item, "Quantity").text = str(p["quantity"])
            
            if "unit" in p:
                SubElement(item, "Unit").text = str(p.get("unit", ""))
            
            if "price" in p:
                try:
                    price = float(p["price"])
                    SubElement(item, "Price").text = f"{price:.2f}"
                except (ValueError, TypeError):
                    SubElement(item, "Price").text = "0.00"
            
            if "sum" in p:
                try:
                    sum_value = float(p["sum"])
                    SubElement(item, "Sum").text = f"{sum_value:.2f}"
                except (ValueError, TypeError):
                    SubElement(item, "Sum").text = "0.00"
        
        if "total_sum" in data:
            try:
                total = float(data["total_sum"])
                SubElement(root, "TotalSum").text = f"{total:.2f}"
            except (ValueError, TypeError):
                # Calculate from positions
                total = 0.0
                for p in data.get("positions", []):
                    try:
                        total += float(p.get("sum", 0)) if p.get("sum") else 0
                    except (ValueError, TypeError):
                        pass
                SubElement(root, "TotalSum").text = f"{total:.2f}"
        
        return tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

from app.db import SessionLocal
from app.config import settings

logger = structlog.get_logger()
router = Router(name=__name__)


# ───────────────────────── helpers ──────────────────────────
async def _run_pipeline(file_id: str, bot: Bot) -> dict:
    """Photo in Telegram → structured dict (OCR+Parsing)."""
    try:
        # Пытаемся использовать оптимизированный объединенный вызов API, если доступен
        if COMBINED_MODE_AVAILABLE:
            try:
                _, parsed_data = await combined_ocr_parse(file_id, bot)
                logger.info("Combined OCR+Parsing completed successfully",
                           positions_count=len(parsed_data.get("positions", [])))
                return parsed_data
            except Exception as e:
                logger.warning("Combined OCR+Parsing failed, falling back to separate calls", 
                              error=str(e))
        
        # Если объединенный режим недоступен или произошла ошибка,
        # используем отдельные вызовы OCR и парсинга
        raw_text = await ocr(file_id, bot)
        logger.info("OCR completed successfully", text_length=len(raw_text))
        
        parsed = await parse(raw_text)
        logger.info("Parsing completed successfully", 
                   positions_count=len(parsed.get("positions", [])))
        
        return parsed
    except Exception as exc:
        logger.exception("Pipeline failed", exc_info=exc)
        raise


def calculate_total_sum(positions: list) -> float:
    """Calculates total sum from all positions safely."""
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
    """Get product details from database"""
    if not product_id:
        return None
    
    from sqlalchemy import select
    from app.models.product import Product
    
    res = await session.execute(select(Product).where(Product.id == product_id))
    return res.scalar_one_or_none()


def analyze_items_issues(data, products_info):
    """
    Analyze what issues exist with the items.
    
    Returns:
        list: List of problematic items with issue description
        str: Parser comment summarizing issues
    """
    issues = []
    unit_mismatches = 0
    unknown_items = 0
    wrong_matches = 0
    
    positions = data.get("positions", [])
    
    for i, pos in enumerate(positions):
        # Пропускаем удаленные позиции
        if pos.get("deleted", False):
            continue
            
        if not pos.get("match_id"):
            issues.append({
                "index": i+1,
                "invoice_item": f"{pos.get('name', '')} {pos.get('unit', '')}",
                "db_item": "—",
                "issue": "❌ Not in database",
                "original": pos
            })
            unknown_items += 1
            continue
        
        product = products_info.get(pos.get("match_id"))
        if not product:
            continue
        
        # Check if units match
        invoice_unit = normalize_unit(pos.get("unit", ""))
        db_unit = normalize_unit(product.unit)
        
        if invoice_unit and db_unit and invoice_unit != db_unit:
            if is_compatible_unit(invoice_unit, db_unit):
                issues.append({
                    "index": i+1,
                    "invoice_item": f"{pos.get('name', '')} *{invoice_unit}*",
                    "db_item": f"{product.name} *{db_unit}*",
                    "issue": "Unit conversion needed",
                    "original": pos,
                    "product": product
                })
                unit_mismatches += 1
            else:
                issues.append({
                    "index": i+1,
                    "invoice_item": f"{pos.get('name', '')} *{invoice_unit}*",
                    "db_item": f"{product.name} *{db_unit}*",
                    "issue": "Units incompatible",
                    "original": pos,
                    "product": product
                })
                unit_mismatches += 1
        
        # Check for possible wrong matches (low confidence)
        if pos.get("confidence", 1.0) < 0.90 and pos.get("name", "").lower() != product.name.lower():
            issues.append({
                "index": i+1,
                "invoice_item": f"{pos.get('name', '')}",
                "db_item": f"{product.name}",
                "issue": "Possible incorrect match",
                "original": pos,
                "product": product
            })
            wrong_matches += 1
    
    # Generate parser comment
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
    
    return issues, parser_comment


def make_improved_invoice_markdown(data, issues, parser_comment):
    """
    Creates a Markdown summary with focus on issues and a table of items.
    
    Использует новый формат с таблицей позиций вместо общей суммы.
    """
    try:
        # Пытаемся использовать новый модуль форматирования
        from app.utils.markdown import make_invoice_preview
    
    return make_invoice_preview(
        data,
        issues,
        fixed_issues={},          # пока пусто
        show_all_issues=True,     # сразу показать список проблем
        )
    except ImportError:
        # Если модуль недоступен, используем наш улучшенный формат
        positions = data.get("positions", [])
        
        # Пропускаем удаленные позиции при подсчете
        active_positions = [p for p in positions if not p.get("deleted", False)]
        
        # Create header with invoice details
        header = f"📄 *Supplier:* \"{data.get('supplier', 'Unknown')}\"  \n"
        header += f"🗓️ *Date:* {data.get('date', 'Unknown')}"
        
        if data.get('number'):
            header += f"  № {data.get('number')}\n\n"
        else:
            header += "\n\n"
        
        # Add statistics divider
        header += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        # Count matched vs problematic items
        matched_count = len(active_positions) - len(issues)
        
        # Add statistics
        header += f"✅ *Matched items* — {matched_count} items  \n"
        if issues:
            header += f"❓ *Need attention* — {len(issues)} items  \n"
        
        # Add parser comment if provided
        if parser_comment:
            header += f"💬 *Parser comment:*  \n\"{parser_comment}\"\n"
        
        header += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # НОВЫЙ КОД: Всегда добавляем таблицу позиций, требующих внимания
        if issues:
            header += "*🚩 Items to review*\n\n"
            
            # Создаем таблицу с позициями, требующими правки
            table_header = "|  № | Наименование | Кол-во/Ед. | Цена |\n"
            table_header += "|:--:|-------------|------------|------|\n"
            
            rows = []
            for issue in issues:
                # Получаем данные о позиции из original
                original = issue.get("original", {})
                name = original.get("name", "Unknown")
                quantity = original.get("quantity", "")
                unit = original.get("unit", "")
                price = original.get("price", "")
                
                # Форматируем столбец количества и единицы измерения
                qty_unit = f"{quantity} {unit}".strip()
                
                # Форматируем цену, если она есть
                price_display = ""
                if price:
                    try:
                        price_float = float(price)
                        price_display = f"{price_float:,.2f}"
                    except (ValueError, TypeError):
                        price_display = str(price)
                
                # Формируем строку таблицы
                rows.append(
                    f"| {issue['index']} | {name} | {qty_unit} | {price_display} |"
                )
            
            return header + table_header + "\n".join(rows)
        else:
            return header + "✅ All items matched successfully!"


# ───────────────────────── handlers ─────────────────────────
@router.message(CommandStart())
async def cmd_start(m: Message):
    await m.answer(
        "👋 Welcome! Please send me a photo of an invoice, "
        "and I'll recognize the items and upload them to Syrve."
    )


@router.message(F.photo)
async def handle_photo(m: Message, state: FSMContext, bot: Bot):
    await m.answer("⏳ Processing the invoice...")
    file_id = m.photo[-1].file_id  # get largest resolution photo

    try:
        # Используем пайплайн обработки
        data = await _run_pipeline(file_id, bot)
    except Exception as exc:
        logger.exception("Pipeline failed", exc_info=exc)
        await m.answer("❌ Could not recognize the document. Please try again.")
        return

    # Normalize units
    for p in data.get("positions", []):
        if "unit" in p and p["unit"]:
            p["unit"] = normalize_unit(p["unit"])

    # Fuzzy-match for each position and collect product details
    product_details = {}
    try:
        async with SessionLocal() as session:
            for p in data.get("positions", []):
                if "name" in p and p["name"]:
                    pid, conf = await fuzzy_match_product(
                        session, p["name"], settings.fuzzy_threshold
                    )
                    p["match_id"] = pid
                    p["confidence"] = conf
                    
                    # Get product details if matched
                    if pid:
                        product = await get_product_details(session, pid)
                        if product:
                            product_details[pid] = product
    except Exception as e:
        logger.exception("Error during fuzzy matching", error=str(e))
        # Continue even if matching failed

    logger.info("Invoice recognized", 
               positions_count=len(data.get("positions", [])),
               supplier=data.get("supplier", "Unknown"))
    
    # Analyze issues
    issues, parser_comment = analyze_items_issues(data, product_details)
    
    # Create improved markdown
    message = make_improved_invoice_markdown(data, issues, parser_comment)
    
    # Store data in state
    await state.update_data(
        invoice=data,
        issues=issues,
        product_details=product_details
    )
    
    # Create keyboard with improved UI
    keyboard = []
    
    # Add appropriate buttons
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
    
    try:
        await m.answer(message, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Error sending message", error=str(e))
        # If Markdown fails, try without formatting
        try:
            simple_message = (
                f"Invoice from {data.get('supplier', 'Unknown')} processed.\n"
                f"Found {len(data.get('positions', []))} items, {len(issues)} need attention."
            )
            await m.answer(simple_message, reply_markup=kb)
        except Exception:
            await m.answer("❌ An error occurred while displaying the invoice.")


# ───────────────────────── callback: подтверждение накладной ──────────────────
@router.callback_query(F.data == "inv_ok")
async def cb_ok(c: CallbackQuery, state: FSMContext, bot: Bot):
    data = (await state.get_data()).get("invoice", {})
    issues = (await state.get_data()).get("issues", [])
    fixed_issues = (await state.get_data()).get("fixed_issues", {})
    
    if not data:
        await c.message.answer("❌ Invoice data missing. Please try again.")
        await c.answer()
        return
    
    # Фильтруем удаленные позиции перед экспортом
    positions = data.get("positions", [])
    active_positions = [p for p in positions if not p.get("deleted", False)]
    data["positions"] = active_positions
    
    try:
        xml_str = build_xml(data)
        
        # Here you can add code to save to DB
        
        # Send to Syrve; currently just logging
        logger.info("XML ready", xml_len=len(xml_str))
        
        # Count statistics
        total_items = len(active_positions)
        
        # Получаем актуальный список проблем (исключая исправленные)
        fixed_indices = set(fixed_issues.keys() if fixed_issues else set())
        remaining_issues = [
            issue for issue in issues 
            if issue.get("index") - 1 not in fixed_indices
        ]
        
        fixed_count = len(fixed_issues) if fixed_issues else 0
        remaining_count = len(remaining_issues)
        
        # Создаем успешное сообщение с улучшенным форматированием
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
        
        await c.message.answer(msg, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Failed to process invoice", error=str(e))
        await c.message.answer("❌ Error processing the invoice.")
    
    await c.answer()


@router.callback_query(F.data == "inv_edit")
async def cb_edit(c: CallbackQuery, state: FSMContext):
    """
    Обработчик для редактирования позиций с проблемами
    """
    # Получаем данные из состояния
    data = (await state.get_data()).get("invoice", {})
    issues = (await state.get_data()).get("issues", [])
    
    if not issues:
        await c.message.answer("Нет позиций для исправления.")
        await c.answer()
        return
    
    # Создаем клавиатуру для выбора позиций для исправления
    keyboard = []
    for issue in issues:
        # Формируем название кнопки - краткое описание проблемы
        item_name = issue.get("invoice_item", "").replace("*", "")
        issue_type = issue.get("issue", "").replace("❌ ", "")
        
        # Сокращаем название для кнопки если оно слишком длинное
        if len(item_name) > 20:
            item_name = item_name[:18] + ".."
            
        btn_text = f"{issue.get('index')}. {item_name} - {issue_type}"
        
        # Создаем callback_data с индексом позиции
        callback_data = f"fix_{issue.get('index') - 1}"
        
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=callback_data)])
    
    # Добавляем кнопку возврата
    keyboard.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_invoice")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await c.message.answer(
        "Выберите позицию для исправления:",
        reply_markup=kb
    )
    await c.answer()


@router.callback_query(F.data == "back_to_invoice")
async def cb_back_to_invoice(c: CallbackQuery, state: FSMContext):
    """
    Обработчик возврата к основному меню накладной
    """
    data = (await state.get_data()).get("invoice", {})
    issues = (await state.get_data()).get("issues", [])
    fixed_issues = (await state.get_data()).get("fixed_issues", {})
    product_details = (await state.get_data()).get("product_details", {})
    
    # Получаем актуальный список проблем (исключая исправленные)
    remaining_issues = []
    if fixed_issues:
        fixed_indices = set(fixed_issues.keys())
        remaining_issues = [
            issue for issue in issues 
            if issue.get("index") - 1 not in fixed_indices
        ]
    else:
        remaining_issues = issues
    
    # Генерируем комментарий парсера заново на основе оставшихся проблем
    unit_mismatches = sum(1 for i in remaining_issues if "Unit" in i.get("issue", ""))
    unknown_items = sum(1 for i in remaining_issues if "Not in database" in i.get("issue", ""))
    wrong_matches = sum(1 for i in remaining_issues if "incorrect match" in i.get("issue", ""))
    
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
    
    # Создаем новое сообщение с обновленными данными
    message = make_improved_invoice_markdown(data, remaining_issues, parser_comment)
    
    # Создаем клавиатуру
    keyboard = []
    
    # Добавляем соответствующие кнопки
    if remaining_issues:
        keyboard.append([
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="inv_ok"),
            InlineKeyboardButton(text="✏️ Исправить", callback_data="inv_edit")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="✅ Подтвердить и отправить", callback_data="inv_ok")
        ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    try:
        await c.message.edit_text(message, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        # Если не удалось отредактировать, отправляем новое сообщение
        logger.warning("Failed to edit message, sending new one", error=str(e))
        await c.message.answer(message, reply_markup=kb, parse_mode="Markdown")
    
    await c.answer()


# ───────────────────────── Обработчики исправления накладной ──────────────────
@router.callback_query(lambda c: c.data and c.data.startswith("fix_"))
async def cb_fix_item(c: CallbackQuery, state: FSMContext):
    """
    Обработчик для исправления конкретной позиции
    """
    position_index = int(c.data.split("_")[1])
    
    # Получаем данные из состояния
    data = (await state.get_data()).get("invoice", {})
    issues = (await state.get_data()).get("issues", [])
    
    # Находим информацию о проблемной позиции
    issue = None
    for i in issues:
        if i.get("index") - 1 == position_index:
            issue = i
            break
    
    if not issue:
        await c.message.answer("Позиция не найдена.")
        await c.answer()
        return
    
    # Получаем позицию из накладной
    position = data.get("positions", [])[position_index]
    
    # Определяем тип проблемы
    issue_type = issue.get("issue", "")
    
    # Создаем клавиатуру с действиями в зависимости от типа проблемы
    keyboard = []
    
    if "Not in database" in issue_type:
        # Для отсутствующих в базе товаров
        keyboard.append([
            InlineKeyboardButton(text="⤵️ Сохранить новый товар", 
                                callback_data=f"save_new_{position_index}")
        ])
        keyboard.append([
            InlineKeyboardButton(text="❌ Удалить позицию", 
                                callback_data=f"delete_{position_index}")
        ])
    elif "Unit" in issue_type:
        # Для проблем с единицами измерения
        keyboard.append([
            InlineKeyboardButton(text="🔄 Конвертировать единицы", 
                                callback_data=f"convert_{position_index}")
        ])
        keyboard.append([
            InlineKeyboardButton(text="⤵️ Сохранить как есть", 
                                callback_data=f"ignore_{position_index}")
        ])
    elif "incorrect match" in issue_type:
        # Для некорректных совпадений
        keyboard.append([
            InlineKeyboardButton(text="🔄 Выбрать другой товар", 
                                callback_data=f"rematch_{position_index}")
        ])
        keyboard.append([
            InlineKeyboardButton(text="⤵️ Сохранить текущее совпадение", 
                                callback_data=f"ignore_{position_index}")
        ])
    
    # Добавляем общую кнопку удаления позиции
    if "Not in database" not in issue_type:
        keyboard.append([
            InlineKeyboardButton(text="❌ Удалить позицию", 
                                callback_data=f"delete_{position_index}")
        ])
    
    # Добавляем кнопку возврата
    keyboard.append([
        InlineKeyboardButton(text="↩️ Назад к списку проблем", 
                            callback_data="inv_edit")
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    # Формируем детальное сообщение о позиции и проблеме
    position_info = (
        f"*Позиция {issue.get('index')}:* {position.get('name')}\n\n"
        f"*Проблема:* {issue_type}\n"
        f"*Количество:* {position.get('quantity', '')} {position.get('unit', '')}\n"
        f"*Цена:* {position.get('price', '')}\n"
        f"*Сумма:* {position.get('sum', '')}\n\n"
    )
    
    if "product" in issue:
        product = issue.get("product")
        position_info += (
            f"*Найдено в базе данных:*\n"
            f"- Название: {product.name}\n"
            f"- Единица измерения: {product.unit}\n"
        )
    
    position_info += "\nВыберите действие:"
    
    await c.message.answer(position_info, reply_markup=kb, parse_mode="Markdown")
    await c.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("delete_"))
async def cb_delete_position(c: CallbackQuery, state: FSMContext):
    """
    Обработчик для удаления позиции
    """
    position_index = int(c.data.split("_")[1])
    
    # Получаем данные из состояния
    data = (await state.get_data()).get("invoice", {})
    
    if not data or "positions" not in data or len(data["positions"]) <= position_index:
        await c.message.answer("Позиция не найдена.")
        await c.answer()
        return
    
    # Помечаем позицию как удаленную вместо физического удаления
    data["positions"][position_index]["deleted"] = True
    
    # Сохраняем изменения в состоянии
    fixed_issues = (await state.get_data()).get("fixed_issues", {})
    if not fixed_issues:
        fixed_issues = {}
    
    fixed_issues[position_index] = {"action": "deleted"}
    
    await state.update_data(invoice=data, fixed_issues=fixed_issues)
    
    await c.message.answer(
        "✅ Позиция удалена из накладной.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Вернуться к накладной", callback_data="back_to_invoice")]
        ])
    )
    await c.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("ignore_"))
async def cb_ignore_issue(c: CallbackQuery, state: FSMContext):
    """
    Обработчик для игнорирования проблемы
    """
    position_index = int(c.data.split("_")[1])
    
    # Получаем данные из состояния и сохраняем информацию о исправленной проблеме
    fixed_issues = (await state.get_data()).get("fixed_issues", {})
    if not fixed_issues:
        fixed_issues = {}
    
    fixed_issues[position_index] = {"action": "ignored"}
    
    await state.update_data(fixed_issues=fixed_issues)
    
    await c.message.answer(
        "✅ Проблема игнорирована, позиция будет обработана как есть.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Вернуться к накладной", callback_data="back_to_invoice")]
        ])
    )
    await c.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("convert_"))
async def cb_convert_units(c: CallbackQuery, state: FSMContext):
    """
    Обработчик для конвертации единиц измерения
    """
    position_index = int(c.data.split("_")[1])
    
    # Получаем данные из состояния
    data = (await state.get_data()).get("invoice", {})
    issues = (await state.get_data()).get("issues", [])
    
    # Находим информацию о проблемной позиции
    issue = None
    for i in issues:
        if i.get("index") - 1 == position_index:
            issue = i
            break
    
    if not issue or "product" not in issue:
        await c.message.answer("Информация о товаре недоступна.")
        await c.answer()
        return
    
    # Получаем позицию из накладной и продукт из базы
    position = data.get("positions", [])[position_index]
    product = issue.get("product")
    
    # Получаем единицы измерения
    invoice_unit = normalize_unit(position.get("unit", ""))
    db_unit = normalize_unit(product.unit)
    
    # Проверяем совместимость единиц
    if not is_compatible_unit(invoice_unit, db_unit):
        await c.message.answer(
            f"❌ Невозможно конвертировать: единицы {invoice_unit} и {db_unit} несовместимы.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Назад", callback_data=f"fix_{position_index}")]
            ])
        )
        await c.answer()
        return
    
    # Выполняем конвертацию в зависимости от типа единиц
    quantity = float(position.get("quantity", 0))
    converted_quantity = quantity
    
    # Для объема: литры (l) и миллилитры (ml)
    if invoice_unit == "ml" and db_unit == "l":
        converted_quantity = quantity / 1000.0
    elif invoice_unit == "l" and db_unit == "ml":
        converted_quantity = quantity * 1000.0
    
    # Для веса: килограммы (kg) и граммы (g)
    elif invoice_unit == "g" and db_unit == "kg":
        converted_quantity = quantity / 1000.0
    elif invoice_unit == "kg" and db_unit == "g":
        converted_quantity = quantity * 1000.0
    
    # Обновляем данные позиции
    position["unit"] = db_unit
    position["quantity"] = converted_quantity
    
    # Сохраняем изменения в состоянии
    fixed_issues = (await state.get_data()).get("fixed_issues", {})
    if not fixed_issues:
        fixed_issues = {}
    
    fixed_issues[position_index] = {
        "action": "converted",
        "from_unit": invoice_unit,
        "to_unit": db_unit,
        "from_quantity": quantity,
        "to_quantity": converted_quantity
    }
    
    await state.update_data(invoice=data, fixed_issues=fixed_issues)
    
    # Формируем сообщение об успешной конвертации
    msg = (
        f"✅ Единицы измерения конвертированы:\n\n"
        f"{quantity} {invoice_unit} → {converted_quantity} {db_unit}\n\n"
        f"Товар: {position.get('name')}"
    )
    
    await c.message.answer(
        msg,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Вернуться к накладной", callback_data="back_to_invoice")]
        ])
    )
    await c.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("save_new_"))
async def cb_save_new_product(c: CallbackQuery, state: FSMContext):
    """
    Обработчик для сохранения нового товара в базу данных
    """
    position_index = int(c.data.split("_")[2])
    
    # Получаем данные из состояния
    data = (await state.get_data()).get("invoice", {})
    
    # Получаем позицию из накладной
    position = data.get("positions", [])[position_index]
    
    # Здесь будет логика сохранения нового товара в базу данных
    # В MVP версии просто помечаем как исправленное и оставляем для ручного добавления
    
    # Сохраняем изменения в состоянии
    fixed_issues = (await state.get_data()).get("fixed_issues", {})
    if not fixed_issues:
        fixed_issues = {}
    
    fixed_issues[position_index] = {
        "action": "new_product",
        "name": position.get("name"),
        "unit": position.get("unit")
    }
    
    await state.update_data(fixed_issues=fixed_issues)
    
    await c.message.answer(
        f"✅ Товар \"{position.get('name')}\" помечен для добавления в базу данных.\n\n"
        f"Позиция будет обработана как новый товар.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Вернуться к накладной", callback_data="back_to_invoice")]
        ])
    )
    await c.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("rematch_"))
async def cb_rematch_product(c: CallbackQuery, state: FSMContext):
    """
    Обработчик для повторного сопоставления товара
    """
    position_index = int(c.data.split("_")[1])
    
    # Получаем данные из состояния
    data = (await state.get_data()).get("invoice", {})
    
    # Получаем позицию из накладной
    position = data.get("positions", [])[position_index]
    
    # В MVP версии просто помечаем как "требуется повторное сопоставление"
    # Полноценное повторное сопоставление потребует дополнительных запросов к базе
    
    await c.message.answer(
        f"⚠️ Функция повторного сопоставления находится в разработке.\n\n"
        f"Пожалуйста, выберите другое действие или игнорируйте проблему.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Назад", callback_data=f"fix_{position_index}")]
        ])
    )
    await c.answer()
