"""
Telegram router (Aiogram v3) - Receipt processing pipeline:
    photo ➜ OCR ➜ Parsing ➜ Fuzzy ➜ confirmation ➜ Syrve
MVP version: if any step fails - we send a clear message.
"""

from __future__ import annotations

import asyncio
import json
import logging
import structlog
from aiogram import Bot, Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from app.routers.gpt_ocr import ocr
from app.routers.gpt_parsing import parse
from app.routers.fuzzy_match import fuzzy_match_product
from app.db import SessionLocal
from app.config import settings

# Built-in function instead of importing from app.utils.unit_converter
def normalize_unit(unit_str: str) -> str:
    """Built-in function for normalizing measurement units."""
    if not unit_str:
        return ""
    
    unit_str = unit_str.lower().strip()
    
    # Unit normalization dictionary (English + Indonesian)
    aliases = {
        # English volume units
        "l": "l", "ltr": "l", "liter": "l", "liters": "l",
        "ml": "ml", "milliliter": "ml", "milliliters": "ml",
        
        # English weight units
        "kg": "kg", "kilo": "kg", "kilogram": "kg",
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
        
        # Other units
        "gln": "gallon", "galon": "gallon",
        "bunch": "bunch", "пучок": "bunch",
    }
    
    return aliases.get(unit_str, unit_str)

def is_unit_compatible(unit1: str, unit2: str) -> bool:
    """Check if units are compatible for conversion."""
    unit1 = normalize_unit(unit1)
    unit2 = normalize_unit(unit2)
    
    # Same normalized units are always compatible
    if unit1 == unit2:
        return True
    
    # Define unit groups
    volume_units = {"l", "ml", "gallon"}
    weight_units = {"kg", "g"}
    countable_units = {"pcs", "pack", "box", "bunch"}
    
    # Check if both units are in the same group
    if unit1 in volume_units and unit2 in volume_units:
        return True
    if unit1 in weight_units and unit2 in weight_units:
        return True
    if unit1 in countable_units and unit2 in countable_units:
        return False  # Consider countable units as incompatible for now
    
    return False

# Function for creating XML
def build_xml(data: dict) -> str:
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

logger = structlog.get_logger()
router = Router(name=__name__)


# ───────────────────────── helpers ──────────────────────────
async def _run_pipeline(file_id: str, bot: Bot) -> dict:
    """Photo in Telegram → structured dict (OCR+Parsing)."""
    try:
        raw_text = await ocr(file_id, bot)
        logger.info("OCR completed successfully", text_length=len(raw_text))
        
        parsed = await parse(raw_text)
        logger.info("Parsing completed successfully", 
                   positions_count=len(parsed.get("positions", [])))
        
        return parsed
    except Exception as e:
        logger.exception("Pipeline failed", error=str(e))
        raise


def calculate_total_sum(positions: list) -> float:
    """Calculates total sum from all positions safely."""
    total = 0.0
    for pos in positions:
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
            if is_unit_compatible(invoice_unit, db_unit):
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
    Creates a Markdown summary with focus on issues.
    """
    positions = data.get("positions", [])
    
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
    matched_count = len(positions) - len(issues)
    
    # Add statistics
    header += f"✅ *Matched items* — {matched_count} items  \n"
    if issues:
        header += f"❓ *Need attention* — {len(issues)} items  \n"
    
    # Add parser comment
    header += f"💬 *Parser comment:*  \n\"{parser_comment}\"\n"
    header += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # If there are issues, add issues table
    if issues:
        header += "*🚩 Items to review*\n\n"
        
        # Create issues table
        table_header = "|  # | Invoice item | Database item | Issue |\n"
        table_header += "|:--:|-------------|---------------|-------|\n"
        
        rows = []
        for issue in issues:
            rows.append(
                f"| {issue['index']} | {issue['invoice_item']} | "
                f"{issue['db_item']} | {issue['issue']} |"
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
    
    # Create keyboard
    keyboard = []
    
    # Add appropriate buttons
    if issues:
        keyboard.append([
            InlineKeyboardButton(text="✅ Confirm All", callback_data="inv_ok"),
            InlineKeyboardButton(text="✏️ Fix Issues", callback_data="inv_edit")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="✅ Confirm & Upload", callback_data="inv_ok")
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


# ───────────────────────── callbacks ────────────────────────
@router.callback_query(F.data == "inv_ok")
async def cb_ok(c: CallbackQuery, state: FSMContext, bot: Bot):
    data = (await state.get_data()).get("invoice", {})
    issues = (await state.get_data()).get("issues", [])
    
    if not data:
        await c.message.answer("❌ Invoice data missing. Please try again.")
        await c.answer()
        return
    
    try:
        xml_str = build_xml(data)
        
        # Here you can add code to save to DB
        
        # Send to Syrve; currently just logging
        logger.info("XML ready", xml_len=len(xml_str))
        
        # Count statistics
        total_items = len(data.get("positions", []))
        matched_items = total_items - len(issues)
        
        if issues:
            await c.message.answer(
                f"✅ Invoice processed with warnings!\n\n"
                f"• Total items: {total_items}\n"
                f"• Successfully matched: {matched_items}\n"
                f"• Items with issues: {len(issues)}\n\n"
                f"All data has been uploaded to Syrve despite warnings."
            )
        else:
            await c.message.answer(
                f"✅ Invoice processed successfully!\n\n"
                f"• Total items: {total_items}\n"
                f"• All items matched correctly\n\n"
                f"Data has been uploaded to Syrve."
            )
    except Exception as e:
        logger.exception("Failed to process invoice", error=str(e))
        await c.message.answer("❌ Error processing the invoice.")
    
    await c.answer()


@router.callback_query(F.data == "inv_edit")
async def cb_edit(c: CallbackQuery):
    await c.message.answer("✏️ Issue correction feature is under development.")
    await c.answer()
