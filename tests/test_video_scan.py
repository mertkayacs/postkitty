from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from engine.video_scan import make_peek, scan_video


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
    subprocess.run(
        ["nice", "-n", "10", *command],
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
