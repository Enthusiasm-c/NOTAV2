"""
Telegram-router  (Aiogram v3)  – приём накладных и весь пайплайн:
    фото ➜ OCR ➜ Parsing ➜ Fuzzy ➜ подтверждение ➜ Syrve
MVP-вариант: если любой шаг падает – посылаем понятное сообщение.
"""

from __future__ import annotations

import asyncio
import json
import structlog
from aiogram import Bot, Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from app.routers.gpt_ocr import ocr
from app.routers.gpt_parsing import parse
from app.routers.fuzzy_match import fuzzy_match_product
from app.db import SessionLocal
from app.utils.xml_generator import build_xml  # если уже есть
from app.config import settings

logger = structlog.get_logger()
router = Router(name=__name__)


# ───────────────────────── helpers ──────────────────────────
async def _run_pipeline(file_id: str, bot: Bot) -> dict:
    """Фото в Telegram → структурированный dict (OCR+Parsing)."""
    raw_text = await ocr(file_id, bot)          # может бросить исключение
    parsed   = await parse(raw_text)            # может бросить исключение
    return parsed


def positions_summary(data: dict) -> str:
    return "\n".join(
        f"• {p['name']} × {p['quantity']}" for p in data["positions"]
    )


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

    # fuzzy-match для каждой позиции (асинхронный БД-сеанс)
    async with SessionLocal() as session:
        for p in data["positions"]:
            pid, conf = await fuzzy_match_product(session, p["name"], settings.fuzzy_threshold)
            p["match_id"] = pid
            p["confidence"] = conf

    logger.info("Invoice recognized", data=data)
    await state.update_data(invoice=data)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Всё верно", callback_data="inv_ok")],
            [InlineKeyboardButton(text="✏️ Исправить", callback_data="inv_edit")],
        ]
    )
    await m.answer(
        f"⚙️ Нашёл {len(data['positions'])} позиций:\n{positions_summary(data)}",
        reply_markup=kb,
    )


# ───────────────────────── callbacks ────────────────────────
@router.callback_query(F.data == "inv_ok")
async def cb_ok(c: CallbackQuery, state: FSMContext, bot: Bot):
    data = (await state.get_data())["invoice"]
    xml_str = build_xml(data)

    # здесь можете отправить xml в Syrve; пока просто лог
    logger.info("XML ready", xml_len=len(xml_str))

    await c.message.answer("✅ Накладная загружена в Syrve.")
    await c.answer()


@router.callback_query(F.data == "inv_edit")
async def cb_edit(c: CallbackQuery):
    await c.message.answer("✏️ Функция редактирования в разработке.")
    await c.answer()
