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

class TrimStates(StatesGroup):
    waiting_video = State()
    waiting_start = State()
    waiting_end   = State()

class MergeStates(StatesGroup):
    waiting_first  = State()
    waiting_second = State()

class WatermarkStates(StatesGroup):
    waiting_video = State()
    waiting_text  = State()

class GifStates(StatesGroup):
    waiting_video  = State()
    waiting_choice = State()
    waiting_time   = State()

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
        BotCommand(command="start",     description="Botni ishga tushirish"),
        BotCommand(command="help",      description="Yordam va qo'llanma"),
        BotCommand(command="trim",      description="✂️ Video kesish"),
        BotCommand(command="merge",     description="🔗 Video birlashtirish"),
        BotCommand(command="watermark", description="💧 Watermark qo'shish"),
        BotCommand(command="gif",       description="🎞 GIF / Screenshot"),
        BotCommand(command="siq",       description="🗜 Tezkor siqish"),
        BotCommand(command="sifat",     description="✨ Sifat ko'tarish"),
        BotCommand(command="olcham",    description="📐 O'lcham o'zgartirish"),
        BotCommand(command="fps",       description="🎬 FPS o'zgartirish"),
        BotCommand(command="ovoz",      description="🔊 Ovoz sozlamalari"),
        BotCommand(command="info",      description="📊 Video ma'lumotlari"),
        BotCommand(command="cancel",    description="❌ Bekor qilish"),
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
        "• 🗜 3 xil siqish darajasi\n"
        "• 📱 Instagram, TikTok, YouTube profillari\n"
        "• ⚙️ FPS, ovoz, ruxsat sozlamalari\n"
        "• ✂️ Video kesish (/trim)\n"
        "• 🔗 Video birlashtirish (/merge)\n"
        "• 💧 Watermark qo'shish (/watermark)\n"
        "• 🎞 GIF / Screenshot (/gif)\n"
        "• 📊 Jonli progress ko'rsatkich\n\n"
        "Video yuboring yoki buyruq tanlang 👇",
        reply_markup=kb_main()
    )
    await state.set_state(VideoStates.waiting_video)

# ── /help ──────────────────────────────────────────────────────────────────
@router.message(Command("help"))
@router.message(F.text == "ℹ️ Yordam")
async def cmd_help(msg: Message):
    await msg.answer(
        "📖 <b>VideoBot — Qo'llanma</b>\n\n"
        "<b>Asosiy buyruqlar:</b>\n"
        "/start — Botni ishga tushirish\n"
        "/help  — Qo'llanma\n"
        "/cancel — Bekor qilish\n\n"
        "<b>Video asboblar:</b>\n"
        "/trim — ✂️ Video kesish\n"
        "/merge — 🔗 2 ta video birlashtirish\n"
        "/watermark — 💧 Watermark qo'shish\n"
        "/gif — 🎞 GIF yoki Screenshot\n\n"
        "<b>Tezkor buyruqlar (video yuborgandan keyin):</b>\n"
        "/siq — 🗜 Hajmni kamaytirish\n"
        "/sifat — ✨ Sifat ko'tarish\n"
        "/olcham — 📐 O'lchamni o'zgartirish\n"
        "/fps — 🎬 FPS o'zgartirish\n"
        "/ovoz — 🔊 Ovoz sozlamalari\n"
        "/info — 📊 Video ma'lumotlari\n\n"
        "<b>Siqish:</b>\n"
        "Video yuboring → siqish turini tanlang\n"
        "🗜 Kengaytirilgan | ⚖️ O'rta | 🪶 Minimal\n\n"
        "<b>Platformalar:</b>\n"
        "📸 Instagram  🎵 TikTok  ▶️ YouTube  🐦 Twitter\n\n"
        "<b>Formatlar:</b> MP4 · MOV · MKV · AVI · WEBM · FLV",
        parse_mode="HTML",
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

# ── Async FFmpeg helper ────────────────────────────────────────────────────
async def run_ffmpeg_async(cmd: list, message: Message, timeout: int = 3600) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            err = stderr.decode()[-500:]
            await message.answer(f"❌ FFmpeg xatosi:\n<code>{err}</code>", parse_mode="HTML")
            return False
        return True
    except asyncio.TimeoutError:
        await message.answer("⏱ Vaqt tugadi. Video juda katta.")
        return False
    except FileNotFoundError:
        await message.answer("❌ FFmpeg topilmadi! <code>sudo apt install ffmpeg</code>", parse_mode="HTML")
        return False

def cleanup_files(*paths):
    for p in paths:
        try:
            if p and Path(p).exists():
                Path(p).unlink()
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════════════════
# ✂️  /trim — Video kesish
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("trim"))
async def cmd_trim(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(TrimStates.waiting_video)
    await msg.answer("✂️ <b>Video kesish</b>\n\nQirqmoqchi bo'lgan videoni yuboring:", parse_mode="HTML")

@router.message(TrimStates.waiting_video, F.video | F.document)
async def trim_get_video(msg: Message, state: FSMContext):
    fobj = msg.video or msg.document
    await state.update_data(file_id=fobj.file_id)
    await state.set_state(TrimStates.waiting_start)
    await msg.answer(
        "⏱ <b>Boshlash vaqtini kiriting:</b>\n\n"
        "• <code>00:01:30</code> — 1 daqiqa 30 soniya\n"
        "• <code>90</code> — 90 soniya", parse_mode="HTML"
    )

@router.message(TrimStates.waiting_start)
async def trim_get_start(msg: Message, state: FSMContext):
    await state.update_data(start=msg.text.strip())
    await state.set_state(TrimStates.waiting_end)
    await msg.answer(
        "⏱ <b>Tugash vaqtini kiriting:</b>\n\n"
        "• <code>00:03:00</code> — 3 daqiqa\n"
        "• <code>end</code> — oxirigacha", parse_mode="HTML"
    )

@router.message(TrimStates.waiting_end)
async def trim_get_end(msg: Message, state: FSMContext):
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
        await msg.answer_video(FSInputFile(str(out)), caption=f"✂️ Qirqilgan: {start} → {end}")
    cleanup_files(inp, out)
    await msg.answer("Yangi buyruq:", reply_markup=kb_main())

# ═══════════════════════════════════════════════════════════════════════════
# 🔗  /merge — Video birlashtirish
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("merge"))
async def cmd_merge(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(MergeStates.waiting_first)
    await msg.answer("🔗 <b>Video birlashtirish</b>\n\n1-chi videoni yuboring:", parse_mode="HTML")

@router.message(MergeStates.waiting_first, F.video | F.document)
async def merge_first(msg: Message, state: FSMContext):
    fobj = msg.video or msg.document
    await state.update_data(file_id_1=fobj.file_id)
    await state.set_state(MergeStates.waiting_second)
    await msg.answer("✅ 1-chi video qabul qilindi.\n\n2-chi videoni yuboring:")

@router.message(MergeStates.waiting_second, F.video | F.document)
async def merge_second(msg: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    uid = msg.from_user.id
    fobj = msg.video or msg.document
    status = await msg.answer("⏳ Videolar birlashtirilmoqda...")

    p1 = UPLOAD_DIR / f"m1_{uid}.mp4"
    p2 = UPLOAD_DIR / f"m2_{uid}.mp4"
    n1 = OUTPUT_DIR / f"n1_{uid}.mp4"
    n2 = OUTPUT_DIR / f"n2_{uid}.mp4"
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

    for src, dst in [(p1, n1), (p2, n2)]:
        ok = await run_ffmpeg_async(
            ["ffmpeg", "-y", "-i", str(src), "-vf", "scale=1280:720,fps=30",
             "-c:v", "libx264", "-c:a", "aac", str(dst)], msg
        )
        if not ok:
            cleanup_files(p1, p2, n1, n2)
            return

    with open(lst, "w") as f:
        f.write(f"file '{n1.resolve()}'\nfile '{n2.resolve()}'\n")

    if await run_ffmpeg_async(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], msg
    ):
        await status.edit_text("✅ Videolar birlashtirildi!")
        await msg.answer_video(FSInputFile(str(out)), caption="🔗 Birlashtirilgan video")
    cleanup_files(p1, p2, n1, n2, lst, out)
    await msg.answer("Yangi buyruq:", reply_markup=kb_main())

# ═══════════════════════════════════════════════════════════════════════════
# 💧  /watermark — Watermark qo'shish
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("watermark"))
async def cmd_watermark(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(WatermarkStates.waiting_video)
    await msg.answer("💧 <b>Watermark qo'shish</b>\n\nVideoni yuboring:", parse_mode="HTML")

@router.message(WatermarkStates.waiting_video, F.video | F.document)
async def wm_get_video(msg: Message, state: FSMContext):
    fobj = msg.video or msg.document
    await state.update_data(file_id=fobj.file_id)
    await state.set_state(WatermarkStates.waiting_text)
    await msg.answer(
        "✏️ <b>Watermark matnini kiriting:</b>\n\n"
        "Misol: <code>@MyChannel</code>\n\n"
        "Joy tanlash: <code>@MyChannel|markaz</code>\n"
        "Joylar: <code>o'ng-ost</code>, <code>chap-ost</code>, "
        "<code>o'ng-ust</code>, <code>chap-ust</code>, <code>markaz</code>",
        parse_mode="HTML"
    )

@router.message(WatermarkStates.waiting_text)
async def wm_apply(msg: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    uid = msg.from_user.id
    parts = msg.text.strip().split("|")
    text = parts[0].strip()
    position = parts[1].strip() if len(parts) > 1 else "o'ng-ost"

    pos_map = {
        "o'ng-ost": "x=w-tw-20:y=h-th-20", "chap-ost": "x=20:y=h-th-20",
        "o'ng-ust": "x=w-tw-20:y=20", "chap-ust": "x=20:y=20",
        "markaz": "x=(w-tw)/2:y=(h-th)/2",
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

    drawtext = (f"drawtext=text='{text}':fontsize=36:fontcolor=white@0.8"
                f":borderw=2:bordercolor=black@0.5:{pos}")
    if await run_ffmpeg_async(
        ["ffmpeg", "-y", "-i", str(inp), "-vf", drawtext,
         "-c:v", "libx264", "-c:a", "copy", str(out)], msg
    ):
        await status.edit_text(f"✅ Watermark qo'shildi!\n💧 {text} | 📍 {position}")
        await msg.answer_video(FSInputFile(str(out)), caption=f"💧 Watermark: {text}")
    cleanup_files(inp, out)
    await msg.answer("Yangi buyruq:", reply_markup=kb_main())

# ═══════════════════════════════════════════════════════════════════════════
# 🎞  /gif — GIF va Screenshot
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("gif"))
async def cmd_gif(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(GifStates.waiting_video)
    await msg.answer("🎞 <b>GIF / Screenshot</b>\n\nVideoni yuboring:", parse_mode="HTML")

@router.message(GifStates.waiting_video, F.video | F.document)
async def gif_get_video(msg: Message, state: FSMContext):
    fobj = msg.video or msg.document
    await state.update_data(file_id=fobj.file_id)
    await state.set_state(GifStates.waiting_choice)
    await msg.answer(
        "🎯 <b>Nima qilmoqchisiz?</b>\n\n"
        "1️⃣ — GIF yaratish\n2️⃣ — Screenshot olish\n\n"
        "Raqam yozing: <code>1</code> yoki <code>2</code>", parse_mode="HTML"
    )

@router.message(GifStates.waiting_choice)
async def gif_choice(msg: Message, state: FSMContext):
    choice = msg.text.strip()
    if choice not in ["1", "2"]:
        await msg.answer("❗ Faqat <code>1</code> yoki <code>2</code> yozing.", parse_mode="HTML")
        return
    await state.update_data(choice=choice)
    await state.set_state(GifStates.waiting_time)
    if choice == "1":
        await msg.answer(
            "⏱ <b>GIF vaqti:</b> <code>00:00:05-00:00:10</code>\n"
            "Max 15 soniya tavsiya", parse_mode="HTML")
    else:
        await msg.answer("⏱ <b>Screenshot vaqti:</b> <code>00:00:05</code>", parse_mode="HTML")

@router.message(GifStates.waiting_time)
async def gif_process(msg: Message, state: FSMContext):
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
            await msg.answer("❗ Format: <code>boshlash-tugash</code>", parse_mode="HTML")
            cleanup_files(inp)
            return
        start, end = parts[0].strip(), parts[1].strip()
        pal = OUTPUT_DIR / f"pal_{uid}.png"
        out = OUTPUT_DIR / f"out_{uid}.gif"
        status = await msg.answer("⏳ GIF yaratilmoqda...")

        ok = await run_ffmpeg_async(
            ["ffmpeg", "-y", "-ss", start, "-to", end, "-i", str(inp),
             "-vf", "fps=12,scale=480:-1:flags=lanczos,palettegen", str(pal)], msg)
        if ok:
            ok = await run_ffmpeg_async(
                ["ffmpeg", "-y", "-ss", start, "-to", end, "-i", str(inp),
                 "-i", str(pal), "-lavfi",
                 "fps=12,scale=480:-1:flags=lanczos[x];[x][1:v]paletteuse", str(out)], msg)
        if ok:
            await status.edit_text(f"✅ GIF tayyor! {start} → {end}")
            await msg.answer_document(FSInputFile(str(out)), caption=f"🎞 GIF: {start}→{end}")
        cleanup_files(inp, pal, out)
    else:
        out = OUTPUT_DIR / f"ss_{uid}.jpg"
        status = await msg.answer("⏳ Screenshot olinmoqda...")
        if await run_ffmpeg_async(
            ["ffmpeg", "-y", "-ss", t, "-i", str(inp),
             "-frames:v", "1", "-q:v", "2", str(out)], msg
        ):
            await status.edit_text(f"✅ Screenshot olindi! Vaqt: {t}")
            await msg.answer_photo(FSInputFile(str(out)), caption=f"📸 Screenshot: {t}")
        cleanup_files(inp, out)
    await msg.answer("Yangi buyruq:", reply_markup=kb_main())

# ═══════════════════════════════════════════════════════════════════════════
# 🗜  /siq — Tezkor video siqish (buyruq orqali)
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("siq"))
async def cmd_siq(msg: Message, state: FSMContext):
    data = await state.get_data()
    input_path = data.get("file_path")
    if not input_path or not Path(input_path).exists():
        await msg.answer("❌ Avval video yuboring!")
        return
    info = data.get("video_info", {})
    out_path = OUTPUT_DIR / f"siq_{uuid.uuid4()}.mp4"
    status = await msg.answer("🗜 <b>Siqilmoqda...</b> Kuting.", parse_mode="HTML")

    ok = await run_ffmpeg_async([
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "libx264", "-crf", "23", "-preset", "slow",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", str(out_path)
    ], msg)

    if ok and out_path.exists():
        in_sz = info.get("size", Path(input_path).stat().st_size)
        out_sz = out_path.stat().st_size
        saved = round((1 - out_sz / in_sz) * 100) if in_sz > 0 else 0
        await status.edit_text(
            f"✅ <b>Tayyor!</b> {saved}% tejaldi\n"
            f"📦 {fmt_size(in_sz)} → {fmt_size(out_sz)}", parse_mode="HTML")
        await msg.answer_video(FSInputFile(str(out_path)),
            caption=f"🗜 Siqilgan video\n📦 {fmt_size(out_sz)} ({saved}% kichikroq)")
        out_path.unlink(missing_ok=True)
    else:
        await status.edit_text("❌ Siqishda xato yuz berdi.")

# ═══════════════════════════════════════════════════════════════════════════
# ✨  /sifat — Sifat ko'tarish (denoise + sharpen + color)
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("sifat"))
async def cmd_sifat(msg: Message, state: FSMContext):
    data = await state.get_data()
    input_path = data.get("file_path")
    if not input_path or not Path(input_path).exists():
        await msg.answer("❌ Avval video yuboring!")
        return
    out_path = OUTPUT_DIR / f"sifat_{uuid.uuid4()}.mp4"
    status = await msg.answer(
        "✨ <b>Sifat ko'tarilmoqda...</b>\n"
        "Denoise + Sharpen + Color — kuting.", parse_mode="HTML")

    ok = await run_ffmpeg_async([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "hqdn3d=4:3:6:4.5,unsharp=5:5:1.5:5:5:0.0,"
               "eq=gamma=1.1:saturation=1.2:contrast=1.05",
        "-c:v", "libx264", "-crf", "18", "-preset", "slow",
        "-c:a", "copy", str(out_path)
    ], msg)

    if ok and out_path.exists():
        out_sz = out_path.stat().st_size
        await status.edit_text("✅ <b>Sifat ko'tarildi!</b>", parse_mode="HTML")
        await msg.answer_video(FSInputFile(str(out_path)),
            caption=f"✨ Sifati yaxshilangan video\n📦 {fmt_size(out_sz)}")
        out_path.unlink(missing_ok=True)
    else:
        await status.edit_text("❌ Sifat ko'tarishda xato.")

# ═══════════════════════════════════════════════════════════════════════════
# 📐  /olcham — O'lcham o'zgartirish
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("olcham"))
async def cmd_olcham(msg: Message):
    await msg.answer(
        "📐 <b>O'lchamni tanlang:</b>\n\n"
        "/olcham_4k — 3840x2160 (4K)\n"
        "/olcham_1080 — 1920x1080 (Full HD)\n"
        "/olcham_720 — 1280x720 (HD)\n"
        "/olcham_480 — 854x480 (SD)\n"
        "/olcham_360 — 640x360 (Mobil)", parse_mode="HTML")

async def do_resize(msg: Message, state: FSMContext, scale: str, label: str):
    data = await state.get_data()
    input_path = data.get("file_path")
    if not input_path or not Path(input_path).exists():
        await msg.answer("❌ Avval video yuboring!")
        return
    out_path = OUTPUT_DIR / f"resize_{uuid.uuid4()}.mp4"
    status = await msg.answer(f"📐 <b>{label} ga o'zgartirilmoqda...</b>", parse_mode="HTML")

    ok = await run_ffmpeg_async([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={scale}:flags=lanczos",
        "-c:v", "libx264", "-crf", "20",
        "-c:a", "copy", str(out_path)
    ], msg)

    if ok and out_path.exists():
        out_sz = out_path.stat().st_size
        await status.edit_text(f"✅ <b>{label}</b> tayyor!", parse_mode="HTML")
        await msg.answer_video(FSInputFile(str(out_path)),
            caption=f"📐 {label}\n📦 {fmt_size(out_sz)}")
        out_path.unlink(missing_ok=True)
    else:
        await status.edit_text("❌ O'lcham o'zgartirishda xato.")

@router.message(Command("olcham_4k"))
async def r_4k(msg: Message, state: FSMContext): await do_resize(msg, state, "3840:2160", "4K Ultra HD")

@router.message(Command("olcham_1080"))
async def r_1080(msg: Message, state: FSMContext): await do_resize(msg, state, "1920:1080", "Full HD 1080p")

@router.message(Command("olcham_720"))
async def r_720(msg: Message, state: FSMContext): await do_resize(msg, state, "1280:720", "HD 720p")

@router.message(Command("olcham_480"))
async def r_480(msg: Message, state: FSMContext): await do_resize(msg, state, "854:480", "SD 480p")

@router.message(Command("olcham_360"))
async def r_360(msg: Message, state: FSMContext): await do_resize(msg, state, "640:360", "Mobil 360p")

# ═══════════════════════════════════════════════════════════════════════════
# 🎬  /fps — FPS o'zgartirish
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("fps"))
async def cmd_fps(msg: Message):
    await msg.answer(
        "🎬 <b>FPS tanlang:</b>\n\n"
        "/fps_24 — 24 FPS (kino)\n"
        "/fps_30 — 30 FPS (standart)\n"
        "/fps_60 — 60 FPS (geyming/sport)\n"
        "/fps_slow — Slow-motion (0.5x)\n"
        "/fps_fast — Tezlashtirish (2x)", parse_mode="HTML")

async def do_fps(msg: Message, state: FSMContext, fps_cmd: list, label: str):
    data = await state.get_data()
    input_path = data.get("file_path")
    if not input_path or not Path(input_path).exists():
        await msg.answer("❌ Avval video yuboring!")
        return
    out_path = OUTPUT_DIR / f"fps_{uuid.uuid4()}.mp4"
    status = await msg.answer(f"🎬 <b>{label}</b> qo'llanilmoqda...", parse_mode="HTML")
    cmd = ["ffmpeg", "-y", "-i", input_path] + fps_cmd + ["-c:a", "copy", str(out_path)]
    if await run_ffmpeg_async(cmd, msg) and out_path.exists():
        out_sz = out_path.stat().st_size
        await status.edit_text(f"✅ <b>{label}</b> tayyor!", parse_mode="HTML")
        await msg.answer_video(FSInputFile(str(out_path)),
            caption=f"🎬 {label}\n📦 {fmt_size(out_sz)}")
        out_path.unlink(missing_ok=True)
    else:
        await status.edit_text("❌ FPS o'zgartirishda xato.")

@router.message(Command("fps_24"))
async def fps_24(msg: Message, state: FSMContext):
    await do_fps(msg, state, ["-r", "24", "-c:v", "libx264", "-crf", "23"], "24 FPS (Kino)")

@router.message(Command("fps_30"))
async def fps_30(msg: Message, state: FSMContext):
    await do_fps(msg, state, ["-r", "30", "-c:v", "libx264", "-crf", "23"], "30 FPS (Standart)")

@router.message(Command("fps_60"))
async def fps_60(msg: Message, state: FSMContext):
    await do_fps(msg, state, ["-r", "60", "-c:v", "libx264", "-crf", "23"], "60 FPS (Geyming)")

@router.message(Command("fps_slow"))
async def fps_slow(msg: Message, state: FSMContext):
    await do_fps(msg, state, ["-vf", "setpts=2.0*PTS", "-c:v", "libx264", "-crf", "23"], "Slow-motion 0.5x")

@router.message(Command("fps_fast"))
async def fps_fast(msg: Message, state: FSMContext):
    await do_fps(msg, state, ["-vf", "setpts=0.5*PTS", "-c:v", "libx264", "-crf", "23"], "Tezlashtirish 2x")

# ═══════════════════════════════════════════════════════════════════════════
# 🔊  /ovoz — Ovoz sozlamalari
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("ovoz"))
async def cmd_ovoz(msg: Message):
    await msg.answer(
        "🔊 <b>Ovoz sozlamalari:</b>\n\n"
        "/ovoz_olib — Ovozni olib tashlash\n"
        "/ovoz_96 — 96k bitrate (kichik)\n"
        "/ovoz_128 — 128k bitrate (standart)\n"
        "/ovoz_192 — 192k bitrate (yuqori)\n"
        "/ovoz_mono — Stereo → Mono", parse_mode="HTML")

async def do_audio(msg: Message, state: FSMContext, audio_cmd: list, label: str):
    data = await state.get_data()
    input_path = data.get("file_path")
    if not input_path or not Path(input_path).exists():
        await msg.answer("❌ Avval video yuboring!")
        return
    out_path = OUTPUT_DIR / f"audio_{uuid.uuid4()}.mp4"
    status = await msg.answer(f"🔊 <b>{label}</b> qo'llanilmoqda...", parse_mode="HTML")
    cmd = ["ffmpeg", "-y", "-i", input_path, "-c:v", "copy"] + audio_cmd + [str(out_path)]
    if await run_ffmpeg_async(cmd, msg) and out_path.exists():
        out_sz = out_path.stat().st_size
        await status.edit_text(f"✅ <b>{label}</b> tayyor!", parse_mode="HTML")
        await msg.answer_video(FSInputFile(str(out_path)),
            caption=f"🔊 {label}\n📦 {fmt_size(out_sz)}")
        out_path.unlink(missing_ok=True)
    else:
        await status.edit_text("❌ Ovoz sozlashda xato.")

@router.message(Command("ovoz_olib"))
async def ovoz_olib(msg: Message, state: FSMContext):
    await do_audio(msg, state, ["-an"], "Ovoz olib tashlandi")

@router.message(Command("ovoz_96"))
async def ovoz_96(msg: Message, state: FSMContext):
    await do_audio(msg, state, ["-c:a", "aac", "-b:a", "96k"], "Ovoz 96kbps")

@router.message(Command("ovoz_128"))
async def ovoz_128(msg: Message, state: FSMContext):
    await do_audio(msg, state, ["-c:a", "aac", "-b:a", "128k"], "Ovoz 128kbps")

@router.message(Command("ovoz_192"))
async def ovoz_192(msg: Message, state: FSMContext):
    await do_audio(msg, state, ["-c:a", "aac", "-b:a", "192k"], "Ovoz 192kbps")

@router.message(Command("ovoz_mono"))
async def ovoz_mono(msg: Message, state: FSMContext):
    await do_audio(msg, state, ["-c:a", "aac", "-b:a", "128k", "-ac", "1"], "Mono ovoz")

# ═══════════════════════════════════════════════════════════════════════════
# ℹ️  /info — Video ma'lumotlari
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("info"))
async def cmd_info(msg: Message, state: FSMContext):
    data = await state.get_data()
    input_path = data.get("file_path")
    if not input_path or not Path(input_path).exists():
        await msg.answer("❌ Avval video yuboring!")
        return
    info = data.get("video_info")
    if not info:
        info = get_video_info(input_path)
    if info:
        dur = info.get("duration", 0)
        await msg.answer(
            f"📊 <b>Video ma'lumotlari:</b>\n\n"
            f"📐 O'lcham: <b>{info.get('width', '?')}x{info.get('height', '?')}</b>\n"
            f"⏱ Davomiylik: <b>{fmt_dur(dur)}</b>\n"
            f"🎞 FPS: <b>{info.get('fps', '?')}</b>\n"
            f"🔧 V-kodek: <b>{info.get('vcodec', '?')}</b>\n"
            f"🔊 A-kodek: <b>{info.get('acodec', '?')}</b>\n"
            f"📦 Hajm: <b>{fmt_size(info.get('size', 0))}</b>\n"
            f"⚡ Bitrate: <b>{info.get('bitrate', 0) // 1000} kbps</b>",
            parse_mode="HTML")
    else:
        await msg.answer("❌ Video ma'lumotlarini o'qib bo'lmadi.")

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

from aiohttp import web

async def handle_health(request):
    return web.Response(text="VideoBot is running!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log.info(f"Dummy HTTP server started on port {port} for Railway health checks.")

# ── Main ───────────────────────────────────────────────────────────────────
async def main():
    dp.include_router(router)
    await set_default_commands(bot)
    log.info("VideoBot ishga tushdi!")
    if not check_ffmpeg():
        log.warning("FFmpeg topilmadi! Video siqish ishlamaydi.")
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Railway (va shunga o'xshash platformalar) uchun fake server:
    if "PORT" in os.environ or os.getenv("RAILWAY_ENVIRONMENT"):
        await start_dummy_server()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
