"""
🎬 VideoBot — Telegram Video Qayta Ishlash Boti
Asosiy ishga tushirish fayli.
"""

import os
import asyncio
import signal
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, USE_LOCAL_SERVER, LOCAL_SERVER_URL, log
from handlers import all_routers
from handlers.start import set_default_commands
from utils.ffmpeg import check_ffmpeg
from utils.cleanup import start_cleanup_scheduler
from server import start_health_server


# ── Bot va Dispatcher yaratish ─────────────────────────────────────────────

session_opt = None
if USE_LOCAL_SERVER:
    session_opt = AiohttpSession(
        api=TelegramAPIServer.from_base(LOCAL_SERVER_URL, is_local=True)
    )

bot = Bot(token=BOT_TOKEN, session=session_opt)
dp  = Dispatcher(storage=MemoryStorage())


# ── Graceful shutdown ──────────────────────────────────────────────────────

async def on_shutdown(dp: Dispatcher):
    """Bot to'xtatilganda barcha resurslarni tozalash."""
    log.info("Bot to'xtatilmoqda...")
    await bot.session.close()
    log.info("Bot to'xtatildi.")


# ── Main ───────────────────────────────────────────────────────────────────

async def main():
    # Routerlarni ulash
    for r in all_routers:
        dp.include_router(r)

    # Shutdown callback
    dp.shutdown.register(on_shutdown)

    # Bot buyruqlari menyusini sozlash
    await set_default_commands(bot)

    # FFmpeg tekshirish
    if not check_ffmpeg():
        log.warning("⚠️  FFmpeg topilmadi! Video qayta ishlash ishlamaydi.")
    else:
        log.info("✅ FFmpeg topildi.")

    # Eski fayllarni tozalash scheduleri
    cleanup_task = asyncio.create_task(start_cleanup_scheduler())

    # Railway / Render / container platformalari uchun health check server
    if "PORT" in os.environ or os.getenv("RAILWAY_ENVIRONMENT"):
        await start_health_server()

    log.info("🎬 VideoBot ishga tushdi!")

    # Eski webhook tozalash va polling boshlash
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot to'xtatildi (signal).")
