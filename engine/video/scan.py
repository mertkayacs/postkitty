from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from ..probe import run_tool, start_tool


@dataclass(frozen=True)
class TrackPoint:
    t: float
    x: float
    y: float
    w: float
    h: float
    score: float
    landmarks: tuple[tuple[float, float], ...] = ()

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass(frozen=True)
class Track:
    id: int
    person: int
    points: tuple[TrackPoint, ...]

    @property
    def start(self) -> float:
        return self.points[0].t

    @property
    def end(self) -> float:
        return self.points[-1].t


@dataclass(frozen=True)
class VideoScan:
    scenes: list[tuple[float, float]]
    tracks: list[Track]
    faces: dict[str, Any]
    audio_rms: list[tuple[float, float]]
    work_dir: Path | None = None


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return run_tool(command, check=True, capture_output=True, text=True)


def _scan_scenes(path: Path, duration: float) -> list[tuple[float, float]]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-threads",
        "4",
        "-i",
        str(path),
        "-vf",
        "scdet=threshold=10,metadata=mode=print:key=lavfi.scd.time",
        "-an",
        "-f",
        "null",
        "-",
    ]
    try:
        output = _run(command).stderr
    except subprocess.CalledProcessError:
        return [(0.0, duration)]

    cuts = sorted(
        {
            float(value)
            for value in re.findall(r"lavfi\.scd\.time=([0-9.]+)", output)
            if 0.0 < float(value) < duration
        }
    )
    boundaries = [0.0, *cuts, duration]
    return [
        (start, end)
        for start, end in pairwise(boundaries)
        if end > start
    ]


def _scan_audio(path: Path, has_audio: bool) -> list[tuple[float, float]]:
    if not has_audio:
        return []

    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-threads",
        "4",
        "-i",
        str(path),
        "-vn",
        "-af",
        (
            "aresample=48000,asetnsamples=n=24000:p=0,"
            "astats=metadata=1:reset=1,"
            "ametadata=mode=print:key=lavfi.astats.Overall.RMS_level"
        ),
        "-f",
        "null",
        "-",
    ]
    try:
        output = _run(command).stderr
    except subprocess.CalledProcessError:
        return []

    points: list[tuple[float, float]] = []
    current_t: float | None = None
    for line in output.splitlines():
        time_match = re.search(r"pts_time:([0-9.]+)", line)
        if time_match:
            current_t = float(time_match.group(1))
            continue
        rms_match = re.search(
            r"lavfi\.astats\.Overall\.RMS_level=(-?(?:inf|[0-9.]+))", line
        )
        if rms_match and current_t is not None:
            value = rms_match.group(1)
            points.append((current_t, -120.0 if value == "-inf" else float(value)))
            current_t = None
    return points


def read_exact(stream: Any, size: int) -> bytes:
    """Read ``size`` bytes from a pipe, which may hand over a frame in several pieces."""
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _face_document(info: Any, detector: Any, sample_fps: float) -> dict[str, Any]:
    scaled_width = min(640, info.width)
    scaled_height = max(2, round(info.height * scaled_width / info.width / 2) * 2)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-threads",
        "4",
        "-i",
        str(info.path),
        "-vf",
        f"fps={sample_fps},scale={scaled_width}:{scaled_height}",
        "-an",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "pipe:1",
    ]
    process = start_tool(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert process.stdout is not None
    frame_size = scaled_width * scaled_height * 3
    x_scale = info.width / scaled_width
    y_scale = info.height / scaled_height
    frames: list[dict[str, Any]] = []
    index = 0
    try:
        while True:
            raw = read_exact(process.stdout, frame_size)
            if len(raw) != frame_size:
                break
            image = np.frombuffer(raw, dtype=np.uint8).reshape(
                (scaled_height, scaled_width, 3)
            )
            faces = []
            for face in detector.detect(image):
                box = face.box
                faces.append(
                    {
                        "x": box.x * x_scale,
                        "y": box.y * y_scale,
                        "w": box.w * x_scale,
                        "h": box.h * y_scale,
                        "score": face.score,
                        "landmarks": [
                            [x * x_scale, y * y_scale] for x, y in face.landmarks
                        ],
                    }
                )
            frames.append({"t": index / sample_fps, "faces": faces})
            index += 1
    finally:
        process.stdout.close()
        return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"ffmpeg frame decode failed with exit code {return_code}")

    return {
        "schema": "postkitty.faces/1",
        "source_sha256": info.sha256,
        "detector": detector.name,
        "width": info.width,
        "height": info.height,
        "fps": info.fps,
        "sample_fps": sample_fps,
        "frames": frames,
    }


def _iou(a: TrackPoint, b: dict[str, Any]) -> float:
    x1 = max(a.x, b["x"])
    y1 = max(a.y, b["y"])
    x2 = min(a.x + a.w, b["x"] + b["w"])
    y2 = min(a.y + a.h, b["y"] + b["h"])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = a.w * a.h + b["w"] * b["h"] - intersection
    return intersection / union if union else 0.0


def _touches_edge(box: TrackPoint | dict[str, Any], width: int, height: int) -> bool:
    return (
        box.x <= 1.0
        or box.y <= 1.0
        or box.x + box.w >= width - 1.0
        or box.y + box.h >= height - 1.0
        if isinstance(box, TrackPoint)
        else box["x"] <= 1.0
        or box["y"] <= 1.0
        or box["x"] + box["w"] >= width - 1.0
        or box["y"] + box["h"] >= height - 1.0
    )


def _linkable(
    points: list[TrackPoint],
    b: dict[str, Any],
    t: float,
    width: int,
    height: int,
) -> tuple[bool, float]:
    a = points[-1]
    overlap = _iou(a, b)
    b_cx = b["x"] + b["w"] / 2
    b_cy = b["y"] + b["h"] / 2
    distance = math.hypot(a.cx - b_cx, a.cy - b_cy)
    face_width = max(a.w, b["w"])
    predicted_distance = distance
    if len(points) >= 2 and a.t > points[-2].t:
        previous = points[-2]
        scale = (t - a.t) / (a.t - previous.t)
        predicted_distance = math.hypot(
            a.cx + (a.cx - previous.cx) * scale - b_cx,
            a.cy + (a.cy - previous.cy) * scale - b_cy,
        )
    edge_link = (
        (_touches_edge(a, width, height) or _touches_edge(b, width, height))
        and distance < 1.5 * max(a.w, a.h, b["w"], b["h"])
    )
    edge_history_link = (
        any(_touches_edge(point, width, height) for point in points[-2:])
        and distance < 0.55 * max(a.w, a.h, b["w"], b["h"])
    )
    escaped_edge = _touches_edge(a, width, height) and not _touches_edge(
        b, width, height
    )
    best_distance = min(distance, predicted_distance)
    linkable = (
        overlap >= 0.3
        or best_distance < 0.5 * face_width
        or edge_link
        or edge_history_link
    )
    return linkable, overlap - best_distance / max(face_width, 1.0) + 3 * escaped_edge


def _scene_index(t: float, scenes: list[tuple[float, float]]) -> int:
    for index, (start, end) in enumerate(scenes):
        if start <= t < end or index == len(scenes) - 1 and math.isclose(t, end):
            return index
    return len(scenes) - 1


def _track_point(t: float, face: dict[str, Any]) -> TrackPoint:
    return TrackPoint(
        t=t,
        x=float(face["x"]),
        y=float(face["y"]),
        w=float(face["w"]),
        h=float(face["h"]),
        score=float(face["score"]),
        landmarks=tuple((float(x), float(y)) for x, y in face.get("landmarks", [])),
    )


def _build_tracks(faces: dict[str, Any], scenes: list[tuple[float, float]]) -> list[Track]:
    sample_fps = float(faces["sample_fps"])
    width = int(faces["width"])
    height = int(faces["height"])
    max_gap = 2.1 / sample_fps
    pending: list[list[TrackPoint]] = []

    for frame in faces["frames"]:
        t = float(frame["t"])
        candidates: list[tuple[int, float, int, int]] = []
        for track_index, points in enumerate(pending):
            last = points[-1]
            if t - last.t > max_gap or _scene_index(t, scenes) != _scene_index(last.t, scenes):
                continue
            for face_index, face in enumerate(frame["faces"]):
                linkable, score = _linkable(points, face, t, width, height)
                if linkable:
                    candidates.append(
                        (int(len(points) > 1), score, track_index, face_index)
                    )

        used_tracks: set[int] = set()
        used_faces: set[int] = set()
        for _, _, track_index, face_index in sorted(candidates, reverse=True):
            if track_index in used_tracks or face_index in used_faces:
                continue
            face = frame["faces"][face_index]
            pending[track_index].append(_track_point(t, face))
            used_tracks.add(track_index)
            used_faces.add(face_index)

        for face_index, face in enumerate(frame["faces"]):
            if face_index in used_faces:
                continue
            pending.append([_track_point(t, face)])

    kept = [
        points
        for points in pending
        if points[-1].t - points[0].t + 1.0 / sample_fps >= 0.6 - 1e-9
    ]
    kept.sort(key=lambda points: (points[0].t, points[0].cx))
    return [
        Track(id=index, person=index, points=tuple(points))
        for index, points in enumerate(kept, start=1)
    ]


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


def scan_video(
    info: Any,
    detector: Any,
    work_dir: Path,
    sample_fps: float = 5.0,
) -> VideoScan:
    if sample_fps <= 0:
        raise ValueError("sample_fps must be positive")
    if info.duration is None or info.duration <= 0:
        raise ValueError("video duration must be positive")

    faces_path = work_dir / "faces" / f"{info.sha256}.json"
    scenes_path = work_dir / "scenes" / f"{info.sha256}.json"
    if faces_path.exists():
        faces = json.loads(faces_path.read_text(encoding="utf-8"))
    else:
        faces = _face_document(info, detector, sample_fps)
        _write_json(faces_path, faces)

    if scenes_path.exists():
        scene_document = json.loads(scenes_path.read_text(encoding="utf-8"))
        scenes = [tuple(scene) for scene in scene_document["scenes"]]
        audio_rms = [tuple(point) for point in scene_document["audio_rms"]]
    else:
        scenes = _scan_scenes(info.path, info.duration)
        audio_rms = _scan_audio(info.path, info.has_audio)
        _write_json(
            scenes_path,
            {
                "schema": "postkitty.scenes/1",
                "source_sha256": info.sha256,
                "scenes": scenes,
                "audio_rms": audio_rms,
            },
        )

    return VideoScan(
        scenes=scenes,
        tracks=_build_tracks(faces, scenes),
        faces=faces,
        audio_rms=audio_rms,
        work_dir=work_dir,
    )


def make_peek(info: Any, scan: VideoScan, out_path: Path, n: int = 6) -> Path:
    if n <= 0:
        raise ValueError("n must be positive")
    if info.duration is None or info.duration <= 0:
        raise ValueError("video duration must be positive")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    interval = info.duration / n
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-threads",
        "4",
        "-y",
        "-i",
        str(info.path),
        "-vf",
        f"fps=1/{interval},scale=320:{max(2, round(320 * info.height / info.width / 2) * 2)},setsar=1,tile={n}x1",
        "-frames:v",
        "1",
        str(out_path),
    ]
    _run(command)
    return out_path
