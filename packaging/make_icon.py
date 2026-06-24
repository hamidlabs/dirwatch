"""Render the app icon to a PNG (used by the AppImage build).

Usage: QT_QPA_PLATFORM=offscreen python packaging/make_icon.py out.png [size]
"""
import sys

from PySide6.QtGui import QGuiApplication

from dirwatch.ui.icon import app_icon


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "dirwatch.png"
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    QGuiApplication([])
    pixmap = app_icon(True).pixmap(size, size)
    if not pixmap.save(out, "PNG"):
        print(f"failed to write {out}", file=sys.stderr)
        return 1
    print(f"wrote {out} ({size}x{size})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
