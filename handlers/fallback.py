from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states import VideoStates
from keyboards import kb_main

router = Router(name="fallback")


@router.message(VideoStates.waiting_video)
async def fallback_waiting(msg: Message):
    """Video kutilayotganda noto'g'ri xabar kelsa."""
    if msg.text and msg.text.startswith("/"):
        return  # Buyruqlarni o'tkazib yubor
    await msg.answer(
        "🎬 Video yuboring!\n"
        "Qo'llab-quvvatlanadigan formatlar: MP4 · MOV · MKV · AVI · WEBM · FLV"
    )


@router.message()
async def fallback_global(msg: Message, state: FSMContext):
    """Hech qanday state bo'lmaganda default xatti-harakat."""
    if await state.get_state() is None:
        await state.set_state(VideoStates.waiting_video)
        await msg.answer("Boshlash uchun:", reply_markup=kb_main())
