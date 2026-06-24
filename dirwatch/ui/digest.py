"""The batch "Review" window: a clean list of waiting files with per-file and
bulk super-actions. Shown when a backlog builds up (e.g. after the machine was
off through several snoozes) instead of flooding the screen with cards."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMenu, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .. import actions
from ..actions import ActionError
from ..db import Database
from ..models import Item, Status
from ..util import category, human_age, human_size
from .icon import app_icon
from .style import QSS

WINDOW_WIDTH = 720

# Fixed widths so a row always fits without a horizontal scrollbar.
_BTN_WIDTHS = {"Keep": 60, "Move": 60, "Snooze": 76, "Delete": 68}
_NAME_ELIDE = 34
_META_ELIDE = 52


class _Row(QFrame):
    def __init__(self, item: Item, parent_window: "DigestWindow"):
        super().__init__()
        self._item = item
        self._win = parent_window
        self.setObjectName("row")
        self._build()

    @property
    def item(self) -> Item:
        return self._item

    def is_checked(self) -> bool:
        return self.check.isChecked()

    def set_checked(self, value: bool) -> None:
        self.check.setChecked(value)

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)

        self.check = QCheckBox()
        self.check.toggled.connect(self._win.update_bulk_label)
        lay.addWidget(self.check, 0, Qt.AlignmentFlag.AlignVCenter)

        label, color = category(self._item.path)
        badge = QLabel(label, objectName="rowBadge")
        badge.setFixedSize(42, 42)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"#rowBadge {{ background-color: {color}; }}")
        lay.addWidget(badge)

        # Name/meta column: stretches to fill, but text is elided so it never
        # forces the row wider than the window (no horizontal scroll).
        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel(self._elide(self._item.name, _NAME_ELIDE), objectName="rowName")
        name.setToolTip(self._item.path)
        name.setMinimumWidth(0)
        col.addWidget(name)
        meta = QLabel(
            self._elide(
                f"{human_size(self._item.size)}  ·  "
                f"{human_age(self._item.age_seconds)}  ·  "
                f"in {self._item.p.parent.name or 'watched'}",
                _META_ELIDE,
            ),
            objectName="rowMeta",
        )
        meta.setMinimumWidth(0)
        col.addWidget(meta)
        lay.addLayout(col, 1)

        for text, obj, slot in (
            ("Keep", "miniPrimary", self._keep),
            ("Move", "mini", self._move),
            ("Snooze", "mini", self._snooze),
            ("Delete", "miniDanger", self._delete),
        ):
            b = QPushButton(text, objectName=obj)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedWidth(_BTN_WIDTHS[text])
            b.clicked.connect(slot)
            lay.addWidget(b, 0)

    # per-row actions
    def _keep(self):
        actions.keep(self._win.db, self._item)
        self._win.refresh()

    def _delete(self):
        try:
            actions.delete(self._win.db, self._item)
        except ActionError as exc:
            QMessageBox.warning(self._win, "dirwatch", str(exc))
        self._win.refresh()

    def _move(self):
        dest = QFileDialog.getExistingDirectory(self._win, f"Move “{self._item.name}” to…")
        if not dest:
            return
        try:
            actions.move(self._win.db, self._item, dest)
        except ActionError as exc:
            QMessageBox.warning(self._win, "dirwatch", str(exc))
        self._win.refresh()

    def _snooze(self):
        menu = QMenu(self)
        menu.setStyleSheet(QSS)
        for text, secs in actions.SNOOZE_PRESETS:
            menu.addAction(text, lambda s=secs: self._do_snooze(s))
        btn = self.sender()
        menu.exec(btn.mapToGlobal(QPoint(0, btn.height() + 4)))

    def _do_snooze(self, secs: int):
        actions.snooze(self._win.db, self._item, secs)
        self._win.refresh()

    @staticmethod
    def _elide(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        head = (limit - 1) * 2 // 3
        return f"{text[:head]}…{text[-(limit - 1 - head):]}"


class DigestWindow(QWidget):
    def __init__(
        self,
        db: Database,
        on_changed: Callable[[], None],
        on_empty: Callable[[], None],
    ):
        super().__init__()
        self.db = db
        self._on_changed = on_changed
        self._on_empty = on_empty
        self._rows: list[_Row] = []

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("dirwatch")
        self.setWindowIcon(app_icon(True))
        self.setFixedWidth(WINDOW_WIDTH)
        self._build()
        self.setStyleSheet(QSS)
        self.refresh()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        shell = QWidget(objectName="window")
        shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer.addWidget(shell)
        root = QVBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        head = QVBoxLayout()
        head.setContentsMargins(22, 20, 22, 12)
        head.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(app_icon(True).pixmap(24, 24))
        top.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)
        self._title = QLabel("Files to review", objectName="windowTitle")
        top.addWidget(self._title)
        top.addStretch(1)
        close = QPushButton("✕", objectName="close")
        close.setFixedSize(26, 26)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.hide)
        top.addWidget(close)
        head.addLayout(top)
        self._sub = QLabel("", objectName="windowSub")
        head.addWidget(self._sub)
        root.addLayout(head)

        # Scrollable list
        self._scroll = QScrollArea(objectName="rowScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._host = QWidget(objectName="rowHost")
        self._host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._host_lay = QVBoxLayout(self._host)
        self._host_lay.setContentsMargins(16, 4, 16, 8)
        self._host_lay.setSpacing(8)
        self._host_lay.addStretch(1)
        self._scroll.setWidget(self._host)
        root.addWidget(self._scroll, 1)

        # Bulk action bar
        bar = QWidget(objectName="bulkBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(18, 12, 18, 12)
        bl.setSpacing(8)
        self._select_all = QCheckBox("Select all")
        self._select_all.toggled.connect(self._toggle_all)
        bl.addWidget(self._select_all)
        bl.addStretch(1)

        keep_all = QPushButton("Keep", objectName="ctaGhost")
        keep_all.clicked.connect(lambda: self._bulk("keep"))
        snooze_all = QPushButton("Snooze ▾", objectName="ctaGhost")
        snooze_all.clicked.connect(self._bulk_snooze_menu)
        move_all = QPushButton("Move…", objectName="ctaGhost")
        move_all.clicked.connect(lambda: self._bulk("move"))
        ignore_all = QPushButton("Ignore", objectName="ctaGhost")
        ignore_all.clicked.connect(lambda: self._bulk("ignore"))
        delete_all = QPushButton("Delete", objectName="miniDanger")
        delete_all.clicked.connect(lambda: self._bulk("delete"))
        for b in (keep_all, snooze_all, move_all, ignore_all, delete_all):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            bl.addWidget(b)
        self._bulk_buttons = bar
        root.addWidget(bar)

        self.resize(WINDOW_WIDTH, 560)

    # ---- data --------------------------------------------------------------

    def refresh(self) -> None:
        items = self.db.by_status(Status.PENDING)
        # drop the old rows
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()

        for item in items:
            if not item.exists():
                self.db.set_status(item.id, Status.MISSING)
                continue
            row = _Row(item, self)
            self._rows.append(row)
            self._host_lay.insertWidget(self._host_lay.count() - 1, row)

        n = len(self._rows)
        self._title.setText("All caught up" if n == 0 else f"{n} files to review")
        self._sub.setText(
            "Nothing waiting." if n == 0
            else "Decide each, or select some and use the bulk actions below."
        )
        self._select_all.blockSignals(True)
        self._select_all.setChecked(False)
        self._select_all.blockSignals(False)
        self.update_bulk_label()
        self._on_changed()
        if n == 0:
            self._on_empty()

    def update_bulk_label(self) -> None:
        """Reflect how many files the bulk buttons will act on (selection, or
        everything when nothing is ticked). Button labels stay stable."""
        if not self._rows:
            return
        checked = sum(1 for r in self._rows if r.is_checked())
        target = checked if checked else len(self._rows)
        scope = "selected" if checked else "all"
        self._sub.setText(
            f"Bulk actions apply to {target} {scope} "
            f"file{'s' if target != 1 else ''}."
        )

    def _toggle_all(self, value: bool) -> None:
        for r in self._rows:
            r.set_checked(value)

    # ---- bulk actions ------------------------------------------------------

    def _targets(self) -> list[Item]:
        chosen = [r.item for r in self._rows if r.is_checked()]
        return chosen if chosen else [r.item for r in self._rows]

    def _bulk(self, kind: str) -> None:
        targets = self._targets()
        if not targets:
            return
        if kind == "delete":
            if QMessageBox.question(
                self, "Delete files",
                f"Move {len(targets)} file(s) to Trash?",
            ) != QMessageBox.StandardButton.Yes:
                return
        if kind == "move":
            dest = QFileDialog.getExistingDirectory(self, f"Move {len(targets)} file(s) to…")
            if not dest:
                return
        for item in targets:
            try:
                if kind == "keep":
                    actions.keep(self.db, item)
                elif kind == "ignore":
                    actions.ignore(self.db, item)
                elif kind == "delete":
                    actions.delete(self.db, item)
                elif kind == "move":
                    actions.move(self.db, item, dest)
            except ActionError:
                continue  # skip files that vanished; never crash a bulk run
        self.refresh()

    def _bulk_snooze_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(QSS)
        for text, secs in actions.SNOOZE_PRESETS:
            menu.addAction(text, lambda s=secs: self._bulk_snooze(s))
        btn = self.sender()
        menu.exec(btn.mapToGlobal(QPoint(0, btn.height() + 4)))

    def _bulk_snooze(self, secs: int) -> None:
        for item in self._targets():
            actions.snooze(self.db, item, secs)
        self.refresh()

    def present(self) -> None:
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()
