"""Launch-on-login via a freedesktop XDG autostart entry."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _autostart_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    d = root / "autostart"
    d.mkdir(parents=True, exist_ok=True)
    return d


def entry_path() -> Path:
    return _autostart_dir() / "dirwatch.desktop"


def launch_command() -> str:
    """Best command to relaunch dirwatch, however it was installed."""
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return appimage
    on_path = shutil.which("dirwatch")
    if on_path:
        return on_path
    return f"{sys.executable} -m dirwatch"


def is_enabled() -> bool:
    return entry_path().exists()


def enable() -> None:
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=dirwatch\n"
        "Comment=Smart watcher for new files in your folders\n"
        f"Exec={launch_command()}\n"
        "Icon=dirwatch\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    entry_path().write_text(content)


def disable() -> None:
    entry_path().unlink(missing_ok=True)


def set_enabled(value: bool) -> None:
    enable() if value else disable()
