"""Programmatic tray icon so we ship no binary assets."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap


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


def action_icon(kind: str, color: str = "#5a5a5e", size: int = 20) -> QIcon:
    """Crisp, theme-independent line icons for the Review-list row actions."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(max(1.6, size * 0.09))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = size

    def pt(fx, fy):
        return QPointF(s * fx, s * fy)

    if kind == "keep":  # check mark
        p.drawPolyline([pt(0.22, 0.54), pt(0.42, 0.73), pt(0.78, 0.30)])
    elif kind == "move":  # folder
        p.drawPolyline([pt(0.16, 0.40), pt(0.16, 0.30), pt(0.36, 0.30),
                        pt(0.43, 0.40)])
        p.drawRoundedRect(QRectF(s * 0.16, s * 0.40, s * 0.68, s * 0.34), 2.5, 2.5)
    elif kind == "snooze":  # clock
        p.drawEllipse(QRectF(s * 0.20, s * 0.20, s * 0.60, s * 0.60))
        p.drawLine(pt(0.50, 0.50), pt(0.50, 0.31))
        p.drawLine(pt(0.50, 0.50), pt(0.66, 0.56))
    elif kind == "delete":  # trash can
        p.drawLine(pt(0.24, 0.30), pt(0.76, 0.30))             # lid
        p.drawPolyline([pt(0.40, 0.30), pt(0.43, 0.21), pt(0.57, 0.21),
                        pt(0.60, 0.30)])                        # handle
        p.drawPolyline([pt(0.30, 0.30), pt(0.34, 0.78), pt(0.66, 0.78),
                        pt(0.70, 0.30)])                        # body
    p.end()
    return QIcon(pm)
