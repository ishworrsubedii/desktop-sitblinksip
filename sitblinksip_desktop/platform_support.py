"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Single place for everything that differs between Linux, Windows and macOS:
where settings live, where bundled resources live once frozen, how to
re-launch the app, and which OpenCV capture backend to ask for.

Keeping these here (rather than sprinkling `sys.platform` checks through the
feature modules) means each platform's quirks are documented in one file and
the rest of the app stays platform-agnostic.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_ID = "sitblinksip-desktop"
APP_NAME = "SitBlinkSip Desktop"
# Reverse-DNS id used for the macOS bundle, its LaunchAgent, and the Windows
# AppUserModelID. Must stay stable across releases - macOS ties the camera
# (TCC) permission grant to it, and Windows ties taskbar/notification identity
# to it.
BUNDLE_ID = "com.github.ishworrsubedii.sitblinksip-desktop"

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = not IS_WINDOWS and not IS_MACOS


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle rather than source."""
    return bool(getattr(sys, "frozen", False))


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

def config_dir() -> Path:
    """Per-user settings directory, following each platform's convention.

    Linux keeps the historical XDG location so existing installs keep their
    settings; Windows and macOS use the locations their users (and backup
    tools) expect rather than a stray ~/.config.
    """
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif IS_MACOS:
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")

    path = Path(base) / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def resources_dir() -> Path:
    """Directory holding bundled resources (alert sounds, ...).

    PyInstaller unpacks bundled data under `sys._MEIPASS`, which is a fresh
    temp dir for --onefile builds and the app's own `_internal` dir for
    --onedir ones. The spec adds our resources under the package path, so
    prefer that and fall back to the source-tree layout.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "sitblinksip_desktop" / "resources"
        if bundled.is_dir():
            return bundled
        flat = Path(meipass) / "resources"
        if flat.is_dir():
            return flat
    return Path(__file__).resolve().parent / "resources"


def macos_app_bundle() -> Path | None:
    """Path to the enclosing `.app` bundle, when running as one."""
    if not (IS_MACOS and is_frozen()):
        return None
    for parent in Path(sys.executable).resolve().parents:
        if parent.suffix == ".app":
            return parent
    return None


def launch_command() -> list[str]:
    """Argv that re-launches this app, for autostart entries.

    Frozen builds point straight at the bundled executable. From source we
    prefer the console-script installed by pip and fall back to
    `<python> -m sitblinksip_desktop`, which always works inside a venv.
    """
    if is_frozen():
        return [str(Path(sys.executable).resolve())]

    script = shutil.which(APP_ID)
    if script:
        return [script]
    return [sys.executable, "-m", "sitblinksip_desktop"]


# --------------------------------------------------------------------------
# Camera
# --------------------------------------------------------------------------

def camera_backend() -> int:
    """Preferred `cv2.VideoCapture` backend for this platform.

    Left to itself OpenCV picks MSMF on Windows, which is slow to open and
    frequently reports the wrong device for a plain integer index; DirectShow
    is the reliable choice for consumer webcams. On macOS the only real option
    is AVFoundation, and naming it explicitly avoids OpenCV probing (and
    logging warnings about) backends that aren't there. Linux is fine with
    the default V4L2 autodetection.
    """
    import cv2

    if IS_WINDOWS:
        return cv2.CAP_DSHOW
    if IS_MACOS:
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_ANY


def camera_error_hint(camera_index: int) -> str:
    """Platform-specific advice when the camera can't be opened."""
    common = (
        f"Could not open camera device {camera_index}. "
        "Check that it's connected and not in use by another app."
    )
    if IS_MACOS:
        return (
            f"{common}\n\nOn macOS you also need to grant camera access: "
            "System Settings -> Privacy & Security -> Camera, and enable "
            f"{APP_NAME} (or your terminal, if you're running from source). "
            "You may need to restart the app afterwards."
        )
    if IS_WINDOWS:
        return (
            f"{common}\n\nOn Windows, also check Settings -> Privacy & security "
            "-> Camera and make sure camera access is on for desktop apps. "
            "If you have several cameras, try a different device index in "
            "Settings."
        )
    return (
        f"{common}\n\nOn Linux, check that your user can read /dev/video* "
        "(usually via the 'video' group)."
    )


# --------------------------------------------------------------------------
# Process / windowing tweaks
# --------------------------------------------------------------------------

def set_windows_app_user_model_id() -> None:
    """Give Windows an explicit app identity.

    Without this, a frozen Python app is grouped under - and shows the icon
    of - "python.exe" in the taskbar, and toast notifications from the tray
    icon are attributed to Python instead of SitBlinkSip. Must run before any
    window is created.
    """
    if not IS_WINDOWS:
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(BUNDLE_ID)
    except Exception:
        # Purely cosmetic - never worth failing startup over.
        pass


def bring_to_front(widget) -> None:
    """Raise and focus a window across platforms.

    macOS in particular will happily show a window from a background
    (LSUIElement) app without giving it keyboard focus, which would break the
    break-overlay's Escape-to-dismiss. Doing raise+activate everywhere also
    fixes focus-stealing-prevention on some Linux window managers.
    """
    widget.raise_()
    widget.activateWindow()
    if IS_MACOS:
        try:
            from AppKit import NSApplication

            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        except Exception:
            # pyobjc isn't a hard dependency; raise_/activateWindow still
            # cover the common case.
            pass
