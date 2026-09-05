"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Entry point that wires the camera worker, HUD, tray icon, break overlay and
global hotkey together.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .blink_engine import BlinkResult
from .break_overlay import BreakOverlay
from .camera_worker import CameraWorker
from .config import AppConfig
from .hotkeys import GlobalHotkey
from .hud_widget import HudWidget
from .icon import build_app_icon
from .onboarding import OnboardingWizard
from .platform_support import (
    APP_ID,
    APP_NAME,
    IS_LINUX,
    set_windows_app_user_model_id,
)
from .posture_engine import PostureResult
from .settings_dialog import SettingsDialog
from .sound import AlertPlayer
from .tray_icon import TrayIcon
from .water_reminder import WaterReminder

# Blinks/min is computed over a trailing 60s window, so it reads artificially
# low right after launch simply for lack of history. Give it time to fill in
# before the first low-rate break can fire.
STARTUP_GRACE_SECONDS = 30.0


class SitBlinkSipApp:
    def __init__(self):
        self.config = AppConfig.load()
        self._start_time = time.time()
        self._last_break_time = 0.0
        self._last_posture_alert_time = 0.0
        self._hotkey_notice_shown = False
        self._hud_closed_notice_shown = False

        self.qt_app = QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setApplicationDisplayName(APP_NAME)
        if IS_LINUX:
            # Lets Wayland/GNOME match the running app to its installed
            # .desktop entry, so it gets the right icon and name in the
            # window list instead of a generic placeholder.
            self.qt_app.setDesktopFileName(APP_ID)

        self.app_icon = build_app_icon()

        if not self.config.onboarding_complete:
            wizard = OnboardingWizard(self.config)
            wizard.setWindowIcon(self.app_icon)
            if wizard.exec():
                wizard.apply_to_config()
            else:
                # Cancelling still counts as "seen it" - this is a one-time
                # explanation, not a mandatory setup gate, so it never nags
                # on a later launch.
                self.config.onboarding_complete = True
                self.config.save()

        self.sound = AlertPlayer()
        self.sound.enabled = self.config.sound_enabled

        self.hud = HudWidget()
        self.hud.setWindowIcon(self.app_icon)
        self.hud.set_posture_visible(self.config.posture_enabled)
        self.hud.closed.connect(self._on_hud_closed)

        self.break_overlay = BreakOverlay(duration_seconds=self.config.break_duration_seconds)

        self.worker = CameraWorker(
            camera_index=self.config.camera_index,
            ear_threshold=self.config.ear_threshold,
            consec_frames_min=self.config.consec_frames_min,
            posture_angle_threshold=self.config.posture_angle_threshold,
            posture_displacement_threshold=self.config.posture_displacement_threshold,
            posture_enabled=self.config.posture_enabled,
        )
        self.worker.set_preview_enabled(self.config.camera_preview_default)
        self.worker.stats_ready.connect(self._on_stats)
        self.worker.posture_ready.connect(self._on_posture)
        self.worker.frame_ready.connect(self.hud.update_frame)
        self.worker.camera_error.connect(self._on_camera_error)

        self.water_reminder = WaterReminder(interval_seconds=self.config.water_break_interval_minutes * 60)
        self.water_reminder.triggered.connect(self._on_water_break)
        if not self.config.water_reminder_enabled:
            self.water_reminder.stop()

        tray_callbacks = dict(
            icon=self.app_icon,
            on_toggle_hud=self._toggle_hud,
            on_toggle_preview=self._toggle_preview,
            on_toggle_pause=self._toggle_pause,
            on_toggle_posture=self._toggle_posture,
            on_toggle_water=self._toggle_water,
            on_toggle_sound=self._toggle_sound,
            on_open_settings=self._open_settings,
            on_quit=self._quit,
        )

        # `self.tray` is only set when a real system tray exists (guards
        # showMessage notifications, which need one). `self._menu` always
        # points at *some* TrayIcon instance - real or the HUD's right-click
        # fallback - so checkable actions stay in sync either way.
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = TrayIcon(**tray_callbacks)
            self._menu = self.tray
            self.hud.set_context_menu(self.tray.contextMenu())
            self.tray.show()
        else:
            # No tray available on this desktop - fall back to the HUD's own
            # right-click menu built from the same actions, so nothing is lost.
            self._menu = TrayIcon(**tray_callbacks)
            self.hud.set_context_menu(self._menu.contextMenu())

        self._menu.set_preview_checked(self.config.camera_preview_default)
        self._menu.set_posture_checked(self.config.posture_enabled)
        self._menu.set_water_checked(self.config.water_reminder_enabled)
        self._menu.set_sound_checked(self.config.sound_enabled)

        self.hud.set_preview_visible(self.config.camera_preview_default)

        # Works whenever the HUD has focus, regardless of session type -
        # the complement to the best-effort global hotkey below.
        self.local_f6_shortcut = QShortcut(QKeySequence("F6"), self.hud)
        self.local_f6_shortcut.activated.connect(self._toggle_preview)

        self.hotkey = GlobalHotkey()
        self.hotkey.triggered.connect(self._toggle_preview)
        self.hotkey.unavailable.connect(self._on_hotkey_unavailable)
        self.hotkey.start()

    def _on_stats(self, result: BlinkResult) -> None:
        self.hud.update_stats(result)
        self._maybe_trigger_break(result)

    def _maybe_trigger_break(self, result: BlinkResult) -> None:
        now = time.time()
        if now - self._start_time < STARTUP_GRACE_SECONDS:
            return
        if result.blinks_per_minute >= self.config.min_blinks_per_minute:
            return
        if now - self._last_break_time < self.config.break_cooldown_seconds:
            return
        self._last_break_time = now
        self.sound.play("blink")
        self.break_overlay.show()

    def _on_posture(self, result: PostureResult) -> None:
        self.hud.update_posture(result)
        self._maybe_trigger_posture_alert(result)

    def _maybe_trigger_posture_alert(self, result: PostureResult) -> None:
        if not result.pose_found:
            return
        if result.posture_score > self.config.posture_alert_score_threshold:
            return
        now = time.time()
        if now - self._last_posture_alert_time < self.config.posture_alert_cooldown_seconds:
            return
        self._last_posture_alert_time = now
        self.sound.play("posture")
        self._notify("Posture check", "Sit up straight - your posture has slipped.")

    def _on_water_break(self) -> None:
        self.sound.play("water")
        self._notify("Water break", "Time to drink some water.")

    def _notify(self, title: str, message: str) -> None:
        # Qt's tray balloon depends on the tray icon actually rendering,
        # which on Linux desktops (GNOME chief among them) is unreliable
        # even when isSystemTrayAvailable() reports True - no visible icon
        # means the balloon has nowhere to anchor and silently never
        # appears. Talking to the desktop's notification daemon directly
        # works regardless of tray state, so prefer it there.
        if IS_LINUX and shutil.which("notify-send"):
            subprocess.Popen(["notify-send", "--app-name", APP_NAME, title, message])
        elif self.tray is not None:
            self.tray.showMessage(title, message, QSystemTrayIcon.Information, 6000)
        else:
            print(f"[sitblinksip-desktop] {title}: {message}", file=sys.stderr)

    def _toggle_hud(self) -> None:
        self.hud.setVisible(not self.hud.isVisible())

    def _on_hud_closed(self) -> None:
        # Closing the HUD only hides it - tracking, breaks and the tray icon
        # all keep running. Let the user know how to bring it back, once.
        if self._hud_closed_notice_shown:
            return
        self._hud_closed_notice_shown = True
        self._notify(
            "SitBlinkSip Desktop",
            "Still running in the background. Click the tray icon (or use "
            "\"Show/Hide counter\") to bring the HUD back.",
        )

    def _toggle_preview(self) -> None:
        enabled = not self.worker.is_preview_enabled()
        self.worker.set_preview_enabled(enabled)
        self.hud.set_preview_visible(enabled)
        self._menu.set_preview_checked(enabled)
        if not self.hud.isVisible():
            self.hud.show()

    def _toggle_pause(self) -> None:
        paused = not self.worker.is_paused()
        self.worker.set_paused(paused)
        self._menu.set_paused_checked(paused)

    def _toggle_posture(self) -> None:
        enabled = not self.config.posture_enabled
        self.config.posture_enabled = enabled
        self.config.save()
        self.worker.set_posture_enabled(enabled)
        self.hud.set_posture_visible(enabled)
        self._menu.set_posture_checked(enabled)

    def _toggle_water(self) -> None:
        enabled = not self.config.water_reminder_enabled
        self.config.water_reminder_enabled = enabled
        self.config.save()
        if enabled:
            self.water_reminder.set_interval(self.config.water_break_interval_minutes * 60)
        else:
            self.water_reminder.stop()
        self._menu.set_water_checked(enabled)

    def _toggle_sound(self) -> None:
        enabled = not self.config.sound_enabled
        self.config.sound_enabled = enabled
        self.config.save()
        self.sound.enabled = enabled
        self._menu.set_sound_checked(enabled)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config)
        if dialog.exec():
            config = dialog.apply_to_config()
            self.worker.update_thresholds(config.ear_threshold, config.consec_frames_min)
            self.worker.update_posture_thresholds(
                config.posture_angle_threshold, config.posture_displacement_threshold
            )
            self.worker.set_posture_enabled(config.posture_enabled)
            self.hud.set_posture_visible(config.posture_enabled)

            self.break_overlay.duration_seconds = config.break_duration_seconds
            self.sound.enabled = config.sound_enabled

            if config.water_reminder_enabled:
                self.water_reminder.set_interval(config.water_break_interval_minutes * 60)
            else:
                self.water_reminder.stop()

            # The dialog can change posture/water/sound too - keep the tray's
            # checkable actions in sync with whatever was just saved.
            self._menu.set_posture_checked(config.posture_enabled)
            self._menu.set_water_checked(config.water_reminder_enabled)
            self._menu.set_sound_checked(config.sound_enabled)

            if config.camera_index != self.worker.camera_index:
                QMessageBox.information(
                    None,
                    "Restart required",
                    "Changing the camera device takes effect after restarting SitBlinkSip Desktop.",
                )

    def _on_camera_error(self, message: str) -> None:
        QMessageBox.critical(None, "Camera error", message)

    def _on_hotkey_unavailable(self, message: str) -> None:
        if self._hotkey_notice_shown:
            return
        self._hotkey_notice_shown = True
        self._notify("SitBlinkSip Desktop", message)

    def _quit(self) -> None:
        self.hotkey.stop()
        self.water_reminder.stop()
        self.worker.stop()
        self.worker.wait(2000)
        self.qt_app.quit()

    def run(self) -> int:
        self.hud.show()
        self.worker.start()
        return self.qt_app.exec()


def main() -> None:
    # Has to happen before the first window exists, or Windows keeps
    # attributing the tray icon and its notifications to "Python".
    set_windows_app_user_model_id()
    app = SitBlinkSipApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
