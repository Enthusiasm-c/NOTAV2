__all__ = ["main"]

"""
Telegram-бот для приема накладных.
Переводит фото в backend, следит за всеми шагами.
"""

import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InputFile
from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from ..config import settings
from ..db import SessionLocal
from .gpt_ocr import call_gpt_ocr
from .gpt_parsing import call_gpt_parse
from .fuzzy_match import fuzzy_match_product
from ..utils.logger import log
from ..models.product import Product
from ..models.invoice import Invoice, InvoiceNameLookup
from ..models.invoice_item import InvoiceItem

bot = Bot(token=settings.telegram_token)
dp = Dispatcher()

async def ask_user_for_mapping(chat_id, parsed_name, candidates):
    # Формирует клавиатуру для уточнения
    builder = InlineKeyboardBuilder()
    for prod in candidates:
        builder.button(text=prod.name, callback_data=f"select_prod_{prod.id}")
    builder.button(text="Добавить новый", callback_data=f"add_new_{parsed_name}")
    await bot.send_message(chat_id, f"🔍 Не удалось однозначно сопоставить '{parsed_name}'. Уточните:",
                           reply_markup=builder.as_markup())

async def process_invoice_photo(message: types.Message):
    log("Получено фото от пользователя %s", str(message.chat.id))
    file_info = await bot.get_file(message.photo[-1].file_id)
    file = await bot.download_file(file_info.file_path)
    content = file.read()
    # 1. Отправить на OCR
    raw_text = await call_gpt_ocr(content)
    log("OCR завершен")
    async with SessionLocal() as session:
        # 2. Создать инвойс с raw_text
        invoice = Invoice(
            supplier_name=None,
            buyer_name=None,
            date=None,
            raw_text=raw_text,
            status="pending",
        )
        session.add(invoice)
        await session.commit()
        await session.refresh(invoice)
        # 3. Парсинг
        data = await call_gpt_parse(raw_text)
        invoice.supplier_name = data.get("supplier_name")
        invoice.buyer_name = data.get("buyer_name")
        invoice.date = data.get("date")
        await session.commit()
        unresolved = []
        for pos in data.get("positions", []):
            # 4. Fuzzy-сопоставление
            prod_id, confidence = await fuzzy_match_product(
                session, pos["name"], settings.fuzzy_threshold
            )
            item = InvoiceItem(
                invoice_id=invoice.id,
                parsed_name=pos["name"],
                quantity=pos["quantity"],
                unit=pos["unit"],
                price=pos["price"],
                sum=pos["sum"],
                match_confidence=confidence,
                product_id=prod_id if confidence >= settings.fuzzy_threshold else None,
            )
            session.add(item)
            if not prod_id:
                unresolved.append(item)
        await session.commit()
        # 5. Уточнения
        if unresolved:
            all_prods = (await session.execute(select(Product))).scalars().all()
            for item in unresolved:
                # Показываем похожие продукты (fuzzy < threshold)
                await ask_user_for_mapping(message.chat.id, item.parsed_name, all_prods[:5])
        else:
            await bot.send_message(message.chat.id, "Все позиции сопоставлены автоматически!")
    await bot.send_message(message.chat.id, "Накладная обработана, ожидайте загрузки в Syrve.")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Отправьте фото накладной для обработки.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    await process_invoice_photo(message)

def main():
    logging.basicConfig(level=logging.INFO)
    log("Бот запускается")
    asyncio.run(dp.start_polling(bot))

if __name__ == "__main__":
    main()
