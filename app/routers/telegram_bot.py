import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

router = Router()


class InvoiceFSM(StatesGroup):
    WaitingPhoto = State()
    Reviewing = State()
    Confirming = State()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Приветствие и переход в состояние ожидания фото."""
    await state.clear()
    await state.set_state(InvoiceFSM.WaitingPhoto)
    logger.info(f"User {message.from_user.id} started bot.")
    await message.answer(
        "Привет! Я Nota V2 — помогаю загружать накладные в Syrve.\n"
        "Пришли фото накладной, а дальше я всё сделаю сам."
    )


@router.message(F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    """Обработка фото, переход к Reviewing, заглушка распознавания."""
    await state.set_state(InvoiceFSM.Reviewing)
    logger.info(f"User {message.from_user.id} sent a photo (invoice).")
    await message.answer("Фото получено, распознаю… (это может занять ~30 сек)")

    # --- Заглушка GPT OCR/Parsing ---
    # Здесь должны быть вызовы await gpt_ocr.ocr(), await gpt_parsing.parse()
    # Для MVP — фиксированный результат:
    fake_result = {
        "positions": [
            {"name": "Товар", "quantity": 1}
        ]
    }
    await state.update_data(invoice=fake_result)
    logger.info(f"Invoice recognized: {fake_result}")

    # --- Кнопки подтверждения ---
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="✅ Да", callback_data="confirm:yes"),
                types.InlineKeyboardButton(text="✏ Нет", callback_data="confirm:no"),
            ]
        ]
    )
    await message.answer(
        f"Нашёл {len(fake_result['positions'])} позицию(и), всё верно?",
        reply_markup=kb
    )
    await state.set_state(InvoiceFSM.Confirming)


@router.callback_query(F.data.startswith("confirm:"))
async def handle_confirm(call: types.CallbackQuery, state: FSMContext):
    """Обработка выбора Да/Нет на этапе подтверждения накладной."""
    answer = call.data.split(":", 1)[1]
    user_id = call.from_user.id
    if answer == "yes":
        logger.info(f"User {user_id} confirmed invoice.")
        await call.message.answer(
            "Накладная отправлена! Готов принять следующую."
        )
        await state.clear()
        await state.set_state(InvoiceFSM.WaitingPhoto)
    else:
        logger.info(f"User {user_id} declined invoice (edit requested).")
        await call.message.answer(
            "Функция редактирования в разработке. Пришли новое фото накладной."
        )
        await state.clear()
        await state.set_state(InvoiceFSM.WaitingPhoto)
    await call.answer()


@router.message(F.text)
async def fallback(message: types.Message, state: FSMContext):
    """Фоллбек для любых нераспознанных сообщений."""
    logger.info(f"User {message.from_user.id} sent text: {message.text!r}")
    await message.answer("Пришли фото накладной или /start.")
