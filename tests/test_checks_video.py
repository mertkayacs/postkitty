from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.photo.framing import Box
from engine.verify import checks as checks_mod
from engine.verify import repair as repair_mod
from engine.video.checks import (
    check_video,
    repair_duration,
    repair_fps,
    repair_subjects,
)
from engine.video.render import VideoPlan, render_video


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
    kind: str = "video"


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


def test_minimum_failures_say_the_value_is_too_low(tmp_path: Path) -> None:
    result, _ = _render(tmp_path)
    target = Target(
        "short_video",
        320,
        180,
        {"duration_min": Spec(3), "fps_min": Spec(23), "bytes_min": Spec(75_000_000)},
    )

    checks = {check.id: check for check in check_video(result, target)}

    for key in ("video.duration_min", "video.fps_min", "video.bytes_min"):
        assert checks[key].status == "fail"
        assert "exceeds" not in checks[key].message
        assert "below" in checks[key].message


def test_checker_measures_a_rotated_phone_clip_at_its_display_size(tmp_path: Path) -> None:
    # Phones store landscape pixels with a rotate tag; players and platforms show them as portrait.
    import subprocess

    from engine.probe import probe

    flat = tmp_path / "flat.mp4"
    subprocess.run(
        [
            "nice", "-n", "10", "ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "2", "-y",
            "-f", "lavfi", "-i", "testsrc2=s=320x180:r=20:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(flat),
        ],
        check=True,
        capture_output=True,
    )
    portrait = tmp_path / "portrait.mp4"
    subprocess.run(
        [
            "nice", "-n", "10", "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-display_rotation", "-90", "-i", str(flat), "-c", "copy", str(portrait),
        ],
        check=True,
        capture_output=True,
    )
    info = probe(portrait, "check")
    assert (info.width, info.height) == (180, 320)
    result = checks_mod.RenderResult(
        "portrait", portrait, info.width, info.height, info.duration, portrait.stat().st_size
    )

    checks = {check.id: check for check in check_video(result, Target("portrait", 180, 320))}

    assert checks["video.width"].status == "pass"
    assert checks["video.height"].status == "pass"


def test_unpublished_defaults_are_advisory_for_a_user_file(tmp_path: Path) -> None:
    # A phone clip with Main profile and 44.1 kHz audio checked against a target whose platform
    # publishes neither rule must not be told it will be rejected.
    import subprocess

    source = tmp_path / "phone.mp4"
    subprocess.run(
        [
            "nice", "-n", "10", "ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "2", "-y",
            "-f", "lavfi", "-i", "testsrc2=s=320x180:r=20:d=1",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=1",
            "-c:v", "libx264", "-profile:v", "main", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-shortest", str(source),
        ],
        check=True,
        capture_output=True,
    )
    result = checks_mod.RenderResult("plain", source, 320, 180, 1.0, source.stat().st_size)

    checks = {check.id: check for check in check_video(result, Target("plain", 320, 180))}

    assert checks["video.profile"].status == "advisory"
    assert checks["audio.sample_rate"].status == "advisory"
    assert checks_mod.hard_pass(list(checks.values()))

    strict = Target("strict", 320, 180, {"video_profiles": Spec(["high"]), "audio_sample_rate": Spec(48000)})
    strict_checks = {check.id: check for check in check_video(result, strict)}
    assert strict_checks["video.profile"].status == "fail"
    assert strict_checks["audio.sample_rate"].status == "fail"


def test_low_frame_rate_is_repaired_into_the_platform_range(tmp_path: Path) -> None:
    # A 15 fps screen recording failed tiktok and instagram_reel (fps_min 23) with nothing to repair it.
    import subprocess

    source = tmp_path / "slow.mp4"
    subprocess.run(
        [
            "nice", "-n", "10", "ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "2", "-y",
            "-f", "lavfi", "-i", "testsrc2=s=320x180:r=15:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
        ],
        check=True,
        capture_output=True,
    )
    info = InputInfo(source, "slow", 320, 180, 2.0, 15.0)
    plan = VideoPlan("tiktok", "crop", (0.0, 2.0), 1.0, "proof", [Box(0.0, 0.0, 320.0, 180.0)] * 30)
    target = Target("tiktok", 320, 180, {"fps_min": Spec(23), "fps_max": Spec(60)})
    result = render_video(info, plan, target, tmp_path / "out.mp4", tmp_path / "work")
    before = {item.id: item for item in check_video(result, target)}
    assert before["video.fps_min"].status == "fail"

    repaired, after, repairs = repair_mod.check_and_repair(result, target, {})

    assert [item["check"] for item in repairs if item["ok"]] == ["video.fps_min"]
    found = {item.id: item for item in after}
    assert found["video.fps_min"].status == "pass"
    assert found["video.fps_max"].status == "pass"
    assert 23 <= found["video.fps_min"].measured <= 60


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


def test_audio_bitrate_repair_brings_a_reused_render_under_the_cap(tmp_path: Path) -> None:
    # A tiktok render at 160k was reused for instagram_reel and its audio.bitrate_max failure was final.
    import subprocess

    from engine.video.checks import repair_audio_bitrate

    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "nice", "-n", "10", "ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "2", "-y",
            "-f", "lavfi", "-i", "testsrc2=s=320x180:r=20:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(source),
        ],
        check=True,
        capture_output=True,
    )
    info = InputInfo(source, "audio-cap", 320, 180, 2.0, 20.0, has_audio=True)
    plan = VideoPlan("tiktok", "crop", (0.0, 2.0), 1.0, "proof", [Box(0.0, 0.0, 320.0, 180.0)] * 40)
    result = render_video(info, plan, Target("tiktok", 320, 180), tmp_path / "out.mp4", tmp_path / "work")
    target = Target("instagram_reel", 320, 180, {"audio_bps_max": Spec(128000)})
    check = next(item for item in check_video(result, target) if item.id == "audio.bitrate_max")
    assert check.status == "fail"

    repaired = repair_audio_bitrate(result, target, check, {})

    assert repair_mod._STRATEGIES["audio.bitrate_max"] is repair_audio_bitrate
    after = {item.id: item for item in check_video(repaired, target)}
    assert after["audio.bitrate_max"].status == "pass"
    assert after["video.codec"].status == "pass" and after["video.width"].status == "pass"


def test_quiet_audio_render_gets_an_advisory(tmp_path: Path) -> None:
    result, target = _render(tmp_path)
    result.extra["quiet_audio"] = True

    checks = {check.id: check for check in check_video(result, target)}

    assert checks["audio.level"].status == "advisory"
    assert "nearly silent" in checks["audio.level"].message
    assert checks_mod.hard_pass(list(checks.values()))
