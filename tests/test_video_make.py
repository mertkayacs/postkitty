from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from engine.framing import Box
from engine.video_make import VideoPlan, export_cover, plan_video, render_video
from engine.video_scan import Track, TrackPoint, VideoScan


@dataclass(frozen=True)
class Spec:
    value: Any


@dataclass(frozen=True)
class Target:
    id: str
    width: int
    height: int
    limits: dict[str, Spec] = field(default_factory=dict)

    @property
    def aspect(self) -> float:
        return self.width / self.height


@dataclass(frozen=True)
class InputInfo:
    path: Path
    sha256: str
    width: int
    height: int
    duration: float
    fps: float
    has_audio: bool = False


def _run(command: list[str]) -> None:
    subprocess.run(
        ["nice", "-n", "10", *command],
        check=True,
        capture_output=True,
    )


def _moving_video(path: Path, duration: float = 2.0) -> InputInfo:
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
            f"color=c=blue:s=320x180:r=10:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"color=c=red:s=30x40:r=10:d={duration}",
            "-filter_complex",
            "[0:v][1:v]overlay=x=20+120*t:y=70:shortest=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ]
    )
    return InputInfo(path, "moving-source", 320, 180, duration, 10.0)


def _box(x: float, y: float, w: float, h: float) -> Any:
    return Box(x, y, w, h)


def _probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=width,height,pix_fmt,codec_name,profile",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_plan_trims_long_source_around_face_presence(tmp_path: Path) -> None:
    points = tuple(
        TrackPoint(t, 80.0, 40.0, 30.0, 40.0, 0.99)
        for t in (175.0, 175.2, 175.4, 175.6)
    )
    scan = VideoScan(
        scenes=[(0.0, 200.0)],
        tracks=[Track(1, 1, points)],
        faces={
            "sample_fps": 5.0,
            "frames": [
                {"t": t, "faces": [{"x": 80, "y": 40, "w": 30, "h": 40}]}
                for t in (175.0, 175.2, 175.4, 175.6)
            ],
        },
        audio_rms=[(176.0, -3.0)],
    )
    info = InputInfo(tmp_path / "unused.mp4", "long", 320, 180, 200.0, 1.0)
    target = Target("x_video", 1920, 1080, {"duration_max": Spec(140.0)})

    plan = plan_video(info, scan, target, {"cover_at": 175.0})

    assert plan.trim == (36.5, 176.5)
    assert plan.cover_at == 175.0


def test_sendcmd_crop_keeps_moving_box_centered(tmp_path: Path) -> None:
    info = _moving_video(tmp_path / "moving.mp4")
    target = Target("square_video", 180, 180)
    windows = [
        _box(min(140.0, 20.0 + 120.0 * (index / 10) - 75.0), 0.0, 180.0, 180.0)
        for index in range(20)
    ]
    plan = VideoPlan(
        target.id,
        "crop",
        (0.0, 2.0),
        1.0,
        "moving crop proof",
        windows,
    )

    result = render_video(info, plan, target, tmp_path / "out.mp4", tmp_path / "work")

    decode = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(result.file),
            "-vf",
            "fps=5",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    frames = np.frombuffer(decode.stdout, dtype=np.uint8).reshape((-1, 180, 180, 3))
    centers = []
    for frame in frames:
        red = (frame[:, :, 2] > 180) & (frame[:, :, 1] < 90)
        _, xs = np.where(red)
        assert len(xs)
        centers.append(float(xs.mean()))
    assert max(abs(center - 90.0) for center in centers[2:-2]) < 18.0
    assert result.width == 180
    assert result.height == 180


def test_split_render_and_cover_have_exact_size(tmp_path: Path) -> None:
    info = _moving_video(tmp_path / "moving.mp4")
    target = Target("instagram_reel", 180, 320)
    pair = (_box(0.0, 0.0, 200.0, 180.0), _box(120.0, 0.0, 200.0, 180.0))
    plan = VideoPlan(
        target.id,
        "split",
        (0.0, 2.0),
        1.0,
        "split proof",
        [pair] * 20,
    )

    result = render_video(info, plan, target, tmp_path / "split.mp4", tmp_path / "work")
    cover = export_cover(info, plan, target, tmp_path / "cover.jpg")

    facts = _probe(result.file)
    assert facts["streams"][0]["width"] == 180
    assert facts["streams"][0]["height"] == 320
    cover_facts = _probe(cover)
    assert cover_facts["streams"][0]["width"] == 180
    assert cover_facts["streams"][0]["height"] == 320


def test_render_reuses_matching_master(tmp_path: Path) -> None:
    info = _moving_video(tmp_path / "moving.mp4", duration=1.0)
    target = Target("square_video", 180, 180)
    plan = VideoPlan(
        target.id,
        "crop",
        (0.0, 1.0),
        0.5,
        "reuse proof",
        [_box(70.0, 0.0, 180.0, 180.0)] * 10,
    )

    first = render_video(info, plan, target, tmp_path / "first.mp4", tmp_path / "work")
    second = render_video(info, plan, target, tmp_path / "second.mp4", tmp_path / "work")

    assert first.file.read_bytes() == second.file.read_bytes()
    assert len(list((tmp_path / "work" / "render").glob("reuse-*.mp4"))) == 1


def test_render_uses_requested_loudness(tmp_path: Path, monkeypatch: Any) -> None:
    import engine.video_make as video_make

    info = _moving_video(tmp_path / "moving.mp4", duration=1.0)
    info = InputInfo(info.path, info.sha256, info.width, info.height, info.duration, info.fps, True)
    target = Target("square_video", 180, 180)
    plan = VideoPlan(target.id, "crop", (0.0, 1.0), 0.5, "proof", [_box(70.0, 0.0, 180.0, 180.0)] * 10)
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        Path(command[-1]).write_bytes(b"video")

    monkeypatch.setattr(video_make.subprocess, "run", fake_run)
    monkeypatch.setattr(video_make, "_probe_render", lambda path: {
        "streams": [{"codec_type": "video", "width": 180, "height": 180}],
        "format": {"duration": "1.0", "size": "5"},
    })

    render_video(info, plan, target, tmp_path / "loud.mp4", tmp_path / "work", loudness_lufs=-16.5)

    graph = seen["command"][seen["command"].index("-filter_complex") + 1]
    assert "loudnorm=I=-16.5:TP=-1.5:LRA=11" in graph


def test_split_panels_have_even_heights_for_odd_half_targets(tmp_path: Path) -> None:
    # 1350 / 2 is odd; ffmpeg 6.1 corrupted its heap scaling 4:2:0 panels to 675 rows.
    import re

    from engine.video_make import _crop_filter

    @dataclass(frozen=True)
    class Info:
        width: int = 1920
        height: int = 1080

    target = Target("linkedin_video", 1080, 1350)
    windows = [(_box(0.0, 0.0, 1728.0, 1080.0), _box(192.0, 0.0, 1728.0, 1080.0))]
    plan = VideoPlan(target.id, "split", (0.0, 1.0), 0.5, "split proof", windows)
    heights = [int(h) for h in re.findall(r"scale=1080:(\d+)", _crop_filter(Info(), plan, target, 24.0, tmp_path / "c.txt"))]
    assert len(heights) == 2
    assert sum(heights) == 1350
    assert all(height % 2 == 0 for height in heights)
