#!/usr/bin/env python3
"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Regenerates the WAV files under sitblinksip_desktop/resources/sounds/.

Tone patterns are kept in sync by hand with frontend/lib/alertSounds.ts
(TONE_PATTERNS) so the desktop app's blink/posture/water alerts sound like
the same product as the web dashboard. Re-run this after changing either
side's patterns.
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 44100
PEAK_GAIN = 0.2
ATTACK_SECONDS = 0.01
GAP_SECONDS = 0.05

# kind -> (frequencies, beep duration in seconds), mirroring TONE_PATTERNS in
# frontend/lib/alertSounds.ts
TONE_PATTERNS = {
    "posture": ([440.0, 440.0], 0.140),
    "blink": ([660.0], 0.180),
    "water": ([523.0, 659.0, 784.0], 0.130),
}

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "sitblinksip_desktop" / "resources" / "sounds"


def _envelope(t: float, duration: float) -> float:
    if t <= ATTACK_SECONDS:
        return PEAK_GAIN * (t / ATTACK_SECONDS)
    remaining = duration - ATTACK_SECONDS
    if remaining <= 0:
        return 0.0
    frac = (t - ATTACK_SECONDS) / remaining
    return max(0.0, PEAK_GAIN * (1 - frac))


def synthesize(frequencies: list[float], beep_seconds: float) -> bytes:
    samples = bytearray()
    for freq in frequencies:
        n = int(SAMPLE_RATE * beep_seconds)
        for i in range(n):
            t = i / SAMPLE_RATE
            amplitude = _envelope(t, beep_seconds)
            value = amplitude * math.sin(2 * math.pi * freq * t)
            sample = int(max(-1.0, min(1.0, value)) * 32767)
            samples += struct.pack("<h", sample)
        gap_n = int(SAMPLE_RATE * GAP_SECONDS)
        samples += b"\x00\x00" * gap_n
    return bytes(samples)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for kind, (frequencies, beep_seconds) in TONE_PATTERNS.items():
        pcm = synthesize(frequencies, beep_seconds)
        path = OUTPUT_DIR / f"{kind}.wav"
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(pcm)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
