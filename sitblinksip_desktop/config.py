"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Persisted user settings, stored as JSON in the per-platform config directory
(see platform_support.config_dir).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .platform_support import APP_ID, config_dir

APP_DIR_NAME = APP_ID

__all__ = ["APP_DIR_NAME", "AppConfig", "config_dir", "config_path"]


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class AppConfig:
    camera_index: int = 0
    ear_threshold: float = 0.21
    consec_frames_min: int = 2
    min_blinks_per_minute: int = 10
    break_duration_seconds: float = 3.0
    break_cooldown_seconds: float = 60.0
    camera_preview_default: bool = False
    autostart: bool = False

    sound_enabled: bool = True

    posture_enabled: bool = True
    posture_angle_threshold: float = 145.0
    posture_displacement_threshold: float = 0.65
    posture_alert_score_threshold: int = 50
    posture_alert_cooldown_seconds: float = 120.0

    water_reminder_enabled: bool = True
    water_break_interval_minutes: float = 45.0

    onboarding_complete: bool = False

    @classmethod
    def load(cls) -> "AppConfig":
        path = config_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self) -> None:
        config_path().write_text(json.dumps(asdict(self), indent=2))
