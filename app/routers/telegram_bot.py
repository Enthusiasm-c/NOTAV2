"""
Telegram-router  (Aiogram v3)  – приём накладных и весь пайплайн:
    фото ➜ OCR ➜ Parsing ➜ Fuzzy ➜ подтверждение ➜ Syrve
MVP-вариант: если любой шаг падает – посылаем понятное сообщение.
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

# Встроенная функция вместо импорта из app.utils.unit_converter
def normalize_unit(unit_str: str) -> str:
    """Встроенная функция нормализации единиц измерения."""
    if not unit_str:
        return ""
    
    unit_str = unit_str.lower().strip()
    
    # Словарь нормализации единиц измерения (English + Indonesian)
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
    }
    
    return aliases.get(unit_str, unit_str)

# Функция для создания XML
def build_xml(data: dict) -> str:
    """
    Формирует XML для Syrve из словаря данных накладной.
    
    :param data: Словарь с данными накладной
    :return: XML-строка
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
    for pos in data.get("positions", []):
        item = SubElement(items, "Item")
        if "name" in pos:
            SubElement(item, "Name").text = pos["name"]
        if "quantity" in pos:
            SubElement(item, "Quantity").text = str(pos["quantity"])
        if "unit" in pos:
            SubElement(item, "Unit").text = str(pos.get("unit", ""))
        if "price" in pos:
            SubElement(item, "Price").text = f"{pos.get('price', 0):.2f}"
        if "sum" in pos:
            SubElement(item, "Sum").text = f"{pos.get('sum', 0):.2f}"
    
    if "total_sum" in data:
        SubElement(root, "TotalSum").text = f"{data['total_sum']:.2f}"
    
    return tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

logger = structlog.get_logger()
router = Router(name=__name__)


# ───────────────────────── helpers ──────────────────────────
async def _run_pipeline(file_id: str, bot: Bot) -> dict:
    """Фото в Telegram → структурированный dict (OCR+Parsing)."""
    try:
        raw_text = await ocr(file_id, bot)          # может бросить исключение
        logger.info("OCR completed successfully", text_length=len(raw_text))
        
        parsed = await parse(raw_text)            # может бросить исключение
        logger.info("Parsing completed successfully", 
                   positions_count=len(parsed.get("positions", [])))
        
        return parsed
    except Exception as e:
        logger.exception("Pipeline failed", error=str(e))
        raise


def positions_summary(data: dict) -> str:
    """Формирует текстовое описание позиций накладной"""
    return "\n".join(
        f"• {p['name']} × {p.get('quantity', '')} {p.get('unit', '')}"
        for p in data.get("positions", [])
    )


def make_invoice_markdown(draft: dict) -> str:
    """Формирует Markdown-таблицу накладной (№, Наименование, Кол-во × Цена, Сумма)"""
    header = "| № | Наименование | Кол-во | Ед. | Цена | Сумма |\n|---|--------------|--------|-----|------|-------|"
    rows = []
    positions = draft.get("positions", [])
    for i, pos in enumerate(positions, 1):
        rows.append(
            f"| {i} | {pos.get('name', '')} | {pos.get('quantity', '')} | {pos.get('unit', '')} | "
            f"{pos.get('price', '')} | {pos.get('sum', '')} |"
        )
    
    # Безопасный расчет общей суммы
    total = 0.0
    for pos in positions:
        try:
            pos_sum = float(pos.get("sum", 0)) if pos.get("sum") else 0
            total += pos_sum
        except (ValueError, TypeError):
            logger.warning("Invalid sum value", position=pos.get("name"), sum=pos.get("sum"))
    
    footer = f"\n\n**Итого:** `{total:.2f}`"
    return "\n".join([header] + rows) + footer


# ───────────────────────── handlers ─────────────────────────
@router.message(CommandStart())
async def cmd_start(m: Message):
    await m.answer(
        "👋 Привет! Пришлите фото накладной, я распознаю позиции и загружу в Syrve."
    )


@router.message(F.photo)
async def handle_photo(m: Message, state: FSMContext, bot: Bot):
    await m.answer("⏳ Обрабатываю накладную…")
    file_id = m.photo[-1].file_id  # берём фото с макс. разрешением

    try:
        data = await _run_pipeline(file_id, bot)
    except Exception as exc:
        logger.exception("Pipeline failed", exc_info=exc)
        await m.answer("❌ Не удалось распознать документ. Попробуйте ещё раз.")
        return

    # Нормализуем единицы измерения
    for p in data.get("positions", []):
        if "unit" in p and p["unit"]:
            p["unit"] = normalize_unit(p["unit"])

    # fuzzy-match для каждой позиции (асинхронный БД-сеанс)
    try:
        async with SessionLocal() as session:
            for p in data.get("positions", []):
                if "name" in p and p["name"]:
                    pid, conf = await fuzzy_match_product(
                        session, p["name"], settings.fuzzy_threshold
                    )
                    p["match_id"] = pid
                    p["confidence"] = conf
    except Exception as e:
        logger.exception("Error during fuzzy matching", error=str(e))
        # Продолжаем работу даже если не удалось сопоставить товары

    logger.info("Invoice recognized", 
               positions_count=len(data.get("positions", [])),
               supplier=data.get("supplier", "Unknown"))
    
    await state.update_data(invoice=data)

    # Формируем красивую таблицу в Markdown
    invoice_table = make_invoice_markdown(data)
    
    # Подсчитываем количество неопознанных товаров
    unmatched = sum(1 for p in data.get("positions", []) 
                    if "match_id" in p and not p.get("match_id"))
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Всё верно", callback_data="inv_ok")],
            [InlineKeyboardButton(text="✏️ Исправить", callback_data="inv_edit")],
        ]
    )
    
    message = f"⚙️ Нашёл {len(data.get('positions', []))} позиций:\n\n{invoice_table}"
    if unmatched > 0:
        message += f"\n\n⚠️ {unmatched} товаров не удалось сопоставить с базой данных."
    
    try:
        await m.answer(message, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Error sending message", error=str(e))
        # Если не удалось отправить с Markdown, пробуем без форматирования
        try:
            simple_message = f"⚙️ Нашёл {len(data.get('positions', []))} позиций в накладной."
            await m.answer(simple_message, reply_markup=kb)
        except Exception:
            await m.answer("❌ Произошла ошибка при отображении накладной.")


# ───────────────────────── callbacks ────────────────────────
@router.callback_query(F.data == "inv_ok")
async def cb_ok(c: CallbackQuery, state: FSMContext, bot: Bot):
    data = (await state.get_data()).get("invoice", {})
    
    if not data:
        await c.message.answer("❌ Данные накладной отсутствуют. Попробуйте снова.")
        await c.answer()
        return
    
    try:
        xml_str = build_xml(data)
        
        # Здесь можно добавить код для сохранения в БД
        
        # здесь можете отправить xml в Syrve; пока просто лог
        logger.info("XML ready", xml_len=len(xml_str))
        
        await c.message.answer("✅ Накладная загружена в Syrve.")
    except Exception as e:
        logger.exception("Failed to process invoice", error=str(e))
        await c.message.answer("❌ Ошибка при обработке накладной.")
    
    await c.answer()


@router.callback_query(F.data == "inv_edit")
async def cb_edit(c: CallbackQuery):
    await c.message.answer("✏️ Функция редактирования в разработке.")
    await c.answer()
