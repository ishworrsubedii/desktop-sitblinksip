"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Global F6 hotkey to toggle the camera preview from anywhere on the desktop.

Linux has no single portable API for this: `pynput` hooks X11 directly and
works well there, but Wayland's security model blocks global key listeners
for regular apps entirely. We detect that up front and fail soft - the
in-app QShortcut bound on the HUD/tray still covers F6 while a
SitBlinkSip window has focus, and the tray menu always has a manual toggle.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QObject, Signal


def is_wayland_session() -> bool:
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    return session_type == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))


class GlobalHotkey(QObject):
    """Best-effort global F6 listener. Emits `triggered` on X11; a no-op on Wayland."""

    triggered = Signal()
    unavailable = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._listener = None

    def start(self) -> None:
        if is_wayland_session():
            self.unavailable.emit(
                "Running under Wayland: the global F6 hotkey can't be registered "
                "system-wide. Use the tray menu, or focus a SitBlinkSip window "
                "and press F6 there."
            )
            return

        try:
            from pynput import keyboard
        except ImportError:
            self.unavailable.emit("pynput is not installed; global F6 hotkey disabled.")
            return

        try:
            self._listener = keyboard.GlobalHotKeys({"<f6>": self._on_triggered})
            self._listener.start()
        except Exception as exc:  # X11 not reachable, permissions, headless, etc.
            self._listener = None
            self.unavailable.emit(f"Could not register global F6 hotkey: {exc}")

    def _on_triggered(self) -> None:
        self.triggered.emit()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
