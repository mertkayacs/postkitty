from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from engine.captions import _ass_document, burn_captions, parse_captions


@dataclass(frozen=True)
class Spec:
    value: Any


@dataclass(frozen=True)
class Target:
    width: int
    height: int
    limits: dict[str, Spec] = field(default_factory=dict)


def test_parse_srt_and_vtt(tmp_path: Path) -> None:
    srt = tmp_path / "captions.srt"
    srt.write_text(
        "1\n00:00:00,200 --> 00:00:01,100\nFirst line\n\n"
        "2\n00:00:01,200 --> 00:00:02,000\nSecond line\n",
        encoding="utf-8",
    )
    vtt = tmp_path / "captions.vtt"
    vtt.write_text(
        "WEBVTT\n\n00:00.200 --> 00:01.100 align:middle\nFirst line\n",
        encoding="utf-8",
    )

    assert parse_captions(srt) == [
        {"start": 0.2, "end": 1.1, "text": "First line"},
        {"start": 1.2, "end": 2.0, "text": "Second line"},
    ]
    assert parse_captions(vtt) == [
        {"start": 0.2, "end": 1.1, "text": "First line"}
    ]


def test_ass_uses_safe_area_and_never_exceeds_two_lines() -> None:
    target = Target(1080, 1920, {"safe_area": Spec({"side": 0.06, "bottom": 0.35})})
    text = " ".join(["caption"] * 30)

    document = _ass_document([{"start": 0, "end": 3, "text": text}], target)

    assert "Style: Default,Arial,86" in document
    assert ",65,65,672,1" in document
    assert all(line.count(r"\N") <= 1 for line in document.splitlines() if line.startswith("Dialogue:"))
    assert document.count("caption") == 30


def test_burn_captions_places_visible_text_above_bottom_quarter(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    output = tmp_path / "captioned.mp4"
    subprocess.run(
        [
            "nice",
            "-n",
            "10",
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
            "color=c=black:s=320x180:r=20:d=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
        capture_output=True,
    )

    burn_captions(
        source,
        [{"start": 0.2, "end": 1.8, "text": "Visible caption"}],
        Target(320, 180),
        output,
    )

    frame = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            "1",
            "-i",
            str(output),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    image = np.frombuffer(frame.stdout, dtype=np.uint8).reshape((180, 320))
    assert image[80:150].max() > 150
    assert image[155:].max() < 20
    assert not list(tmp_path.glob("postkitty-*.ass"))
