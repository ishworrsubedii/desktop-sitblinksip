"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Toggles a standard XDG autostart entry so the app can optionally launch on login.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

_AUTOSTART_ENTRY = """[Desktop Entry]
Type=Application
Name=SitBlinkSip Desktop
Comment=Background eye-blink tracker with break reminders
Exec={exec_path}
Icon=sitblinksip-desktop
X-GNOME-Autostart-enabled=true
NoDisplay=false
Terminal=false
"""


def _autostart_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart"


def _autostart_file() -> Path:
    return _autostart_dir() / "sitblinksip-desktop.desktop"


def is_enabled() -> bool:
    return _autostart_file().exists()


def set_enabled(enabled: bool) -> None:
    if not enabled:
        _autostart_file().unlink(missing_ok=True)
        return

    exec_path = shutil.which("sitblinksip-desktop") or "sitblinksip-desktop"
    _autostart_dir().mkdir(parents=True, exist_ok=True)
    _autostart_file().write_text(_AUTOSTART_ENTRY.format(exec_path=exec_path))
