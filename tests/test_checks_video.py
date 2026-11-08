from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine import checks as checks_mod
from engine import repair as repair_mod
from engine.checks_video import (
    check_video,
    repair_duration,
    repair_fps,
    repair_subjects,
)
from engine.framing import Box
from engine.video_make import VideoPlan, render_video


@dataclass(frozen=True)
class Spec:
    value: Any
    enforcement: str = "hard"
    source_url: str | None = "https://example.test/spec"
    source_scope: str | None = "official"
    checked_on: str | None = "2026-11-07"


@dataclass(frozen=True)
class Target:
    id: str
    width: int
    height: int
    limits: dict[str, Spec] = field(default_factory=dict)


@dataclass(frozen=True)
class InputInfo:
    path: Path
    sha256: str
    width: int
    height: int
    duration: float
    fps: float
    has_audio: bool = False


def _render(tmp_path: Path) -> tuple[Any, Target]:
    import subprocess

    source = tmp_path / "source.mp4"
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
            "testsrc2=s=320x180:r=20:d=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    info = InputInfo(source, "checks", 320, 180, 2.0, 20.0)
    target = Target(
        "test_video",
        320,
        180,
        {
            "containers": Spec(["mp4"]),
            "video_codecs": Spec(["h264"]),
            "fps_min": Spec(10),
            "fps_max": Spec(30),
            "duration_min": Spec(1),
            "duration_max": Spec(3),
            "bytes_max": Spec(2_000_000),
            "video_bps_max": Spec(5_000_000),
        },
    )
    box = Box(0.0, 0.0, 320.0, 180.0)
    plan = VideoPlan(target.id, "crop", (0.0, 2.0), 1.0, "checks", [box] * 40)
    result = render_video(info, plan, target, tmp_path / "out.mp4", tmp_path / "work")
    return result, target


def test_video_checker_passes_rendered_output(tmp_path: Path) -> None:
    result, target = _render(tmp_path)

    checks = check_video(result, target)

    assert all(check.status in {"pass", "skipped"} for check in checks)
    assert {check.id for check in checks} >= {
        "video.container",
        "video.codec",
        "video.profile",
        "video.pix_fmt",
        "video.width",
        "video.height",
        "frame.subjects_inside",
    }
    assert next(check for check in checks if check.id == "video.duration_max").source_scope == "official"


def test_video_checker_reports_hard_and_advisory_failures(tmp_path: Path) -> None:
    result, _ = _render(tmp_path)
    target = Target(
        "strict_video",
        1080,
        1920,
        {
            "duration_max": Spec(1.0),
            "fps_max": Spec(10, enforcement="recommendation"),
        },
    )
    result.subjects_inside = 0.95

    checks = {check.id: check for check in check_video(result, target)}

    assert checks["video.width"].status == "fail"
    assert checks["video.duration_max"].status == "fail"
    assert checks["video.fps_max"].status == "advisory"
    assert checks["frame.subjects_inside"].status == "fail"


def test_repairs_are_registered() -> None:
    assert check_video in checks_mod._CHECKERS["video"]
    assert repair_mod._STRATEGIES.keys() >= {
        "video.bytes_max",
        "video.bitrate_max",
        "video.duration_max",
        "video.fps_max",
        "frame.subjects_inside",
    }


def test_duration_and_subject_repairs_use_rerender_context(tmp_path: Path) -> None:
    result, target = _render(tmp_path)
    duration_check = checks_mod.Check(
        "video.duration_max", target.id, "fail", True, 2.0, 1.0, "too long"
    )
    subject_check = checks_mod.Check(
        "frame.subjects_inside", target.id, "fail", True, 0.9, 0.98, "cut"
    )
    calls: list[dict[str, Any]] = []

    def rerender(overrides: dict[str, Any]) -> Any:
        calls.append(overrides)
        return result

    assert repair_duration(result, target, duration_check, {"render": rerender}) is result
    assert calls[-1]["trim"] == [0.0, 1.0]
    assert repair_subjects(result, target, subject_check, {"render": rerender}) is result
    assert calls[-1]["layout"] == "pad"


def test_fps_repair_caps_real_output(tmp_path: Path) -> None:
    result, target = _render(tmp_path)
    check = checks_mod.Check(
        "video.fps_max", target.id, "fail", True, 20.0, 10.0, "too fast"
    )

    repaired = repair_fps(result, target, check, {})
    target = Target(target.id, 320, 180, {"fps_max": Spec(10.0)})
    fps_check = next(
        item for item in check_video(repaired, target) if item.id == "video.fps_max"
    )

    assert fps_check.status == "pass"
