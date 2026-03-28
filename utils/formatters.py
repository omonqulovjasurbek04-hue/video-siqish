def fmt_size(b: int) -> str:
    """Baytlarni o'qiladigan formatga o'girish (B / KB / MB / GB)."""
    if b < 1024:
        return f"{b} B"
    if b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    if b < 1024 ** 3:
        return f"{b / 1024 ** 2:.2f} MB"
    return f"{b / 1024 ** 3:.2f} GB"


def fmt_dur(sec: float) -> str:
    """Soniyalarni soat:daqiqa:soniya formatiga o'girish."""
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def progress_bar(pct: int, width: int = 15) -> str:
    """Matnli progress bar."""
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)
