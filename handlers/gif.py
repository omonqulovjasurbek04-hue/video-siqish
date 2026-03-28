import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import UPLOAD_DIR, OUTPUT_DIR
from states import GifStates
from keyboards import kb_main, kb_gif_choice
from utils.ffmpeg import run_ffmpeg_async
from utils.cleanup import cleanup_files

log = logging.getLogger("videobot.gif")
router = Router(name="gif")


# ── /gif yoki menyu tugmasi ───────────────────────────────────────────────
@router.message(Command("gif"))
@router.message(F.text == "🎞 GIF/Screenshot")
async def cmd_gif(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(GifStates.waiting_video)
    await msg.answer(
        "🎞 <b>GIF / Screenshot</b>\n\n"
        "Videoni yuboring:",
        parse_mode="HTML",
    )


@router.message(GifStates.waiting_video, F.video | F.document)
async def gif_get_video(msg: Message, state: FSMContext):
    fobj = msg.video or msg.document
    await state.update_data(file_id=fobj.file_id)
    await state.set_state(GifStates.waiting_choice)
    await msg.answer(
        "🎯 <b>Nima qilmoqchisiz?</b>",
        parse_mode="HTML",
        reply_markup=kb_gif_choice(),
    )


# ── Inline tugma orqali tanlash ───────────────────────────────────────────
@router.callback_query(GifStates.waiting_choice, F.data.startswith("gif:"))
async def gif_choice_cb(cq: CallbackQuery, state: FSMContext):
    choice = cq.data.split(":", 1)[1]

    if choice == "cancel":
        await state.clear()
        await cq.message.edit_text("❌ Bekor qilindi.")
        await cq.message.answer("Yangi buyruq:", reply_markup=kb_main())
        await cq.answer()
        return

    await state.update_data(choice=choice)
    await state.set_state(GifStates.waiting_time)

    if choice == "1":
        await cq.message.edit_text(
            "⏱ <b>GIF vaqti:</b> <code>00:00:05-00:00:10</code>\n"
            "Max 15 soniya tavsiya",
            parse_mode="HTML",
        )
    else:
        await cq.message.edit_text(
            "⏱ <b>Screenshot vaqti:</b> <code>00:00:05</code>",
            parse_mode="HTML",
        )
    await cq.answer()


# ── Matn orqali ham tanlash (orqaga mos) ──────────────────────────────────
@router.message(GifStates.waiting_choice)
async def gif_choice_text(msg: Message, state: FSMContext):
    choice = msg.text.strip()
    if choice not in ["1", "2"]:
        await msg.answer(
            "❗ Faqat <code>1</code> yoki <code>2</code> yozing.",
            parse_mode="HTML",
        )
        return
    await state.update_data(choice=choice)
    await state.set_state(GifStates.waiting_time)
    if choice == "1":
        await msg.answer(
            "⏱ <b>GIF vaqti:</b> <code>00:00:05-00:00:10</code>\n"
            "Max 15 soniya tavsiya",
            parse_mode="HTML",
        )
    else:
        await msg.answer(
            "⏱ <b>Screenshot vaqti:</b> <code>00:00:05</code>",
            parse_mode="HTML",
        )


@router.message(GifStates.waiting_time)
async def gif_process(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    choice = data["choice"]
    t = msg.text.strip()
    uid = msg.from_user.id

    inp = UPLOAD_DIR / f"gif_in_{uid}.mp4"
    try:
        f = await bot.get_file(data["file_id"])
        await bot.download_file(f.file_path, destination=str(inp))
    except Exception as e:
        await msg.answer(f"❌ Yuklab olishda xato: {e}")
        return

    if choice == "1":
        parts = t.split("-")
        if len(parts) != 2:
            await msg.answer(
                "❗ Format: <code>boshlash-tugash</code>", parse_mode="HTML"
            )
            cleanup_files(inp)
            return
        start, end = parts[0].strip(), parts[1].strip()
        pal = OUTPUT_DIR / f"pal_{uid}.png"
        out = OUTPUT_DIR / f"out_{uid}.gif"
        status = await msg.answer("⏳ GIF yaratilmoqda...")

        ok = await run_ffmpeg_async(
            [
                "ffmpeg", "-y", "-ss", start, "-to", end, "-i", str(inp),
                "-vf", "fps=12,scale=480:-1:flags=lanczos,palettegen", str(pal),
            ],
            msg,
        )
        if ok:
            ok = await run_ffmpeg_async(
                [
                    "ffmpeg", "-y", "-ss", start, "-to", end, "-i", str(inp),
                    "-i", str(pal), "-lavfi",
                    "fps=12,scale=480:-1:flags=lanczos[x];[x][1:v]paletteuse",
                    str(out),
                ],
                msg,
            )
        if ok:
            await status.edit_text(f"✅ GIF tayyor! {start} → {end}")
            await msg.answer_document(
                FSInputFile(str(out)), caption=f"🎞 GIF: {start} → {end}"
            )
        cleanup_files(inp, pal, out)
    else:
        out = OUTPUT_DIR / f"ss_{uid}.jpg"
        status = await msg.answer("⏳ Screenshot olinmoqda...")
        if await run_ffmpeg_async(
            [
                "ffmpeg", "-y", "-ss", t, "-i", str(inp),
                "-frames:v", "1", "-q:v", "2", str(out),
            ],
            msg,
        ):
            await status.edit_text(f"✅ Screenshot olindi! Vaqt: {t}")
            await msg.answer_photo(
                FSInputFile(str(out)), caption=f"📸 Screenshot: {t}"
            )
        cleanup_files(inp, out)
    await msg.answer("Yangi buyruq:", reply_markup=kb_main())
