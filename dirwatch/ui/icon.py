"""Programmatic tray icon so we ship no binary assets."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap


def app_icon(active: bool = True) -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    bg = QColor("#0a84ff") if active else QColor("#8e8e93")
    p.setBrush(QBrush(bg))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(4, 4, 56, 56), 16, 16)

    # an eye: white sclera + dark pupil = "watching"
    p.setBrush(QBrush(QColor("white")))
    p.drawEllipse(QRectF(14, 22, 36, 20))
    p.setBrush(QBrush(QColor("#1d1d1f")))
    p.drawEllipse(QRectF(26, 26, 12, 12))
    p.end()
    return QIcon(pm)
