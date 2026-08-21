"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

"Launch on login", implemented three ways because the three desktop platforms
have nothing in common here:

  Linux    an XDG autostart .desktop entry in ~/.config/autostart
  Windows  a value under HKCU\\...\\CurrentVersion\\Run
  macOS    a launchd user agent plist in ~/Library/LaunchAgents

Each backend exposes the same is_enabled()/set_enabled() pair, and every one
of them fails soft: a login item that can't be written is an annoyance, never
a reason to break the settings dialog.
"""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from .platform_support import (
    APP_ID,
    APP_NAME,
    BUNDLE_ID,
    IS_MACOS,
    IS_WINDOWS,
    launch_command,
)

# --------------------------------------------------------------------------
# Linux - XDG autostart
# --------------------------------------------------------------------------

_AUTOSTART_ENTRY = """[Desktop Entry]
Type=Application
Name={name}
Comment=Background eye-blink tracker with break reminders
Exec={exec_line}
Icon={app_id}
X-GNOME-Autostart-enabled=true
NoDisplay=false
Terminal=false
"""


def _desktop_exec_quote(arg: str) -> str:
    """Quote one argv element for a .desktop `Exec=` line.

    The Desktop Entry spec has its own quoting rules (double quotes, with
    backslash escaping inside them) - close to, but not the same as, shell
    quoting, so shlex is not the right tool.
    """
    if not arg or any(c in arg for c in ' \t\n"\'\\><~|&;$*?#()`'):
        escaped = arg.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return arg


def _autostart_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart"


def _autostart_file() -> Path:
    return _autostart_dir() / f"{APP_ID}.desktop"


def _linux_is_enabled() -> bool:
    return _autostart_file().exists()


def _linux_set_enabled(enabled: bool) -> None:
    if not enabled:
        _autostart_file().unlink(missing_ok=True)
        return

    exec_line = " ".join(_desktop_exec_quote(part) for part in launch_command())
    _autostart_dir().mkdir(parents=True, exist_ok=True)
    _autostart_file().write_text(
        _AUTOSTART_ENTRY.format(name=APP_NAME, exec_line=exec_line, app_id=APP_ID)
    )


# --------------------------------------------------------------------------
# Windows - HKCU Run key
# --------------------------------------------------------------------------

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE = "SitBlinkSipDesktop"


def _windows_is_enabled() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _RUN_VALUE)
        return True
    except OSError:
        return False


def _windows_set_enabled(enabled: bool) -> None:
    import winreg

    if not enabled:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, _RUN_VALUE)
        except OSError:
            pass  # Already absent.
        return

    # list2cmdline applies the exact quoting rules CreateProcess expects,
    # which matters because the install path ("C:\Program Files\...") has a
    # space in it and an unquoted Run value would be parsed as two arguments.
    command = subprocess.list2cmdline(launch_command())
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, _RUN_VALUE, 0, winreg.REG_SZ, command)


# --------------------------------------------------------------------------
# macOS - launchd user agent
# --------------------------------------------------------------------------

def _launch_agent_file() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{BUNDLE_ID}.plist"


def _macos_is_enabled() -> bool:
    return _launch_agent_file().exists()


def _launchctl(*args: str) -> None:
    """Best-effort launchctl call, so the change applies without a re-login."""
    try:
        subprocess.run(
            ["launchctl", *args],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _macos_set_enabled(enabled: bool) -> None:
    path = _launch_agent_file()
    domain = f"gui/{os.getuid()}"

    if not enabled:
        if path.exists():
            _launchctl("bootout", f"{domain}/{BUNDLE_ID}")
            path.unlink(missing_ok=True)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": BUNDLE_ID,
        "ProgramArguments": launch_command(),
        "RunAtLoad": True,
        # It's a long-running background app, but a crash loop restarting
        # every second would be worse than it staying down until next login.
        "KeepAlive": False,
        "ProcessType": "Interactive",
    }
    with path.open("wb") as handle:
        plistlib.dump(plist, handle)

    # Replace any previously-registered copy, then register this one.
    _launchctl("bootout", f"{domain}/{BUNDLE_ID}")
    _launchctl("bootstrap", domain, str(path))


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def is_enabled() -> bool:
    try:
        if IS_WINDOWS:
            return _windows_is_enabled()
        if IS_MACOS:
            return _macos_is_enabled()
        return _linux_is_enabled()
    except Exception:
        return False


def set_enabled(enabled: bool) -> bool:
    """Enable/disable launch-on-login. Returns True if the change stuck."""
    try:
        if IS_WINDOWS:
            _windows_set_enabled(enabled)
        elif IS_MACOS:
            _macos_set_enabled(enabled)
        else:
            _linux_set_enabled(enabled)
    except Exception as exc:
        print(f"[{APP_ID}] could not update launch-on-login: {exc}", file=sys.stderr)
        return False
    return True
