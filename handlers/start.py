from aiogram import Router, F
from aiogram.types import Message, BotCommand
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from states import VideoStates
from keyboards import kb_main

router = Router(name="start")


# ── Bot commands menyusi (Telegram menyu tugmasi) ──────────────────────────
async def set_default_commands(bot):
    commands = [
        BotCommand(command="start",     description="🏠 Botni ishga tushirish"),
        BotCommand(command="help",      description="📖 Yordam va qo'llanma"),
        BotCommand(command="trim",      description="✂️ Video kesish"),
        BotCommand(command="merge",     description="🔗 Video birlashtirish"),
        BotCommand(command="watermark", description="💧 Watermark qo'shish"),
        BotCommand(command="gif",       description="🎞 GIF / Screenshot"),
        BotCommand(command="cancel",    description="❌ Bekor qilish"),
    ]
    await bot.set_my_commands(commands)


# ── /start ─────────────────────────────────────────────────────────────────
@router.message(CommandStart())
@router.message(F.text == "🔄 Bosh menyu")
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        f"👋 Salom, <b>{msg.from_user.first_name}</b>!\n\n"
        "🎬 <b>VideoBot</b> — professional video qayta ishlash boti\n\n"
        "📌 <b>Imkoniyatlar:</b>\n"
        "├ 🗜 Video siqish (3 xil daraja)\n"
        "├ 📱 Instagram, TikTok, YouTube profillari\n"
        "├ ✂️ Video kesish va qirqish\n"
        "├ 🔗 2 ta videoni birlashtirish\n"
        "├ 💧 Watermark matn qo'shish\n"
        "├ 🎞 GIF yaratish / Screenshot\n"
        "├ ✨ Sifat ko'tarish\n"
        "├ 📐 O'lcham va FPS o'zgartirish\n"
        "└ 📊 Jonli progress ko'rsatkich\n\n"
        "💡 Video yuboring yoki quyidagi tugmalardan foydalaning 👇",
        parse_mode="HTML",
        reply_markup=kb_main(),
    )
    await state.set_state(VideoStates.waiting_video)


# ── /help ──────────────────────────────────────────────────────────────────
@router.message(Command("help"))
@router.message(F.text == "ℹ️ Yordam")
async def cmd_help(msg: Message):
    await msg.answer(
        "📖 <b>VideoBot — Qo'llanma</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>Asosiy buyruqlar:</b>\n"
        "├ /start — Botni ishga tushirish\n"
        "├ /help — Qo'llanma\n"
        "└ /cancel — Bekor qilish\n\n"
        "🛠 <b>Video asboblar:</b>\n"
        "├ /trim — ✂️ Video kesish\n"
        "├ /merge — 🔗 2 ta video birlashtirish\n"
        "├ /watermark — 💧 Watermark qo'shish\n"
        "└ /gif — 🎞 GIF yoki Screenshot\n\n"
        "⚡ <b>Tezkor buyruqlar:</b>\n"
        "<i>(video yuborgandan keyin menyuda chiqadi)</i>\n"
        "├ 🗜 Siqish — hajmni kamaytirish\n"
        "├ ✨ Sifat — sifatni ko'tarish\n"
        "├ 📐 O'lcham — resolution o'zgartirish\n"
        "├ 🎬 FPS — kadr tezligi\n"
        "├ 🔊 Ovoz — audio sozlamalar\n"
        "└ 📊 Ma'lumot — video haqida\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🗜 <b>Siqish darajalari:</b>\n"
        "├ 🗜 Kengaytirilgan — eng kichik hajm\n"
        "├ ⚖️ O'rta — balanslangan\n"
        "└ 🪶 Minimal — sifat saqlanadi\n\n"
        "📱 <b>Platformalar:</b>\n"
        "📸 Instagram  🎵 TikTok  ▶️ YouTube  🐦 Twitter\n\n"
        "📁 <b>Formatlar:</b> MP4 · MOV · MKV · AVI · WEBM · FLV",
        parse_mode="HTML",
        reply_markup=kb_main(),
    )


# ── /cancel ────────────────────────────────────────────────────────────────
@router.message(Command("cancel"))
async def cmd_cancel(msg: Message, state: FSMContext):
    if await state.get_state():
        await state.clear()
        await msg.answer(
            "❌ Jarayon bekor qilindi.\n"
            "Yangi video yuborish uchun tugmani bosing.",
            reply_markup=kb_main(),
        )
    else:
        await msg.answer("Hech qanday faol jarayon yo'q.", reply_markup=kb_main())
