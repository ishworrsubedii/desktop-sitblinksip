"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii
"""
from sitblinksip_desktop.blink_engine import _euclidean, _eye_aspect_ratio


def test_euclidean_distance():
    assert _euclidean((0, 0), (3, 4)) == 5.0


def test_ear_wide_open_eye_is_larger_than_closed_eye():
    # A roughly circular eye outline (open) vs. a flattened one (closed),
    # using the same 6-point layout the engine expects:
    # [outer_corner, upper_1, upper_2, inner_corner, lower_2, lower_1]
    open_eye = [(0, 5), (3, 0), (7, 0), (10, 5), (7, 10), (3, 10)]
    closed_eye = [(0, 5), (3, 4), (7, 4), (10, 5), (7, 6), (3, 6)]

    open_ear = _eye_aspect_ratio(open_eye)
    closed_ear = _eye_aspect_ratio(closed_eye)

    assert open_ear > closed_ear
    assert closed_ear < 0.21 <= open_ear
