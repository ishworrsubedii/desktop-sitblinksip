"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Headless posture checker. Same head-tilt-angle / forward-lean-displacement
approach as src/services/posture_det_service/posture_det.py in the main
project, ported to be display-free and reused here via MediaPipe Pose.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np


@dataclass
class PostureResult:
    pose_found: bool
    head_tilt: float | None
    displacement_ratio: float | None
    bad_posture: bool
    posture_score: int


def _angle(a, b, c) -> float:
    a, b, c = np.array(a), np.array(b), np.array(c)
    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    if angle > 180.0:
        angle = 360 - angle
    return float(angle)


def _distance(a, b) -> float:
    return float(np.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2))


class PostureEngine:
    def __init__(
        self,
        angle_threshold: float = 145.0,
        displacement_threshold: float = 0.65,
        score_decay: float = 0.5,
        score_gain: float = 0.3,
    ):
        self.angle_threshold = angle_threshold
        self.displacement_threshold = displacement_threshold
        self.score_decay = score_decay
        self.score_gain = score_gain
        self.posture_score = 100.0

        self._mp_pose = mp.solutions.pose
        self._pose = self._mp_pose.Pose(
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
            model_complexity=0,  # "lite" model - this runs alongside blink detection
        )

    def close(self) -> None:
        self._pose.close()

    def reset(self) -> None:
        self.posture_score = 100.0

    def process_frame(self, frame_bgr: np.ndarray) -> PostureResult:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self._pose.process(rgb)

        if not results.pose_landmarks:
            return PostureResult(
                pose_found=False,
                head_tilt=None,
                displacement_ratio=None,
                bad_posture=False,
                posture_score=int(self.posture_score),
            )

        landmarks = results.pose_landmarks.landmark
        Lm = self._mp_pose.PoseLandmark

        def point(landmark_id) -> tuple[float, float]:
            p = landmarks[landmark_id.value]
            return p.x, p.y

        left_shoulder = point(Lm.LEFT_SHOULDER)
        right_shoulder = point(Lm.RIGHT_SHOULDER)
        left_ear = point(Lm.LEFT_EAR)
        right_ear = point(Lm.RIGHT_EAR)
        nose = point(Lm.NOSE)

        head_tilt = _angle(left_ear, nose, right_ear)

        ear_midpoint = ((left_ear[0] + right_ear[0]) / 2, (left_ear[1] + right_ear[1]) / 2)
        shoulder_midpoint = (
            (left_shoulder[0] + right_shoulder[0]) / 2,
            (left_shoulder[1] + right_shoulder[1]) / 2,
        )
        forward_displacement = _distance(ear_midpoint, shoulder_midpoint)
        shoulder_width = _distance(left_shoulder, right_shoulder)
        displacement_ratio = forward_displacement / shoulder_width if shoulder_width else 0.0

        bad_posture = head_tilt < self.angle_threshold or displacement_ratio < self.displacement_threshold

        if bad_posture:
            self.posture_score = max(0.0, self.posture_score - self.score_decay)
        else:
            self.posture_score = min(100.0, self.posture_score + self.score_gain)

        return PostureResult(
            pose_found=True,
            head_tilt=head_tilt,
            displacement_ratio=displacement_ratio,
            bad_posture=bad_posture,
            posture_score=int(self.posture_score),
        )
