from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from engine.probe import run_tool
from engine.video.scan import _build_tracks, make_peek, scan_video


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class Face:
    box: Box
    score: float
    landmarks: tuple[tuple[float, float], ...] = ()


class ColorDetector:
    name = "test-color"

    def __init__(self) -> None:
        self.calls = 0

    def detect(self, image_bgr: np.ndarray) -> list[Face]:
        self.calls += 1
        red = (image_bgr[:, :, 2] > 180) & (image_bgr[:, :, 1] < 90)
        ys, xs = np.where(red)
        if not len(xs):
            return []
        return [
            Face(
                Box(
                    float(xs.min()),
                    float(ys.min()),
                    float(xs.max() - xs.min() + 1),
                    float(ys.max() - ys.min() + 1),
                ),
                0.99,
            )
        ]


class FailingDetector:
    name = "must-not-run"

    def detect(self, image_bgr: np.ndarray) -> list[Face]:
        raise AssertionError("cached scan decoded frames")


@dataclass(frozen=True)
class InputInfo:
    path: Path
    sha256: str
    width: int
    height: int
    duration: float
    fps: float
    has_audio: bool


def _run(command: list[str]) -> None:
    run_tool(
        command,
        check=True,
        capture_output=True,
    )


def _make_video(path: Path) -> InputInfo:
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-threads",
            "4",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x180:r=20:d=2",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=36x45:r=20:d=2",
            "-filter_complex",
            "[0:v][1:v]overlay=x=40+40*t:y=50:shortest=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ]
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return InputInfo(path, digest, 320, 180, 2.0, 20.0, False)


def test_scan_tracks_faces_and_reuses_cache(tmp_path: Path) -> None:
    info = _make_video(tmp_path / "moving.mp4")
    detector = ColorDetector()
    scan = scan_video(info, detector, tmp_path / "work")

    assert detector.calls == 10
    assert len(scan.tracks) == 1
    assert scan.tracks[0].person == 1
    assert scan.tracks[0].points[-1].cx > scan.tracks[0].points[0].cx
    assert scan.audio_rms == []
    assert (tmp_path / "work" / "faces" / f"{info.sha256}.json").exists()
    assert (tmp_path / "work" / "scenes" / f"{info.sha256}.json").exists()

    cached = scan_video(info, FailingDetector(), tmp_path / "work")
    assert cached == scan


def test_track_keeps_partial_edge_face_with_moving_subject() -> None:
    def face(x: float, y: float, w: float, h: float, score: float) -> dict[str, float]:
        return {"x": x, "y": y, "w": w, "h": h, "score": score}

    faces = {
        "width": 1920,
        "height": 1080,
        "sample_fps": 5.0,
        "frames": [
            {"t": 0.0, "faces": [face(0.4, 76.4, 55.6, 80.1, 0.65)]},
            {
                "t": 0.2,
                "faces": [
                    face(32.2, 209.4, 111.8, 149.0, 0.91),
                    face(0.7, 75.2, 57.1, 94.1, 0.62),
                ],
            },
            {"t": 0.4, "faces": [face(105.6, 208.2, 115.2, 149.2, 0.91)]},
            {"t": 0.6, "faces": [face(212.8, 224.9, 119.2, 150.9, 0.92)]},
        ],
    }

    tracks = _build_tracks(faces, [(0.0, 1.0)])

    assert len(tracks) == 1
    assert [point.t for point in tracks[0].points] == [0.0, 0.2, 0.4, 0.6]
    assert tracks[0].points[1].x == 32.2


def test_scan_detects_a_hard_scene_cut(tmp_path: Path) -> None:
    path = tmp_path / "cut.mp4"
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-threads",
            "4",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x180:r=20:d=1",
            "-f",
            "lavfi",
            "-i",
            "color=c=white:s=320x180:r=20:d=1",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ]
    )
    info = InputInfo(path, "scene-cut", 320, 180, 2.0, 20.0, False)

    scan = scan_video(info, ColorDetector(), tmp_path / "work")

    assert len(scan.scenes) == 2
    assert 0.9 <= scan.scenes[0][1] <= 1.1


def test_make_peek_writes_one_horizontal_strip(tmp_path: Path) -> None:
    info = _make_video(tmp_path / "moving.mp4")
    scan = scan_video(info, ColorDetector(), tmp_path / "work")

    output = make_peek(info, scan, tmp_path / "peek.jpg", n=4)

    assert output.exists()
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    width, height = map(int, probe.stdout.strip().split(","))
    assert width == 1280
    assert height == 180
