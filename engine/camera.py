from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, Literal

from .video_scan import Track, TrackPoint, VideoScan


@dataclass(frozen=True)
class CameraPath:
    layout: Literal["crop", "split", "pad"]
    windows: list[Any]
    note: str
    subjects_inside: float


def _geometry() -> tuple[Any, Any, Any]:
    from .framing import Box, fit_crop, subject_box

    return Box, fit_crop, subject_box


def _points_in_scene(track: Track, start: float, end: float) -> list[TrackPoint]:
    return [point for point in track.points if start <= point.t < end]


def _track_score(track: Track, start: float, end: float, sample_fps: float) -> float:
    points = _points_in_scene(track, start, end)
    if not points:
        return 0.0
    expected = max(1, round((end - start) * sample_fps))
    presence = min(1.0, len(points) / expected)
    mean_area = sum(point.w * point.h for point in points) / len(points)
    return presence * mean_area


def _present_tracks(
    scan: VideoScan, start: float, end: float, minimum: float = 0.0
) -> list[Track]:
    sample_fps = float(scan.faces["sample_fps"])
    expected = max(1, round((end - start) * sample_fps))
    tracks = [
        track
        for track in scan.tracks
        if len(_points_in_scene(track, start, end)) / expected >= minimum
    ]
    return sorted(
        tracks,
        key=lambda track: _track_score(track, start, end, sample_fps),
        reverse=True,
    )


def _face_box(point: TrackPoint) -> Any:
    Box, _, _ = _geometry()
    return Box(point.x, point.y, point.w, point.h)


def _subject(point: TrackPoint, width: int, height: int) -> Any:
    _, _, subject_box = _geometry()
    return subject_box(_face_box(point), width, height)


def _representative(track: Track, start: float, end: float) -> TrackPoint:
    points = _points_in_scene(track, start, end)
    count = len(points)
    return TrackPoint(
        t=(start + end) / 2,
        x=sum(point.x for point in points) / count,
        y=sum(point.y for point in points) / count,
        w=sum(point.w for point in points) / count,
        h=sum(point.h for point in points) / count,
        score=sum(point.score for point in points) / count,
    )


def _focus(value: str | None) -> tuple[int | None, float | None]:
    if not value or value == "auto":
        return None, None
    if value.startswith("person:"):
        try:
            person = int(value.removeprefix("person:"))
        except ValueError as error:
            raise ValueError("focus person must be a positive integer") from error
        if person <= 0:
            raise ValueError("focus person must be a positive integer")
        return person, None
    anchors = {"left": 0.0, "center": 0.5, "right": 1.0}
    if value in anchors:
        return None, anchors[value]
    if value.startswith("x:"):
        try:
            anchor = float(value.removeprefix("x:"))
        except ValueError as error:
            raise ValueError("focus x must be between 0 and 1") from error
        if not 0.0 <= anchor <= 1.0:
            raise ValueError("focus x must be between 0 and 1")
        return None, anchor
    raise ValueError(f"unsupported focus: {value}")


def _select_track(
    tracks: list[Track], person: int | None, start: float, end: float
) -> Track | None:
    if person is None:
        return tracks[0] if tracks else None
    return next(
        (
            track
            for track in tracks
            if track.person == person and _points_in_scene(track, start, end)
        ),
        None,
    )


def _interpolate(track: Track, t: float) -> TrackPoint:
    points = track.points
    if t <= points[0].t:
        return points[0]
    if t >= points[-1].t:
        return points[-1]
    for left, right in pairwise(points):
        if left.t <= t <= right.t:
            span = right.t - left.t
            weight = 0.0 if span == 0 else (t - left.t) / span
            return TrackPoint(
                t=t,
                x=left.x + (right.x - left.x) * weight,
                y=left.y + (right.y - left.y) * weight,
                w=left.w + (right.w - left.w) * weight,
                h=left.h + (right.h - left.h) * weight,
                score=left.score + (right.score - left.score) * weight,
            )
    return points[-1]


def _window_size(width: int, height: int, aspect: float) -> tuple[float, float]:
    if width / height >= aspect:
        return height * aspect, float(height)
    return float(width), width / aspect


def _clamped_box(x: float, y: float, w: float, h: float, width: int, height: int) -> Any:
    Box, _, _ = _geometry()
    return Box(
        min(max(0.0, x), width - w),
        min(max(0.0, y), height - h),
        w,
        h,
    )


def _desired_window(
    point: TrackPoint, width: int, height: int, aspect: float
) -> Any:
    window_width, window_height = _window_size(width, height, aspect)
    eye_y = point.y + point.h * 0.4
    return _clamped_box(
        point.cx - window_width / 2,
        eye_y - window_height / 3,
        window_width,
        window_height,
        width,
        height,
    )


def _contain_face(box: Any, point: TrackPoint, width: int, height: int) -> Any:
    margin = point.w * 0.15
    left = max(0.0, point.x - margin)
    top = max(0.0, point.y - margin)
    right = min(float(width), point.x + point.w + margin)
    bottom = min(float(height), point.y + point.h + margin)
    x = min(box.x, left) if left < box.x else max(box.x, right - box.w)
    y = min(box.y, top) if top < box.y else max(box.y, bottom - box.h)
    return _clamped_box(x, y, box.w, box.h, width, height)


def _static_window(
    track: Track,
    start: float,
    end: float,
    width: int,
    height: int,
    aspect: float,
    anchor_x: float | None,
) -> Any | None:
    _, fit_crop, _ = _geometry()
    subjects = [
        _subject(point, width, height) for point in _points_in_scene(track, start, end)
    ]
    fit = fit_crop(
        width,
        height,
        aspect,
        subjects,
        anchor=(anchor_x, 0.5) if anchor_x is not None else None,
    )
    if fit.fits_all or anchor_x is not None:
        return fit.box
    return None


def _moving_windows(
    track: Track,
    times: list[float],
    width: int,
    height: int,
    aspect: float,
    fps: float,
) -> list[Any]:
    desired = [
        _desired_window(_interpolate(track, t), width, height, aspect) for t in times
    ]
    dead_zone: list[Any] = [desired[0]]
    for point, target in zip(
        (_interpolate(track, t) for t in times[1:]), desired[1:], strict=True
    ):
        previous = dead_zone[-1]
        threshold = previous.w * 0.12
        if previous.cx - threshold <= point.cx <= previous.cx + threshold:
            x = previous.x
        elif point.cx < previous.cx:
            x = point.cx + threshold - previous.w / 2
        else:
            x = point.cx - threshold - previous.w / 2
        dead_zone.append(
            _clamped_box(x, target.y, target.w, target.h, width, height)
        )

    radius = max(0, round(0.4 * fps))
    smoothed = []
    for index, box in enumerate(dead_zone):
        neighbors = dead_zone[max(0, index - radius) : index + radius + 1]
        smoothed.append(
            _clamped_box(
                sum(item.x for item in neighbors) / len(neighbors),
                sum(item.y for item in neighbors) / len(neighbors),
                box.w,
                box.h,
                width,
                height,
            )
        )

    points = [_interpolate(track, t) for t in times]
    sample_constraints: dict[int, list[TrackPoint]] = {}
    for point in track.points:
        index = math.floor((point.t - times[0]) * fps + 1e-9)
        if 0 <= index < len(times):
            sample_constraints.setdefault(index, []).append(point)

    first = _contain_face(desired[0], points[0], width, height)
    for point in sample_constraints.get(0, []):
        first = _contain_face(first, point, width, height)
    capped = [first]
    speed = smoothed[0].w * 0.2 / fps
    for index, (target, point) in enumerate(
        zip(smoothed[1:], points[1:], strict=True), start=1
    ):
        previous = capped[-1]
        dx = target.x - previous.x
        dy = target.y - previous.y
        distance = math.hypot(dx, dy)
        scale = min(1.0, speed / distance) if distance else 1.0
        candidate = _clamped_box(
            previous.x + dx * scale,
            previous.y + dy * scale,
            target.w,
            target.h,
            width,
            height,
        )
        candidate = _contain_face(candidate, point, width, height)
        for sample in sample_constraints.get(index, []):
            candidate = _contain_face(candidate, sample, width, height)
        capped.append(candidate)
    return capped


def _track_windows(
    track: Track | None,
    times: list[float],
    scene: tuple[float, float],
    width: int,
    height: int,
    aspect: float,
    fps: float,
    anchor_x: float | None,
) -> list[Any]:
    Box, _, _ = _geometry()
    if track is None:
        window_width, window_height = _window_size(width, height, aspect)
        x = (width - window_width) * (0.5 if anchor_x is None else anchor_x)
        box = Box(x, (height - window_height) / 2, window_width, window_height)
        return [box] * len(times)
    static = _static_window(
        track, scene[0], scene[1], width, height, aspect, anchor_x
    )
    if static is not None:
        return [static] * len(times)
    return _moving_windows(track, times, width, height, aspect, fps)


def _can_split(
    scan: VideoScan,
    scene: tuple[float, float],
    width: int,
    height: int,
    aspect: float,
) -> tuple[Track, Track] | None:
    if aspect >= 1.0:
        return None
    tracks = _present_tracks(scan, *scene, minimum=0.5)
    if len(tracks) < 2:
        return None
    left, right = sorted(
        tracks[:2], key=lambda track: _representative(track, *scene).cx
    )
    _, fit_crop, _ = _geometry()
    subjects = [
        _subject(_representative(track, *scene), width, height)
        for track in (left, right)
    ]
    if fit_crop(width, height, aspect, subjects).fits_all:
        return None
    return left, right


def _inside(box: Any, subject: Any) -> bool:
    return (
        subject.x >= box.x
        and subject.y >= box.y
        and subject.x + subject.w <= box.x + box.w
        and subject.y + subject.h <= box.y + box.h
    )


def _rendered_window(box: Any, width: int, height: int) -> Any:
    Box, _, _ = _geometry()
    crop_width = min(max(2, round(box.w / 2) * 2), width - width % 2)
    crop_height = min(max(2, round(box.h / 2) * 2), height - height % 2)
    x = min(max(0, round(box.x)), width - crop_width)
    y = min(max(0, round(box.y)), height - crop_height)
    return Box(float(x), float(y), float(crop_width), float(crop_height))


def build_camera_path(
    info: Any,
    scan: VideoScan,
    target: Any,
    trim: tuple[float, float],
    focus: str = "auto",
    layout_override: str = "auto",
) -> CameraPath:
    if info.fps is None or info.fps <= 0:
        raise ValueError("video fps must be positive")
    if trim[0] < 0 or trim[1] <= trim[0]:
        raise ValueError("trim must be an increasing non-negative range")
    if layout_override not in {"auto", "crop", "split", "pad"}:
        raise ValueError(f"unsupported video layout: {layout_override}")

    person, anchor_x = _focus(focus)
    fps = min(float(info.fps), 60.0)
    frame_count = max(1, round((trim[1] - trim[0]) * fps))
    times = [trim[0] + index / fps for index in range(frame_count)]
    scenes = [
        (max(start, trim[0]), min(end, trim[1]))
        for start, end in scan.scenes
        if min(end, trim[1]) > max(start, trim[0])
    ]
    split_scenes = {
        scene: _can_split(scan, scene, info.width, info.height, target.aspect)
        for scene in scenes
    }
    split_available = any(value is not None for value in split_scenes.values())
    if layout_override == "pad":
        layout: Literal["crop", "split", "pad"] = "pad"
    elif split_available and (
        layout_override == "split"
        or layout_override == "auto" and person is None
    ):
        layout = "split"
    else:
        layout = "crop"

    Box, _, _ = _geometry()
    windows: list[Any] = [Box(0.0, 0.0, info.width, info.height)] * frame_count
    inside_count = 0
    subject_count = 0
    for scene in scenes:
        indices = [index for index, t in enumerate(times) if scene[0] <= t < scene[1]]
        if not indices:
            continue
        scene_times = [times[index] for index in indices]
        tracks = _present_tracks(scan, *scene)
        if layout == "pad":
            scene_windows = [Box(0.0, 0.0, info.width, info.height)] * len(indices)
            selected = [_select_track(tracks, person, *scene)]
        elif layout == "split":
            pair = split_scenes[scene]
            if pair is None:
                selected_track = _select_track(tracks, person, *scene)
                pair = (selected_track, selected_track)
            panel_aspect = target.aspect * 2
            first = _track_windows(
                pair[0],
                scene_times,
                scene,
                info.width,
                info.height,
                panel_aspect,
                fps,
                anchor_x,
            )
            second = _track_windows(
                pair[1],
                scene_times,
                scene,
                info.width,
                info.height,
                panel_aspect,
                fps,
                anchor_x,
            )
            scene_windows = list(zip(first, second, strict=True))
            selected = [pair[0], pair[1]]
        else:
            selected_track = _select_track(tracks, person, *scene)
            scene_windows = _track_windows(
                selected_track,
                scene_times,
                scene,
                info.width,
                info.height,
                target.aspect,
                fps,
                anchor_x,
            )
            selected = [selected_track]

        for index, window in zip(indices, scene_windows, strict=True):
            windows[index] = window

        for selected_index, track in enumerate(selected):
            if track is None:
                continue
            for point in _points_in_scene(track, *scene):
                index = math.floor((point.t - trim[0]) * fps + 1e-9)
                if not 0 <= index < len(windows):
                    continue
                window = windows[index]
                candidate = window[selected_index] if layout == "split" else window
                rendered = _rendered_window(candidate, info.width, info.height)
                subject_count += 1
                inside_count += int(_inside(rendered, _face_box(point)))

    if layout == "split":
        note = "two subjects cannot share one vertical window"
    elif layout == "pad":
        note = "full source retained over a blurred fill"
    else:
        note = "single-subject camera path"
    return CameraPath(
        layout=layout,
        windows=windows,
        note=note,
        subjects_inside=inside_count / subject_count if subject_count else 1.0,
    )
