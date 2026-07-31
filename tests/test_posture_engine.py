"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii
"""
from sitblinksip_desktop.posture_engine import _angle, _distance


def test_distance():
    assert _distance((0, 0), (3, 4)) == 5.0


def test_angle_straight_line_is_180_degrees():
    # ear - nose - ear all in a straight horizontal line: no head tilt.
    left_ear = (0.0, 0.0)
    nose = (0.5, 0.0)
    right_ear = (1.0, 0.0)
    assert _angle(left_ear, nose, right_ear) == 180.0


def test_angle_shrinks_as_head_tilts():
    left_ear = (0.0, 0.0)
    right_ear = (1.0, 0.0)

    straight_nose = (0.5, 0.0)
    tilted_nose = (0.5, 0.4)

    straight_angle = _angle(left_ear, straight_nose, right_ear)
    tilted_angle = _angle(left_ear, tilted_nose, right_ear)

    assert tilted_angle < straight_angle
