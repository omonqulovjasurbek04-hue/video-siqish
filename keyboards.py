from aiogram.types import (
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from config import RES_OPTS, RES_LABELS, DEFAULT_CUSTOM


# ═══════════════════════════════════════════════════════════════════════════
#  Reply (pastki) klaviaturalar
# ═══════════════════════════════════════════════════════════════════════════

def kb_main() -> ReplyKeyboardMarkup:
    """Asosiy menyu — 6 ta tugma, chiroyli joylashgan."""
    b = ReplyKeyboardBuilder()
    b.button(text="🎬 Video yuborish")
    b.button(text="✂️ Kesish")
    b.button(text="🔗 Birlashtirish")
    b.button(text="💧 Watermark")
    b.button(text="🎞 GIF/Screenshot")
    b.button(text="ℹ️ Yordam")
    b.adjust(2, 2, 2)
    return b.as_markup(resize_keyboard=True)


def kb_tools() -> ReplyKeyboardMarkup:
    """Tezkor asboblar menyusi — video yuborilgandan keyin ko'rsatiladi."""
    b = ReplyKeyboardBuilder()
    b.button(text="🗜 Siqish")
    b.button(text="✨ Sifat ko'tarish")
    b.button(text="📐 O'lcham")
    b.button(text="🎬 FPS")
    b.button(text="🔊 Ovoz")
    b.button(text="📊 Ma'lumot")
    b.button(text="🔄 Bosh menyu")
    b.adjust(2, 2, 2, 1)
    return b.as_markup(resize_keyboard=True)


# ═══════════════════════════════════════════════════════════════════════════
#  Inline klaviaturalar
# ═══════════════════════════════════════════════════════════════════════════

def kb_compress_type() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🗜 Kengaytirilgan siqish",  callback_data="c:heavy")
    b.button(text="⚖️ O'rta siqish",          callback_data="c:medium")
    b.button(text="🪶 Minimal siqish",         callback_data="c:light")
    b.button(text="📱 Platforma profili",      callback_data="c:platform")
    b.button(text="⚙️ Kengaytirilgan sozlash", callback_data="c:custom")
    b.button(text="❌ Bekor qilish",            callback_data="c:cancel")
    b.adjust(1)
    return b.as_markup()


def kb_platforms() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📸 Instagram",  callback_data="p:instagram")
    b.button(text="🎵 TikTok",    callback_data="p:tiktok")
    b.button(text="▶️ YouTube",   callback_data="p:youtube")
    b.button(text="🐦 Twitter/X", callback_data="p:twitter")
    b.button(text="⬅️ Orqaga",    callback_data="p:back")
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
        callback_data="cs:toggle_audio",
    )
    sub_status = "Saqlash ✅" if s.get("keep_sub", True) else "O'chirish ❌"
    b.button(text=f"📝 Subtitle: {sub_status}", callback_data="cs:toggle_sub")
    b.button(text="⚡ Siqishni boshlash",       callback_data="cs:start")
    b.button(text="⬅️ Orqaga",                  callback_data="cs:back")
    b.adjust(1, 2, 1, 1, 1, 1, 1, 1)
    return b.as_markup()


def kb_result() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Yangi video",    callback_data="r:new")
    b.button(text="⚙️ Qayta sozlash", callback_data="r:redo")
    b.adjust(2)
    return b.as_markup()


def kb_cancel_inline() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Bekor qilish", callback_data="c:cancel")
    return b.as_markup()


def kb_gif_choice() -> InlineKeyboardMarkup:
    """GIF yoki Screenshot tanlash uchun inline tugmalar."""
    b = InlineKeyboardBuilder()
    b.button(text="🎞 GIF yaratish",      callback_data="gif:1")
    b.button(text="📸 Screenshot olish",  callback_data="gif:2")
    b.button(text="❌ Bekor qilish",       callback_data="gif:cancel")
    b.adjust(2, 1)
    return b.as_markup()


def kb_olcham() -> InlineKeyboardMarkup:
    """O'lcham tanlash uchun inline tugmalar."""
    b = InlineKeyboardBuilder()
    b.button(text="📺 4K Ultra HD",   callback_data="sz:3840:2160")
    b.button(text="🖥 Full HD 1080p", callback_data="sz:1920:1080")
    b.button(text="💻 HD 720p",       callback_data="sz:1280:720")
    b.button(text="📱 SD 480p",       callback_data="sz:854:480")
    b.button(text="📲 Mobil 360p",    callback_data="sz:640:360")
    b.button(text="❌ Bekor qilish",   callback_data="sz:cancel")
    b.adjust(1)
    return b.as_markup()


def kb_fps() -> InlineKeyboardMarkup:
    """FPS tanlash uchun inline tugmalar."""
    b = InlineKeyboardBuilder()
    b.button(text="🎬 24 FPS (Kino)",       callback_data="fp:24")
    b.button(text="📹 30 FPS (Standart)",   callback_data="fp:30")
    b.button(text="🎮 60 FPS (Geyming)",    callback_data="fp:60")
    b.button(text="🐌 Slow-motion (0.5x)",  callback_data="fp:slow")
    b.button(text="⚡ Tezlashtirish (2x)",  callback_data="fp:fast")
    b.button(text="❌ Bekor qilish",         callback_data="fp:cancel")
    b.adjust(1)
    return b.as_markup()


def kb_ovoz() -> InlineKeyboardMarkup:
    """Ovoz sozlamalari uchun inline tugmalar."""
    b = InlineKeyboardBuilder()
    b.button(text="🔇 Ovozni olib tashlash",  callback_data="au:remove")
    b.button(text="🔈 96 kbps (kichik)",      callback_data="au:96")
    b.button(text="🔉 128 kbps (standart)",   callback_data="au:128")
    b.button(text="🔊 192 kbps (yuqori)",     callback_data="au:192")
    b.button(text="🎧 Mono",                  callback_data="au:mono")
    b.button(text="❌ Bekor qilish",           callback_data="au:cancel")
    b.adjust(1)
    return b.as_markup()
