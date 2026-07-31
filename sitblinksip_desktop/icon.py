"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

The tray/window icon is drawn in code with QPainter instead of loaded from a
raster/SVG asset, so the running app never depends on which image plugins a
given PySide6 install ships with. The installed .desktop entry still points at
the hand-authored SVG in packaging/icons/ for the system app-menu icon.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen


def build_app_icon(size: int = 128) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    background = QColor("#1b1f2a")
    painter.setBrush(background)
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)

    eye_rect = QRectF(size * 0.12, size * 0.34, size * 0.76, size * 0.34)
    painter.setBrush(QColor("#f0f4ff"))
    painter.drawEllipse(eye_rect)

    iris_radius = size * 0.13
    painter.setBrush(QColor("#3aa1ff"))
    painter.drawEllipse(
        eye_rect.center().x() - iris_radius,
        eye_rect.center().y() - iris_radius,
        iris_radius * 2,
        iris_radius * 2,
    )

    pupil_radius = size * 0.055
    painter.setBrush(QColor("#0b0d12"))
    painter.drawEllipse(
        eye_rect.center().x() - pupil_radius,
        eye_rect.center().y() - pupil_radius,
        pupil_radius * 2,
        pupil_radius * 2,
    )

    pen = QPen(QColor("#f0f4ff"))
    pen.setWidthF(size * 0.03)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawArc(eye_rect.adjusted(-2, -2, 2, 2), 0, 180 * 16)

    painter.end()
    return QIcon(pixmap)
