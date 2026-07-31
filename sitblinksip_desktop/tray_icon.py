"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu


class TrayIcon(QSystemTrayIcon):
    def __init__(
        self,
        icon: QIcon,
        on_toggle_hud: Callable[[], None],
        on_toggle_preview: Callable[[], None],
        on_toggle_pause: Callable[[], None],
        on_toggle_posture: Callable[[], None],
        on_toggle_water: Callable[[], None],
        on_toggle_sound: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_quit: Callable[[], None],
        parent=None,
    ):
        super().__init__(icon, parent)
        self.setToolTip("SitBlinkSip Desktop")

        # Left-click/double-click the tray icon to toggle the HUD - the
        # main way back in once it's been closed. Not all desktop
        # environments deliver Trigger/DoubleClick (some route every click
        # to the context menu instead), so the menu action below always
        # works as a fallback.
        self.activated.connect(self._on_activated)
        self._on_toggle_hud = on_toggle_hud

        menu = QMenu()

        self.hud_action = QAction("Show/Hide counter", menu)
        self.hud_action.triggered.connect(on_toggle_hud)
        menu.addAction(self.hud_action)

        self.preview_action = QAction("Show camera preview (F6)", menu)
        self.preview_action.setCheckable(True)
        self.preview_action.triggered.connect(on_toggle_preview)
        menu.addAction(self.preview_action)

        self.pause_action = QAction("Pause tracking", menu)
        self.pause_action.setCheckable(True)
        self.pause_action.triggered.connect(on_toggle_pause)
        menu.addAction(self.pause_action)

        menu.addSeparator()

        self.posture_action = QAction("Posture checks", menu)
        self.posture_action.setCheckable(True)
        self.posture_action.triggered.connect(on_toggle_posture)
        menu.addAction(self.posture_action)

        self.water_action = QAction("Water break reminders", menu)
        self.water_action.setCheckable(True)
        self.water_action.triggered.connect(on_toggle_water)
        menu.addAction(self.water_action)

        self.sound_action = QAction("Alert sounds", menu)
        self.sound_action.setCheckable(True)
        self.sound_action.triggered.connect(on_toggle_sound)
        menu.addAction(self.sound_action)

        menu.addSeparator()

        settings_action = QAction("Settings...", menu)
        settings_action.triggered.connect(on_open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(on_quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._on_toggle_hud()

    def set_preview_checked(self, checked: bool) -> None:
        self.preview_action.setChecked(checked)

    def set_paused_checked(self, checked: bool) -> None:
        self.pause_action.setChecked(checked)

    def set_posture_checked(self, checked: bool) -> None:
        self.posture_action.setChecked(checked)

    def set_water_checked(self, checked: bool) -> None:
        self.water_action.setChecked(checked)

    def set_sound_checked(self, checked: bool) -> None:
        self.sound_action.setChecked(checked)
