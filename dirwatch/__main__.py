"""Entry point: launch the tray app and event loop."""
from __future__ import annotations

import signal
import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon

    from .ui.app import DirwatchApp
    from .ui.style import apply_light_theme

    app = QApplication(sys.argv)
    apply_light_theme(app)
    app.setApplicationName("dirwatch")
    app.setApplicationDisplayName("dirwatch")
    # On Wayland this becomes the xdg-toplevel app_id, which compositors
    # (niri, sway, …) match in window rules to float/center the card.
    app.setDesktopFileName("dirwatch")
    # Keep running with only the tray icon and transient popups visible.
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        # Not fatal: the popups are independent windows. We just lose the menu.
        print("Note: no system tray detected; running without a tray icon.",
              file=sys.stderr)

    controller = DirwatchApp(app)
    controller.start()

    # Let Ctrl+C kill it from a terminal.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
