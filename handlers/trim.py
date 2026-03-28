import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import UPLOAD_DIR, OUTPUT_DIR
from states import TrimStates
from keyboards import kb_main
from utils.ffmpeg import run_ffmpeg_async
from utils.cleanup import cleanup_files

log = logging.getLogger("videobot.trim")
router = Router(name="trim")


# ── /trim yoki menyu tugmasi ──────────────────────────────────────────────
@router.message(Command("trim"))
@router.message(F.text == "✂️ Kesish")
async def cmd_trim(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(TrimStates.waiting_video)
    await msg.answer(
        "✂️ <b>Video kesish</b>\n\n"
        "Qirqmoqchi bo'lgan videoni yuboring:",
        parse_mode="HTML",
    )


@router.message(TrimStates.waiting_video, F.video | F.document)
async def trim_get_video(msg: Message, state: FSMContext):
    fobj = msg.video or msg.document
    await state.update_data(file_id=fobj.file_id)
    await state.set_state(TrimStates.waiting_start)
    await msg.answer(
        "⏱ <b>Boshlash vaqtini kiriting:</b>\n\n"
        "• <code>00:01:30</code> — 1 daqiqa 30 soniya\n"
        "• <code>90</code> — 90 soniya",
        parse_mode="HTML",
    )


@router.message(TrimStates.waiting_start)
async def trim_get_start(msg: Message, state: FSMContext):
    await state.update_data(start=msg.text.strip())
    await state.set_state(TrimStates.waiting_end)
    await msg.answer(
        "⏱ <b>Tugash vaqtini kiriting:</b>\n\n"
        "• <code>00:03:00</code> — 3 daqiqa\n"
        "• <code>end</code> — oxirigacha",
        parse_mode="HTML",
    )


@router.message(TrimStates.waiting_end)
async def trim_get_end(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    start, end = data["start"], msg.text.strip()
    uid = msg.from_user.id

    status = await msg.answer("⏳ Video qirqilmoqda...")
    inp = UPLOAD_DIR / f"trim_in_{uid}.mp4"
    out = OUTPUT_DIR / f"trim_out_{uid}.mp4"

    try:
        f = await bot.get_file(data["file_id"])
        await bot.download_file(f.file_path, destination=str(inp))
    except Exception as e:
        await status.edit_text(f"❌ Yuklab olishda xato: {e}")
        return

    cmd = ["ffmpeg", "-y", "-i", str(inp), "-ss", start]
    if end.lower() != "end":
        cmd += ["-to", end]
    cmd += ["-c:v", "libx264", "-c:a", "aac", "-avoid_negative_ts", "1", str(out)]

    if await run_ffmpeg_async(cmd, msg):
        await status.edit_text(f"✅ Video qirqildi! {start} → {end}")
        await msg.answer_video(
            FSInputFile(str(out)),
            caption=f"✂️ Qirqilgan: {start} → {end}",
        )
    cleanup_files(inp, out)
    await msg.answer("Yangi buyruq:", reply_markup=kb_main())
