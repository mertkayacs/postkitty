from __future__ import annotations

import math
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Any, Literal

from .scan import Track, TrackPoint, VideoScan


@dataclass(frozen=True)
class CameraPath:
    layout: Literal["crop", "split", "speaker", "pad"]
    windows: list[Any]
    note: str
    subjects_inside: float
    advisory: str = ""


def _geometry() -> tuple[Any, Any, Any]:
    from ..photo.framing import Box, fit_crop, subject_box

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


def _faces_overlap(box: Any, point: TrackPoint) -> bool:
    return (
        box.x < point.x + point.w
        and box.x + box.w > point.x
        and box.y < point.y + point.h
        and box.y + box.h > point.y
    )


def _panel_box(
    point: TrackPoint,
    other: TrackPoint,
    window_width: float,
    window_height: float,
    width: int,
    height: int,
) -> Any:
    eye_y = point.y + point.h * 0.4
    box = _clamped_box(
        point.cx - window_width / 2,
        eye_y - window_height / 3,
        window_width,
        window_height,
        width,
        height,
    )
    box = _contain_face(box, point, width, height)
    if _faces_overlap(box, other):
        x = other.x - box.w if other.cx > point.cx else other.x + other.w
        box = _contain_face(
            _clamped_box(x, box.y, box.w, box.h, width, height),
            point,
            width,
            height,
        )
    return box


def _panel_windows(
    track: Track,
    other: Track,
    times: list[float],
    scene: tuple[float, float],
    width: int,
    height: int,
    aspect: float,
    panel_height: float | None = None,
) -> list[Any]:
    points = _points_in_scene(track, *scene)
    other_points = _points_in_scene(other, *scene)
    # A panel can never be taller or wider than the source, or the rendered crop loses its aspect.
    frame_height = min(float(height), width / aspect)
    minimum_height = min(2.4 * max(point.h for point in points), frame_height)
    maximum_height = min(4.0 * min(point.h for point in points), frame_height)
    maximum_height = max(maximum_height, minimum_height)
    if panel_height is None:
        heights = [
            maximum_height - (maximum_height - minimum_height) * step / 20
            for step in range(21)
        ]
    else:
        minimum_height = panel_height
        heights = [panel_height]

    representative = _representative(track, *scene)
    other_representative = _representative(other, *scene)
    for window_height in heights:
        window_width = window_height * aspect
        box = _panel_box(
            representative,
            other_representative,
            window_width,
            window_height,
            width,
            height,
        )
        if all(_inside(box, _face_box(point)) for point in points) and not any(
            _faces_overlap(box, point) for point in other_points
        ):
            return [box] * len(times)

    window_height = minimum_height
    window_width = window_height * aspect
    return [
        _panel_box(
            _interpolate(track, t),
            _interpolate(other, t),
            window_width,
            window_height,
            width,
            height,
        )
        for t in times
    ]


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


def _shared_window(
    scan: VideoScan, scene: tuple[float, float], width: int, height: int, aspect: float
) -> tuple[Any, tuple[Track, Track]] | None:
    """The one window that holds the two main people of a shot, when such a window exists."""
    pair = _present_tracks(scan, *scene, minimum=0.5)[:2]
    if len(pair) < 2:
        return None
    _, fit_crop, _ = _geometry()
    fit = fit_crop(
        width, height, aspect, [_subject(_representative(track, *scene), width, height) for track in pair]
    )
    return (fit.box, (pair[0], pair[1])) if fit.fits_all else None


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


def _left_outside(
    scan: VideoScan,
    windows: list[Any],
    scenes: list[tuple[float, float]],
    trim: tuple[float, float],
    fps: float,
    width: int,
    height: int,
    present: float = 0.0,
) -> tuple[int, int]:
    """People in the fullest shot, and how many a one-window layout leaves out for most of the clip.

    A cut ends a track, so a person cannot be followed across shots. Each shot counts the tracks
    that are out of its window for most of their samples, and a count stands when the shots with
    at least that many people left out cover most of the clip. ``present`` is the share of a shot
    a track must be seen in to count, so a passer-by does not decide the layout.
    """
    people = 0
    shots: list[tuple[float, int]] = []
    for scene in scenes:
        present = missed = 0
        for track in _present_tracks(scan, *scene, minimum=present):
            total = outside = 0
            for point in _points_in_scene(track, *scene):
                index = math.floor((point.t - trim[0]) * fps + 1e-9)
                if 0 <= index < len(windows):
                    total += 1
                    outside += int(not _inside(_rendered_window(windows[index], width, height), _face_box(point)))
            present += int(total > 0)
            missed += int(outside * 2 > total)
        people = max(people, present)
        shots.append((scene[1] - scene[0], missed))
    clip = sum(duration for duration, _ in shots)
    for count in range(max((missed for _, missed in shots), default=0), 0, -1):
        if sum(duration for duration, missed in shots if missed >= count) * 2 > clip:
            return people, count
    return people, 0


def _on_frame(value: float, scene: tuple[float, float], start: float, fps: float) -> float:
    # Cuts land on rendered frames, so a face sample at a cut is judged against its own shot.
    if value <= scene[0] or value >= scene[1]:
        return value
    return start + math.ceil((value - start) * fps - 1e-9) / fps


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
    if layout_override not in {"auto", "crop", "split", "speaker", "pad"}:
        raise ValueError(f"unsupported video layout: {layout_override}")

    person, anchor_x = _focus(focus)
    if person is not None and not 1 <= person <= len(scan.tracks):
        count = len(scan.tracks)
        raise ValueError(
            f"focus person is not present; the video has {count} {'person' if count == 1 else 'people'}"
        )
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
    if layout_override == "speaker":
        layout: Literal["crop", "split", "speaker", "pad"] = "speaker"
    elif layout_override == "pad":
        layout = "pad"
    elif split_available and (
        layout_override == "split"
        or layout_override == "auto" and person is None
    ):
        layout = "split"
    else:
        layout = "crop"
    # A requested layout the footage cannot support is reported as what was actually used.
    unmet = "no face was found" if not scan.tracks else "{} needs two people in one shot"
    fallback_note = ""
    if layout_override == "split" and layout != "split":
        fallback_note = f"{unmet.format('split')}; used crop instead of split"
    speaker_segments_found = False

    Box, _, _ = _geometry()
    # The render crops both panels at one fixed size (sendcmd only moves x and y), so every
    # split shot shares the tallest panel any shot needs.
    panel_aspect = target.aspect * 2
    split_pairs: dict[tuple[float, float], tuple[Track, Track] | None] = {}
    panel_height = 0.0
    if layout == "split":
        for scene in scenes:
            pair = split_scenes[scene]
            if pair is None:
                selected_track = _select_track(_present_tracks(scan, *scene), person, *scene)
                if selected_track is not None and _points_in_scene(selected_track, *scene):
                    pair = (selected_track, selected_track)
            split_pairs[scene] = pair
            for track, other in ((pair[0], pair[1]), (pair[1], pair[0])) if pair else ():
                box = _panel_windows(
                    track, other, [scene[0]], scene, info.width, info.height, panel_aspect
                )[0]
                panel_height = max(panel_height, box.h)
        if not panel_height:
            panel_height = _window_size(info.width, info.height, panel_aspect)[1]
    windows: list[Any] = [Box(0.0, 0.0, info.width, info.height)] * frame_count
    inside_count = 0
    subject_count = 0
    speaker_cuts = 0
    shared_crop = False
    for scene in scenes:
        indices = [index for index, t in enumerate(times) if scene[0] <= t < scene[1]]
        if not indices:
            continue
        scene_times = [times[index] for index in indices]
        tracks = _present_tracks(scan, *scene)
        accounting: list[tuple[Track | None, float, float, int | None]] = []
        if layout == "pad":
            scene_windows = [Box(0.0, 0.0, info.width, info.height)] * len(indices)
            accounting.append((_select_track(tracks, person, *scene), *scene, None))
        elif layout == "split":
            pair = split_pairs[scene]
            if pair is None:
                # Nobody is in this shot: both panels show the centre of the frame.
                panel_width = panel_height * panel_aspect
                panel = Box(
                    (info.width - panel_width) * (0.5 if anchor_x is None else anchor_x),
                    (info.height - panel_height) / 2,
                    panel_width,
                    panel_height,
                )
                for index in indices:
                    windows[index] = (panel, panel)
                continue
            first = _panel_windows(
                pair[0],
                pair[1],
                scene_times,
                scene,
                info.width,
                info.height,
                panel_aspect,
                panel_height,
            )
            second = _panel_windows(
                pair[1],
                pair[0],
                scene_times,
                scene,
                info.width,
                info.height,
                panel_aspect,
                panel_height,
            )
            scene_windows = list(zip(first, second, strict=True))
            accounting.extend(
                [(pair[0], *scene, 0), (pair[1], *scene, 1)]
            )
        elif layout == "speaker":
            from .speakers import cached_activity, speaker_segments

            speaker_tracks = _present_tracks(scan, *scene, minimum=0.3)[:4]
            segments: list[tuple[float, float, int]] = []
            if len(speaker_tracks) >= 2:
                activity_times, activity, speech = cached_activity(
                    info.path,
                    info.sha256,
                    speaker_tracks,
                    scene[0],
                    scene[1],
                    info.width,
                    info.height,
                    scan.work_dir,
                )
                segments = speaker_segments(activity_times, activity, speech)
            if not segments:
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
                accounting.append((selected_track, *scene, None))
            else:
                speaker_segments_found = True
                segments = [
                    (
                        _on_frame(start, scene, trim[0], fps),
                        _on_frame(stop, scene, trim[0], fps),
                        speaker,
                    )
                    for start, stop, speaker in segments
                ]
                segments[0] = (scene[0], segments[0][1], segments[0][2])
                segments[-1] = (segments[-1][0], scene[1], segments[-1][2])
                scene_windows = [None] * len(indices)
                for segment_start, segment_end, speaker_index in segments:
                    positions = [
                        index
                        for index, t in enumerate(scene_times)
                        if segment_start <= t < segment_end
                    ]
                    if not positions:
                        continue
                    segment_times = [scene_times[index] for index in positions]
                    selected_track = speaker_tracks[speaker_index]
                    segment_windows = _track_windows(
                        selected_track,
                        segment_times,
                        (segment_start, segment_end),
                        info.width,
                        info.height,
                        target.aspect,
                        fps,
                        anchor_x,
                    )
                    for index, window in zip(
                        positions, segment_windows, strict=True
                    ):
                        scene_windows[index] = window
                    accounting.append(
                        (selected_track, segment_start, segment_end, None)
                    )
                speaker_cuts += max(0, len(segments) - 1)
        else:
            # Without a chosen person or position, two people who fit one frame are framed together.
            shared = (
                _shared_window(scan, scene, info.width, info.height, target.aspect)
                if person is None and anchor_x is None
                else None
            )
            if shared is not None:
                scene_windows = [shared[0]] * len(indices)
                accounting.extend((track, *scene, None) for track in shared[1])
                shared_crop = True
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
                accounting.append((selected_track, *scene, None))

        for index, window in zip(indices, scene_windows, strict=True):
            windows[index] = window

        for track, selected_start, selected_end, panel_index in accounting:
            if track is None:
                continue
            for point in _points_in_scene(track, selected_start, selected_end):
                index = math.floor((point.t - trim[0]) * fps + 1e-9)
                if not 0 <= index < len(windows):
                    continue
                window = windows[index]
                candidate = window[panel_index] if panel_index is not None else window
                rendered = _rendered_window(candidate, info.width, info.height)
                subject_count += 1
                inside_count += int(_inside(rendered, _face_box(point)))

    if layout == "speaker" and not speaker_segments_found:
        layout = "crop"
        fallback_note = f"{unmet.format('speaker')}; used crop instead of speaker"
    if fallback_note:
        note = fallback_note
    elif layout == "split":
        note = "two subjects cannot share one vertical window"
    elif layout == "speaker":
        suffix = "cut" if speaker_cuts == 1 else "cuts"
        note = f"cuts to whoever is talking ({speaker_cuts} {suffix})"
    elif layout == "pad":
        note = "full source retained over a blurred fill"
    elif shared_crop:
        note = "both people share one frame"
    else:
        note = "single-subject camera path"
    subjects_inside = inside_count / subject_count if subject_count else 1.0
    if layout == "crop" and layout_override == "auto" and person is None and anchor_x is None:
        # auto promises that nobody is cut: when the crop loses a person the shot holds for most of
        # the clip, and no split is possible, the whole picture is kept.
        _, outside = _left_outside(scan, windows, scenes, trim, fps, info.width, info.height, present=0.5)
        if outside:
            return replace(
                build_camera_path(info, scan, target, trim, focus, "pad"),
                note="the people in this clip do not fit one frame, so the full source is kept over a blurred fill",
            )
    advisory = ""
    if anchor_x is not None and layout in ("crop", "speaker"):
        # A focus position is the user's choice: the window stays where they put it, and the people it
        # leaves out are reported instead of failing the check. Split and pad frame people their own way.
        people, outside = _left_outside(scan, windows, scenes, trim, fps, info.width, info.height)
        subjects_inside = (people - outside) / people if people else 1.0
        if outside:
            advisory = (
                f"{outside} {'person is' if outside == 1 else 'people are'} outside the frame "
                f"for most of the clip because the focus is set to {focus}."
            )
    return CameraPath(
        layout=layout,
        windows=windows,
        note=note,
        subjects_inside=subjects_inside,
        advisory=advisory,
    )
