"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

First-run onboarding: a short QWizard shown once, before the tray icon and
HUD would otherwise leave a new user staring at an unfamiliar tray menu with
no explanation of what just started running or why it wants a webcam.
"""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWizard, QWizardPage

from . import autostart
from .config import AppConfig
from .platform_support import IS_LINUX, IS_MACOS, IS_WINDOWS


def _page(title: str, subtitle: str) -> QWizardPage:
    page = QWizardPage()
    page.setTitle(title)
    page.setSubTitle(subtitle)
    return page


class OnboardingWizard(QWizard):
    """Four short pages: what it does, camera access, the tray/hotkey, prefs.

    Shown once on first launch (gated by `AppConfig.onboarding_complete`).
    Cancelling is treated the same as finishing - the goal is a one-time
    explanation, not a mandatory setup gate - so it never nags twice.
    """

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Welcome to SitBlinkSip Desktop")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setMinimumSize(520, 360)

        self.addPage(self._welcome_page())
        self.addPage(self._camera_page())
        self.addPage(self._tray_page())
        self.addPage(self._preferences_page())

    def _welcome_page(self) -> QWizardPage:
        page = _page(
            "Blink, sit up, drink water.",
            "SitBlinkSip Desktop watches three things in the background so you don't have to.",
        )
        label = QLabel(
            "&bull; <b>Blinks</b> &ndash; counts blinks via webcam; if your rate drops too low, "
            "the screen briefly blanks as a nudge.<br><br>"
            "&bull; <b>Posture</b> &ndash; flags slouching or head-tilt with a sound + notification.<br><br>"
            "&bull; <b>Water</b> &ndash; reminds you to drink water on a timer, independent of the "
            "other two.<br><br>"
            "Nothing leaves your machine &ndash; all detection runs locally, and no camera feed "
            "is shown unless you ask for it."
        )
        label.setWordWrap(True)
        layout = QVBoxLayout(page)
        layout.addWidget(label)
        return page

    def _camera_page(self) -> QWizardPage:
        page = _page(
            "It needs your webcam",
            "Blink and posture checks both read the webcam. No image is ever saved or sent anywhere.",
        )
        if IS_MACOS:
            hint = (
                "macOS will prompt for <b>Camera</b> access on first launch &ndash; click Allow.<br><br>"
                "For the global F6 hotkey (to reveal the camera preview from anywhere), also grant "
                "<b>Accessibility</b> in System Settings &rarr; Privacy &amp; Security. This is "
                "optional &ndash; the tray menu always has a manual toggle too."
            )
        elif IS_WINDOWS:
            hint = (
                "If the camera doesn't start, check Settings &rarr; Privacy &amp; security &rarr; "
                "Camera and make sure desktop apps are allowed to use it."
            )
        else:
            hint = (
                "If the camera doesn't start, make sure your user account can read "
                "<b>/dev/video*</b> (usually via the <b>video</b> group)."
            )
        label = QLabel(hint)
        label.setWordWrap(True)
        layout = QVBoxLayout(page)
        layout.addWidget(label)
        return page

    def _tray_page(self) -> QWizardPage:
        tray_name = "menu bar" if IS_MACOS else "system tray"
        page = _page(
            "Where it lives",
            f"There's no main window &ndash; everything is driven from the {tray_name} icon.",
        )
        hotkey_note = (
            "F6 also works, but only while a SitBlinkSip window has focus &ndash; Wayland blocks "
            "global hotkeys for regular apps there."
            if IS_LINUX
            else "Press <b>F6</b> anywhere to show or hide it."
        )
        label = QLabel(
            "A small always-on-top counter shows your blink count. The camera preview stays "
            f"hidden by default; {hotkey_note}<br><br>"
            f"Everything else &ndash; pause tracking, Settings, quit &ndash; is in the {tray_name} "
            "icon's menu. Closing the counter just hides it; the app keeps running."
        )
        label.setWordWrap(True)
        layout = QVBoxLayout(page)
        layout.addWidget(label)
        return page

    def _preferences_page(self) -> QWizardPage:
        page = _page("A couple of quick choices", "You can change any of this later from Settings.")

        self.posture_check = QCheckBox("Check my posture too")
        self.posture_check.setChecked(self._config.posture_enabled)

        self.water_check = QCheckBox("Remind me to drink water")
        self.water_check.setChecked(self._config.water_reminder_enabled)

        self.autostart_check = QCheckBox("Launch SitBlinkSip Desktop when I log in")
        self.autostart_check.setChecked(autostart.is_enabled())

        layout = QVBoxLayout(page)
        layout.addWidget(self.posture_check)
        layout.addWidget(self.water_check)
        layout.addWidget(self.autostart_check)
        layout.addStretch(1)
        return page

    def apply_to_config(self) -> None:
        """Persist the preferences page. Call only when the wizard was accepted."""
        self._config.posture_enabled = self.posture_check.isChecked()
        self._config.water_reminder_enabled = self.water_check.isChecked()

        # Login items can fail for reasons outside our control (locked-down
        # registry, read-only LaunchAgents dir) - persist what actually
        # happened, mirroring SettingsDialog.apply_to_config.
        wanted_autostart = self.autostart_check.isChecked()
        if autostart.set_enabled(wanted_autostart):
            self._config.autostart = wanted_autostart
        else:
            self._config.autostart = autostart.is_enabled()

        self._config.onboarding_complete = True
        self._config.save()
