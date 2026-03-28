import asyncio
import logging
import time
from pathlib import Path

from config import UPLOAD_DIR, OUTPUT_DIR, CLEANUP_INTERVAL_MIN, CLEANUP_MAX_AGE_MIN

log = logging.getLogger("videobot.cleanup")


def cleanup_files(*paths):
    """Berilgan fayllarni o'chirish (xatoga chidamli)."""
    for p in paths:
        try:
            if p and Path(p).exists():
                Path(p).unlink()
                log.debug(f"O'chirildi: {p}")
        except Exception:
            pass


def _cleanup_old_files():
    """Eski vaqtinchalik fayllarni tozalash."""
    now = time.time()
    max_age = CLEANUP_MAX_AGE_MIN * 60
    removed = 0

    for folder in (UPLOAD_DIR, OUTPUT_DIR):
        if not folder.exists():
            continue
        for f in folder.iterdir():
            if f.is_file():
                age = now - f.stat().st_mtime
                if age > max_age:
                    try:
                        f.unlink()
                        removed += 1
                    except Exception:
                        pass

    if removed:
        log.info(f"Tozalash: {removed} ta eski fayl o'chirildi.")


async def start_cleanup_scheduler():
    """Har CLEANUP_INTERVAL_MIN daqiqada eski fayllarni avtomatik tozalash."""
    log.info(
        f"Fayl tozalash scheduleri ishga tushdi "
        f"(har {CLEANUP_INTERVAL_MIN} daqiqada, {CLEANUP_MAX_AGE_MIN} daqiqadan eski fayllar)"
    )
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_MIN * 60)
        try:
            _cleanup_old_files()
        except Exception as e:
            log.error(f"Tozalash xatosi: {e}")
