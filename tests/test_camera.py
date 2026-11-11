from __future__ import annotations

import math
from dataclasses import dataclass

from engine.video import camera
from engine.video.camera import build_camera_path
from engine.video.scan import Track, TrackPoint, VideoScan


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
    from engine.photo.framing import Box
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


def test_speaker_layout_cuts_from_first_person_to_second(speaker_media) -> None:
    info, scan = speaker_media.info, speaker_media.scan
    target = Target(1080, 1920)
    path = build_camera_path(
        info, scan, target, (0.0, 9.0), layout_override="speaker"
    )

    assert path.layout == "speaker"
    assert path.windows[round(1.0 * info.fps)].cx < info.width / 2
    assert path.windows[round(4.5 * info.fps)].cx > info.width / 2
    assert "cuts to whoever is talking" in path.note


def test_speaker_layout_with_one_person_matches_crop() -> None:
    left = _track(1, [(index / 5, 40.0) for index in range(10)])
    scan = _scan([left], [(0.0, 2.0)])
    target = Target(1080, 1920)
    crop = build_camera_path(
        InputInfo(), scan, target, (0.0, 2.0), layout_override="crop"
    )
    speaker = build_camera_path(
        InputInfo(), scan, target, (0.0, 2.0), layout_override="speaker"
    )

    assert speaker.windows == crop.windows
    assert speaker.subjects_inside == crop.subjects_inside


@dataclass(frozen=True)
class VideoInfo24:
    width: int = 1280
    height: int = 720
    fps: float = 24.0
    path: str = "unused.mp4"
    sha256: str = "0" * 64


def test_speaker_cut_between_frames_keeps_every_subject_inside(monkeypatch) -> None:
    import numpy as np

    from engine.video import speakers

    left = _track(1, [(index / 5, 40.0) for index in range(10)])
    right = _track(2, [(index / 5, 1120.0) for index in range(10)])
    scan = _scan([left, right], [(0.0, 2.0)])
    monkeypatch.setattr(
        speakers,
        "cached_activity",
        lambda *args, **kwargs: (np.zeros(1), np.zeros((1, 2)), np.ones(1, dtype=bool)),
    )
    # 1.19 s falls after the frame at 28/24 s and before the face sample at 1.2 s.
    monkeypatch.setattr(
        speakers,
        "speaker_segments",
        lambda *args, **kwargs: [(0.0, 1.19, 0), (1.19, 2.0, 1)],
    )
    path = build_camera_path(
        VideoInfo24(), scan, Target(1080, 1920), (0.0, 2.0), layout_override="speaker"
    )

    assert path.layout == "speaker"
    assert path.subjects_inside == 1.0
    assert path.windows[0].cx != path.windows[-1].cx


def test_speaker_option_does_not_change_auto_or_split() -> None:
    left = _track(1, [(index / 5, 40.0) for index in range(10)])
    right = _track(2, [(index / 5, 1120.0) for index in range(10)])
    scan = _scan([left, right], [(0.0, 2.0)])
    target = Target(1080, 1920)
    automatic = build_camera_path(InputInfo(), scan, target, (0.0, 2.0))
    split = build_camera_path(
        InputInfo(), scan, target, (0.0, 2.0), layout_override="split"
    )

    assert automatic.layout == "split"
    assert automatic.windows == split.windows
    assert automatic.subjects_inside == split.subjects_inside


def _sized_track(person: int, x: float, face_height: float, start: float) -> Track:
    return Track(
        id=person,
        person=person,
        points=tuple(
            TrackPoint(start + index / 5, x, 100.0, face_height * 0.75, face_height, 0.99)
            for index in range(10)
        ),
    )


def test_split_panels_stay_inside_the_frame_for_large_faces() -> None:
    left = _sized_track(1, 40.0, 400.0, 0.0)
    right = _sized_track(2, 900.0, 400.0, 0.0)

    path = build_camera_path(
        InputInfo(), _scan([left, right], [(0.0, 2.0)]), Target(1080, 1920), (0.0, 2.0)
    )

    assert path.layout == "split"
    panel_aspect = 1080 / 1920 * 2
    for top, bottom in path.windows:
        for box in (top, bottom):
            assert box.h <= InputInfo.height + 1e-6
            assert box.w <= InputInfo.width + 1e-6
            assert math.isclose(box.w / box.h, panel_aspect, rel_tol=1e-6)


def test_focus_on_a_missing_person_is_an_error_that_counts_people() -> None:
    import pytest

    left = _track(1, [(index / 5, 40.0) for index in range(10)])
    right = _track(2, [(index / 5, 1120.0) for index in range(10)])
    scan = _scan([left, right], [(0.0, 2.0)])

    with pytest.raises(ValueError, match="not present.*2 people"):
        build_camera_path(InputInfo(), scan, Target(1080, 1920), (0.0, 2.0), focus="person:99")
    with pytest.raises(ValueError, match="not present"):
        build_camera_path(InputInfo(), scan, Target(1080, 1920), (0.0, 2.0), focus="person:0")
    with pytest.raises(ValueError, match="not present.*0 people"):
        build_camera_path(InputInfo(), _scan([], [(0.0, 2.0)]), Target(1080, 1920), (0.0, 2.0), focus="person:1")


def test_unusable_layout_request_falls_back_to_crop_with_a_note() -> None:
    nobody = _scan([], [(0.0, 2.0)])
    one = _scan([_track(1, [(index / 5, 40.0) for index in range(10)])], [(0.0, 2.0)])

    for scan, layout in ((nobody, "split"), (nobody, "speaker"), (one, "split")):
        path = build_camera_path(InputInfo(), scan, Target(1080, 1920), (0.0, 2.0), layout_override=layout)
        assert path.layout == "crop"
        assert layout in path.note and "crop" in path.note


def test_split_survives_a_scene_without_faces() -> None:
    left = _track(1, [(index / 5, 40.0) for index in range(10)])
    right = _track(2, [(index / 5, 1120.0) for index in range(10)])

    path = build_camera_path(
        InputInfo(),
        _scan([left, right], [(0.0, 2.0), (2.0, 4.0)]),
        Target(1080, 1920),
        (0.0, 4.0),
    )

    assert path.layout == "split"
    assert len(path.windows) == 40
    for top, bottom in path.windows:
        for box in (top, bottom):
            assert 0.0 <= box.x and box.x + box.w <= InputInfo.width + 1e-6
            assert 0.0 <= box.y and box.y + box.h <= InputInfo.height + 1e-6


def test_split_panels_keep_one_size_across_scenes() -> None:
    wide = [_sized_track(1, 40.0, 100.0, 0.0), _sized_track(2, 1120.0, 100.0, 0.0)]
    tight = [_sized_track(3, 40.0, 160.0, 2.0), _sized_track(4, 1000.0, 160.0, 2.0)]

    path = build_camera_path(
        InputInfo(),
        _scan(wide + tight, [(0.0, 2.0), (2.0, 4.0)]),
        Target(1080, 1920),
        (0.0, 4.0),
    )

    assert path.layout == "split"
    # The render crops both panels at one fixed size (sendcmd only moves x and y), so every
    # scene must use the same panel size.
    assert len({(round(top.w, 3), round(top.h, 3)) for top, _ in path.windows}) == 1
    assert len({(round(bottom.w, 3), round(bottom.h, 3)) for _, bottom in path.windows}) == 1
    assert path.subjects_inside == 1.0


def test_focus_position_is_kept_and_the_person_left_outside_is_reported() -> None:
    # focus: right on a clip whose one person stands at the left edge used to be replaced by a pad render.
    scan = _scan([_track(1, [(index / 5, 40.0) for index in range(10)])], [(0.0, 2.0)])

    path = build_camera_path(InputInfo(), scan, Target(1080, 1920), (0.0, 2.0), focus="right")

    assert path.layout == "crop"
    assert {round(box.x) for box in path.windows} == {875}
    assert path.subjects_inside == 0.0
    assert path.advisory == "1 person is outside the frame for most of the clip because the focus is set to right."


def test_focus_position_counts_every_person_and_other_focus_values_report_nothing() -> None:
    near = _track(1, [(index / 5, 100.0) for index in range(10)])
    far = _track(2, [(index / 5, 1100.0) for index in range(10)])
    scan = _scan([near, far], [(0.0, 2.0)])
    args = (InputInfo(), scan, Target(1080, 1920), (0.0, 2.0))

    kept = build_camera_path(*args, focus="x:0.1", layout_override="crop")
    fits = build_camera_path(*args, focus="left", layout_override="pad")

    assert kept.subjects_inside == 0.5
    assert kept.advisory == "1 person is outside the frame for most of the clip because the focus is set to x:0.1."
    assert (fits.subjects_inside, fits.advisory) == (1.0, "")
    assert build_camera_path(*args, layout_override="crop").advisory == ""
    assert build_camera_path(*args, focus="person:2", layout_override="crop").advisory == ""


def test_focus_position_reports_nobody_in_a_split_which_frames_people_its_own_way() -> None:
    people = [_track(person, [(index / 5, x) for index in range(10)]) for person, x in ((1, 100.0), (2, 1100.0))]
    passer_by = Track(3, 3, tuple(TrackPoint(index / 5, 600.0, 600.0, 40.0, 50.0, 0.99) for index in range(10)))
    scan = _scan([*people, passer_by], [(0.0, 2.0)])

    path = build_camera_path(InputInfo(), scan, Target(1080, 1920), (0.0, 2.0), focus="left")

    assert path.layout == "split"
    assert (path.subjects_inside, path.advisory) == (1.0, "")

