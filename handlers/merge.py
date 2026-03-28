import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import UPLOAD_DIR, OUTPUT_DIR
from states import MergeStates
from keyboards import kb_main
from utils.ffmpeg import run_ffmpeg_async
from utils.cleanup import cleanup_files

log = logging.getLogger("videobot.merge")
router = Router(name="merge")


# ── /merge yoki menyu tugmasi ─────────────────────────────────────────────
@router.message(Command("merge"))
@router.message(F.text == "🔗 Birlashtirish")
async def cmd_merge(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(MergeStates.waiting_first)
    await msg.answer(
        "🔗 <b>Video birlashtirish</b>\n\n"
        "1-chi videoni yuboring:",
        parse_mode="HTML",
    )


@router.message(MergeStates.waiting_first, F.video | F.document)
async def merge_first(msg: Message, state: FSMContext):
    fobj = msg.video or msg.document
    await state.update_data(file_id_1=fobj.file_id)
    await state.set_state(MergeStates.waiting_second)
    await msg.answer("✅ 1-chi video qabul qilindi.\n\n2-chi videoni yuboring:")


@router.message(MergeStates.waiting_second, F.video | F.document)
async def merge_second(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    uid = msg.from_user.id
    fobj = msg.video or msg.document
    status = await msg.answer("⏳ Videolar birlashtirilmoqda...")

    p1  = UPLOAD_DIR / f"m1_{uid}.mp4"
    p2  = UPLOAD_DIR / f"m2_{uid}.mp4"
    n1  = OUTPUT_DIR / f"n1_{uid}.mp4"
    n2  = OUTPUT_DIR / f"n2_{uid}.mp4"
    lst = OUTPUT_DIR / f"list_{uid}.txt"
    out = OUTPUT_DIR / f"merged_{uid}.mp4"

    try:
        f1 = await bot.get_file(data["file_id_1"])
        await bot.download_file(f1.file_path, destination=str(p1))
        f2 = await bot.get_file(fobj.file_id)
        await bot.download_file(f2.file_path, destination=str(p2))
    except Exception as e:
        await status.edit_text(f"❌ Yuklab olishda xato: {e}")
        cleanup_files(p1, p2)
        return

    # Normalise both videos to same resolution/fps
    for src, dst in [(p1, n1), (p2, n2)]:
        ok = await run_ffmpeg_async(
            [
                "ffmpeg", "-y", "-i", str(src),
                "-vf", "scale=1280:720,fps=30",
                "-c:v", "libx264", "-c:a", "aac", str(dst),
            ],
            msg,
        )
        if not ok:
            cleanup_files(p1, p2, n1, n2)
            return

    with open(lst, "w") as f:
        f.write(f"file '{n1.resolve()}'\nfile '{n2.resolve()}'\n")

    if await run_ffmpeg_async(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(lst), "-c", "copy", str(out),
        ],
        msg,
    ):
        await status.edit_text("✅ Videolar birlashtirildi!")
        await msg.answer_video(
            FSInputFile(str(out)), caption="🔗 Birlashtirilgan video"
        )
    cleanup_files(p1, p2, n1, n2, lst, out)
    await msg.answer("Yangi buyruq:", reply_markup=kb_main())
