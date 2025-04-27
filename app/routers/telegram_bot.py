import json
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from app.db import SessionLocal
from app.models.product import Product
from app.models.invoice_state import InvoiceState, FSMState
from app.utils.markdown import make_invoice_markdown
from app.utils.syrve_export import build_xml, post_to_syrve

dp = Router()
router = dp        # экспорт под вторым именем

# Класс состояний (FSM)
class Notafsm:
    waiting_photo = "waiting_photo"
    reviewing = "reviewing"
    editing = "editing"
    confirming = "confirming"
    done = "done"

# --- EDITING CALLBACK HANDLER ---

@dp.callback_query(lambda c: c.data.startswith("edit:"))
async def handle_editing_callback(call: CallbackQuery, state: FSMContext):
    # edit:<invoice_id>:<item_idx>:<action>
    _, invoice_id, item_idx, action = call.data.split(":")
    data = await state.get_data()
    draft = data.get("draft", {})
    positions = draft.get("positions", [])
    pos = positions[int(item_idx)]

    if action == "accept":
        pos["status"] = "accepted"
        await call.answer("Позиция оставлена без изменений 👌")
    elif action == "update":
        await state.update_data(editing_idx=item_idx)
        await call.message.answer(
            f"Изменение позиции:\n"
            f"Наименование: {pos['name']}\nКол-во: {pos['quantity']}\n"
            f"Ед.: {pos['unit']}\nЦена: {pos['price']}\nСумма: {pos['sum']}\n\n"
            f"Напишите исправленное наименование (или /skip)."
        )
        await state.set_state("editing_item")
        return
    elif action == "new_product":
        pos["status"] = "new"
        # Логика добавления товара в БД Products и обновления lookup — реализуйте здесь.
        await call.answer("Будет создан новый товар!")
    await state.update_data(draft=draft)
    await show_next_editing(call.message, state)

async def show_next_editing(msg, state: FSMContext):
    """Показывает след. неразрешённую позицию и её варианты управления."""
    data = await state.get_data()
    draft = data.get("draft", {})
    positions = draft.get("positions", [])
    for idx, pos in enumerate(positions):
        if pos.get("status") not in ("accepted", "new"):
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✔ Оставить как есть",
                            callback_data=f"edit:{draft.get('invoice_id','')}:"
                                          f"{idx}:accept"
                        ),
                        InlineKeyboardButton(
                            text="✏ Изменить",
                            callback_data=f"edit:{draft.get('invoice_id','')}:"
                                          f"{idx}:update"
                        ),
                        InlineKeyboardButton(
                            text="➕ Создать новый товар",
                            callback_data=f"edit:{draft.get('invoice_id','')}:"
                                          f"{idx}:new_product"
                        ),
                    ]
                ]
            )
            await msg.answer(
                f"Позиция {idx + 1}:\nНаименование: {pos['name']}\n"
                f"Кол-во: {pos['quantity']}, {pos['unit']}\nЦена: {pos['price']}\n"
                f"Совпадение: {pos.get('confidence', 0) * 100:.1f}%",
                reply_markup=kb
            )
            return
    # Все обработаны — переход к Confirming
    await state.set_state(Notafsm.confirming)
    md = make_invoice_markdown(draft)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Отправить в Syrve",
                    callback_data=f"confirm:{draft.get('invoice_id','')}:commit"
                ),
                InlineKeyboardButton(
                    text="🔄 Отмена",
                    callback_data=f"confirm:{draft.get('invoice_id','')}:cancel"
                ),
            ]
        ]
    )
    await msg.answer(f"**Черновик накладной:**\n\n{md}", reply_markup=kb, parse_mode="Markdown")

# --- CONFIRMING CALLBACK HANDLER ---

@dp.callback_query(lambda c: c.data.startswith("confirm:"))
async def handle_confirming_callback(call: CallbackQuery, state: FSMContext):
    # confirm:<invoice_id>:<action>
    _, invoice_id, action = call.data.split(":")
    data = await state.get_data()
    draft = data.get("draft", {})
    if action == "commit":
        xml = build_xml(draft)
        ok, msg_text = await post_to_syrve(xml)
        result_text = (f"✅ Успех! Накладная №{invoice_id} отправлена." 
                       if ok else f"❌ Ошибка: {msg_text}")
        await state.set_state(Notafsm.done)
        await call.message.answer(result_text)
    elif action == "cancel":
        await call.message.answer("Операция отменена.")
        await state.set_state(Notafsm.reviewing)
    else:
        await call.message.answer("Неопознанная команда.")
    # --- Сохраняем draft (BД) после любого действия
    async with SessionLocal() as session:
        invoice_state = await session.get(InvoiceState, invoice_id)
        if invoice_state:
            invoice_state.json_draft = json.dumps(draft, ensure_ascii=False)
            invoice_state.state = Notafsm.confirming
            await session.commit()
