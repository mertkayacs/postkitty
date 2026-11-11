from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from engine.photo.framing import Box
from engine.video.render import VideoPlan, export_cover, plan_video, render_video
from engine.video.scan import Track, TrackPoint, VideoScan


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
    import engine.video.render as video_make

    info = _moving_video(tmp_path / "moving.mp4", duration=1.0)
    info = InputInfo(info.path, info.sha256, info.width, info.height, info.duration, info.fps, True)
    target = Target("square_video", 180, 180)
    plan = VideoPlan(target.id, "crop", (0.0, 1.0), 0.5, "proof", [_box(70.0, 0.0, 180.0, 180.0)] * 10)
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        Path(command[-1]).write_bytes(b"video")

    monkeypatch.setattr(video_make.subprocess, "run", fake_run)
    monkeypatch.setattr(video_make, "_hdr_transfer", lambda path, sha256: None)
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

    from engine.video.render import _crop_filter

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


def test_speaker_layout_uses_the_crop_renderer(tmp_path: Path) -> None:
    from engine.video.render import _crop_filter

    @dataclass(frozen=True)
    class Info:
        width: int = 1280
        height: int = 720

    target = Target("tiktok", 1080, 1920)
    windows = [_box(0.0, 0.0, 405.0, 720.0)] * 10
    crop = VideoPlan(target.id, "crop", (0.0, 1.0), 0.5, "crop", windows)
    speaker = VideoPlan(target.id, "speaker", (0.0, 1.0), 0.5, "speaker", windows)

    assert _crop_filter(Info(), speaker, target, 10.0, tmp_path / "c.txt") == _crop_filter(
        Info(), crop, target, 10.0, tmp_path / "c.txt"
    )



def test_audio_encode_leaves_margin_under_platform_cap(tmp_path: Path, monkeypatch: Any) -> None:
    # AAC lands a little above its nominal rate: a stereo film clip encoded at "-b:a 128k" measured
    # 128,621 bit/s against Instagram's 128,000 cap and failed the hard check.
    import engine.video.render as video_make

    info = _moving_video(tmp_path / "moving.mp4", duration=1.0)
    info = InputInfo(info.path, info.sha256, info.width, info.height, info.duration, info.fps, True)
    target = Target("instagram_reel", 180, 320, {"audio_bps_max": Spec(128000)})
    plan = VideoPlan(target.id, "crop", (0.0, 1.0), 0.5, "proof", [_box(110.0, 0.0, 100.0, 180.0)] * 10)
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        Path(command[-1]).write_bytes(b"video")

    monkeypatch.setattr(video_make.subprocess, "run", fake_run)
    monkeypatch.setattr(video_make, "_hdr_transfer", lambda path, sha256: None)
    monkeypatch.setattr(video_make, "_probe_render", lambda path: {
        "streams": [{"codec_type": "video", "width": 180, "height": 320}],
        "format": {"duration": "1.0", "size": "5"},
    })

    render_video(info, plan, target, tmp_path / "reel.mp4", tmp_path / "work")

    command = seen["command"]
    assert int(command[command.index("-b:a") + 1]) <= 0.95 * 128000


def test_near_silent_audio_is_not_normalised_and_is_flagged(tmp_path: Path, monkeypatch: Any) -> None:
    # Room tone at about -70 dBFS was boosted 55 dB to -14 LUFS with status ready and no advisory.
    import engine.video.render as video_make

    info = _moving_video(tmp_path / "moving.mp4", duration=1.0)
    info = InputInfo(info.path, info.sha256, info.width, info.height, info.duration, info.fps, True)
    target = Target("tiktok", 180, 320)
    scan = VideoScan(
        scenes=[(0.0, 1.0)],
        tracks=[],
        faces={"sample_fps": 5.0, "frames": []},
        audio_rms=[(0.0, -69.0), (0.5, -71.0)],
    )
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        Path(command[-1]).write_bytes(b"video")

    monkeypatch.setattr(video_make.subprocess, "run", fake_run)
    monkeypatch.setattr(video_make, "_hdr_transfer", lambda path, sha256: None)
    monkeypatch.setattr(video_make, "_probe_render", lambda path: {
        "streams": [{"codec_type": "video", "width": 180, "height": 320}],
        "format": {"duration": "1.0", "size": "5"},
    })
    monkeypatch.setattr(video_make, "_sharpest_cover", lambda *args: 0.5)

    plan = plan_video(info, scan, target)
    result = render_video(info, plan, target, tmp_path / "quiet.mp4", tmp_path / "work")

    graph = seen["command"][seen["command"].index("-filter_complex") + 1]
    assert "loudnorm" not in graph and "[0:a]" in graph
    assert result.extra["quiet_audio"] is True

    loud = plan_video(info, VideoScan([(0.0, 1.0)], [], {"sample_fps": 5.0, "frames": []}, [(0.0, -22.0)]), target)
    render_video(info, loud, target, tmp_path / "loud.mp4", tmp_path / "work")
    assert "loudnorm" in seen["command"][seen["command"].index("-filter_complex") + 1]


def test_cover_at_the_trim_end_still_writes_a_frame(tmp_path: Path) -> None:
    # ffmpeg seeks past the last frame, exits 0 and writes nothing; the job then points at a missing cover.
    info = _moving_video(tmp_path / "moving.mp4", duration=1.0)
    target = Target("square_video", 180, 180)
    plan = VideoPlan(target.id, "crop", (0.0, 1.0), 1.0, "cover proof", [_box(70.0, 0.0, 180.0, 180.0)] * 10)

    cover = export_cover(info, plan, target, tmp_path / "cover.jpg")

    assert cover.is_file() and cover.stat().st_size > 0
    facts = _probe(cover)
    assert (facts["streams"][0]["width"], facts["streams"][0]["height"]) == (180, 180)


def test_render_reuse_respects_the_audio_cap_of_the_new_target(tmp_path: Path, monkeypatch: Any) -> None:
    # A tiktok render (no audio cap, 160k) was reused for instagram_reel and failed its 128k audio cap.
    import engine.video.render as video_make

    info = _moving_video(tmp_path / "moving.mp4", duration=1.0)
    info = InputInfo(info.path, info.sha256, info.width, info.height, info.duration, info.fps, True)
    plan = VideoPlan("tiktok", "crop", (0.0, 1.0), 0.5, "proof", [_box(110.0, 0.0, 100.0, 180.0)] * 10)
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"video")

    monkeypatch.setattr(video_make.subprocess, "run", fake_run)
    monkeypatch.setattr(video_make, "_hdr_transfer", lambda path, sha256: None)
    monkeypatch.setattr(video_make, "_probe_render", lambda path: {
        "streams": [{"codec_type": "video", "width": 180, "height": 320}],
        "format": {"duration": "1.0", "size": "5"},
    })

    render_video(info, plan, Target("tiktok", 180, 320), tmp_path / "tiktok.mp4", tmp_path / "work")
    render_video(
        info, plan, Target("instagram_reel", 180, 320, {"audio_bps_max": Spec(128000)}),
        tmp_path / "reel.mp4", tmp_path / "work",
    )

    assert len(commands) == 2
    reel = commands[1]
    assert int(reel[reel.index("-b:a") + 1]) <= 0.95 * 128000


def _anamorphic_video(path: Path) -> InputInfo:
    """A 240x240 coded frame shown 480x240, holding a box that is square on screen."""
    _run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
            "-i", "color=c=black:s=240x240:r=10:d=1",
            "-vf", "drawbox=x=90:y=60:w=60:h=120:color=white:t=fill,setsar=2/1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
        ]
    )
    return InputInfo(path, "anamorphic-source", 480, 240, 1.0, 10.0)


def _white_box_size(path: Path, width: int, height: int) -> tuple[int, int]:
    decode = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-frames:v", "1",
            "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    image = np.frombuffer(decode.stdout, dtype=np.uint8).reshape((height, width))
    ys, xs = np.where(image > 225)
    return int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


def test_anamorphic_source_is_not_stretched_in_crop_pad_or_cover(tmp_path: Path) -> None:
    info = _anamorphic_video(tmp_path / "anamorphic.mp4")
    wide = Target("wide_video", 480, 240)
    crop = VideoPlan(wide.id, "crop", (0.0, 1.0), 0.5, "", [_box(0.0, 0.0, 480.0, 240.0)] * 10)
    tall = Target("tall_video", 240, 480)
    pad = VideoPlan(tall.id, "pad", (0.0, 1.0), 0.5, "", [_box(0.0, 0.0, 480.0, 240.0)] * 10)

    cropped = render_video(info, crop, wide, tmp_path / "crop.mp4", tmp_path / "work")
    padded = render_video(info, pad, tall, tmp_path / "pad.mp4", tmp_path / "work")
    cover = export_cover(info, crop, wide, tmp_path / "cover.jpg")

    for path, size, side in ((cropped.file, (480, 240), 120), (padded.file, (240, 480), 60), (cover, (480, 240), 120)):
        box_width, box_height = _white_box_size(path, *size)
        assert abs(box_width - side) <= 6
        assert abs(box_height - side) <= 6


def test_pad_layout_scales_only_to_even_sizes(tmp_path: Path) -> None:
    # ffmpeg 6.1 corrupts its heap scaling 4:2:0 frames to an odd size; 320x176 fits 270x480 at 270x148.5.
    import re

    from engine.video.render import _pad_filter

    source = tmp_path / "source.mp4"
    _run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
            "-i", "color=c=blue:s=320x176:r=10:d=0.5", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
        ]
    )
    info = InputInfo(source, "even-proof", 320, 176, 0.5, 10.0)
    graph = _pad_filter(info, Target("tall_video", 270, 480), 10.0) + "[v]"

    log = subprocess.run(
        ["ffmpeg", "-hide_banner", "-v", "verbose", "-i", str(source), "-filter_complex", graph,
         "-map", "[v]", "-frames:v", "1", "-f", "null", "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stderr
    sizes = [(int(w), int(h)) for w, h in re.findall(r"Parsed_scale_\d+.*-> w:(\d+) h:(\d+)", log)]
    assert len(sizes) >= 2
    assert all(w % 2 == 0 and h % 2 == 0 for w, h in sizes), sizes



def test_render_works_from_a_job_folder_with_quotes_and_filter_syntax_in_its_name(tmp_path: Path) -> None:
    info = _moving_video(tmp_path / "moving.mp4", duration=1.0)
    target = Target("square_video", 180, 180)
    plan = VideoPlan(target.id, "crop", (0.0, 1.0), 0.5, "", [_box(70.0, 0.0, 180.0, 180.0)] * 10)

    result = render_video(info, plan, target, tmp_path / "out.mp4", tmp_path / "it's a [job], 50%; x=1:2")

    assert (result.width, result.height) == (180, 180)


def _colour(path: Path) -> list[str]:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=pix_fmt,color_space,color_transfer,color_primaries", "-of", "default=nw=1:nk=1", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()


def test_hdr_phone_clip_is_rendered_as_sdr(tmp_path: Path, monkeypatch: Any) -> None:
    # Phones record 10-bit HLG by default; a platform file is 8-bit BT.709.
    import engine.video.render as video_make

    source = tmp_path / "hlg.mp4"
    _run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=10:d=0.5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p10le", "-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
            "-colorspace", "bt2020nc", str(source),
        ]
    )
    info = InputInfo(source, "hlg-source", 320, 180, 0.5, 10.0)
    target = Target("wide_video", 320, 180)
    plan = VideoPlan(target.id, "crop", (0.0, 0.5), 0.2, "", [_box(0.0, 0.0, 320.0, 180.0)] * 5)

    result = render_video(info, plan, target, tmp_path / "out.mp4", tmp_path / "work")

    assert _colour(result.file) == ["yuv420p", "bt709", "bt709", "bt709"]
    assert export_cover(info, plan, target, tmp_path / "cover.jpg").is_file()
    monkeypatch.setattr(video_make, "has_filter", lambda name: name != "zscale")
    with pytest.raises(ValueError, match="hlg.mp4 is HDR video and this ffmpeg build has no zscale filter"):
        render_video(info, plan, target, tmp_path / "other.mp4", tmp_path / "work2")
