"""A centered, floating macOS-alert-style triage card, shown one at a time."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QMenu, QPushButton,
    QVBoxLayout, QWidget,
)

from ..models import Item
from ..util import category, human_age, human_size
from .style import QSS

CARD_WIDTH = 420

# A friendly application id used to match a floating window rule in the
# compositor (e.g. niri / sway). Kept in sync with __main__.
APP_ID = "dirwatch"


class Controller(Protocol):
    def keep(self, item: Item) -> None: ...
    def delete(self, item: Item) -> None: ...
    def ignore(self, item: Item) -> None: ...
    def move(self, item: Item) -> None: ...
    def snooze(self, item: Item, seconds: int) -> None: ...


class Popup(QWidget):
    def __init__(
        self,
        item: Item,
        controller: Controller,
        on_dismiss: Callable[["Popup"], None],
        remaining: int = 0,
        on_review_all: Callable[[], None] | None = None,
    ):
        super().__init__()
        self._item = item
        self._ctrl = controller
        self._on_dismiss = on_dismiss
        self._remaining = remaining
        self._on_review_all = on_review_all
        self._dismissed = False

        # Frameless + no taskbar entry; the compositor floats & centers it.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Stable title so a compositor window-rule can target the card.
        self.setWindowTitle("dirwatch")
        self.setFixedWidth(CARD_WIDTH)
        self._build()
        self.setStyleSheet(QSS)

    @property
    def item(self) -> Item:
        return self._item

    # ---- layout ------------------------------------------------------------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)  # room for the soft shadow

        card = QWidget(objectName="card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 90))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 26, 28, 22)
        lay.setSpacing(0)

        # Big centered file-type badge (the "icon").
        label, color = category(self._item.path)
        badge = QLabel(label, objectName="iconBadge")
        badge.setFixedSize(72, 72)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"#iconBadge {{ background-color: {color}; }}")
        lay.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(16)

        # Title = filename, centered and wrapping.
        title = QLabel(self._item.name, objectName="title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        title.setToolTip(self._item.path)
        lay.addWidget(title)
        lay.addSpacing(8)

        # Message line, macOS-alert style.
        msg = QLabel(
            f"New file in your {self._folder_name()} folder.\n"
            "What would you like to do with it?",
            objectName="message",
        )
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        lay.addWidget(msg)
        lay.addSpacing(10)

        # Meta line: size · age (· N more queued).
        meta_text = f"{human_size(self._item.size)}  ·  {human_age(self._item.age_seconds)}"
        if self._remaining > 0:
            meta_text += f"  ·  {self._remaining} more waiting"
        meta = QLabel(meta_text, objectName="meta")
        meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(meta)

        if self._remaining > 0 and self._on_review_all is not None:
            review = QPushButton(f"Review all {self._remaining + 1} files", objectName="link")
            review.setCursor(Qt.CursorShape.PointingHandCursor)
            review.clicked.connect(self._review_all)
            lay.addSpacing(2)
            lay.addWidget(review, 0, Qt.AlignmentFlag.AlignHCenter)

        lay.addSpacing(20)

        # Primary two-button row: Delete (neutral) | Keep (blue default).
        primary_row = QHBoxLayout()
        primary_row.setSpacing(10)
        delete = QPushButton("Delete", objectName="secondary")
        delete.setCursor(Qt.CursorShape.PointingHandCursor)
        delete.clicked.connect(lambda: self._do(self._ctrl.delete))
        primary_row.addWidget(delete, 1)

        keep = QPushButton("Keep", objectName="primary")
        keep.setCursor(Qt.CursorShape.PointingHandCursor)
        keep.setDefault(True)
        keep.clicked.connect(lambda: self._do(self._ctrl.keep))
        primary_row.addWidget(keep, 1)
        lay.addLayout(primary_row)
        lay.addSpacing(12)

        # Secondary subtle actions: Move… · Snooze · Ignore.
        sub = QHBoxLayout()
        sub.setSpacing(4)
        sub.addStretch(1)

        move = QPushButton("Move…", objectName="link")
        move.setCursor(Qt.CursorShape.PointingHandCursor)
        move.clicked.connect(lambda: self._do(self._ctrl.move))
        sub.addWidget(move)
        sub.addWidget(QLabel("·", objectName="dot"))

        self._snooze_btn = QPushButton("Snooze", objectName="link")
        self._snooze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._snooze_btn.clicked.connect(self._show_snooze_menu)
        sub.addWidget(self._snooze_btn)
        sub.addWidget(QLabel("·", objectName="dot"))

        ignore = QPushButton("Ignore", objectName="linkDanger")
        ignore.setCursor(Qt.CursorShape.PointingHandCursor)
        ignore.clicked.connect(lambda: self._do(self._ctrl.ignore))
        sub.addWidget(ignore)
        sub.addStretch(1)
        lay.addLayout(sub)

    # ---- snooze menu -------------------------------------------------------

    def _show_snooze_menu(self) -> None:
        from ..actions import SNOOZE_PRESETS

        menu = QMenu(self)
        menu.setStyleSheet(QSS)
        for text, seconds in SNOOZE_PRESETS:
            menu.addAction(text, lambda s=seconds: self._do(self._ctrl.snooze, s))
        anchor = self._snooze_btn
        menu.exec(anchor.mapToGlobal(QPoint(0, anchor.height() + 4)))

    # ---- decisions ---------------------------------------------------------

    def _do(self, fn: Callable, *args) -> None:
        if self._dismissed:
            return
        fn(self._item, *args)
        self.dismiss()

    def _review_all(self) -> None:
        if self._dismissed:
            return
        self._dismissed = True
        self.close()
        self._on_dismiss(self)
        if self._on_review_all is not None:
            self._on_review_all()

    def dismiss(self) -> None:
        if self._dismissed:
            return
        self._dismissed = True
        self.close()
        self._on_dismiss(self)

    # ---- presentation ------------------------------------------------------

    def present(self) -> None:
        """Show centered. On Wayland the compositor places it; on X11 we center."""
        self.show()
        self._center_if_possible()
        # A gentle pop-in via the title-bar-less window opacity (ignored on some
        # compositors, harmless if so).
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(140)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def _center_if_possible(self) -> None:
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.sizeHint().height() // 2,
        )

    # ---- helpers -----------------------------------------------------------

    def _folder_name(self) -> str:
        return self._item.p.parent.name or "watched"


class PopupManager:
    """Shows one centered alert at a time; the rest queue behind it."""

    def __init__(self, controller: Controller, on_review_all: Callable[[], None] | None = None):
        self._ctrl = controller
        self._on_review_all = on_review_all
        self._active: Popup | None = None
        self._queue: deque[Item] = deque()

    def present(self, item: Item) -> None:
        if self._active is not None and self._active.item.id == item.id:
            return
        if any(q.id == item.id for q in self._queue):
            return
        self._queue.append(item)
        self._show_next()

    def _show_next(self) -> None:
        if self._active is not None or not self._queue:
            return
        item = self._queue.popleft()
        self._active = Popup(
            item, self._ctrl, self._dismissed,
            remaining=len(self._queue), on_review_all=self._on_review_all,
        )
        self._active.present()

    def _dismissed(self, popup: Popup) -> None:
        if popup is self._active:
            self._active = None
        QTimer.singleShot(90, self._show_next)

    def pending_count(self) -> int:
        return (1 if self._active else 0) + len(self._queue)

    def close_all(self) -> None:
        if self._active is not None:
            self._active.close()
            self._active = None
        self._queue.clear()
