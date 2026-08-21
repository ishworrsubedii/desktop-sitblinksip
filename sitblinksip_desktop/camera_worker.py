"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Background capture thread. Keeps the camera device open and runs blink
detection on every frame regardless of whether the preview is visible - only
the (comparatively cheap) Qt image conversion/emission is skipped while the
preview is hidden, so tracking never stops just because the video isn't shown.

Posture checks piggyback on the same frames but only run every POSTURE_EVERY_N
frames - posture drifts slowly compared to blinks, and MediaPipe Pose is
heavier than FaceMesh, so there's no need to run it at full frame rate.
"""
from __future__ import annotations

import threading
import time

import cv2
from PySide6.QtCore import QThread, Signal

from .blink_engine import BlinkEngine, BlinkResult
from .platform_support import camera_backend, camera_error_hint
from .posture_engine import PostureEngine, PostureResult

POSTURE_EVERY_N_FRAMES = 5

# Blink/posture detection works fine on a small frame, and asking for one
# explicitly stops macOS AVFoundation and some Windows webcams from handing us
# 1080p (or worse) by default, which costs CPU for no benefit.
CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 480


def _open_capture(camera_index: int):
    """Open the webcam, preferring this platform's best backend.

    The explicit backend is a strong preference, not a requirement: unusual
    setups (a virtual camera on Windows that only exposes MSMF, a Linux
    gstreamer source) can still work through OpenCV's autodetection, so fall
    back to it rather than refusing to start.
    """
    preferred = camera_backend()
    cap = cv2.VideoCapture(camera_index, preferred)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(camera_index)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
    return cap


class CameraWorker(QThread):
    stats_ready = Signal(object)  # BlinkResult
    posture_ready = Signal(object)  # PostureResult
    frame_ready = Signal(object)  # numpy.ndarray (BGR)
    camera_error = Signal(str)

    def __init__(
        self,
        camera_index: int,
        ear_threshold: float,
        consec_frames_min: int,
        posture_angle_threshold: float,
        posture_displacement_threshold: float,
        posture_enabled: bool,
        parent=None,
    ):
        super().__init__(parent)
        self.camera_index = camera_index
        self.engine = BlinkEngine(ear_threshold=ear_threshold, consec_frames_min=consec_frames_min)
        self.posture_engine = PostureEngine(
            angle_threshold=posture_angle_threshold,
            displacement_threshold=posture_displacement_threshold,
        )

        self._stop_event = threading.Event()
        self._paused = False
        self._preview_enabled = False
        self._posture_enabled = posture_enabled
        self._lock = threading.Lock()

    def set_preview_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._preview_enabled = enabled

    def is_preview_enabled(self) -> bool:
        with self._lock:
            return self._preview_enabled

    def set_posture_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._posture_enabled = enabled
            if not enabled:
                self.posture_engine.reset()

    def is_posture_enabled(self) -> bool:
        with self._lock:
            return self._posture_enabled

    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self._paused = paused
            if paused:
                self.engine.reset_stats()
                self.posture_engine.reset()

    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    def update_thresholds(self, ear_threshold: float, consec_frames_min: int) -> None:
        self.engine.ear_threshold = ear_threshold
        self.engine.consec_frames_min = consec_frames_min

    def update_posture_thresholds(self, angle_threshold: float, displacement_threshold: float) -> None:
        self.posture_engine.angle_threshold = angle_threshold
        self.posture_engine.displacement_threshold = displacement_threshold

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        cap = _open_capture(self.camera_index)
        if not cap.isOpened():
            self.camera_error.emit(camera_error_hint(self.camera_index))
            return

        frame_count = 0
        try:
            while not self._stop_event.is_set():
                if self.is_paused():
                    time.sleep(0.2)
                    continue

                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.05)
                    continue

                frame_count += 1

                result: BlinkResult = self.engine.process_frame(frame)
                self.stats_ready.emit(result)

                if self.is_posture_enabled() and frame_count % POSTURE_EVERY_N_FRAMES == 0:
                    posture_result: PostureResult = self.posture_engine.process_frame(frame)
                    self.posture_ready.emit(posture_result)

                if self.is_preview_enabled():
                    self.frame_ready.emit(frame)

                # ~15fps is plenty for blink detection and keeps CPU usage low.
                time.sleep(0.066)
        finally:
            cap.release()
            self.engine.close()
            self.posture_engine.close()
