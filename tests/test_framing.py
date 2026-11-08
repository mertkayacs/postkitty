from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from engine.framing import Box, choose_layout, fit_crop, subject_box


@given(
    width=st.integers(16, 4000),
    height=st.integers(16, 4000),
    aspect=st.floats(0.25, 4.0, allow_nan=False, allow_infinity=False),
)
def test_crop_has_target_aspect_and_stays_inside(
    width: int, height: int, aspect: float
) -> None:
    crop = fit_crop(width, height, aspect, []).box

    assert abs(crop.w / crop.h - aspect) / aspect <= 0.005
    assert Box(0, 0, width, height).contains(crop, 1e-6)


@given(
    width=st.integers(100, 2000),
    height=st.integers(100, 2000),
    left=st.floats(0.0, 0.4, allow_nan=False),
    top=st.floats(0.0, 0.4, allow_nan=False),
    box_width=st.floats(0.05, 0.25, allow_nan=False),
    box_height=st.floats(0.05, 0.25, allow_nan=False),
)
def test_fitting_crop_contains_every_keep_box(
    width: int,
    height: int,
    left: float,
    top: float,
    box_width: float,
    box_height: float,
) -> None:
    boxes = [
        Box(left * width, top * height, box_width * width, box_height * height),
        Box(
            (0.75 - left / 2) * width,
            (0.75 - top / 2) * height,
            box_width * width,
            box_height * height,
        ),
    ]
    result = fit_crop(width, height, 1.0, boxes)

    if result.fits_all:
        assert all(result.box.contains(box, 1e-6) for box in boxes)


def test_one_face_eye_line_is_near_upper_third() -> None:
    face = Box(400, 500, 100, 150)
    crop = fit_crop(1000, 1600, 0.8, [face]).box
    eye_y = face.y + face.h * 0.4

    assert abs((eye_y - crop.y) / crop.h - 1 / 3) < 0.02


def test_anchor_moves_crop_window() -> None:
    left = fit_crop(1600, 900, 1.0, [], anchor=(0.0, 0.5)).box
    right = fit_crop(1600, 900, 1.0, [], anchor=(1.0, 0.5)).box

    assert left.x == 0
    assert right.x2 == 1600
    assert right.x > left.x


def test_box_helpers_and_subject_box() -> None:
    face = Box(10, 20, 30, 40)
    subject = subject_box(face, 100, 100)

    assert subject == Box(0, 0, 58.0, 100.0)
    assert Box(0, 0, 10, 10).intersect(Box(5, 5, 10, 10)) == Box(5, 5, 5, 5)
    assert Box(0, 0, 10, 10).union(Box(5, 5, 10, 10)) == Box(0, 0, 15, 15)
    assert Box(10, 20, 30, 40).expand(2, 3) == Box(-5, -20, 60, 120)
    assert Box(1.2, 2.8, 3.1, 4.1).to_int() == Box(1, 2, 4, 5)


def test_crop_centers_subject_that_is_too_large_to_fit() -> None:
    subject = Box(100, 100, 800, 800)

    crop = fit_crop(1000, 1000, 0.5, [subject], headroom=False).box

    assert not crop.contains(subject)
    assert crop.cx == subject.cx


def test_layout_selection() -> None:
    separated = [Box(0, 200, 250, 400), Box(1750, 200, 250, 400)]

    assert choose_layout(2000, 1000, 9 / 16, separated, True).mode == "split"
    assert choose_layout(2000, 1000, 1.6, separated, True).mode == "seam"
    assert choose_layout(2000, 1000, 1.0, separated, False).mode == "pad"
    assert choose_layout(2000, 1000, 2.0, separated, False).mode == "crop"
