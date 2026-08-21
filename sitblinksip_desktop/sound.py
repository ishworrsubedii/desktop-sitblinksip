"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Plays the same three distinct alert tones (blink/posture/water) as the web
dashboard's frontend/lib/alertSounds.ts, pre-rendered to WAV by
scripts/generate_alert_sounds.py and played back with QSoundEffect.
"""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

from .platform_support import resources_dir

_KINDS = ("blink", "posture", "water")


class AlertPlayer:
    def __init__(self):
        self.enabled = True
        # Resolved at construction rather than import time: in a frozen build
        # this lives under the PyInstaller extraction dir, not next to the .py.
        sound_dir = resources_dir() / "sounds"
        self._effects: dict[str, QSoundEffect] = {}
        for kind in _KINDS:
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(sound_dir / f"{kind}.wav")))
            effect.setVolume(0.6)
            self._effects[kind] = effect

    def play(self, kind: str) -> None:
        if not self.enabled:
            return
        effect = self._effects.get(kind)
        if effect is not None:
            effect.play()
