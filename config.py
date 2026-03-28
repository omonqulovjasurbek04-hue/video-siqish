import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ── Environment ────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("videobot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    raise ValueError(".env faylida BOT_TOKEN ni to'ldiring!")

UPLOAD_DIR = Path("bot_uploads")
OUTPUT_DIR = Path("bot_outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

USE_LOCAL_SERVER = os.getenv("USE_LOCAL_SERVER", "false").lower() == "true"
LOCAL_SERVER_URL = os.getenv("LOCAL_SERVER_URL", "http://localhost:8081")


MAX_SIZE_LOCAL = int(2 * 1024 * 1024 * 1024)    # 2 GB — Local Bot API Server
MAX_SIZE_CLOUD = int(2 * 1024 * 1024 * 1024)     # 2 GB — Cloud uchun ham

COMPRESS_PROFILES = {
    "heavy": {
        "label":  "🗜 Kengaytirilgan siqish",
        "desc":   "Eng kichik hajm · Minimal sifat pasayishi",
        "crf": 32, "audio": "64k", "preset": "slow", "scale": "1280:720",
    },
    "medium": {
        "label":  "⚖️ O'rta siqish",
        "desc":   "Balanslangan sifat va hajm",
        "crf": 24, "audio": "128k", "preset": "medium", "scale": "-2:1080",
    },
    "light": {
        "label":  "🪶 Minimal siqish",
        "desc":   "Sifat deyarli o'zgarmaydi · Kichik hajm kamayishi",
        "crf": 18, "audio": "192k", "preset": "fast", "scale": "-2:-2",
    },
}

PLATFORM_PROFILES = {
    "instagram": {"label": "📸 Instagram",  "crf": 23, "audio": "128k", "scale": "1080:1080", "fps": 30},
    "tiktok":    {"label": "🎵 TikTok",     "crf": 23, "audio": "128k", "scale": "1080:1920", "fps": 30},
    "youtube":   {"label": "▶️ YouTube",    "crf": 20, "audio": "192k", "scale": "1920:1080", "fps": 60},
    "twitter":   {"label": "🐦 Twitter/X",  "crf": 25, "audio": "128k", "scale": "1280:720",  "fps": 30},
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

CLEANUP_INTERVAL_MIN = 30
CLEANUP_MAX_AGE_MIN  = 60 
