"""Tezkor asboblar — /siq, /sifat, /olcham, /fps, /ovoz, /info

Video yuborilgandan keyin menyudagi tugmalar yoki buyruqlar orqali ishlatiladi.
Barcha asboblar state.get_data() dan file_path oladi.
"""

import uuid
import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import UPLOAD_DIR, OUTPUT_DIR
from keyboards import kb_main, kb_tools, kb_olcham, kb_fps, kb_ovoz
from utils.ffmpeg import run_ffmpeg_async, get_video_info
from utils.formatters import fmt_size, fmt_dur

log = logging.getLogger("videobot.tools")
router = Router(name="tools")


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_input(data: dict) -> str | None:
    p = data.get("file_path")
    if p and Path(p).exists():
        return p
    return None


# ═══════════════════════════════════════════════════════════════════════════
#  🗜  /siq — Tezkor video siqish
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("siq"))
async def cmd_siq(msg: Message, state: FSMContext):
    data = await state.get_data()
    input_path = _get_input(data)
    if not input_path:
        await msg.answer("❌ Avval video yuboring!", reply_markup=kb_main())
        return

    info = data.get("video_info", {})
    out_path = OUTPUT_DIR / f"siq_{uuid.uuid4()}.mp4"
    status = await msg.answer("🗜 <b>Siqilmoqda...</b> Kuting.", parse_mode="HTML")

    ok = await run_ffmpeg_async(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-c:v", "libx264", "-crf", "23", "-preset", "slow",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", str(out_path),
        ],
        msg,
    )

    if ok and out_path.exists():
        in_sz = info.get("size", Path(input_path).stat().st_size)
        out_sz = out_path.stat().st_size
        saved = round((1 - out_sz / in_sz) * 100) if in_sz > 0 else 0
        await status.edit_text(
            f"✅ <b>Tayyor!</b> {saved}% tejaldi\n"
            f"📦 {fmt_size(in_sz)} → {fmt_size(out_sz)}",
            parse_mode="HTML",
        )
        await msg.answer_video(
            FSInputFile(str(out_path)),
            caption=f"🗜 Siqilgan video\n📦 {fmt_size(out_sz)} ({saved}% kichikroq)",
        )
        out_path.unlink(missing_ok=True)
    else:
        await status.edit_text("❌ Siqishda xato yuz berdi.")


# ═══════════════════════════════════════════════════════════════════════════
#  ✨  /sifat — Sifat ko'tarish (denoise + sharpen + color)
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("sifat"))
@router.message(F.text == "✨ Sifat ko'tarish")
async def cmd_sifat(msg: Message, state: FSMContext):
    data = await state.get_data()
    input_path = _get_input(data)
    if not input_path:
        await msg.answer("❌ Avval video yuboring!", reply_markup=kb_main())
        return

    out_path = OUTPUT_DIR / f"sifat_{uuid.uuid4()}.mp4"
    status = await msg.answer(
        "✨ <b>Sifat ko'tarilmoqda...</b>\n"
        "Denoise + Sharpen + Color — kuting.",
        parse_mode="HTML",
    )

    ok = await run_ffmpeg_async(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-vf",
            "hqdn3d=4:3:6:4.5,unsharp=5:5:1.5:5:5:0.0,"
            "eq=gamma=1.1:saturation=1.2:contrast=1.05",
            "-c:v", "libx264", "-crf", "18", "-preset", "slow",
            "-c:a", "copy", str(out_path),
        ],
        msg,
    )

    if ok and out_path.exists():
        out_sz = out_path.stat().st_size
        await status.edit_text("✅ <b>Sifat ko'tarildi!</b>", parse_mode="HTML")
        await msg.answer_video(
            FSInputFile(str(out_path)),
            caption=f"✨ Sifati yaxshilangan video\n📦 {fmt_size(out_sz)}",
        )
        out_path.unlink(missing_ok=True)
    else:
        await status.edit_text("❌ Sifat ko'tarishda xato.")


# ═══════════════════════════════════════════════════════════════════════════
#  📐  /olcham — O'lcham o'zgartirish (inline tugmalar bilan)
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("olcham"))
@router.message(F.text == "📐 O'lcham")
async def cmd_olcham(msg: Message, state: FSMContext):
    data = await state.get_data()
    if not _get_input(data):
        await msg.answer("❌ Avval video yuboring!", reply_markup=kb_main())
        return
    await msg.answer(
        "📐 <b>O'lchamni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=kb_olcham(),
    )


@router.callback_query(F.data.startswith("sz:"))
async def on_resize(cq: CallbackQuery, state: FSMContext):
    raw = cq.data[3:]  # "3840:2160" yoki "cancel"
    if raw == "cancel":
        await cq.message.edit_text("❌ Bekor qilindi.")
        await cq.answer()
        return

    data = await state.get_data()
    input_path = _get_input(data)
    if not input_path:
        await cq.message.edit_text("❌ Fayl topilmadi.")
        await cq.answer()
        return

    scale = raw  # "1920:1080"
    label = scale.replace(":", "x")
    out_path = OUTPUT_DIR / f"resize_{uuid.uuid4()}.mp4"
    await cq.message.edit_text(f"📐 <b>{label}</b> ga o'zgartirilmoqda...", parse_mode="HTML")
    await cq.answer()

    ok = await run_ffmpeg_async(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"scale={scale}:flags=lanczos",
            "-c:v", "libx264", "-crf", "20",
            "-c:a", "copy", str(out_path),
        ],
        cq.message,
    )

    if ok and out_path.exists():
        out_sz = out_path.stat().st_size
        await cq.message.edit_text(f"✅ <b>{label}</b> tayyor!", parse_mode="HTML")
        await cq.message.answer_video(
            FSInputFile(str(out_path)),
            caption=f"📐 {label}\n📦 {fmt_size(out_sz)}",
        )
        out_path.unlink(missing_ok=True)
    else:
        await cq.message.edit_text("❌ O'lcham o'zgartirishda xato.")


# ═══════════════════════════════════════════════════════════════════════════
#  🎬  /fps — FPS o'zgartirish (inline tugmalar bilan)
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("fps"))
@router.message(F.text == "🎬 FPS")
async def cmd_fps(msg: Message, state: FSMContext):
    data = await state.get_data()
    if not _get_input(data):
        await msg.answer("❌ Avval video yuboring!", reply_markup=kb_main())
        return
    await msg.answer(
        "🎬 <b>FPS tanlang:</b>",
        parse_mode="HTML",
        reply_markup=kb_fps(),
    )


@router.callback_query(F.data.startswith("fp:"))
async def on_fps(cq: CallbackQuery, state: FSMContext):
    raw = cq.data[3:]  # "24", "30", "60", "slow", "fast", "cancel"
    if raw == "cancel":
        await cq.message.edit_text("❌ Bekor qilindi.")
        await cq.answer()
        return

    data = await state.get_data()
    input_path = _get_input(data)
    if not input_path:
        await cq.message.edit_text("❌ Fayl topilmadi.")
        await cq.answer()
        return

    fps_map = {
        "24":   (["-r", "24", "-c:v", "libx264", "-crf", "23"],   "24 FPS (Kino)"),
        "30":   (["-r", "30", "-c:v", "libx264", "-crf", "23"],   "30 FPS (Standart)"),
        "60":   (["-r", "60", "-c:v", "libx264", "-crf", "23"],   "60 FPS (Geyming)"),
        "slow": (["-vf", "setpts=2.0*PTS", "-c:v", "libx264", "-crf", "23"], "Slow-motion 0.5x"),
        "fast": (["-vf", "setpts=0.5*PTS", "-c:v", "libx264", "-crf", "23"], "Tezlashtirish 2x"),
    }
    fps_cmd, label = fps_map[raw]

    out_path = OUTPUT_DIR / f"fps_{uuid.uuid4()}.mp4"
    await cq.message.edit_text(f"🎬 <b>{label}</b> qo'llanilmoqda...", parse_mode="HTML")
    await cq.answer()

    cmd = ["ffmpeg", "-y", "-i", input_path] + fps_cmd + ["-c:a", "copy", str(out_path)]
    if await run_ffmpeg_async(cmd, cq.message) and out_path.exists():
        out_sz = out_path.stat().st_size
        await cq.message.edit_text(f"✅ <b>{label}</b> tayyor!", parse_mode="HTML")
        await cq.message.answer_video(
            FSInputFile(str(out_path)),
            caption=f"🎬 {label}\n📦 {fmt_size(out_sz)}",
        )
        out_path.unlink(missing_ok=True)
    else:
        await cq.message.edit_text("❌ FPS o'zgartirishda xato.")


# ═══════════════════════════════════════════════════════════════════════════
#  🔊  /ovoz — Ovoz sozlamalari (inline tugmalar bilan)
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("ovoz"))
@router.message(F.text == "🔊 Ovoz")
async def cmd_ovoz(msg: Message, state: FSMContext):
    data = await state.get_data()
    if not _get_input(data):
        await msg.answer("❌ Avval video yuboring!", reply_markup=kb_main())
        return
    await msg.answer(
        "🔊 <b>Ovoz sozlamasini tanlang:</b>",
        parse_mode="HTML",
        reply_markup=kb_ovoz(),
    )


@router.callback_query(F.data.startswith("au:"))
async def on_audio(cq: CallbackQuery, state: FSMContext):
    raw = cq.data[3:]
    if raw == "cancel":
        await cq.message.edit_text("❌ Bekor qilindi.")
        await cq.answer()
        return

    data = await state.get_data()
    input_path = _get_input(data)
    if not input_path:
        await cq.message.edit_text("❌ Fayl topilmadi.")
        await cq.answer()
        return

    audio_map = {
        "remove": (["-an"],                                        "Ovoz olib tashlandi"),
        "96":     (["-c:a", "aac", "-b:a", "96k"],                "Ovoz 96 kbps"),
        "128":    (["-c:a", "aac", "-b:a", "128k"],               "Ovoz 128 kbps"),
        "192":    (["-c:a", "aac", "-b:a", "192k"],               "Ovoz 192 kbps"),
        "mono":   (["-c:a", "aac", "-b:a", "128k", "-ac", "1"],   "Mono ovoz"),
    }
    audio_cmd, label = audio_map[raw]

    out_path = OUTPUT_DIR / f"audio_{uuid.uuid4()}.mp4"
    await cq.message.edit_text(f"🔊 <b>{label}</b> qo'llanilmoqda...", parse_mode="HTML")
    await cq.answer()

    cmd = ["ffmpeg", "-y", "-i", input_path, "-c:v", "copy"] + audio_cmd + [str(out_path)]
    if await run_ffmpeg_async(cmd, cq.message) and out_path.exists():
        out_sz = out_path.stat().st_size
        await cq.message.edit_text(f"✅ <b>{label}</b> tayyor!", parse_mode="HTML")
        await cq.message.answer_video(
            FSInputFile(str(out_path)),
            caption=f"🔊 {label}\n📦 {fmt_size(out_sz)}",
        )
        out_path.unlink(missing_ok=True)
    else:
        await cq.message.edit_text("❌ Ovoz sozlashda xato.")


# ═══════════════════════════════════════════════════════════════════════════
#  📊  /info — Video ma'lumotlari
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("info"))
@router.message(F.text == "📊 Ma'lumot")
async def cmd_info(msg: Message, state: FSMContext):
    data = await state.get_data()
    input_path = _get_input(data)
    if not input_path:
        await msg.answer("❌ Avval video yuboring!", reply_markup=kb_main())
        return

    info = data.get("video_info")
    if not info:
        info = get_video_info(input_path)
    if info:
        dur = info.get("duration", 0)
        await msg.answer(
            f"📊 <b>Video ma'lumotlari:</b>\n\n"
            f"📐 O'lcham:    <b>{info.get('width', '?')}x{info.get('height', '?')}</b>\n"
            f"⏱ Davomiylik: <b>{fmt_dur(dur)}</b>\n"
            f"🎞 FPS:        <b>{info.get('fps', '?')}</b>\n"
            f"🔧 V-kodek:   <b>{info.get('vcodec', '?')}</b>\n"
            f"🔊 A-kodek:   <b>{info.get('acodec', '?')}</b>\n"
            f"📦 Hajm:      <b>{fmt_size(info.get('size', 0))}</b>\n"
            f"⚡ Bitrate:   <b>{info.get('bitrate', 0) // 1000} kbps</b>",
            parse_mode="HTML",
        )
    else:
        await msg.answer("❌ Video ma'lumotlarini o'qib bo'lmadi.")
