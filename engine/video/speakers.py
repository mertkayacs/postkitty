from __future__ import annotations

import hashlib
import json
import math
import subprocess
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from .scan import Track, TrackPoint


def _read_exact(stream: Any, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


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
            if len(left.landmarks) == len(right.landmarks):
                landmarks = tuple(
                    (a[0] + (b[0] - a[0]) * weight, a[1] + (b[1] - a[1]) * weight)
                    for a, b in zip(left.landmarks, right.landmarks, strict=True)
                )
            else:
                landmarks = (left if weight < 0.5 else right).landmarks
            return TrackPoint(
                t=t,
                x=left.x + (right.x - left.x) * weight,
                y=left.y + (right.y - left.y) * weight,
                w=left.w + (right.w - left.w) * weight,
                h=left.h + (right.h - left.h) * weight,
                score=left.score + (right.score - left.score) * weight,
                landmarks=landmarks,
            )
    return points[-1]


def _blur(image: np.ndarray) -> np.ndarray:
    padded = np.pad(image.astype(np.float32), 1, mode="edge")
    return sum(
        padded[y : y + image.shape[0], x : x + image.shape[1]]
        for y in range(3)
        for x in range(3)
    ) / 9.0


def _region(
    point: TrackPoint,
    x_scale: float,
    y_scale: float,
    y_start: float,
    y_end: float,
    width: int,
    height: int,
) -> tuple[slice, slice]:
    center_x = (point.x + point.w / 2) * x_scale
    center_y = (point.y + point.h * (y_start + y_end) / 2) * y_scale
    box_width = max(6.0, point.w * 0.6 * x_scale)
    box_height = max(4.0, point.h * (y_end - y_start) * y_scale)
    left = max(0, min(math.floor(center_x - box_width / 2), width - 1))
    top = max(0, min(math.floor(center_y - box_height / 2), height - 1))
    right = min(width, max(left + 1, math.ceil(center_x + box_width / 2)))
    bottom = min(height, max(top + 1, math.ceil(center_y + box_height / 2)))
    if right - left < min(6, width):
        left = max(0, min(round(center_x) - 3, width - min(6, width)))
        right = min(width, left + 6)
    if bottom - top < min(4, height):
        top = max(0, min(round(center_y) - 2, height - min(4, height)))
        bottom = min(height, top + 4)
    return slice(top, bottom), slice(left, right)


def _mouth_region(
    point: TrackPoint, x_scale: float, y_scale: float, width: int, height: int
) -> tuple[slice, slice]:
    # YuNet landmarks 3 and 4 are the mouth corners. They find the lips in profile too, where the
    # middle of the face box is mostly cheek. Without landmarks, fall back to the lower face.
    if len(point.landmarks) < 5:
        return _region(point, x_scale, y_scale, 0.62, 1.0, width, height)
    (left_x, left_y), (right_x, right_y) = point.landmarks[3], point.landmarks[4]
    center_x = (left_x + right_x) / 2 * x_scale
    center_y = ((left_y + right_y) / 2 + point.h * 0.04) * y_scale
    box_width = max(6.0, max(abs(right_x - left_x) * 1.8, point.w * 0.35) * x_scale)
    box_height = max(4.0, point.h * 0.32 * y_scale)
    left = max(0, min(math.floor(center_x - box_width / 2), width - 6))
    top = max(0, min(math.floor(center_y - box_height / 2), height - 4))
    right = min(width, max(left + 6, math.ceil(center_x + box_width / 2)))
    bottom = min(height, max(top + 4, math.ceil(center_y + box_height / 2)))
    return slice(top, bottom), slice(left, right)


def mouth_activity(
    path: Path,
    tracks: list[Track],
    start: float,
    end: float,
    width: int,
    height: int,
    analysis_fps: float = 15.0,
) -> tuple[np.ndarray, np.ndarray]:
    if analysis_fps <= 0:
        raise ValueError("analysis_fps must be positive")
    if end <= start:
        raise ValueError("activity range must be increasing")
    scaled_width = min(640, width)
    scaled_height = max(2, round(height * scaled_width / width / 2) * 2)
    command = [
        "nice",
        "-n",
        "10",
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-threads",
        "4",
        "-ss",
        str(start),
        "-t",
        str(end - start),
        "-i",
        str(path),
        "-vf",
        f"fps={analysis_fps},scale={scaled_width}:{scaled_height}",
        "-an",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert process.stdout is not None
    frame_size = scaled_width * scaled_height
    frames: list[np.ndarray] = []
    try:
        while True:
            raw = _read_exact(process.stdout, frame_size)
            if len(raw) != frame_size:
                break
            frames.append(
                np.frombuffer(raw, dtype=np.uint8)
                .reshape((scaled_height, scaled_width))
                .copy()
            )
    finally:
        process.stdout.close()
        return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"ffmpeg activity decode failed with exit code {return_code}")

    times = start + np.arange(len(frames), dtype=np.float64) / analysis_fps
    activity = np.zeros((len(frames), len(tracks)), dtype=np.float64)
    x_scale = scaled_width / width
    y_scale = scaled_height / height
    previous: np.ndarray | None = None
    for frame_index, (t, frame) in enumerate(zip(times, frames, strict=True)):
        blurred = _blur(frame)
        if previous is not None:
            for track_index, track in enumerate(tracks):
                if min(abs(point.t - t) for point in track.points) > 0.6:
                    continue
                point = _interpolate(track, float(t))
                mouth = _mouth_region(
                    point, x_scale, y_scale, scaled_width, scaled_height
                )
                activity[frame_index, track_index] = float(
                    np.mean(np.abs(blurred[mouth] - previous[mouth]))
                )
        previous = blurred
    return times, activity


def speech_activity(
    path: Path, start: float, end: float, analysis_fps: float
) -> np.ndarray:
    if analysis_fps <= 0:
        raise ValueError("analysis_fps must be positive")
    if end <= start:
        raise ValueError("activity range must be increasing")
    frame_count = max(1, round((end - start) * analysis_fps))
    command = [
        "nice",
        "-n",
        "10",
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-threads",
        "4",
        "-ss",
        str(start),
        "-t",
        str(end - start),
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "s16le",
        "pipe:1",
    ]
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode != 0 or not completed.stdout:
        return np.ones(frame_count, dtype=bool)

    samples = np.frombuffer(completed.stdout, dtype="<i2").astype(np.float64)
    levels = np.full(frame_count, -120.0, dtype=np.float64)
    for index in range(frame_count):
        left = round(index * 16000 / analysis_fps)
        right = min(len(samples), round((index + 1) * 16000 / analysis_fps))
        if right <= left:
            continue
        rms = math.sqrt(float(np.mean(np.square(samples[left:right]))))
        if rms > 0:
            levels[index] = 20 * math.log10(rms / 32768.0)
    threshold = max(float(np.percentile(levels, 10)) + 8.0, -50.0)
    return levels > threshold


def _smooth(activity: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return activity.astype(np.float64, copy=True)
    left = (window - 1) // 2
    right = window // 2
    smoothed = np.empty_like(activity, dtype=np.float64)
    cumulative = np.vstack(
        (np.zeros((1, activity.shape[1])), np.cumsum(activity, axis=0))
    )
    for index in range(len(activity)):
        start = max(0, index - left)
        end = min(len(activity), index + right + 1)
        smoothed[index] = (cumulative[end] - cumulative[start]) / (end - start)
    return smoothed


def speaker_segments(
    times: np.ndarray,
    activity: np.ndarray,
    speech: np.ndarray,
    min_shot: float = 1.2,
    switch_margin: float = 1.35,
    confirm: float = 0.5,
    overlap_confirm: float = 1.0,
    speech_gap: float = 0.27,
) -> list[tuple[float, float, int]]:
    times = np.asarray(times, dtype=np.float64)
    activity = np.asarray(activity, dtype=np.float64)
    speech = np.asarray(speech, dtype=bool)
    if activity.ndim != 2 or len(activity) != len(times) or len(speech) != len(times):
        raise ValueError("times, activity and speech must have matching lengths")
    if not len(times) or not activity.shape[1]:
        return []
    step = float(np.median(np.diff(times))) if len(times) > 1 else 1.0
    end = float(times[-1] + step)
    window = max(1, round(0.4 / step))
    smoothed = _smooth(activity, window)
    # Short pauses between words still count as speech, so they do not reset a pending cut.
    reach = max(0, round(speech_gap / step))
    if reach:
        speech = np.array(
            [bool(speech[max(0, i - reach) : i + reach + 1].any()) for i in range(len(speech))]
        )
    first_speech = np.flatnonzero(speech)
    first_index = int(first_speech[0]) if len(first_speech) else 0
    # Open on whoever talks most in the first second of speech, so one noisy frame cannot decide it.
    opening = smoothed[first_index : first_index + max(1, round(1.0 / step))]
    current = int(np.argmax(opening.mean(axis=0)))
    segment_start = float(times[0])
    candidate: int | None = None
    candidate_start = 0.0
    segments: list[tuple[float, float, int]] = []

    for index, t in enumerate(times):
        other = int(np.argmax(smoothed[index]))
        dominates = (
            speech[index]
            and other != current
            and smoothed[index, other] > 0
            and smoothed[index, other] >= switch_margin * smoothed[index, current]
        )
        if not dominates:
            candidate = None
            continue
        if candidate != other:
            candidate = other
            candidate_start = float(t)
        # While the current speaker is still talking too, wait longer before cutting away.
        overlapping = smoothed[index, current] >= 0.5 * smoothed[index, other]
        needed = overlap_confirm if overlapping else confirm
        confirmed = float(t + step) - candidate_start >= needed - 1e-9
        if not confirmed:
            continue
        cut = max(candidate_start, segment_start + min_shot)
        if float(t + step) < cut - 1e-9 or cut >= end:
            continue
        segments.append((segment_start, cut, current))
        segment_start = cut
        current = other
        candidate = None

    segments.append((segment_start, end, current))
    return segments


def cached_activity(
    path: Path,
    source_sha256: str,
    tracks: list[Track],
    start: float,
    end: float,
    width: int,
    height: int,
    work_dir: Path | None,
    analysis_fps: float = 15.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cache_path: Path | None = None
    if work_dir is not None:
        payload = json.dumps(
            {
                "method": "mouth-landmarks-1",
                "source": source_sha256,
                "scene": [start, end],
                "persons": [track.person for track in tracks],
                "analysis_fps": analysis_fps,
            },
            separators=(",", ":"),
        )
        key = hashlib.sha256(payload.encode()).hexdigest()
        cache_path = Path(work_dir) / "speakers" / f"{key}.npz"
        if cache_path.is_file():
            with np.load(cache_path, allow_pickle=False) as cached:
                return cached["times"], cached["activity"], cached["speech"]

    times, activity = mouth_activity(
        path, tracks, start, end, width, height, analysis_fps
    )
    speech = speech_activity(path, start, end, analysis_fps)
    count = min(len(times), len(speech))
    result = times[:count], activity[:count], speech[:count]
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(".tmp.npz")
        np.savez_compressed(
            temporary, times=result[0], activity=result[1], speech=result[2]
        )
        temporary.replace(cache_path)
    return result
