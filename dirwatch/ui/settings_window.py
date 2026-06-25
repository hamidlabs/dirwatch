"""A polished, sidebar-navigated settings window."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFileDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)

from .. import __version__, autostart, desktop
from ..config import Config, WatchedDir
from ..paths import config_file, db_file
from .icon import app_icon
from .style import QSS


def _group(title: str, hint: str | None = None) -> tuple[QWidget, QVBoxLayout]:
    """A white rounded 'card' container with an optional title + hint."""
    box = QWidget(objectName="group")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(10)
    if title:
        lay.addWidget(QLabel(title, objectName="groupLabel"))
    if hint:
        h = QLabel(hint, objectName="groupHint")
        h.setWordWrap(True)
        lay.addWidget(h)
    return box, lay


class SettingsWindow(QWidget):
    def __init__(self, config: Config, on_apply: Callable[[], None]):
        super().__init__()
        self._cfg = config
        self._on_apply = on_apply
        self.setWindowTitle("dirwatch — Settings")
        self.setWindowIcon(app_icon(True))
        self.setMinimumSize(740, 520)
        self._build()
        self.setStyleSheet(QSS)

    # ---- shell -------------------------------------------------------------

    def _header(self) -> QWidget:
        bar = QWidget(objectName="headerBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 10, 12, 10)
        h.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(app_icon(True).pixmap(22, 22))
        h.addWidget(icon)
        h.addWidget(QLabel("dirwatch — Settings", objectName="headerTitle"))
        h.addStretch(1)
        close = QPushButton("✕", objectName="close")
        close.setFixedSize(26, 26)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setToolTip("Close")
        close.clicked.connect(self.close)
        h.addWidget(close)
        return bar

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._header())

        body = QWidget(objectName="pane")
        root = QHBoxLayout(body)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        outer.addWidget(body, 1)

        # Sidebar
        sidebar = QWidget(objectName="sidebar")
        sidebar.setFixedWidth(190)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(14, 20, 14, 20)
        sb.setSpacing(6)
        brand = QLabel("dirwatch")
        brand.setStyleSheet("font-size:17px; font-weight:700; color:#1d1d1f; padding:0 8px 12px 8px;")
        sb.addWidget(brand)

        self._stack = QStackedWidget()
        self._nav = QButtonGroup(self)
        self._nav.setExclusive(True)
        for i, (name, builder) in enumerate([
            ("General", self._pane_general),
            ("Folders", self._pane_folders),
            ("Floating", self._pane_floating),
            ("About", self._pane_about),
        ]):
            btn = QPushButton(name, objectName="navItem")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, idx=i: self._stack.setCurrentIndex(idx))
            self._nav.addButton(btn, i)
            sb.addWidget(btn)
            self._stack.addWidget(builder())
        sb.addStretch(1)
        self._nav.button(0).setChecked(True)

        root.addWidget(sidebar)

        right = QWidget(objectName="pane")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self._stack, 1)

        # Bottom save bar
        bar = QHBoxLayout()
        bar.setContentsMargins(24, 12, 24, 16)
        bar.addStretch(1)
        save = QPushButton("Save", objectName="cta")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self._save)
        bar.addWidget(save)
        rl.addLayout(bar)
        root.addWidget(right, 1)

    def _scroll_pane(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(28, 24, 28, 8)
        lay.setSpacing(16)
        lay.addWidget(QLabel(title, objectName="sectionTitle"))
        return pane, lay

    # ---- General -----------------------------------------------------------

    def _pane_general(self) -> QWidget:
        pane, lay = self._scroll_pane("General")

        box, b = _group("Startup")
        self._watch_launch = QCheckBox("Start watching automatically when dirwatch opens")
        self._watch_launch.setChecked(self._cfg.autostart_watching)
        b.addWidget(self._watch_launch)
        self._login = QCheckBox("Launch dirwatch at login")
        self._login.setChecked(autostart.is_enabled())
        b.addWidget(self._login)
        lay.addWidget(box)

        box2, b2 = _group("Detection")
        self._ignore_hidden = QCheckBox("Ignore hidden (dot) files")
        self._ignore_hidden.setChecked(self._cfg.ignore_hidden)
        b2.addWidget(self._ignore_hidden)

        self._skip_in_use = QCheckBox("Don't ask while a file is open in another app")
        self._skip_in_use.setChecked(self._cfg.skip_in_use)
        b2.addWidget(self._skip_in_use)

        b2.addLayout(self._spin_row(
            "Wait for a file to finish before asking",
            "debounce", self._cfg.debounce_seconds, 1, 120, " s"))
        b2.addLayout(self._spin_row(
            "Show the Review list when more than this many files wait",
            "threshold", self._cfg.batch_threshold, 1, 50, ""))
        b2.addLayout(self._spin_row(
            "Forget handled / missing files after",
            "retention", self._cfg.retention_days, 1, 365, " days"))
        lay.addWidget(box2)

        lay.addStretch(1)
        return pane

    def _spin_row(self, label, attr, value, lo, hi, suffix) -> QHBoxLayout:
        row = QHBoxLayout()
        lbl = QLabel(label, objectName="groupHint")
        lbl.setWordWrap(True)
        row.addWidget(lbl, 1)
        spin = QSpinBox()
        spin.setRange(lo, hi)
        spin.setValue(value)
        if suffix:
            spin.setSuffix(suffix)
        setattr(self, f"_spin_{attr}", spin)
        row.addWidget(spin)
        return row

    # ---- Folders -----------------------------------------------------------

    def _pane_folders(self) -> QWidget:
        pane, lay = self._scroll_pane("Watched folders")
        hint = QLabel("dirwatch asks you about new files that appear in these "
                      "folders. Existing files are left alone.", objectName="groupHint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self._list = QListWidget(objectName="folders")
        self._list.itemChanged.connect(self._on_folder_toggled)
        lay.addWidget(self._list, 1)
        self._reload_folders()

        row = QHBoxLayout()
        add = QPushButton("Add folder…", objectName="cta")
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.clicked.connect(self._add_folder)
        remove = QPushButton("Remove selected", objectName="ctaGhost")
        remove.setCursor(Qt.CursorShape.PointingHandCursor)
        remove.clicked.connect(self._remove_folder)
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch(1)
        lay.addLayout(row)
        return pane

    def _reload_folders(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for w in self._cfg.watched:
            it = QListWidgetItem(w.path)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if w.enabled else Qt.CheckState.Unchecked)
            self._list.addItem(it)
        self._list.blockSignals(False)

    def _on_folder_toggled(self, item: QListWidgetItem) -> None:
        for w in self._cfg.watched:
            if w.path == item.text():
                w.enabled = item.checkState() == Qt.CheckState.Checked

    def _add_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose a folder to watch")
        if path and not any(w.path == path for w in self._cfg.watched):
            self._cfg.watched.append(WatchedDir(path=path, enabled=True))
            self._reload_folders()

    def _remove_folder(self) -> None:
        for item in self._list.selectedItems():
            self._cfg.watched = [w for w in self._cfg.watched if w.path != item.text()]
        self._reload_folders()

    # ---- Floating ----------------------------------------------------------

    def _pane_floating(self) -> QWidget:
        pane, lay = self._scroll_pane("Floating window")
        box, b = _group(
            "Compositor",
            "On tiling Wayland compositors (niri, sway, hyprland) the triage card "
            "needs a rule to float and center instead of being tiled. dirwatch can "
            "manage this for you.",
        )
        self._float_status = QLabel("", objectName="groupHint")
        self._float_status.setWordWrap(True)
        b.addWidget(self._float_status)

        row = QHBoxLayout()
        self._float_apply = QPushButton("Enable floating", objectName="cta")
        self._float_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self._float_apply.clicked.connect(self._apply_floating)
        self._float_remove = QPushButton("Disable", objectName="ctaGhost")
        self._float_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self._float_remove.clicked.connect(self._remove_floating)
        row.addWidget(self._float_apply)
        row.addWidget(self._float_remove)
        row.addStretch(1)
        b.addLayout(row)
        lay.addWidget(box)
        lay.addStretch(1)
        self._refresh_floating()
        return pane

    def _refresh_floating(self) -> None:
        res = desktop.status()
        comp = res.compositor.value
        if not res.needs_rule:
            self._float_status.setText(f"Detected: {comp}. {res.message}")
            self._float_apply.setEnabled(False)
            self._float_remove.setEnabled(False)
            return
        state = "configured ✓" if res.configured else "not configured"
        self._float_status.setText(
            f"Detected: {comp} — floating is {state}.\nConfig: {res.config_path}"
        )
        self._float_apply.setEnabled(not res.configured)
        self._float_remove.setEnabled(res.configured)

    def _apply_floating(self) -> None:
        res = desktop.ensure_floating()
        self._float_status.setText(res.message)
        self._refresh_floating()

    def _remove_floating(self) -> None:
        res = desktop.remove_floating()
        self._float_status.setText(res.message)
        self._refresh_floating()

    # ---- About -------------------------------------------------------------

    def _pane_about(self) -> QWidget:
        pane, lay = self._scroll_pane("About")
        box, b = _group("dirwatch")
        b.addWidget(QLabel(f"Version {__version__}", objectName="groupHint"))
        b.addWidget(QLabel(
            "A smart watcher that asks what to do with new files in your folders: "
            "keep, move, snooze, or send to Trash.", objectName="groupHint"))
        info = QLabel(f"Config: {config_file()}\nDatabase: {db_file()}",
                      objectName="groupHint")
        info.setWordWrap(True)
        b.addWidget(info)
        lay.addWidget(box)
        lay.addStretch(1)
        return pane

    # ---- save --------------------------------------------------------------

    def _save(self) -> None:
        self._cfg.autostart_watching = self._watch_launch.isChecked()
        self._cfg.autostart_login = self._login.isChecked()
        self._cfg.ignore_hidden = self._ignore_hidden.isChecked()
        self._cfg.skip_in_use = self._skip_in_use.isChecked()
        self._cfg.debounce_seconds = self._spin_debounce.value()
        self._cfg.batch_threshold = self._spin_threshold.value()
        self._cfg.retention_days = self._spin_retention.value()
        self._cfg.save()
        self._on_apply()
        self.close()
