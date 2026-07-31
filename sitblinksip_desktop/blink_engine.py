"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Headless eye-blink counting core. No Qt / display dependency here so it can be
unit-tested with synthetic landmarks and reused outside the GUI if needed.

Uses MediaPipe FaceMesh landmarks and the standard 6-point Eye Aspect Ratio
(EAR) formula (Soukupova & Cech, 2016) instead of dlib, so the app has no large
model file to ship or compile-from-source dependency to install.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np

# 6-point EAR landmark indices into MediaPipe FaceMesh's 468 points:
# [outer_corner, upper_lid_1, upper_lid_2, inner_corner, lower_lid_2, lower_lid_1]
LEFT_EYE_EAR_IDX = (362, 385, 387, 263, 373, 380)
RIGHT_EYE_EAR_IDX = (33, 160, 158, 133, 153, 144)


@dataclass
class BlinkResult:
    face_found: bool
    ear: float | None
    blink_occurred: bool
    total_blinks: int
    blinks_per_minute: int


def _euclidean(a, b) -> float:
    return float(np.linalg.norm(np.array(a) - np.array(b)))


def _eye_aspect_ratio(points: list[tuple[float, float]]) -> float:
    p1, p2, p3, p4, p5, p6 = points
    vertical = _euclidean(p2, p6) + _euclidean(p3, p5)
    horizontal = 2.0 * _euclidean(p1, p4)
    if horizontal == 0:
        return 0.0
    return vertical / horizontal


class BlinkEngine:
    """Feed it BGR frames one at a time; it tracks blink count and rate."""

    def __init__(self, ear_threshold: float = 0.21, consec_frames_min: int = 2):
        self.ear_threshold = ear_threshold
        self.consec_frames_min = consec_frames_min

        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6,
        )

        self._low_ear_streak = 0
        self.total_blinks = 0
        self._blink_timestamps: deque[float] = deque()

    def close(self) -> None:
        self._face_mesh.close()

    def reset_stats(self) -> None:
        self.total_blinks = 0
        self._low_ear_streak = 0
        self._blink_timestamps.clear()

    def blinks_in_last(self, seconds: float, now: float | None = None) -> int:
        now = now if now is not None else time.time()
        cutoff = now - seconds
        while self._blink_timestamps and self._blink_timestamps[0] < cutoff:
            self._blink_timestamps.popleft()
        return len(self._blink_timestamps)

    def process_frame(self, frame_bgr: np.ndarray) -> BlinkResult:
        now = time.time()
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self._face_mesh.process(rgb)

        if not results.multi_face_landmarks:
            self._low_ear_streak = 0
            return BlinkResult(
                face_found=False,
                ear=None,
                blink_occurred=False,
                total_blinks=self.total_blinks,
                blinks_per_minute=self.blinks_in_last(60, now),
            )

        landmarks = results.multi_face_landmarks[0].landmark

        def pt(idx: int) -> tuple[float, float]:
            lm = landmarks[idx]
            return lm.x * w, lm.y * h

        left_ear = _eye_aspect_ratio([pt(i) for i in LEFT_EYE_EAR_IDX])
        right_ear = _eye_aspect_ratio([pt(i) for i in RIGHT_EYE_EAR_IDX])
        ear = (left_ear + right_ear) / 2.0

        blink_occurred = False
        if ear < self.ear_threshold:
            self._low_ear_streak += 1
        else:
            if self._low_ear_streak >= self.consec_frames_min:
                blink_occurred = True
                self.total_blinks += 1
                self._blink_timestamps.append(now)
            self._low_ear_streak = 0

        return BlinkResult(
            face_found=True,
            ear=ear,
            blink_occurred=blink_occurred,
            total_blinks=self.total_blinks,
            blinks_per_minute=self.blinks_in_last(60, now),
        )
