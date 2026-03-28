import uuid
import time
import asyncio
import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import (
    UPLOAD_DIR, OUTPUT_DIR, ALLOWED_EXTS,
    COMPRESS_PROFILES, PLATFORM_PROFILES, DEFAULT_CUSTOM,
    RES_OPTS, RES_LABELS, FPS_OPTS,
    USE_LOCAL_SERVER, MAX_SIZE_LOCAL, MAX_SIZE_CLOUD,
)
from states import VideoStates
from keyboards import (
    kb_main, kb_tools, kb_compress_type, kb_platforms,
    kb_custom, kb_result,
)
from utils.ffmpeg import get_video_info, check_ffmpeg
from utils.formatters import fmt_size, fmt_dur, progress_bar

log = logging.getLogger("videobot.compress")
router = Router(name="compress")


# ── Video yuborish tugmasi ─────────────────────────────────────────────────
@router.message(F.text == "🎬 Video yuborish")
async def btn_upload(msg: Message, state: FSMContext):
    await state.set_state(VideoStates.waiting_video)
    await msg.answer(
        "🎬 <b>Video yuboring</b>\n\n"
        "📁 Qo'llab-quvvatlanadigan formatlar:\n"
        "MP4 · MOV · MKV · AVI · WEBM · FLV\n\n"
        "Bekor qilish uchun /cancel",
        parse_mode="HTML",
        reply_markup=kb_main(),
    )


# ── Tezkor siqish tugmasi (menyudan) ──────────────────────────────────────
@router.message(F.text == "🗜 Siqish")
async def btn_siq(msg: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("file_path") or not Path(data["file_path"]).exists():
        await msg.answer("❌ Avval video yuboring!", reply_markup=kb_main())
        return
    await msg.answer(
        "🗜 <b>Siqish turini tanlang:</b>",
        parse_mode="HTML",
        reply_markup=kb_compress_type(),
    )
    await state.set_state(VideoStates.choosing_compress)


# ── Video qabul qilish ────────────────────────────────────────────────────
@router.message(VideoStates.waiting_video, F.video | F.document)
async def handle_video(msg: Message, state: FSMContext, bot: Bot):
    if not check_ffmpeg():
        await msg.answer(
            "❌ <b>FFmpeg topilmadi!</b>\n\n"
            "Bot ishlashi uchun FFmpeg kerak.\n"
            "O'rnatish: https://ffmpeg.org/download.html",
            parse_mode="HTML",
        )
        return

    fobj = msg.video or msg.document
    file_size = getattr(fobj, "file_size", 0)
    max_limit = MAX_SIZE_LOCAL if USE_LOCAL_SERVER else MAX_SIZE_CLOUD

    if file_size and file_size > max_limit:
        sz_str = "1.8 GB" if USE_LOCAL_SERVER else "20 MB"
        await msg.answer(
            f"❌ Fayl hajmi katta: <b>{fmt_size(file_size)}</b>\n\n"
            f"Bot faqatgina {sz_str} gacha bo'lgan videolarni qabul qila oladi.",
            parse_mode="HTML",
        )
        return

    filename = getattr(fobj, "file_name", None) or "video.mp4"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "mp4"

    if ext not in ALLOWED_EXTS:
        await msg.answer(
            f"❌ <b>.{ext}</b> formati qo'llab-quvvatlanmaydi.\n\n"
            f"Ruxsat etilgan: {', '.join(sorted(ALLOWED_EXTS)).upper()}",
            parse_mode="HTML",
        )
        return

    prog = await msg.answer("⏬ Video yuklanmoqda...", reply_markup=ReplyKeyboardRemove())

    try:
        fid = str(uuid.uuid4())
        save_path = UPLOAD_DIR / f"{fid}.{ext}"
        finfo = await bot.get_file(fobj.file_id)
        await bot.download_file(finfo.file_path, destination=str(save_path))

        await prog.edit_text("🔍 Video tahlil qilinmoqda...")
        info = get_video_info(str(save_path))

        if not info:
            await prog.edit_text(
                "❌ Videoni tahlil qilib bo'lmadi.\nBoshqa fayl yuboring."
            )
            save_path.unlink(missing_ok=True)
            await state.set_state(VideoStates.waiting_video)
            await msg.answer("Video yuborish:", reply_markup=kb_main())
            return

        await state.update_data(
            file_id=fid,
            file_path=str(save_path),
            filename=filename,
            video_info=info,
            custom=DEFAULT_CUSTOM.copy(),
        )

        res = (
            f"{info.get('width', 0)}x{info.get('height', 0)}"
            if info.get("width") else "—"
        )
        await prog.edit_text(
            f"✅ <b>Video tahlil qilindi!</b>\n\n"
            f"📄 Fayl:       {filename}\n"
            f"📦 Hajm:       {fmt_size(info['size'])}\n"
            f"⏱ Davomiylik: {fmt_dur(info['duration'])}\n"
            f"📐 Ruxsat:     {res}\n"
            f"🎞 FPS:        {info.get('fps', '—')}\n"
            f"🔧 V-kodek:    {info.get('vcodec', '—')}\n"
            f"🔊 A-kodek:    {info.get('acodec', '—')}\n"
            f"⚡ Bit tezlik: {info.get('bitrate', 0) // 1000} kbps\n\n"
            "Siqish turini tanlang yoki menyudan asbob tanlang 👇",
            parse_mode="HTML",
            reply_markup=kb_compress_type(),
        )

        # Tezkor asboblar menyusi ham chiqsin
        await msg.answer("⚡ Tezkor asboblar:", reply_markup=kb_tools())
        await state.set_state(VideoStates.choosing_compress)

    except Exception as e:
        log.exception("handle_video xato")
        try:
            await prog.edit_text("❌ Xato yuz berdi, faylni yuklab bo'lmadi.")
        except TelegramBadRequest:
            await msg.answer("❌ Xato yuz berdi, faylni yuklab bo'lmadi.")
        await msg.answer("Qaytish:", reply_markup=kb_main())


# ── Compression type ───────────────────────────────────────────────────────
@router.callback_query(VideoStates.choosing_compress, F.data.startswith("c:"))
async def on_compress(cq: CallbackQuery, state: FSMContext):
    key = cq.data.split(":", 1)[1]

    if key == "cancel":
        await state.clear()
        await cq.message.edit_text("❌ Bekor qilindi.")
        await cq.message.answer("Yangi video yuborish:", reply_markup=kb_main())
        await cq.answer()
        return

    if key == "platform":
        await cq.message.edit_text(
            "📱 <b>Platforma profilini tanlang:</b>\n\n"
            "Har bir platforma uchun optimal sozlamalar avtomatik o'rnatiladi.",
            parse_mode="HTML",
            reply_markup=kb_platforms(),
        )
        await cq.answer()
        return

    if key == "custom":
        data = await state.get_data()
        await cq.message.edit_text(
            "⚙️ <b>Kengaytirilgan sozlamalar</b>\n\n"
            "CRF: 0 = eng yuqori sifat, 51 = eng past sifat",
            parse_mode="HTML",
            reply_markup=kb_custom(data.get("custom", DEFAULT_CUSTOM.copy())),
        )
        await state.set_state(VideoStates.custom_settings)
        await cq.answer()
        return

    if key in COMPRESS_PROFILES:
        p = COMPRESS_PROFILES[key]
        await state.update_data(
            custom={
                "crf":    p["crf"],
                "audio":  p["audio"],
                "preset": p["preset"],
                "scale":  p["scale"],
                "fps": 0, "remove_audio": False, "keep_sub": True,
            }
        )
        await cq.message.edit_text(
            f"{p['label']} tanlandi\n{p['desc']}\n\n⏳ Siqish boshlanyapti..."
        )
        await cq.answer()
        await state.set_state(VideoStates.processing)
        await run_compression(cq.message, state)


# ── Platform selection ─────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("p:"))
async def on_platform(cq: CallbackQuery, state: FSMContext):
    key = cq.data.split(":", 1)[1]

    if key == "back":
        await cq.message.edit_text(
            "Siqish turini tanlang:", reply_markup=kb_compress_type()
        )
        await state.set_state(VideoStates.choosing_compress)
        await cq.answer()
        return

    if key in PLATFORM_PROFILES:
        p = PLATFORM_PROFILES[key]
        await state.update_data(
            custom={
                "crf":    p["crf"],
                "audio":  p["audio"],
                "scale":  p["scale"],
                "fps":    p.get("fps", 30),
                "preset": "medium",
                "remove_audio": False,
                "keep_sub": True,
            }
        )
        await cq.message.edit_text(
            f"{p['label']} profili tanlandi\n\n"
            f"📐 Ruxsat: {p['scale'].replace(':', 'x')}\n"
            f"🎞 FPS:    {p.get('fps', 30)}\n"
            f"🔊 Ovoz:   {p['audio']}\n\n"
            "⏳ Siqish boshlanyapti..."
        )
        await cq.answer()
        await state.set_state(VideoStates.processing)
        await run_compression(cq.message, state)


# ── Custom settings ────────────────────────────────────────────────────────
@router.callback_query(VideoStates.custom_settings, F.data.startswith("cs:"))
async def on_custom(cq: CallbackQuery, state: FSMContext):
    action = cq.data.split(":", 1)[1]
    data = await state.get_data()
    s = data.get("custom", DEFAULT_CUSTOM.copy())

    if action == "back":
        await cq.message.edit_text(
            "Siqish turini tanlang:", reply_markup=kb_compress_type()
        )
        await state.set_state(VideoStates.choosing_compress)
        await cq.answer()
        return

    if action == "crf_info":
        await cq.answer(
            f"CRF: {s.get('crf', 24)}\n0=eng yuqori sifat, 51=eng past",
            show_alert=True,
        )
        return

    elif action == "crf_up":
        s["crf"] = max(0, s.get("crf", 24) - 2)
        await cq.answer(f"CRF: {s['crf']}")

    elif action == "crf_dn":
        s["crf"] = min(51, s.get("crf", 24) + 2)
        await cq.answer(f"CRF: {s['crf']}")

    elif action == "audio":
        opts = ["192k", "128k", "64k"]
        cur = s.get("audio", "128k")
        idx = opts.index(cur) if cur in opts else 1
        s["audio"] = opts[(idx + 1) % len(opts)]
        await cq.answer(f"Ovoz: {s['audio']}")

    elif action == "fps":
        cur = s.get("fps", 0)
        idx = FPS_OPTS.index(cur) if cur in FPS_OPTS else 0
        s["fps"] = FPS_OPTS[(idx + 1) % len(FPS_OPTS)]
        await cq.answer(f"FPS: {s['fps'] or 'Asl'}")

    elif action == "res":
        cur = s.get("scale", "-2:-2")
        idx = RES_OPTS.index(cur) if cur in RES_OPTS else 0
        s["scale"] = RES_OPTS[(idx + 1) % len(RES_OPTS)]
        await cq.answer(f"Ruxsat: {RES_LABELS[RES_OPTS.index(s['scale'])]}")

    elif action == "toggle_audio":
        s["remove_audio"] = not s.get("remove_audio", False)
        await cq.answer("Ovoz o'chirildi" if s["remove_audio"] else "Ovoz yoqildi")

    elif action == "toggle_sub":
        s["keep_sub"] = not s.get("keep_sub", True)
        await cq.answer("Subtitle saqlanadi" if s["keep_sub"] else "Subtitle o'chirildi")

    elif action == "start":
        await state.update_data(custom=s)
        res_lbl = (
            RES_LABELS[RES_OPTS.index(s.get("scale", "-2:-2"))]
            if s.get("scale") in RES_OPTS else "Asl"
        )
        await cq.message.edit_text(
            f"✅ Sozlamalar qabul qilindi\n\n"
            f"🎨 CRF:    {s.get('crf', 24)}\n"
            f"🔊 Ovoz:   {s.get('audio', '128k')}\n"
            f"🎞 FPS:    {s.get('fps') or 'Asl'}\n"
            f"📐 Ruxsat: {res_lbl}\n\n"
            "⏳ Siqish boshlanyapti..."
        )
        await cq.answer()
        await state.set_state(VideoStates.processing)
        await run_compression(cq.message, state)
        return

    await state.update_data(custom=s)
    try:
        await cq.message.edit_reply_markup(reply_markup=kb_custom(s))
    except TelegramBadRequest:
        pass


# ── Result callbacks ───────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("r:"))
async def on_result(cq: CallbackQuery, state: FSMContext):
    action = cq.data.split(":", 1)[1]
    if action == "new":
        await state.clear()
        await cq.message.answer("Yangi video yuboring:", reply_markup=kb_main())
        await state.set_state(VideoStates.waiting_video)
    elif action == "redo":
        data = await state.get_data()
        if not data.get("file_path") or not Path(data["file_path"]).exists():
            await cq.message.answer(
                "Oldingi fayl topilmadi. Yangi video yuboring.",
                reply_markup=kb_main(),
            )
            await state.set_state(VideoStates.waiting_video)
            await cq.answer()
            return
        await cq.message.answer(
            "Siqish turini tanlang:", reply_markup=kb_compress_type()
        )
        await state.set_state(VideoStates.choosing_compress)
    await cq.answer()


# ── Compression core ───────────────────────────────────────────────────────
async def run_compression(msg: Message, state: FSMContext):
    data       = await state.get_data()
    input_path = data.get("file_path")
    filename   = data.get("filename", "video.mp4")
    info       = data.get("video_info", {})
    s          = data.get("custom", DEFAULT_CUSTOM.copy())

    if not input_path or not Path(input_path).exists():
        await msg.answer("❌ Fayl topilmadi. Qayta video yuboring.", reply_markup=kb_main())
        await state.clear()
        return

    duration = info.get("duration", 0)
    out_id   = str(uuid.uuid4())
    out_path = OUTPUT_DIR / f"compressed_{out_id}.mp4"

    # Build FFmpeg command
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "libx264",
        "-crf", str(s.get("crf", 24)),
        "-preset", s.get("preset", "medium"),
    ]
    scale = s.get("scale", "-2:-2")
    if scale and scale != "-2:-2":
        cmd += ["-vf", f"scale={scale}"]
    fps = s.get("fps", 0)
    if fps and fps > 0:
        cmd += ["-r", str(fps)]
    if s.get("remove_audio"):
        cmd += ["-an"]
    else:
        cmd += ["-c:a", "aac", "-b:a", s.get("audio", "128k")]
    if s.get("keep_sub", True):
        cmd += ["-c:s", "copy"]
    else:
        cmd += ["-sn"]
    cmd += ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(out_path)]

    prog_msg = await msg.answer(
        f"⏳ Siqish jarayoni\n\n"
        f"{progress_bar(0)} 0%\n\n"
        "Iltimos kuting..."
    )

    start_time = time.time()
    process = None

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        last_edit = 0
        last_pct  = -1

        async def read_progress():
            nonlocal last_edit, last_pct
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line = line.decode().strip()
                if "out_time_ms=" in line:
                    try:
                        ms  = int(line.split("=")[1])
                        cur = ms / 1_000_000
                        pct = min(int(cur / duration * 100), 99) if duration > 0 else 0
                        now = time.time()
                        if pct != last_pct and now - last_edit >= 2.5:
                            last_pct  = pct
                            last_edit = now
                            elapsed   = int(now - start_time)
                            eta       = int((elapsed / pct) * (100 - pct)) if pct > 0 else 0

                            if pct < 20:   stage = "📖 Faylni o'qiyapman..."
                            elif pct < 50: stage = "🔄 Video qayta ishlanmoqda..."
                            elif pct < 75: stage = "🔊 Audio optimizatsiya..."
                            elif pct < 90: stage = "📝 Subtitle tekshirilmoqda..."
                            else:          stage = "✅ Yakunlanmoqda..."

                            try:
                                await prog_msg.edit_text(
                                    f"⏳ Siqish jarayoni\n\n"
                                    f"{progress_bar(pct)} {pct}%\n\n"
                                    f"{stage}\n"
                                    f"⏱ O'tgan: {elapsed}s  |  📍 Taxmin: ~{eta}s"
                                )
                            except TelegramBadRequest:
                                pass
                    except (ValueError, ZeroDivisionError):
                        pass

        await asyncio.gather(read_progress(), process.wait())

        if process.returncode != 0:
            err = (await process.stderr.read()).decode()[-300:]
            await prog_msg.edit_text(f"❌ Siqish xatoligi:\n<code>{err}</code>", parse_mode="HTML")
            out_path.unlink(missing_ok=True)
            await msg.answer("Qaytish:", reply_markup=kb_main())
            await state.clear()
            return

        if not out_path.exists():
            await prog_msg.edit_text("❌ Chiqish fayli yaratilmadi.")
            await msg.answer("Qaytish:", reply_markup=kb_main())
            await state.clear()
            return

        in_size   = info.get("size", 1)
        out_size  = out_path.stat().st_size
        saved     = in_size - out_size
        saved_pct = round(saved / in_size * 100, 1) if in_size > 0 else 0
        elapsed   = int(time.time() - start_time)

        await prog_msg.edit_text(
            f"✅ <b>Siqish tugadi!</b>\n\n"
            f"📦 Asl hajm:   {fmt_size(in_size)}\n"
            f"📦 Yangi hajm: {fmt_size(out_size)}\n"
            f"💰 Tejaldi:    {fmt_size(saved)} ({saved_pct}%)\n"
            f"⏱ Vaqt:       {elapsed}s\n\n"
            "📤 Video yuborilmoqda...",
            parse_mode="HTML",
        )

        out_file = FSInputFile(
            str(out_path),
            filename=f"compressed_{Path(filename).stem}.mp4",
        )
        await msg.answer_video(
            out_file,
            caption=(
                f"✅ Video muvaffaqiyatli siqildi!\n\n"
                f"📦 {fmt_size(in_size)} → {fmt_size(out_size)}  (-{saved_pct}%)"
            ),
            reply_markup=kb_result(),
        )

        out_path.unlink(missing_ok=True)
        Path(input_path).unlink(missing_ok=True)
        await state.clear()
        await state.set_state(VideoStates.waiting_video)
        await msg.answer("Yangi video uchun:", reply_markup=kb_main())

    except asyncio.CancelledError:
        if process and process.returncode is None:
            process.kill()
        out_path.unlink(missing_ok=True)
        await prog_msg.edit_text("❌ Jarayon to'xtatildi.")
        await msg.answer("Qaytish:", reply_markup=kb_main())
        await state.clear()
    except Exception as e:
        log.exception("Siqish xatosi")
        await prog_msg.edit_text(f"❌ Kutilmagan xato:\n<code>{e}</code>", parse_mode="HTML")
        await msg.answer("Qaytish:", reply_markup=kb_main())
        await state.clear()
