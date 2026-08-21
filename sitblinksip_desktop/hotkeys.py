"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Global F6 hotkey to toggle the camera preview from anywhere on the desktop.

There is no portable API for this, and each platform withholds it differently:

  Windows  works out of the box (`pynput` uses a Win32 low-level keyboard hook).
  macOS    needs the user to grant Accessibility permission first; without it
           the listener starts but silently never fires, so we check up front
           and say so rather than leaving a dead key.
  Linux    `pynput` hooks X11 and works well there, but Wayland's security
           model blocks global key listeners for regular apps entirely.

Every failure mode is soft: the in-app QShortcut still covers F6 while a
SitBlinkSip window has focus, and the tray menu always has a manual toggle.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QObject, Signal

from .platform_support import APP_NAME, IS_LINUX, IS_MACOS


def is_wayland_session() -> bool:
    if not IS_LINUX:
        return False
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    return session_type == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))


def macos_accessibility_trusted() -> bool | None:
    """Whether macOS has granted this process Accessibility access.

    Returns None when we can't tell (pyobjc's ApplicationServices bindings
    aren't guaranteed to be present), in which case the caller should just try
    and let the listener fail quietly.
    """
    if not IS_MACOS:
        return None
    try:
        from ApplicationServices import AXIsProcessTrusted

        return bool(AXIsProcessTrusted())
    except Exception:
        return None


class GlobalHotkey(QObject):
    """Best-effort global F6 listener; degrades to a no-op where blocked."""

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

        if macos_accessibility_trusted() is False:
            self.unavailable.emit(
                "macOS is blocking the global F6 hotkey. To enable it, open "
                "System Settings -> Privacy & Security -> Accessibility and "
                f"turn on {APP_NAME}, then restart the app. Until then, use the "
                "menu bar icon, or press F6 with a SitBlinkSip window focused."
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
