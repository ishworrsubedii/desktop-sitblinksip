"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import autostart
from .config import AppConfig


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SitBlinkSip Desktop - Settings")
        self._config = config

        tabs = QTabWidget()
        tabs.addTab(self._build_blink_tab(config), "Blink")
        tabs.addTab(self._build_posture_tab(config), "Posture")
        tabs.addTab(self._build_water_tab(config), "Water")
        tabs.addTab(self._build_general_tab(config), "General")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    def _build_blink_tab(self, config: AppConfig) -> QWidget:
        self.camera_index_spin = QSpinBox()
        self.camera_index_spin.setRange(0, 10)
        self.camera_index_spin.setValue(config.camera_index)

        self.min_bpm_spin = QSpinBox()
        self.min_bpm_spin.setRange(1, 40)
        self.min_bpm_spin.setValue(config.min_blinks_per_minute)
        self.min_bpm_spin.setToolTip(
            "If your blink rate over the last minute drops below this, "
            "the screen blanks briefly to prompt a blink."
        )

        self.break_duration_spin = QDoubleSpinBox()
        self.break_duration_spin.setRange(2.0, 3.0)
        self.break_duration_spin.setSingleStep(0.5)
        self.break_duration_spin.setSuffix(" s")
        self.break_duration_spin.setValue(config.break_duration_seconds)

        self.break_cooldown_spin = QSpinBox()
        self.break_cooldown_spin.setRange(15, 600)
        self.break_cooldown_spin.setSuffix(" s")
        self.break_cooldown_spin.setValue(int(config.break_cooldown_seconds))
        self.break_cooldown_spin.setToolTip("Minimum time between two blank-screen reminders.")

        self.ear_threshold_spin = QDoubleSpinBox()
        self.ear_threshold_spin.setRange(0.10, 0.35)
        self.ear_threshold_spin.setSingleStep(0.01)
        self.ear_threshold_spin.setDecimals(2)
        self.ear_threshold_spin.setValue(config.ear_threshold)
        self.ear_threshold_spin.setToolTip(
            "Eye-aspect-ratio below which an eye counts as closed. Lower it if "
            "blinks are missed; raise it if blinks are over-counted."
        )

        form = QFormLayout()
        form.addRow("Camera device index", self.camera_index_spin)
        form.addRow("Minimum blinks / minute", self.min_bpm_spin)
        form.addRow("Break screen duration", self.break_duration_spin)
        form.addRow("Cooldown between breaks", self.break_cooldown_spin)
        form.addRow("EAR threshold (sensitivity)", self.ear_threshold_spin)

        widget = QWidget()
        widget.setLayout(form)
        return widget

    def _build_posture_tab(self, config: AppConfig) -> QWidget:
        self.posture_enabled_check = QCheckBox("Check posture via webcam")
        self.posture_enabled_check.setChecked(config.posture_enabled)

        self.posture_angle_spin = QDoubleSpinBox()
        self.posture_angle_spin.setRange(90.0, 180.0)
        self.posture_angle_spin.setSingleStep(1.0)
        self.posture_angle_spin.setValue(config.posture_angle_threshold)
        self.posture_angle_spin.setToolTip(
            "Head-tilt angle (ear-nose-ear) below which your head counts as tilted."
        )

        self.posture_displacement_spin = QDoubleSpinBox()
        self.posture_displacement_spin.setRange(0.30, 1.00)
        self.posture_displacement_spin.setSingleStep(0.05)
        self.posture_displacement_spin.setDecimals(2)
        self.posture_displacement_spin.setValue(config.posture_displacement_threshold)
        self.posture_displacement_spin.setToolTip(
            "Forward head displacement (relative to shoulder width) below which "
            "you count as leaning in / slouching."
        )

        self.posture_alert_score_spin = QSpinBox()
        self.posture_alert_score_spin.setRange(0, 100)
        self.posture_alert_score_spin.setValue(config.posture_alert_score_threshold)
        self.posture_alert_score_spin.setToolTip(
            "Posture score (0-100, decays while posture is bad) below which an "
            "alert fires."
        )

        self.posture_cooldown_spin = QSpinBox()
        self.posture_cooldown_spin.setRange(15, 1800)
        self.posture_cooldown_spin.setSuffix(" s")
        self.posture_cooldown_spin.setValue(int(config.posture_alert_cooldown_seconds))
        self.posture_cooldown_spin.setToolTip("Minimum time between two posture alerts.")

        form = QFormLayout()
        form.addRow(self.posture_enabled_check)
        form.addRow("Head-tilt angle threshold", self.posture_angle_spin)
        form.addRow("Forward-lean threshold", self.posture_displacement_spin)
        form.addRow("Alert below score", self.posture_alert_score_spin)
        form.addRow("Cooldown between alerts", self.posture_cooldown_spin)

        widget = QWidget()
        widget.setLayout(form)
        return widget

    def _build_water_tab(self, config: AppConfig) -> QWidget:
        self.water_enabled_check = QCheckBox("Remind me to drink water")
        self.water_enabled_check.setChecked(config.water_reminder_enabled)

        self.water_interval_spin = QDoubleSpinBox()
        self.water_interval_spin.setRange(5.0, 240.0)
        self.water_interval_spin.setSingleStep(5.0)
        self.water_interval_spin.setSuffix(" min")
        self.water_interval_spin.setValue(config.water_break_interval_minutes)

        form = QFormLayout()
        form.addRow(self.water_enabled_check)
        form.addRow("Reminder interval", self.water_interval_spin)

        widget = QWidget()
        widget.setLayout(form)
        return widget

    def _build_general_tab(self, config: AppConfig) -> QWidget:
        self.sound_enabled_check = QCheckBox("Play a sound with alerts")
        self.sound_enabled_check.setChecked(config.sound_enabled)

        self.autostart_check = QCheckBox("Launch on login")
        self.autostart_check.setChecked(autostart.is_enabled())

        form = QFormLayout()
        form.addRow(self.sound_enabled_check)
        form.addRow(self.autostart_check)

        widget = QWidget()
        widget.setLayout(form)
        return widget

    def apply_to_config(self) -> AppConfig:
        self._config.camera_index = self.camera_index_spin.value()
        self._config.min_blinks_per_minute = self.min_bpm_spin.value()
        self._config.break_duration_seconds = self.break_duration_spin.value()
        self._config.break_cooldown_seconds = float(self.break_cooldown_spin.value())
        self._config.ear_threshold = self.ear_threshold_spin.value()

        self._config.posture_enabled = self.posture_enabled_check.isChecked()
        self._config.posture_angle_threshold = self.posture_angle_spin.value()
        self._config.posture_displacement_threshold = self.posture_displacement_spin.value()
        self._config.posture_alert_score_threshold = self.posture_alert_score_spin.value()
        self._config.posture_alert_cooldown_seconds = float(self.posture_cooldown_spin.value())

        self._config.water_reminder_enabled = self.water_enabled_check.isChecked()
        self._config.water_break_interval_minutes = self.water_interval_spin.value()

        self._config.sound_enabled = self.sound_enabled_check.isChecked()

        self._config.autostart = self.autostart_check.isChecked()
        autostart.set_enabled(self._config.autostart)

        self._config.save()
        return self._config
