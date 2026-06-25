"""Small formatting helpers used by the UI."""
from __future__ import annotations

import time
from pathlib import Path


def human_size(num: int) -> str:
    size = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def human_age(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


# Coarse category by extension, used for the colored badge in the popup.
_CATEGORIES: dict[str, tuple[str, str]] = {
    # extension : (label, hex color)
    ".pdf": ("PDF", "#e5484d"),
    ".doc": ("DOC", "#3b82f6"), ".docx": ("DOC", "#3b82f6"),
    ".xls": ("XLS", "#22c55e"), ".xlsx": ("XLS", "#22c55e"),
    ".ppt": ("PPT", "#f97316"), ".pptx": ("PPT", "#f97316"),
    ".zip": ("ZIP", "#a855f7"), ".rar": ("ZIP", "#a855f7"),
    ".7z": ("ZIP", "#a855f7"), ".gz": ("ZIP", "#a855f7"),
    ".tar": ("ZIP", "#a855f7"),
    ".png": ("IMG", "#06b6d4"), ".jpg": ("IMG", "#06b6d4"),
    ".jpeg": ("IMG", "#06b6d4"), ".gif": ("IMG", "#06b6d4"),
    ".webp": ("IMG", "#06b6d4"), ".svg": ("IMG", "#06b6d4"),
    ".mp4": ("VID", "#ec4899"), ".mkv": ("VID", "#ec4899"),
    ".mov": ("VID", "#ec4899"), ".webm": ("VID", "#ec4899"),
    ".mp3": ("AUD", "#14b8a6"), ".wav": ("AUD", "#14b8a6"),
    ".flac": ("AUD", "#14b8a6"),
    ".exe": ("APP", "#64748b"), ".appimage": ("APP", "#64748b"),
    ".deb": ("PKG", "#64748b"), ".rpm": ("PKG", "#64748b"),
    ".dmg": ("APP", "#64748b"),
    ".txt": ("TXT", "#94a3b8"), ".md": ("TXT", "#94a3b8"),
    ".csv": ("CSV", "#22c55e"), ".json": ("TXT", "#94a3b8"),
}


def category(path: str) -> tuple[str, str]:
    suffix = Path(path).suffix.lower()
    return _CATEGORIES.get(suffix, (suffix.lstrip(".").upper()[:4] or "FILE", "#64748b"))


def item_badge(item) -> tuple[str, str]:
    """Badge label + color for an item, with a distinct look for folders."""
    if getattr(item, "is_dir", False):
        return ("DIR", "#f0a020")
    return category(item.path)
