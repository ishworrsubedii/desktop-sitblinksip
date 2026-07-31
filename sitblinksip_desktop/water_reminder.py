"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Plain periodic reminder to take a water break - no camera involved, just a
timer. Independent of blink/posture tracking so it keeps firing even while
those are paused.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class WaterReminder(QObject):
    triggered = Signal()

    def __init__(self, interval_seconds: float, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.triggered.emit)
        self.set_interval(interval_seconds)

    def set_interval(self, interval_seconds: float) -> None:
        self._timer.start(int(interval_seconds * 1000))

    def stop(self) -> None:
        self._timer.stop()

    def start(self) -> None:
        self._timer.start()
