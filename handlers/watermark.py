import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import UPLOAD_DIR, OUTPUT_DIR
from states import WatermarkStates
from keyboards import kb_main
from utils.ffmpeg import run_ffmpeg_async
from utils.cleanup import cleanup_files

log = logging.getLogger("videobot.watermark")
router = Router(name="watermark")


# ── /watermark yoki menyu tugmasi ─────────────────────────────────────────
@router.message(Command("watermark"))
@router.message(F.text == "💧 Watermark")
async def cmd_watermark(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(WatermarkStates.waiting_video)
    await msg.answer(
        "💧 <b>Watermark qo'shish</b>\n\n"
        "Videoni yuboring:",
        parse_mode="HTML",
    )


@router.message(WatermarkStates.waiting_video, F.video | F.document)
async def wm_get_video(msg: Message, state: FSMContext):
    fobj = msg.video or msg.document
    await state.update_data(file_id=fobj.file_id)
    await state.set_state(WatermarkStates.waiting_text)
    await msg.answer(
        "✏️ <b>Watermark matnini kiriting:</b>\n\n"
        "Misol: <code>@MyChannel</code>\n\n"
        "📍 <b>Joy tanlash:</b> <code>@MyChannel|markaz</code>\n"
        "Joylar: <code>o'ng-ost</code>, <code>chap-ost</code>, "
        "<code>o'ng-ust</code>, <code>chap-ust</code>, <code>markaz</code>",
        parse_mode="HTML",
    )


@router.message(WatermarkStates.waiting_text)
async def wm_apply(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    uid = msg.from_user.id
    parts = msg.text.strip().split("|")
    text = parts[0].strip()
    position = parts[1].strip() if len(parts) > 1 else "o'ng-ost"

    pos_map = {
        "o'ng-ost":  "x=w-tw-20:y=h-th-20",
        "chap-ost":  "x=20:y=h-th-20",
        "o'ng-ust":  "x=w-tw-20:y=20",
        "chap-ust":  "x=20:y=20",
        "markaz":    "x=(w-tw)/2:y=(h-th)/2",
    }
    pos = pos_map.get(position, "x=w-tw-20:y=h-th-20")
    status = await msg.answer("⏳ Watermark qo'shilmoqda...")

    inp = UPLOAD_DIR / f"wm_in_{uid}.mp4"
    out = OUTPUT_DIR / f"wm_out_{uid}.mp4"
    try:
        f = await bot.get_file(data["file_id"])
        await bot.download_file(f.file_path, destination=str(inp))
    except Exception as e:
        await status.edit_text(f"❌ Yuklab olishda xato: {e}")
        return

    drawtext = (
        f"drawtext=text='{text}':fontsize=36:fontcolor=white@0.8"
        f":borderw=2:bordercolor=black@0.5:{pos}"
    )
    if await run_ffmpeg_async(
        [
            "ffmpeg", "-y", "-i", str(inp), "-vf", drawtext,
            "-c:v", "libx264", "-c:a", "copy", str(out),
        ],
        msg,
    ):
        await status.edit_text(
            f"✅ Watermark qo'shildi!\n💧 {text} | 📍 {position}"
        )
        await msg.answer_video(
            FSInputFile(str(out)), caption=f"💧 Watermark: {text}"
        )
    cleanup_files(inp, out)
    await msg.answer("Yangi buyruq:", reply_markup=kb_main())
