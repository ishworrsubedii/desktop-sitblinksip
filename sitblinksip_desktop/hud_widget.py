"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Small always-on-top HUD. By default it only shows the running blink count and
rate - no video. The camera preview panel is created but hidden, and is only
revealed when the user explicitly asks for it (F6 or the tray menu), per the
"count blinks, don't show the camera unless asked" requirement.

The HUD also carries its own minimize/close controls so it behaves like a
normal small window even though it is frameless: minimize collapses it down
to just the blink count, and close hides it entirely without quitting the
app (tracking, breaks, etc. all keep running - it's just the widget that
goes away, and it can be brought back from the tray).
"""
from __future__ import annotations

import cv2
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QImage, QPixmap, QMouseEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton

from .blink_engine import BlinkResult
from .posture_engine import PostureResult

PREVIEW_WIDTH = 240
PREVIEW_HEIGHT = 180

_TITLEBAR_BUTTON_STYLE = """
    QPushButton {
        background-color: transparent;
        color: #b0b0b0;
        border: none;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 600;
    }
    QPushButton:hover {
        background-color: rgba(255, 255, 255, 35);
        color: #ffffff;
    }
"""

_CLOSE_BUTTON_STYLE = """
    QPushButton {
        background-color: transparent;
        color: #b0b0b0;
        border: none;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 600;
    }
    QPushButton:hover {
        background-color: rgba(231, 76, 60, 220);
        color: #ffffff;
    }
"""


class HudWidget(QWidget):
    # Emitted after the HUD hides itself via the close button (or an OS-level
    # close attempt) so the app can, e.g., surface a one-time "still running
    # in the tray" notice. The app never needs to react to minimize.
    closed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_offset: QPoint | None = None
        self._context_menu = None
        self._minimized = False
        self._preview_wanted = False
        self._posture_wanted = True

        container = QFrame(self)
        container.setObjectName("hudContainer")
        container.setStyleSheet(
            """
            #hudContainer {
                background-color: rgba(20, 20, 24, 210);
                border-radius: 10px;
            }
            QLabel { color: #f0f0f0; }
            """
        )

        self.minimize_btn = QPushButton("–")
        self.minimize_btn.setFixedSize(18, 18)
        self.minimize_btn.setCursor(Qt.PointingHandCursor)
        self.minimize_btn.setToolTip("Minimize")
        self.minimize_btn.setStyleSheet(_TITLEBAR_BUTTON_STYLE)
        self.minimize_btn.clicked.connect(self.toggle_minimized)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(18, 18)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setToolTip("Close (keeps running in the tray)")
        self.close_btn.setStyleSheet(_CLOSE_BUTTON_STYLE)
        self.close_btn.clicked.connect(self.close)

        titlebar = QHBoxLayout()
        titlebar.setContentsMargins(0, 0, 0, 0)
        titlebar.setSpacing(2)
        titlebar.addStretch(1)
        titlebar.addWidget(self.minimize_btn)
        titlebar.addWidget(self.close_btn)

        self.count_label = QLabel("Blinks: 0")
        self.count_label.setStyleSheet("font-size: 15px; font-weight: 600;")

        self.rate_label = QLabel("Rate: -- / min")
        self.rate_label.setStyleSheet("font-size: 12px; color: #b0b0b0;")

        self.status_label = QLabel("Looking for a face...")
        self.status_label.setStyleSheet("font-size: 11px; color: #909090;")

        self.posture_label = QLabel("Posture: --")
        self.posture_label.setStyleSheet("font-size: 12px; color: #b0b0b0;")

        self.preview_label = QLabel()
        self.preview_label.setFixedSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: black; border-radius: 6px;")
        self.preview_label.setVisible(False)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 6, 10, 12)
        layout.setSpacing(4)
        layout.addLayout(titlebar)
        layout.addWidget(self.count_label)
        layout.addWidget(self.rate_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.posture_label)
        layout.addWidget(self.preview_label)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        self._position_top_right()

    def _position_top_right(self) -> None:
        screen = self.screen() or self.window().screen()
        geo = screen.availableGeometry() if screen else None
        self.adjustSize()
        if geo is not None:
            x = geo.right() - self.width() - 24
            y = geo.top() + 24
            self.move(x, y)

    def set_preview_visible(self, visible: bool) -> None:
        self._preview_wanted = visible
        if not self._minimized:
            self.preview_label.setVisible(visible)
            self.adjustSize()

    def set_posture_visible(self, visible: bool) -> None:
        self._posture_wanted = visible
        if not self._minimized:
            self.posture_label.setVisible(visible)
            self.adjustSize()

    def is_minimized(self) -> bool:
        return self._minimized

    def toggle_minimized(self) -> None:
        self.set_minimized(not self._minimized)

    def set_minimized(self, minimized: bool) -> None:
        if minimized == self._minimized:
            return
        self._minimized = minimized
        # Collapse down to just the blink count (plus the titlebar buttons)
        # rather than hiding the whole widget - it's still a "minimize", not
        # a close.
        self.rate_label.setVisible(not minimized)
        self.status_label.setVisible(not minimized)
        self.posture_label.setVisible(not minimized and self._posture_wanted)
        self.preview_label.setVisible(not minimized and self._preview_wanted)
        self.minimize_btn.setText("▢" if minimized else "–")
        self.minimize_btn.setToolTip("Restore" if minimized else "Minimize")
        self.adjustSize()

    def update_stats(self, result: BlinkResult) -> None:
        self.count_label.setText(f"Blinks: {result.total_blinks}")
        self.rate_label.setText(f"Rate: {result.blinks_per_minute} / min")
        self.status_label.setText("Tracking" if result.face_found else "No face detected")

    def update_posture(self, result: PostureResult) -> None:
        if not result.pose_found:
            self.posture_label.setText("Posture: --")
            self.posture_label.setStyleSheet("font-size: 12px; color: #b0b0b0;")
            return
        label = "Adjust" if result.bad_posture else "Good"
        color = "#e74c3c" if result.bad_posture else "#2ecc71"
        self.posture_label.setText(f"Posture: {label} ({result.posture_score})")
        self.posture_label.setStyleSheet(f"font-size: 12px; color: {color};")

    def update_frame(self, frame_bgr) -> None:
        if not self.preview_label.isVisible():
            return
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (PREVIEW_WIDTH, PREVIEW_HEIGHT))
        h, w, ch = rgb.shape
        image = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
        self.preview_label.setPixmap(QPixmap.fromImage(image))

    # Allow the user to drag the HUD to a preferred corner of the screen.
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None

    # Right-click gives access to the same menu as the tray icon - useful on
    # desktop environments/sandboxes where a system tray isn't available.
    def set_context_menu(self, menu) -> None:
        self._context_menu = menu

    def contextMenuEvent(self, event) -> None:
        if self._context_menu is not None:
            self._context_menu.exec(event.globalPos())

    # The close button (and any OS-level close, e.g. Alt+F4) hides the HUD
    # rather than destroying it - the app keeps running (camera worker, break
    # reminders, tray icon, ...) and the HUD can be reopened from the tray.
    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
        self.closed.emit()
