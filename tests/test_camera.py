from __future__ import annotations

import math
from dataclasses import dataclass

from engine import camera
from engine.camera import build_camera_path
from engine.video_scan import Track, TrackPoint, VideoScan


@dataclass(frozen=True)
class InputInfo:
    width: int = 1280
    height: int = 720
    fps: float = 10.0


@dataclass(frozen=True)
class Target:
    width: int
    height: int

    @property
    def aspect(self) -> float:
        return self.width / self.height


def _track(person: int, positions: list[tuple[float, float]]) -> Track:
    return Track(
        id=person,
        person=person,
        points=tuple(
            TrackPoint(t, x, 180.0, 80.0, 100.0, 0.99)
            for t, x in positions
        ),
    )


def _scan(tracks: list[Track], scenes: list[tuple[float, float]]) -> VideoScan:
    return VideoScan(
        scenes=scenes,
        tracks=tracks,
        faces={"sample_fps": 5.0},
        audio_rms=[],
    )


def test_static_window_when_subject_motion_fits() -> None:
    track = _track(1, [(index / 5, 420.0 + index * 2) for index in range(10)])

    path = build_camera_path(
        InputInfo(), _scan([track], [(0.0, 2.0)]), Target(1080, 1920), (0.0, 2.0)
    )

    assert path.layout == "crop"
    assert len(path.windows) == 20
    assert len({(box.x, box.y) for box in path.windows}) == 1
    assert path.subjects_inside == 1.0


def test_moving_window_speed_cap_yields_to_containment() -> None:
    track = _track(1, [(index / 5, 20.0 + index * 120) for index in range(10)])

    path = build_camera_path(
        InputInfo(), _scan([track], [(0.0, 2.0)]), Target(1080, 1920), (0.0, 2.0)
    )

    speed_cap = path.windows[0].w * 0.2 / InputInfo.fps
    assert path.windows[-1].x > path.windows[0].x
    for index, (left, right) in enumerate(
        zip(path.windows, path.windows[1:], strict=False), start=1
    ):
        delta = right.x - left.x
        assert delta >= 0
        if delta <= speed_cap + 1e-6:
            continue
        t = min(index / InputInfo.fps, track.end)
        face_x = 20.0 + 600.0 * t
        required_x = face_x + 80.0 * 1.15 - right.w
        assert math.isclose(right.x, required_x, abs_tol=1e-6)


def test_moving_window_hard_contains_face_margin_without_reversals() -> None:
    positions = [(index / 5, index * 130.0) for index in range(10)]
    track = _track(1, positions)

    path = build_camera_path(
        InputInfo(), _scan([track], [(0.0, 2.0)]), Target(1080, 1920), (0.0, 2.0)
    )

    assert path.windows[0].x == 0.0
    for point in track.points:
        window = path.windows[math.floor(point.t * InputInfo.fps + 1e-9)]
        margin = point.w * 0.15
        assert window.x <= max(0.0, point.x - margin)
        assert window.x + window.w >= min(
            InputInfo.width, point.x + point.w + margin
        )

    deltas = [right.x - left.x for left, right in zip(path.windows, path.windows[1:], strict=False)]
    directions = [1 if delta > 1e-6 else -1 if delta < -1e-6 else 0 for delta in deltas]
    for index, direction in enumerate(directions):
        if not direction:
            continue
        assert -direction not in directions[index + 1 : index + 6]


def test_subjects_inside_counts_recorded_face_samples(monkeypatch: object) -> None:
    from engine.framing import Box
    track = _track(1, [(0.0, 20.0), (1.0, 1000.0)])

    def fixed_windows(*args: object) -> list[object]:
        times = args[1]
        return [Box(0.0, 0.0, 405.0, 720.0)] * len(times)

    monkeypatch.setattr(camera, "_track_windows", fixed_windows)
    path = build_camera_path(
        InputInfo(), _scan([track], [(0.0, 2.0)]), Target(1080, 1920), (0.0, 2.0)
    )

    assert path.subjects_inside == 0.5


def test_camera_hard_resets_at_scene_cut() -> None:
    left = _track(1, [(index / 5, 30.0) for index in range(5)])
    right = _track(2, [(1.0 + index / 5, 1120.0) for index in range(5)])

    path = build_camera_path(
        InputInfo(),
        _scan([left, right], [(0.0, 1.0), (1.0, 2.0)]),
        Target(1080, 1920),
        (0.0, 2.0),
    )

    assert path.windows[10].x - path.windows[9].x > path.windows[0].w * 0.2


def test_split_places_left_person_in_top_panel() -> None:
    left = _track(1, [(index / 5, 40.0) for index in range(10)])
    right = _track(2, [(index / 5, 1120.0) for index in range(10)])

    path = build_camera_path(
        InputInfo(),
        _scan([left, right], [(0.0, 2.0)]),
        Target(1080, 1920),
        (0.0, 2.0),
    )

    assert path.layout == "split"
    top, bottom = path.windows[0]
    assert top.cx < bottom.cx
    assert path.subjects_inside == 1.0


def test_split_panels_isolate_one_subject_at_supported_aspects() -> None:
    left = _track(1, [(index / 5, 40.0) for index in range(10)])
    right = _track(2, [(index / 5, 1120.0) for index in range(10)])

    for target in (Target(1080, 1350), Target(1080, 1920)):
        path = build_camera_path(
            InputInfo(), _scan([left, right], [(0.0, 2.0)]), target, (0.0, 2.0)
        )
        top, bottom = path.windows[0]

        assert 2.4 <= top.h / left.points[0].h <= 4.0
        assert 2.4 <= bottom.h / right.points[0].h <= 4.0
        assert top.x <= left.points[0].x
        assert top.x + top.w >= left.points[0].x + left.points[0].w
        assert bottom.x <= right.points[0].x
        assert bottom.x + bottom.w >= right.points[0].x + right.points[0].w
        assert top.x + top.w <= right.points[0].x
        assert bottom.x >= left.points[0].x + left.points[0].w
        left_eye = left.points[0].y + left.points[0].h * 0.4
        right_eye = right.points[0].y + right.points[0].h * 0.4
        assert math.isclose((left_eye - top.y) / top.h, 1 / 3, abs_tol=0.05)
        assert math.isclose((right_eye - bottom.y) / bottom.h, 1 / 3, abs_tol=0.05)


def test_person_focus_disables_auto_split() -> None:
    left = _track(1, [(index / 5, 40.0) for index in range(10)])
    right = _track(2, [(index / 5, 1120.0) for index in range(10)])

    path = build_camera_path(
        InputInfo(),
        _scan([left, right], [(0.0, 2.0)]),
        Target(1080, 1920),
        (0.0, 2.0),
        focus="person:2",
    )

    assert path.layout == "crop"
    assert path.windows[0].cx > InputInfo.width / 2
