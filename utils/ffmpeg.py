import json
import asyncio
import subprocess
import logging

from aiogram.types import Message

log = logging.getLogger("videobot.ffmpeg")


def get_video_info(path: str) -> dict | None:
    """FFprobe yordamida video haqida ma'lumot olish."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", path,
        ]
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
    """FFmpeg o'rnatilganligini tekshirish."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except FileNotFoundError:
        return False


async def run_ffmpeg_async(
    cmd: list,
    message: Message,
    timeout: int = 3600,
) -> bool:
    """FFmpeg buyrug'ini asinxron ishga tushirish.

    Xatoga yo'l qo'yilganda foydalanuvchiga xabar beradi va ``False`` qaytaradi.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            err = stderr.decode()[-500:]
            await message.answer(
                f"❌ FFmpeg xatosi:\n<code>{err}</code>", parse_mode="HTML"
            )
            return False
        return True
    except asyncio.TimeoutError:
        await message.answer("⏱ Vaqt tugadi. Video juda katta yoki murakkab.")
        return False
    except FileNotFoundError:
        await message.answer(
            "❌ FFmpeg topilmadi!\n<code>sudo apt install ffmpeg</code>",
            parse_mode="HTML",
        )
        return False
