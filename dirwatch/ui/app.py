"""The QApplication that wires the engine, watcher, tray and popups together."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QMenu, QMessageBox, QSystemTrayIcon,
)

from .. import actions, autostart, desktop
from ..actions import ActionError
from ..config import Config
from ..db import Database
from ..engine import Engine
from ..models import Item, Status
from ..watcher import Watcher
from .archive_prompt import offer_archive_cleanup
from .digest import DigestWindow
from .icon import app_icon
from .popup import PopupManager
from .settings_window import SettingsWindow

TICK_MS = 1000
COALESCE_MS = 700  # gather a burst of new/woken files before deciding how to show


class DirwatchApp:
    def __init__(self, app: QApplication):
        self._app = app
        self._cfg = Config.load()
        self._db = Database()
        self._paused = False
        self._settings: SettingsWindow | None = None
        self._inbox: DigestWindow | None = None

        self._popups = PopupManager(self, on_review_all=self._open_review)
        self._engine = Engine(self._cfg, self._db, self._on_item_ready)
        self._watcher = Watcher(self._on_candidate)

        self._tray = QSystemTrayIcon(app_icon(True))
        self._build_tray()

        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._coalesce = QTimer()
        self._coalesce.setSingleShot(True)
        self._coalesce.timeout.connect(self._flush_ready)

    # ---- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        self._first_run_setup()
        autostart.set_enabled(self._cfg.autostart_login)
        self._sync_watches()
        if self._cfg.autostart_watching:
            self._watcher.start()
        else:
            self._paused = True
        self._engine.recover()          # surface anything due / left over
        self._timer.start(TICK_MS)
        self._tray.show()
        self._schedule_flush()
        self._refresh_tray()

    def _first_run_setup(self) -> None:
        if self._cfg.floating_configured:
            return
        try:
            res = desktop.ensure_floating()
            if res.changed:
                self._tray.showMessage("dirwatch", res.message)
        except Exception:
            pass  # never let compositor quirks block startup
        self._cfg.floating_configured = True
        self._cfg.save()

    def _sync_watches(self) -> None:
        wanted = {str(p) for p in self._cfg.enabled_dirs() if p.is_dir()}
        for existing in self._watcher.watched_dirs():
            if existing not in wanted:
                self._watcher.unwatch(Path(existing))
        for path in self._cfg.enabled_dirs():
            if path.is_dir():
                self._engine.baseline_dir(path)
                self._watcher.watch(path)

    # ---- engine/watcher callbacks -----------------------------------------

    def _on_candidate(self, path: str, watch_dir: str) -> None:
        if not self._paused:
            self._engine.note_candidate(path, watch_dir)

    def _on_item_ready(self, item: Item) -> None:
        # If the Review window is already up, just let it refresh.
        if self._inbox is not None and self._inbox.isVisible():
            self._inbox.refresh()
            return
        self._schedule_flush()

    def _schedule_flush(self) -> None:
        self._coalesce.start(COALESCE_MS)

    def _tick(self) -> None:
        if not self._paused:
            self._engine.tick()
        self._refresh_tray()

    # ---- presenter: decide cards vs the Review window ----------------------

    def _flush_ready(self) -> None:
        pending = [i for i in self._db.by_status(Status.PENDING) if self._ensure_exists(i)]
        if not pending:
            self._refresh_tray()
            return
        if len(pending) >= self._cfg.batch_threshold:
            self._popups.close_all()
            self._review_window().present()
        elif self._inbox is not None and self._inbox.isVisible():
            self._inbox.refresh()
        else:
            for item in pending:
                self._popups.present(item)
        self._refresh_tray()

    def _ensure_exists(self, item: Item) -> bool:
        if item.exists():
            return True
        self._db.set_status(item.id, Status.MISSING)
        return False

    def _review_window(self) -> DigestWindow:
        if self._inbox is None:
            self._inbox = DigestWindow(
                self._db, on_changed=self._refresh_tray, on_empty=self._on_review_empty
            )
        return self._inbox

    def _open_review(self) -> None:
        self._popups.close_all()
        self._review_window().present()

    def _on_review_empty(self) -> None:
        if self._inbox is not None:
            self._inbox.hide()
        self._refresh_tray()

    # ---- Controller protocol (called by single cards) ---------------------

    def keep(self, item: Item) -> None:
        actions.keep(self._db, item)
        offer_archive_cleanup(None, self._db, item)

    def ignore(self, item: Item) -> None:
        actions.ignore(self._db, item)

    def delete(self, item: Item) -> None:
        try:
            actions.delete(self._db, item)
        except ActionError as exc:
            self._warn(str(exc))

    def snooze(self, item: Item, seconds: int) -> None:
        actions.snooze(self._db, item, seconds)

    def move(self, item: Item) -> None:
        dest = QFileDialog.getExistingDirectory(
            None, f"Move “{item.name}” to…", str(Path.home())
        )
        if not dest:
            actions.snooze(self._db, item, 1)  # re-show soon; don't lose it
            return
        try:
            actions.move(self._db, item, dest)
        except ActionError as exc:
            self._warn(str(exc))
            return
        offer_archive_cleanup(None, self._db, item)

    # ---- tray --------------------------------------------------------------

    def _build_tray(self) -> None:
        menu = QMenu()
        self._status_action = menu.addAction("dirwatch")
        self._status_action.setEnabled(False)
        self._review_action = menu.addAction("No files to review")
        self._review_action.triggered.connect(self._open_review)
        menu.addSeparator()
        self._pause_action = menu.addAction("Pause watching")
        self._pause_action.triggered.connect(self._toggle_pause)
        menu.addAction("Settings…", self._open_settings)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.setToolTip("dirwatch")
        self._tray.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger and self._pending_count():
            self._open_review()

    def _pending_count(self) -> int:
        return len(self._db.by_status(Status.PENDING))

    def _refresh_tray(self) -> None:
        n_dirs = len(self._cfg.enabled_dirs())
        state = "paused" if self._paused else "watching"
        self._status_action.setText(f"dirwatch — {state} {n_dirs} folder(s)")
        pending = self._pending_count()
        self._review_action.setText(
            "No files to review" if pending == 0 else f"Review {pending} file(s)…"
        )
        self._review_action.setEnabled(pending > 0)
        self._pause_action.setText(
            "Resume watching" if self._paused else "Pause watching"
        )
        self._tray.setIcon(app_icon(not self._paused))

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if not self._paused:
            self._sync_watches()
        self._refresh_tray()

    def _open_settings(self) -> None:
        if self._settings is None:
            self._settings = SettingsWindow(self._cfg, self._apply_settings)
        self._settings.show()
        self._settings.raise_()
        self._settings.activateWindow()

    def _apply_settings(self) -> None:
        autostart.set_enabled(self._cfg.autostart_login)
        self._sync_watches()
        self._refresh_tray()

    # ---- misc --------------------------------------------------------------

    def _warn(self, message: str) -> None:
        QMessageBox.warning(None, "dirwatch", message)

    def _quit(self) -> None:
        self._timer.stop()
        self._watcher.stop()
        self._popups.close_all()
        if self._inbox is not None:
            self._inbox.close()
        self._db.close()
        self._tray.hide()
        self._app.quit()
