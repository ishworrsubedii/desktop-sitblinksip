"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Full-screen "blink now" break: when the rolling blink rate drops below the
configured minimum, every screen goes blank for a couple of seconds to force
a break and a blink. Dismissible early with Escape or a click.
"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, QObject, Signal
from PySide6.QtGui import QGuiApplication, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget, QVBoxLayout, QLabel

from .platform_support import IS_MACOS, bring_to_front

# Snapping straight to a full-black screen and back reads as a jarring flash.
# Fading in and out over this long softens it into more of a dim than a jolt,
# while still being unmissable.
_FADE_MS = 250


class _OverlayWindow(QWidget):
    dismissed = Signal()

    def __init__(self, message: str, submessage: str):
        super().__init__()
        # Qt.Tool keeps the overlay out of the taskbar/window list on Linux
        # and Windows. On macOS it also stops the window becoming "key",
        # which would leave it stuck below the menu bar and unable to receive
        # the Escape key - so there we use a plain window instead and rely on
        # WindowStaysOnTopHint plus the app being a background (LSUIElement)
        # app to keep it out of the way.
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if not IS_MACOS:
            flags |= Qt.Tool
        self.setWindowFlags(flags)
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

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

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
        self._animations: list[QPropertyAnimation] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out_and_close)

    def is_active(self) -> bool:
        return bool(self._windows)

    def show(self) -> None:
        if self._windows:
            return
        for screen in QGuiApplication.screens():
            window = _OverlayWindow(self.message, self.submessage)
            window.dismissed.connect(self._close_all)
            geo = screen.geometry()
            window.setScreen(screen)
            window.move(geo.topLeft())
            window.resize(geo.size())
            window.showFullScreen()
            self._windows.append(window)

        # Only the first screen's window takes focus, so Escape has somewhere
        # to land. Without this the overlay can come up unfocused (macOS
        # background apps, and Linux WMs with focus-stealing prevention) and
        # the only way out would be to wait it out.
        if self._windows:
            bring_to_front(self._windows[0])
            self._windows[0].setFocus()

        self._animate(start=0.0, end=1.0)
        self._timer.start(int(self.duration_seconds * 1000))

    def _animate(self, start: float, end: float) -> None:
        self._animations = []
        for window in self._windows:
            anim = QPropertyAnimation(window.opacity_effect, b"opacity", self)
            anim.setDuration(_FADE_MS)
            anim.setStartValue(start)
            anim.setEndValue(end)
            anim.setEasingCurve(QEasingCurve.OutCubic if end > start else QEasingCurve.InCubic)
            anim.start()
            self._animations.append(anim)

    def _fade_out_and_close(self) -> None:
        self._timer.stop()
        if not self._windows:
            return
        self._animate(start=1.0, end=0.0)
        QTimer.singleShot(_FADE_MS, self._close_all)

    def _close_all(self) -> None:
        self._timer.stop()
        self._animations = []
        for window in self._windows:
            window.close()
        self._windows = []
