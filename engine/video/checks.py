from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

from ..verify.checks import Check, RenderResult, register_checker
from ..verify.repair import register
from .render import run_ffmpeg


def _spec(target: Any, key: str) -> Any | None:
    return target.limits.get(key)


def _value(spec: Any | None, default: Any = None) -> Any:
    return default if spec is None else getattr(spec, "value", spec)


def _hard(spec: Any | None, default: bool = True) -> bool:
    return default if spec is None else getattr(spec, "enforcement", "hard") == "hard"


def _check(
    check_id: str,
    target: Any,
    measured: Any,
    expected: Any,
    passed: bool,
    message: str,
    spec: Any | None = None,
    default_hard: bool = True,
) -> Check:
    # A rule the platform does not publish is a sane default, so it only advises.
    hard = _hard(spec, default_hard)
    return Check(
        id=check_id,
        target=target.id,
        status="pass" if passed else "fail" if hard else "advisory",
        hard=hard,
        measured=measured,
        expected=expected,
        message=message,
        source_url=getattr(spec, "source_url", None),
        source_scope=getattr(spec, "source_scope", None),
        checked_on=getattr(spec, "checked_on", None),
    )


def _skipped(check_id: str, target: Any, expected: Any, message: str, spec: Any) -> Check:
    return Check(
        id=check_id,
        target=target.id,
        status="skipped",
        hard=_hard(spec),
        measured=None,
        expected=expected,
        message=message,
        source_url=getattr(spec, "source_url", None),
        source_scope=getattr(spec, "source_scope", None),
        checked_on=getattr(spec, "checked_on", None),
    )


def _probe(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=format_name,duration,size,bit_rate",
            "-show_entries",
            (
                "stream=index,codec_type,codec_name,profile,pix_fmt,width,height,"
                "avg_frame_rate,bit_rate,sample_rate:stream_side_data=rotation:stream_tags=rotate"
            ),
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _display_size(video: dict[str, Any]) -> tuple[int, int]:
    """Width and height as shown: phone clips store landscape pixels with a rotate tag."""
    rotation = 0.0
    for raw in [(video.get("tags") or {}).get("rotate")] + [
        item.get("rotation") for item in video.get("side_data_list") or []
    ][:1]:
        try:
            rotation = float(raw)
        except (TypeError, ValueError):
            continue
    width, height = int(video["width"]), int(video["height"])
    if int(rotation) % 180 == 90:
        return height, width
    return width, height


def _fps(value: str) -> float:
    return float(Fraction(value)) if value != "0/0" else 0.0


def check_video(result: RenderResult, target: Any) -> list[Check]:
    probe = _probe(result.file)
    video = next(
        stream for stream in probe["streams"] if stream["codec_type"] == "video"
    )
    audio = next(
        (stream for stream in probe["streams"] if stream["codec_type"] == "audio"),
        None,
    )
    format_info = probe["format"]
    duration = float(format_info["duration"])
    size = int(format_info["size"])
    fps = _fps(video["avg_frame_rate"])
    checks: list[Check] = []

    container_spec = _spec(target, "containers")
    containers = _value(container_spec, ["mp4"])
    measured_containers = format_info["format_name"].split(",")
    checks.append(
        _check(
            "video.container",
            target,
            measured_containers,
            containers,
            any(item in containers for item in measured_containers),
            (
                "The video container is allowed."
                if any(item in containers for item in measured_containers)
                else "The video container is not allowed."
            ),
            container_spec,
        )
    )

    codec_spec = _spec(target, "video_codecs")
    codecs = _value(codec_spec, ["h264"])
    checks.append(
        _check(
            "video.codec",
            target,
            video["codec_name"],
            codecs,
            video["codec_name"] in codecs,
            "The video codec is allowed." if video["codec_name"] in codecs else "The video codec is not allowed.",
            codec_spec,
            default_hard=False,
        )
    )

    profile_spec = _spec(target, "video_profiles")
    profiles = _value(profile_spec, ["high"])
    profile = str(video.get("profile", "")).lower()
    checks.append(
        _check(
            "video.profile",
            target,
            profile,
            profiles,
            profile in {str(item).lower() for item in profiles},
            (
                "The H.264 profile is allowed."
                if profile in {str(item).lower() for item in profiles}
                else "The H.264 profile is not allowed."
            ),
            profile_spec,
            default_hard=False,
        )
    )

    pixel_spec = _spec(target, "pixel_formats")
    pixel_formats = _value(pixel_spec, ["yuv420p"])
    checks.append(
        _check(
            "video.pix_fmt",
            target,
            video.get("pix_fmt"),
            pixel_formats,
            video.get("pix_fmt") in pixel_formats,
            "The pixel format is allowed." if video.get("pix_fmt") in pixel_formats else "The pixel format is not allowed.",
            pixel_spec,
            default_hard=False,
        )
    )

    for dimension, measured in zip(("width", "height"), _display_size(video), strict=True):
        expected = getattr(target, dimension)
        checks.append(
            _check(
                f"video.{dimension}",
                target,
                measured,
                expected,
                measured == expected,
                f"The video {dimension} is exact." if measured == expected else f"The video {dimension} is not exact.",
            )
        )

    range_checks = (
        ("fps_min", fps, lambda measured, expected: measured >= expected, "frame rate"),
        ("fps_max", fps, lambda measured, expected: measured <= expected, "frame rate"),
        ("duration_min", duration, lambda measured, expected: measured >= expected, "duration"),
        ("duration_max", duration, lambda measured, expected: measured <= expected + 0.05, "duration"),
        ("bytes_min", size, lambda measured, expected: measured >= expected, "file size"),
        ("bytes_max", size, lambda measured, expected: measured <= expected, "file size"),
    )
    for key, measured, compare, label in range_checks:
        spec = _spec(target, key)
        if spec is None:
            continue
        expected = _value(spec)
        passed = compare(measured, expected)
        message = (
            f"The video {label} meets the {key.removeprefix(label.split()[0] + '_')} limit."
            if passed
            else f"The video {label} is below its minimum."
            if key.endswith("_min")
            else f"The video {label} exceeds its maximum."
        )
        if key == "duration_max" and not passed and not _hard(spec):
            message = (
                f"The video is {round(measured, 1):g} s long, longer than the {expected:g} s recommended "
                f"for {target.id}. "
                "It was not cut."
            )
        elif key == "duration_max" and passed and result.extra.get("cut_to_duration_max"):
            start, end = result.extra["trim"]
            message = (
                f"The video was cut to the {expected:g} s {target.id} allows; "
                f"it keeps {start:g} s to {end:g} s of the source."
            )
        checks.append(_check(f"video.{key}", target, measured, expected, passed, message, spec))

    bitrate_spec = _spec(target, "video_bps_max")
    if bitrate_spec is not None:
        if video.get("bit_rate"):
            video_bitrate = int(video["bit_rate"])
        else:
            audio_bitrate = int(audio.get("bit_rate", 0)) if audio else 0
            video_bitrate = max(0, round(size * 8 / duration) - audio_bitrate)
        maximum = int(_value(bitrate_spec))
        checks.append(
            _check(
                "video.bitrate_max",
                target,
                video_bitrate,
                maximum,
                video_bitrate <= maximum,
                "The video bitrate is within the limit." if video_bitrate <= maximum else "The video bitrate exceeds the limit.",
                bitrate_spec,
            )
        )

    sample_rate_spec = _spec(target, "audio_sample_rate")
    expected_rate = int(_value(sample_rate_spec, 48000))
    if audio is None:
        checks.append(
            _skipped(
                "audio.sample_rate",
                target,
                expected_rate,
                "The source has no audio stream.",
                sample_rate_spec,
            )
        )
    else:
        sample_rate = int(audio["sample_rate"])
        checks.append(
            _check(
                "audio.sample_rate",
                target,
                sample_rate,
                expected_rate,
                sample_rate == expected_rate,
                "The audio sample rate is exact." if sample_rate == expected_rate else "The audio sample rate is not exact.",
                sample_rate_spec,
                default_hard=False,
            )
        )

    audio_bitrate_spec = _spec(target, "audio_bps_max")
    if audio_bitrate_spec is not None:
        maximum = int(_value(audio_bitrate_spec))
        if audio is None:
            checks.append(
                _skipped(
                    "audio.bitrate_max",
                    target,
                    maximum,
                    "The source has no audio stream.",
                    audio_bitrate_spec,
                )
            )
        else:
            bitrate = int(audio.get("bit_rate", 0))
            checks.append(
                _check(
                    "audio.bitrate_max",
                    target,
                    bitrate,
                    maximum,
                    bitrate <= maximum,
                    "The audio bitrate is within the limit." if bitrate <= maximum else "The audio bitrate exceeds the limit.",
                    audio_bitrate_spec,
                )
            )

    if result.extra.get("quiet_audio"):
        checks.append(
            _check(
                "audio.level",
                target,
                "below -50 dBFS",
                "speech level",
                False,
                "The audio is nearly silent, so it was kept at its own level instead of being normalised.",
                default_hard=False,
            )
        )

    captions = result.extra.get("captions")
    if captions is not None and not captions["shown"]:
        checks.append(
            _check(
                "captions.shown",
                target,
                0,
                "at least 1",
                False,
                "No caption falls inside the trimmed part of the video, so none was burned in.",
                default_hard=False,
            )
        )

    if result.subjects_inside is None:
        checks.append(
            _skipped(
                "frame.subjects_inside",
                target,
                0.98,
                "Subject framing data is unavailable.",
                None,
            )
        )
    else:
        checks.append(
            _check(
                "frame.subjects_inside",
                target,
                result.subjects_inside,
                0.98,
                result.subjects_inside >= 0.98,
                (
                    "Subjects stay inside the frame."
                    if result.subjects_inside >= 0.98
                    else "Subjects leave the frame in too many sampled frames."
                ),
            )
        )
    return checks


def _refresh(result: RenderResult) -> RenderResult:
    probe = _probe(result.file)
    video = next(
        stream for stream in probe["streams"] if stream["codec_type"] == "video"
    )
    extra = dict(result.extra)
    extra["probe"] = probe
    width, height = _display_size(video)
    return replace(
        result,
        width=width,
        height=height,
        duration=float(probe["format"]["duration"]),
        bytes=int(probe["format"]["size"]),
        extra=extra,
    )


def _transcode(
    result: RenderResult,
    *,
    video_bitrate: int | None = None,
    duration: float | None = None,
    fps: float | None = None,
    audio_bitrate: int = 128000,
    copy_video: bool = False,
) -> RenderResult:
    temporary = result.file.with_name(result.file.stem + ".repair.mp4")
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
        "-y",
        "-i",
        str(result.file),
    ]
    if duration is not None:
        command.extend(["-t", str(duration)])
    if fps is not None:
        command.extend(["-vf", f"fps={fps},format=yuv420p"])
    if copy_video:
        command.extend(["-c:v", "copy"])
    else:
        command.extend(["-c:v", "libx264", "-profile:v", "high", "-preset", "medium"])
        if video_bitrate is None:
            command.extend(["-crf", "20"])
        else:
            command.extend(
                [
                    "-b:v",
                    str(video_bitrate),
                    "-maxrate",
                    str(video_bitrate),
                    "-bufsize",
                    str(video_bitrate * 2),
                ]
            )
    command.extend(
        [
            "-c:a",
            "aac",
            "-profile:a",
            "aac_low",
            "-ar",
            "48000",
            "-b:a",
            str(audio_bitrate),
            "-movflags",
            "+faststart",
            "-f",
            "mp4",
            str(temporary),
        ]
    )
    try:
        run_ffmpeg(command, f"repairing {result.file.name}")
        temporary.replace(result.file)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return _refresh(result)


def _call_rerender(rerender: dict[str, Any], updates: dict[str, Any]) -> RenderResult | None:
    callback: Callable[..., RenderResult] | None = rerender.get("render") or rerender.get("rerender")
    if callback is None:
        return None
    current = dict(rerender.get("overrides", {}))
    current.update(updates)
    try:
        return callback(current)
    except TypeError:
        return callback(overrides=current)


def repair_bitrate(
    result: RenderResult, target: Any, check: Check, rerender: dict[str, Any]
) -> RenderResult:
    maximum = int(check.expected)
    # AAC lands a little above its nominal rate, so stay under the platform cap.
    audio_maximum = int(int(_value(_spec(target, "audio_bps_max"), 128000)) * 0.94)
    bitrate = max(100000, round(maximum * 0.92))
    return _transcode(result, video_bitrate=bitrate, audio_bitrate=audio_maximum)


def repair_audio_bitrate(
    result: RenderResult, target: Any, check: Check, rerender: dict[str, Any]
) -> RenderResult:
    # AAC lands a little above its nominal rate, so stay under the platform cap. The video is untouched.
    return _transcode(
        result, audio_bitrate=int(int(check.expected) * 0.94), copy_video=True
    )


def repair_size(
    result: RenderResult, target: Any, check: Check, rerender: dict[str, Any]
) -> RenderResult | None:
    if not result.duration:
        return None
    # AAC lands a little above its nominal rate, so stay under the platform cap.
    audio_maximum = int(int(_value(_spec(target, "audio_bps_max"), 128000)) * 0.94)
    total_bitrate = int(check.expected * 8 / result.duration * 0.9)
    video_bitrate = max(100000, total_bitrate - audio_maximum)
    platform_maximum = _value(_spec(target, "video_bps_max"))
    if platform_maximum is not None:
        video_bitrate = min(video_bitrate, int(platform_maximum * 0.92))
    return _transcode(
        result, video_bitrate=video_bitrate, audio_bitrate=audio_maximum
    )


def repair_duration(
    result: RenderResult, target: Any, check: Check, rerender: dict[str, Any]
) -> RenderResult | None:
    trim = result.extra.get("trim")
    if trim:
        repaired = _call_rerender(
            rerender, {"trim": [float(trim[0]), float(trim[0]) + float(check.expected)]}
        )
        if repaired is not None:
            return repaired
    return _transcode(result, duration=float(check.expected))


def repair_fps(
    result: RenderResult, target: Any, check: Check, rerender: dict[str, Any]
) -> RenderResult:
    return _transcode(result, fps=float(check.expected))


def repair_fps_min(
    result: RenderResult, target: Any, check: Check, rerender: dict[str, Any]
) -> RenderResult:
    # Re-time a slow source to 30 fps when the platform range allows it, else to its minimum.
    minimum = float(check.expected)
    maximum = _value(_spec(target, "fps_max"))
    fps = 30.0 if minimum <= 30.0 and (maximum is None or float(maximum) >= 30.0) else minimum
    return _transcode(result, fps=fps)


def repair_subjects(
    result: RenderResult, target: Any, check: Check, rerender: dict[str, Any]
) -> RenderResult | None:
    return _call_rerender(rerender, {"layout": "pad"})


register_checker("video", check_video)
register("video.bytes_max", repair_size)
register("video.bitrate_max", repair_bitrate)
register("audio.bitrate_max", repair_audio_bitrate)
register("video.duration_max", repair_duration)
register("video.fps_max", repair_fps)
register("video.fps_min", repair_fps_min)
register("frame.subjects_inside", repair_subjects)
