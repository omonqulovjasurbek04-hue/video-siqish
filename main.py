

import os
import asyncio
import json
import uuid
import subprocess
import logging
import time
from pathlib import Path
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, BotCommand
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

# ── Setup ──────────────────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    raise ValueError(".env faylida BOT_TOKEN ni to'ldiring!")

UPLOAD_DIR = Path("bot_uploads")
OUTPUT_DIR = Path("bot_outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

bot_token = BOT_TOKEN

USE_LOCAL_SERVER = os.getenv("USE_LOCAL_SERVER", "false").lower() == "true"
LOCAL_SERVER_URL = os.getenv("LOCAL_SERVER_URL", "https://www.compress2go.com/ru/compress-video")

session_opt = None
if USE_LOCAL_SERVER:
    session_opt = AiohttpSession(
        api=TelegramAPIServer.from_base(LOCAL_SERVER_URL, is_local=True)
    )

bot = Bot(token=bot_token, session=session_opt)
dp  = Dispatcher(storage=MemoryStorage())
router = Router()

# ── FSM States ─────────────────────────────────────────────────────────────
class VideoStates(StatesGroup):
    waiting_video     = State()
    choosing_compress = State()
    custom_settings   = State()
    processing        = State()

# ── Compression profiles ───────────────────────────────────────────────────
COMPRESS_PROFILES = {
    "heavy": {
        "label":  "Kengaytirilgan siqish",
        "desc":   "Eng kichik hajm | Minimal sifat pasayishi",
        "crf": 32, "audio": "64k", "preset": "slow",   "scale": "1280:720",
    },
    "medium": {
        "label":  "O'rta siqish",
        "desc":   "Balanslangan sifat va hajm",
        "crf": 24, "audio": "128k", "preset": "medium", "scale": "-2:1080",
    },
    "light": {
        "label":  "Minimal siqish",
        "desc":   "Sifat deyarli o'zgarmaydi | Kichik hajm kamayishi",
        "crf": 18, "audio": "192k", "preset": "fast",   "scale": "-2:-2",
    },
}

PLATFORM_PROFILES = {
    "instagram": {"label": "Instagram",  "crf": 23, "audio": "128k", "scale": "1080:1080", "fps": 30},
    "tiktok":    {"label": "TikTok",     "crf": 23, "audio": "128k", "scale": "1080:1920", "fps": 30},
    "youtube":   {"label": "YouTube",    "crf": 20, "audio": "192k", "scale": "1920:1080", "fps": 60},
    "twitter":   {"label": "Twitter/X",  "crf": 25, "audio": "128k", "scale": "1280:720",  "fps": 30},
}

RES_OPTS   = ["-2:-2", "1920:1080", "1280:720", "854:480", "640:360"]
RES_LABELS = ["Asl", "1080p", "720p", "480p", "360p"]
FPS_OPTS   = [0, 24, 30, 60]

DEFAULT_CUSTOM = {
    "crf": 24, "audio": "128k", "fps": 0,
    "scale": "-2:-2", "remove_audio": False,
    "keep_sub": True, "preset": "medium",
}

ALLOWED_EXTS = {"mp4", "mov", "mkv", "avi", "webm", "flv", "wmv"}

# ── Helpers ────────────────────────────────────────────────────────────────
def fmt_size(b: int) -> str:
    if b < 1024:     return f"{b} B"
    if b < 1024**2:  return f"{b/1024:.1f} KB"
    if b < 1024**3:  return f"{b/1024**2:.2f} MB"
    return f"{b/1024**3:.2f} GB"

def fmt_dur(sec: float) -> str:
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"

def progress_bar(pct: int, width: int = 15) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)

def get_video_info(path: str) -> dict | None:
    try:
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
               "-show_format", "-show_streams", path]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        fmt  = data.get("format", {})
        info = {
            "size":     int(fmt.get("size", 0)),
            "duration": float(fmt.get("duration", 0)),
            "bitrate":  int(fmt.get("bit_rate", 0)),
        }
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                info["width"]  = s.get("width", 0)
                info["height"] = s.get("height", 0)
                info["vcodec"] = s.get("codec_name", "?")
                try:
                    n, d = s["r_frame_rate"].split("/")
                    info["fps"] = round(int(n) / int(d), 2)
                except Exception:
                    info["fps"] = 0
            elif s.get("codec_type") == "audio":
                info["acodec"] = s.get("codec_name", "?")
        return info
    except Exception as e:
        log.error(f"ffprobe xato: {e}")
        return None

def check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except FileNotFoundError:
        return False

# ── Bot commands setup ─────────────────────────────────────────────────────
async def set_default_commands(bot: Bot):
    commands = [
        BotCommand(command="start",  description="Botni ishga tushirish"),
        BotCommand(command="help",   description="Yordam va qo'llanma"),
        BotCommand(command="cancel", description="Jarayonni bekor qilish"),
    ]
    await bot.set_my_commands(commands)

# ── Keyboards ──────────────────────────────────────────────────────────────
def kb_main() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.button(text="🎬 Video yuborish")
    b.button(text="ℹ️ Yordam")
    b.adjust(1)
    return b.as_markup(resize_keyboard=True)

def kb_compress_type() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🗜 Kengaytirilgan siqish", callback_data="c:heavy")
    b.button(text="⚖️ O'rta siqish",         callback_data="c:medium")
    b.button(text="🪶 Minimal siqish",        callback_data="c:light")
    b.button(text="📱 Platforma profili",     callback_data="c:platform")
    b.button(text="⚙️ Sozlamalar",            callback_data="c:custom")
    b.button(text="❌ Bekor qilish",           callback_data="c:cancel")
    b.adjust(1)
    return b.as_markup()

def kb_platforms() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📸 Instagram",  callback_data="p:instagram")
    b.button(text="🎵 TikTok",     callback_data="p:tiktok")
    b.button(text="▶️ YouTube",    callback_data="p:youtube")
    b.button(text="🐦 Twitter/X",  callback_data="p:twitter")
    b.button(text="⬅️ Orqaga",     callback_data="p:back")
    b.adjust(2, 2, 1)
    return b.as_markup()

def kb_custom(s: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    crf   = s.get("crf", 24)
    audio = s.get("audio", "128k")
    fps   = s.get("fps", 0)
    scale = s.get("scale", "-2:-2")
    res_lbl = RES_LABELS[RES_OPTS.index(scale)] if scale in RES_OPTS else "Asl"

    b.button(text=f"🎨 CRF: {crf} (sifat)",    callback_data="cs:crf_info")
    b.button(text="➖",                         callback_data="cs:crf_up")
    b.button(text="➕",                         callback_data="cs:crf_dn")
    b.button(text=f"🔊 Ovoz: {audio}",          callback_data="cs:audio")
    b.button(text=f"🎞 FPS: {fps or 'Asl'}",    callback_data="cs:fps")
    b.button(text=f"📐 Ruxsat: {res_lbl}",      callback_data="cs:res")
    b.button(
        text=f"🔇 Ovoz o'chirish: {'✅' if s.get('remove_audio') else '❌'}",
        callback_data="cs:toggle_audio"
    )
    b.button(
        text=f"📝 Subtitle: {'Saqlash ✅' if s.get('keep_sub', True) else 'O\'chirish ❌'}",
        callback_data="cs:toggle_sub"
    )
    b.button(text="⚡ Siqishni boshlash", callback_data="cs:start")
    b.button(text="⬅️ Orqaga",           callback_data="cs:back")
    b.adjust(1, 2, 1, 1, 1, 1, 1, 1)
    return b.as_markup()

def kb_result() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Yangi video",    callback_data="r:new")
    b.button(text="⚙️ Qayta sozlash", callback_data="r:redo")
    b.adjust(1)
    return b.as_markup()

def kb_cancel_inline() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Bekor qilish", callback_data="c:cancel")
    return b.as_markup()

# ── /start ─────────────────────────────────────────────────────────────────
@router.message(CommandStart())
@router.message(F.text == "🔄 Bosh menyu")
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        f"👋 Salom, {msg.from_user.first_name}!\n\n"
        "🎬 VideoBot — video siqish boti\n\n"
        "Imkoniyatlar:\n"
        "• 3 xil siqish darajasi\n"
        "• Instagram, TikTok, YouTube profillari\n"
        "• FPS, ovoz, ruxsat sozlamalari\n"
        "• Jonli progress ko'rsatkich\n\n"
        "Boshlash uchun video yuboring 👇",
        reply_markup=kb_main()
    )
    await state.set_state(VideoStates.waiting_video)

# ── /help ──────────────────────────────────────────────────────────────────
@router.message(Command("help"))
@router.message(F.text == "ℹ️ Yordam")
async def cmd_help(msg: Message):
    await msg.answer(
        "📖 VideoBot — Qo'llanma\n\n"
        "Buyruqlar:\n"
        "/start — Botni ishga tushirish\n"
        "/help  — Qo'llanma\n"
        "/cancel — Bekor qilish\n\n"
        "Ishlash tartibi:\n"
        "1. Video yuboring (max 1.8GB)\n"
        "2. Siqish turini tanlang\n"
        "3. Sozlamalarni o'zgartiring (ixtiyoriy)\n"
        "4. Siqilgan videoni oling\n\n"
        "Siqish profillari:\n"
        "🗜 Kengaytirilgan — maksimal siqish\n"
        "⚖️ O'rta — tavsiya etiladi\n"
        "🪶 Minimal — yuqori sifat\n\n"
        "Platforma profillari:\n"
        "📸 Instagram  🎵 TikTok  ▶️ YouTube  🐦 Twitter\n\n"
        "Qo'llab-quvvatlanadigan formatlar:\n"
        "MP4 · MOV · MKV · AVI · WEBM · FLV",
        reply_markup=kb_main()
    )

# ── /cancel ────────────────────────────────────────────────────────────────
@router.message(Command("cancel"))
async def cmd_cancel(msg: Message, state: FSMContext):
    if await state.get_state():
        await state.clear()
        await msg.answer(
            "❌ Jarayon bekor qilindi.\n"
            "Yangi video yuborish uchun tugmani bosing.",
            reply_markup=kb_main()
        )
    else:
        await msg.answer("Hech qanday faol jarayon yo'q.", reply_markup=kb_main())

# ── Video yuborish tugmasi ─────────────────────────────────────────────────
@router.message(F.text == "🎬 Video yuborish")
async def btn_upload(msg: Message, state: FSMContext):
    await state.set_state(VideoStates.waiting_video)
    await msg.answer(
        "🎬 Video yuboring\n\n"
        "Qo'llab-quvvatlanadigan formatlar:\n"
        "MP4, MOV, MKV, AVI, WEBM, FLV\n\n"
        "Bekor qilish uchun /cancel",
        reply_markup=kb_main()
    )

# ── Video qabul qilish ─────────────────────────────────────────────────────
@router.message(VideoStates.waiting_video, F.video | F.document)
async def handle_video(msg: Message, state: FSMContext):
    if not check_ffmpeg():
        await msg.answer(
            "❌ FFmpeg topilmadi!\n\n"
            "Bot ishlashi uchun FFmpeg kerak.\n"
            "O'rnatish: https://ffmpeg.org/download.html"
        )
        return

    fobj     = msg.video or msg.document
    file_size = getattr(fobj, "file_size", 0)

    max_size_limit = (1.8 * 1024 * 1024 * 1024) if USE_LOCAL_SERVER else (20 * 1024 * 1024)

    if file_size and file_size > max_size_limit:
        sz_str = "1.8GB" if USE_LOCAL_SERVER else "20MB"
        await msg.answer(
            f"❌ Fayl hajmi katta: {fmt_size(file_size)}\n\n"
            f"Bot faqatgina {sz_str} gacha bo'lgan videolarni qabul qila oladi."
        )
        return

    filename = getattr(fobj, "file_name", None) or "video.mp4"
    ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else "mp4"

    if ext not in ALLOWED_EXTS:
        await msg.answer(
            f"❌ .{ext} formati qo'llab-quvvatlanmaydi.\n\n"
            f"Ruxsat etilgan: {', '.join(sorted(ALLOWED_EXTS)).upper()}"
        )
        return

    prog = await msg.answer("⏬ Video yuklanmoqda...", reply_markup=ReplyKeyboardRemove())

    try:
        fid       = str(uuid.uuid4())
        save_path = UPLOAD_DIR / f"{fid}.{ext}"
        finfo     = await bot.get_file(fobj.file_id)
        await bot.download_file(finfo.file_path, destination=str(save_path))

        await prog.edit_text("🔍 Video tahlil qilinmoqda...")
        info = get_video_info(str(save_path))

        if not info:
            await prog.edit_text(
                "❌ Videoni tahlil qilib bo'lmadi.\n"
                "Boshqa fayl yuboring."
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

        res = f"{info.get('width',0)}x{info.get('height',0)}" if info.get("width") else "—"
        await prog.edit_text(
            f"✅ Video tahlil qilindi!\n\n"
            f"Fayl:       {filename}\n"
            f"Hajm:       {fmt_size(info['size'])}\n"
            f"Davomiylik: {fmt_dur(info['duration'])}\n"
            f"Ruxsat:     {res}\n"
            f"FPS:        {info.get('fps', '—')}\n"
            f"V-kodek:    {info.get('vcodec', '—')}\n"
            f"A-kodek:    {info.get('acodec', '—')}\n"
            f"Bit tezlik: {info.get('bitrate',0)//1000} kbps\n\n"
            "Siqish turini tanlang:",
            reply_markup=kb_compress_type()
        )
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
            "📱 Platforma profilini tanlang:\n\n"
            "Har bir platforma uchun optimal sozlamalar avtomatik o'rnatiladi.",
            reply_markup=kb_platforms()
        )
        await cq.answer()
        return

    if key == "custom":
        data = await state.get_data()
        await cq.message.edit_text(
            "⚙️ Kengaytirilgan sozlamalar\n\n"
            "CRF: 0 = eng yuqori sifat, 51 = eng past sifat",
            reply_markup=kb_custom(data.get("custom", DEFAULT_CUSTOM.copy()))
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
            f"{p['label']} tanlandi\n{p['desc']}\n\nSiqish boshlanyapti..."
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
            "Siqish turini tanlang:",
            reply_markup=kb_compress_type()
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
            f"Ruxsat: {p['scale'].replace(':', 'x')}\n"
            f"FPS:    {p.get('fps', 30)}\n"
            f"Ovoz:   {p['audio']}\n\n"
            "Siqish boshlanyapti..."
        )
        await cq.answer()
        await state.set_state(VideoStates.processing)
        await run_compression(cq.message, state)

# ── Custom settings ────────────────────────────────────────────────────────
@router.callback_query(VideoStates.custom_settings, F.data.startswith("cs:"))
async def on_custom(cq: CallbackQuery, state: FSMContext):
    action = cq.data.split(":", 1)[1]
    data   = await state.get_data()
    s      = data.get("custom", DEFAULT_CUSTOM.copy())

    if action == "back":
        await cq.message.edit_text(
            "Siqish turini tanlang:",
            reply_markup=kb_compress_type()
        )
        await state.set_state(VideoStates.choosing_compress)
        await cq.answer()
        return

    if action == "crf_info":
        await cq.answer(
            f"CRF: {s.get('crf', 24)}\n0=eng yuqori sifat, 51=eng past",
            show_alert=True
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
        cur  = s.get("audio", "128k")
        idx  = opts.index(cur) if cur in opts else 1
        s["audio"] = opts[(idx + 1) % len(opts)]
        await cq.answer(f"Ovoz: {s['audio']}")

    elif action == "fps":
        cur  = s.get("fps", 0)
        idx  = FPS_OPTS.index(cur) if cur in FPS_OPTS else 0
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
        await cq.message.edit_text(
            f"Sozlamalar qabul qilindi\n\n"
            f"CRF:    {s.get('crf', 24)}\n"
            f"Ovoz:   {s.get('audio', '128k')}\n"
            f"FPS:    {s.get('fps') or 'Asl'}\n"
            f"Ruxsat: {RES_LABELS[RES_OPTS.index(s.get('scale','-2:-2'))] if s.get('scale') in RES_OPTS else 'Asl'}\n\n"
            "Siqish boshlanyapti..."
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
        await cq.message.answer(
            "Yangi video yuboring:",
            reply_markup=kb_main()
        )
        await state.set_state(VideoStates.waiting_video)
    elif action == "redo":
        data = await state.get_data()
        if not data.get("file_path") or not Path(data["file_path"]).exists():
            await cq.message.answer(
                "Oldingi fayl topilmadi. Yangi video yuboring.",
                reply_markup=kb_main()
            )
            await state.set_state(VideoStates.waiting_video)
            await cq.answer()
            return
        await cq.message.answer(
            "Siqish turini tanlang:",
            reply_markup=kb_compress_type()
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
        f"Siqish jarayoni\n\n"
        f"{progress_bar(0)} 0%\n\n"
        "Iltimos kuting..."
    )

    start_time = time.time()

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

                            if pct < 20:   stage = "Faylni o'qiyapman..."
                            elif pct < 50: stage = "Video qayta ishlanmoqda..."
                            elif pct < 75: stage = "Audio optimizatsiya..."
                            elif pct < 90: stage = "Subtitle tekshirilmoqda..."
                            else:          stage = "Yakunlanmoqda..."

                            try:
                                await prog_msg.edit_text(
                                    f"Siqish jarayoni\n\n"
                                    f"{progress_bar(pct)} {pct}%\n\n"
                                    f"{stage}\n"
                                    f"O'tgan: {elapsed}s  |  Taxmin: ~{eta}s"
                                )
                            except TelegramBadRequest:
                                pass
                    except (ValueError, ZeroDivisionError):
                        pass

        await asyncio.gather(read_progress(), process.wait())

        if process.returncode != 0:
            err = (await process.stderr.read()).decode()[-300:]
            await prog_msg.edit_text(f"❌ Siqish xatoligi:\n{err}")
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
            f"Siqish tugadi!\n\n"
            f"Asl hajm:   {fmt_size(in_size)}\n"
            f"Yangi hajm: {fmt_size(out_size)}\n"
            f"Tejaldi:    {fmt_size(saved)} ({saved_pct}%)\n"
            f"Vaqt:       {elapsed}s\n\n"
            "Video yuborilmoqda..."
        )

        out_file = FSInputFile(
            str(out_path),
            filename=f"compressed_{Path(filename).stem}.mp4"
        )
        await msg.answer_video(
            out_file,
            caption=(
                f"Video muvaffaqiyatli kamaytirildi!\n\n"
                f"{fmt_size(in_size)} → {fmt_size(out_size)}  (-{saved_pct}%)"
            ),
            reply_markup=kb_result()
        )

        out_path.unlink(missing_ok=True)
        Path(input_path).unlink(missing_ok=True)
        await state.clear()
        await state.set_state(VideoStates.waiting_video)
        await msg.answer("Yangi video uchun:", reply_markup=kb_main())

    except asyncio.CancelledError:
        if process.returncode is None:
            process.kill()
        out_path.unlink(missing_ok=True)
        await prog_msg.edit_text("❌ Jarayon to'xtatildi.")
        await msg.answer("Qaytish:", reply_markup=kb_main())
        await state.clear()
    except Exception as e:
        log.exception("Siqish xatosi")
        await prog_msg.edit_text(f"❌ Kutilmagan xato:\n{e}")
        await msg.answer("Qaytish:", reply_markup=kb_main())
        await state.clear()

# ── Fallback ────────────────────────────────────────────────────────────────
@router.message(VideoStates.waiting_video)
async def fallback_waiting(msg: Message):
    if msg.text and msg.text.startswith("/"):
        return
    await msg.answer(
        "🎬 Video yuboring!\n"
        "Qo'llab-quvvatlanadigan: MP4, MOV, MKV, AVI, WEBM, FLV"
    )

@router.message()
async def fallback_global(msg: Message, state: FSMContext):
    if await state.get_state() is None:
        await state.set_state(VideoStates.waiting_video)
        await msg.answer("Boshlash uchun:", reply_markup=kb_main())

# ── Main ───────────────────────────────────────────────────────────────────
async def main():
    dp.include_router(router)
    await set_default_commands(bot)
    log.info("VideoBot ishga tushdi!")
    if not check_ffmpeg():
        log.warning("FFmpeg topilmadi! Video siqish ishlamaydi.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
