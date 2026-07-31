"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Full-screen "blink now" break: when the rolling blink rate drops below the
configured minimum, every screen goes blank for a couple of seconds to force
a break and a blink. Dismissible early with Escape or a click.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QObject, Signal
from PySide6.QtGui import QGuiApplication, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class _OverlayWindow(QWidget):
    dismissed = Signal()

    def __init__(self, message: str, submessage: str):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setStyleSheet("background-color: black;")
        self.setCursor(Qt.BlankCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel(message)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white; font-size: 42px; font-weight: 700;")

        subtitle = QLabel(submessage)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #a0a0a0; font-size: 16px; margin-top: 12px;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.dismissed.emit()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.dismissed.emit()


class BreakOverlay(QObject):
    """Shows/hides one blank window per connected screen."""

    def __init__(
        self,
        duration_seconds: float = 3.0,
        message: str = "Blink",
        submessage: str = "Your blink rate dropped - take a second to blink.",
        parent=None,
    ):
        super().__init__(parent)
        self.duration_seconds = duration_seconds
        self.message = message
        self.submessage = submessage
        self._windows: list[_OverlayWindow] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._close_all)

    def is_active(self) -> bool:
        return bool(self._windows)

    def show(self) -> None:
        if self._windows:
            return
        for screen in QGuiApplication.screens():
            window = _OverlayWindow(self.message, self.submessage)
            window.dismissed.connect(self._close_all)
            geo = screen.geometry()
            window.move(geo.topLeft())
            window.resize(geo.size())
            window.showFullScreen()
            self._windows.append(window)
        self._timer.start(int(self.duration_seconds * 1000))

    def _close_all(self) -> None:
        self._timer.stop()
        for window in self._windows:
            window.close()
        self._windows = []
