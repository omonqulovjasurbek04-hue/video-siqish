"""Health check HTTP server — Railway, Render va shunga o'xshash platformalar uchun."""

import os
import logging
from aiohttp import web

from utils.ffmpeg import check_ffmpeg
from config import UPLOAD_DIR, OUTPUT_DIR

log = logging.getLogger("videobot.server")


async def handle_health(request):
    """Kengaytirilgan health check — FFmpeg, disk, va bot holati."""
    ffmpeg_ok = check_ffmpeg()

    # Disk holati
    uploads = sum(1 for f in UPLOAD_DIR.iterdir() if f.is_file()) if UPLOAD_DIR.exists() else 0
    outputs = sum(1 for f in OUTPUT_DIR.iterdir() if f.is_file()) if OUTPUT_DIR.exists() else 0

    status_code = 200 if ffmpeg_ok else 503
    data = {
        "status": "healthy" if ffmpeg_ok else "degraded",
        "ffmpeg": "ok" if ffmpeg_ok else "missing",
        "temp_files": {"uploads": uploads, "outputs": outputs},
    }
    return web.json_response(data, status=status_code)


async def handle_root(request):
    return web.Response(text="🎬 VideoBot is running!")


async def start_health_server():
    """Aiohttp web server ishga tushirish."""
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info(f"Health check server started on port {port}")
