from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np

from .camera import build_camera_path
from .scan import VideoScan


@dataclass(frozen=True)
class VideoPlan:
    target: str
    layout: Literal["crop", "split", "speaker", "pad"]
    trim: tuple[float, float]
    cover_at: float
    note: str
    windows: list[Any]
    subjects_inside: float = 1.0
    normalize_audio: bool = True


def _limit(target: Any, key: str, default: Any = None) -> Any:
    value = target.limits.get(key)
    if value is None:
        return default
    return getattr(value, "value", value)


def _best_trim(scan: VideoScan, duration: float, maximum: float) -> tuple[float, float]:
    if duration <= maximum:
        return 0.0, duration
    latest = duration - maximum
    starts = [index / 2 for index in range(math.floor(latest * 2) + 1)]
    if not math.isclose(starts[-1], latest):
        starts.append(latest)

    face_times = [
        float(frame["t"]) for frame in scan.faces["frames"] if frame["faces"]
    ]
    best_start = 0.0
    best_score = -1.0
    for start in starts:
        end = start + maximum
        face_score = sum(start <= t < end for t in face_times)
        audio_score = sum(
            10 ** (dbfs / 20) for t, dbfs in scan.audio_rms if start <= t < end
        )
        score = face_score + audio_score
        if score > best_score:
            best_start = start
            best_score = score
    return best_start, best_start + maximum


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


def _sharpest_cover(info: Any, scan: VideoScan, trim: tuple[float, float]) -> float:
    sample_fps = float(scan.faces["sample_fps"])
    cuts = [start for start, _ in scan.scenes[1:]]
    candidates = {
        round((float(frame["t"]) - trim[0]) * sample_fps)
        for frame in scan.faces["frames"]
        if frame["faces"]
        and trim[0] <= float(frame["t"]) < trim[1]
        and all(abs(float(frame["t"]) - cut) >= 0.5 for cut in cuts)
    }
    if not candidates:
        return (trim[0] + trim[1]) / 2

    width = min(640, info.width)
    height = max(2, round(info.height * width / info.width / 2) * 2)
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
        str(trim[0]),
        "-t",
        str(trim[1] - trim[0]),
        "-i",
        str(info.path),
        "-vf",
        f"fps={sample_fps},scale={width}:{height}",
        "-an",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert process.stdout is not None
    frame_size = width * height
    best_index = min(candidates)
    best_score = -1.0
    index = 0
    try:
        while True:
            raw = _read_exact(process.stdout, frame_size)
            if len(raw) != frame_size:
                break
            if index in candidates:
                image = np.frombuffer(raw, dtype=np.uint8).reshape((height, width))
                score = float(cv2.Laplacian(image, cv2.CV_64F).var())
                if score > best_score:
                    best_index = index
                    best_score = score
            index += 1
    finally:
        process.stdout.close()
        return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"ffmpeg cover scan failed with exit code {return_code}")
    return min(trim[1], trim[0] + best_index / sample_fps)


def plan_video(
    info: Any,
    scan: VideoScan,
    target: Any,
    override: dict[str, Any] | None = None,
) -> VideoPlan:
    if info.duration is None or info.duration <= 0:
        raise ValueError("video duration must be positive")
    override = override or {}
    if "trim" in override:
        trim = tuple(float(value) for value in override["trim"])
        if len(trim) != 2 or trim[0] < 0 or trim[1] <= trim[0] or trim[1] > info.duration:
            raise ValueError("trim must be inside the source duration")
    else:
        maximum = float(_limit(target, "duration_max", info.duration))
        trim = _best_trim(scan, info.duration, maximum)

    camera = build_camera_path(
        info,
        scan,
        target,
        trim,
        focus=override.get("focus", "auto"),
        layout_override=override.get("layout", "auto"),
    )
    if "cover_at" in override:
        cover_at = float(override["cover_at"])
        if not trim[0] <= cover_at <= trim[1]:
            raise ValueError("cover_at must be inside the trim")
    else:
        cover_at = _sharpest_cover(info, scan, trim)
    # Room tone at -70 dBFS must not be boosted 55 dB to the platform loudness.
    levels = [dbfs for t, dbfs in scan.audio_rms if trim[0] <= t < trim[1]]
    return VideoPlan(
        target=target.id,
        layout=camera.layout,
        trim=trim,
        cover_at=cover_at,
        note=camera.note,
        windows=camera.windows,
        subjects_inside=camera.subjects_inside,
        normalize_audio=not levels or max(levels) >= -50.0,
    )


def _even(value: float) -> int:
    return max(2, round(value / 2) * 2)


def _position(value: float, maximum: int) -> int:
    return min(max(0, round(value)), maximum)


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _window_values(window: Any, width: int, height: int) -> tuple[int, int, int, int]:
    crop_width = min(_even(window.w), width - width % 2)
    crop_height = min(_even(window.h), height - height % 2)
    x = _position(window.x, width - crop_width)
    y = _position(window.y, height - crop_height)
    return crop_width, crop_height, x, y


def _write_commands(
    plan: VideoPlan,
    info: Any,
    fps: float,
    path: Path,
) -> None:
    lines = []
    for index, window in enumerate(plan.windows):
        t = index / fps
        if plan.layout == "split":
            _, _, top_x, top_y = _window_values(window[0], info.width, info.height)
            _, _, bottom_x, bottom_y = _window_values(
                window[1], info.width, info.height
            )
            lines.append(
                f"{t:.6f} crop@top x {top_x}, crop@top y {top_y}, "
                f"crop@bottom x {bottom_x}, crop@bottom y {bottom_y};"
            )
        else:
            _, _, x, y = _window_values(window, info.width, info.height)
            lines.append(f"{t:.6f} crop@c x {x}, crop@c y {y};")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _crop_filter(
    info: Any,
    plan: VideoPlan,
    target: Any,
    fps: float,
    commands_path: Path,
) -> str:
    command_file = _escape_filter_path(commands_path)
    prefix = f"[0:v]setpts=PTS-STARTPTS,fps={fps},sendcmd=f='{command_file}'"
    if plan.layout == "split":
        top = _window_values(plan.windows[0][0], info.width, info.height)
        bottom = _window_values(plan.windows[0][1], info.width, info.height)
        # 4:2:0 frames need even panel heights; ffmpeg 6.1 corrupts its heap scaling to an odd height (1350 / 2).
        panel_height = _even(target.height / 2)
        return (
            f"{prefix},split=2[topin][bottomin];"
            f"[topin]crop@top={top[0]}:{top[1]}:{top[2]}:{top[3]},"
            f"scale={target.width}:{panel_height}:flags=lanczos[top];"
            f"[bottomin]crop@bottom={bottom[0]}:{bottom[1]}:{bottom[2]}:{bottom[3]},"
            f"scale={target.width}:{target.height - panel_height}:flags=lanczos[bottom];"
            "[top][bottom]vstack=inputs=2,setsar=1,format=yuv420p[v]"
        )
    window = _window_values(plan.windows[0], info.width, info.height)
    return (
        f"{prefix},crop@c={window[0]}:{window[1]}:{window[2]}:{window[3]},"
        f"scale={target.width}:{target.height}:flags=lanczos,"
        "setsar=1,format=yuv420p[v]"
    )


def _pad_filter(target: Any, fps: float) -> str:
    return (
        f"[0:v]setpts=PTS-STARTPTS,fps={fps},split=2[background][foreground];"
        f"[background]scale={target.width}:{target.height}:"
        "force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={target.width}:{target.height},boxblur=20:10,"
        "eq=brightness=-0.25[fill];"
        f"[foreground]scale={target.width}:{target.height}:"
        "force_original_aspect_ratio=decrease:flags=lanczos[front];"
        "[fill][front]overlay=(W-w)/2:(H-h)/2:shortest=1,"
        "setsar=1,format=yuv420p[v]"
    )


def _audio_bitrate(info: Any, target: Any) -> str | None:
    if not info.has_audio:
        return None
    audio_cap = _limit(target, "audio_bps_max")
    if audio_cap is not None:
        # AAC lands a little above its nominal rate, so stay under the platform cap.
        return str(int(int(audio_cap) * 0.94))
    return "128k" if target.id in {"instagram_reel", "facebook_reel"} else "160k"


def _plan_key(
    info: Any, plan: VideoPlan, target: Any, loudness_lufs: float, audio_bitrate: str | None
) -> str:
    windows = []
    for window in plan.windows:
        items = window if plan.layout == "split" else (window,)
        windows.append(
            [[round(box.x, 3), round(box.y, 3), round(box.w, 3), round(box.h, 3)] for box in items]
        )
    payload = json.dumps(
        {
            "source": info.sha256,
            "size": [target.width, target.height],
            "layout": plan.layout,
            "trim": plan.trim,
            "windows": windows,
            "loudness_lufs": loudness_lufs,
            "audio_bitrate": audio_bitrate,
            "normalize_audio": plan.normalize_audio,
        },
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def _probe_render(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-show_entries",
            (
                "stream=index,codec_type,codec_name,profile,pix_fmt,width,height,"
                "avg_frame_rate,bit_rate,sample_rate"
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


def _render_result(
    plan: VideoPlan, target: Any, path: Path, probe: dict[str, Any]
) -> Any:
    from ..verify.checks import RenderResult

    video = next(
        stream for stream in probe["streams"] if stream["codec_type"] == "video"
    )
    return RenderResult(
        target=target.id,
        file=path,
        width=int(video["width"]),
        height=int(video["height"]),
        duration=float(probe["format"]["duration"]),
        bytes=int(probe["format"]["size"]),
        layout={"mode": plan.layout, "note": plan.note},
        subjects_inside=plan.subjects_inside,
        extra={"trim": list(plan.trim), "probe": probe, "quiet_audio": not plan.normalize_audio},
    )


def render_video(
    info: Any,
    plan: VideoPlan,
    target: Any,
    out_path: Path,
    work_dir: Path,
    loudness_lufs: float = -14.0,
) -> Any:
    if not plan.windows:
        raise ValueError("video plan has no camera windows")
    fps = min(float(info.fps), 60.0)
    render_dir = work_dir / "render"
    render_dir.mkdir(parents=True, exist_ok=True)
    audio_bitrate = _audio_bitrate(info, target)
    key = _plan_key(info, plan, target, loudness_lufs, audio_bitrate)
    master = render_dir / f"reuse-{key}.mp4"
    commands_path = render_dir / f"reuse-{key}.commands"
    if not master.exists():
        if plan.layout == "pad":
            filter_graph = _pad_filter(target, fps)
        else:
            _write_commands(plan, info, fps, commands_path)
            filter_graph = _crop_filter(info, plan, target, fps, commands_path)

        temporary = master.with_name(master.stem + ".tmp.mp4")
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
            "-ss",
            str(plan.trim[0]),
            "-t",
            str(plan.trim[1] - plan.trim[0]),
            "-i",
            str(info.path),
            "-filter_complex",
            filter_graph
            + (
                ""
                if not info.has_audio
                else f";[0:a]loudnorm=I={loudness_lufs:g}:TP=-1.5:LRA=11,aresample=48000[a]"
                if plan.normalize_audio
                else ";[0:a]aresample=48000[a]"
            ),
            "-map",
            "[v]",
        ]
        if audio_bitrate is not None:
            command.extend(
                [
                    "-map",
                    "[a]",
                    "-c:a",
                    "aac",
                    "-profile:a",
                    "aac_low",
                    "-ar",
                    "48000",
                    "-b:a",
                    audio_bitrate,
                ]
            )
        else:
            command.append("-an")
        command.extend(
            [
                "-c:v",
                "libx264",
                "-profile:v",
                "high",
                "-preset",
                "medium",
                "-crf",
                "20",
            ]
        )
        maximum_bitrate = _limit(target, "video_bps_max")
        if maximum_bitrate is not None:
            command.extend(
                [
                    "-maxrate",
                    str(maximum_bitrate),
                    "-bufsize",
                    str(int(maximum_bitrate) * 2),
                ]
            )
        command.extend(
            [
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                str(temporary),
            ]
        )
        try:
            subprocess.run(command, check=True, capture_output=True)
            temporary.replace(master)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.resolve() != master.resolve():
        shutil.copy2(master, out_path)
    probe = _probe_render(out_path)
    return _render_result(plan, target, out_path, probe)


def _cover_filter(info: Any, plan: VideoPlan, target: Any, index: int) -> str:
    if plan.layout == "pad":
        return _pad_filter(target, 1.0).replace("fps=1.0,", "")
    if plan.layout == "split":
        top = _window_values(plan.windows[index][0], info.width, info.height)
        bottom = _window_values(plan.windows[index][1], info.width, info.height)
        # 4:2:0 frames need even panel heights; ffmpeg 6.1 corrupts its heap scaling to an odd height (1350 / 2).
        panel_height = _even(target.height / 2)
        return (
            f"[0:v]split=2[topin][bottomin];"
            f"[topin]crop={top[0]}:{top[1]}:{top[2]}:{top[3]},"
            f"scale={target.width}:{panel_height}:flags=lanczos[top];"
            f"[bottomin]crop={bottom[0]}:{bottom[1]}:{bottom[2]}:{bottom[3]},"
            f"scale={target.width}:{target.height - panel_height}:flags=lanczos[bottom];"
            "[top][bottom]vstack=inputs=2,setsar=1[v]"
        )
    window = _window_values(plan.windows[index], info.width, info.height)
    return (
        f"[0:v]crop={window[0]}:{window[1]}:{window[2]}:{window[3]},"
        f"scale={target.width}:{target.height}:flags=lanczos,setsar=1[v]"
    )


def export_cover(info: Any, plan: VideoPlan, target: Any, out_path: Path) -> Path:
    fps = min(float(info.fps), 60.0)
    index = min(
        len(plan.windows) - 1,
        max(0, round((plan.cover_at - plan.trim[0]) * fps)),
    )
    # A seek at or past the last frame decodes nothing and ffmpeg still exits 0 without a file.
    seek_at = max(plan.trim[0], min(plan.cover_at, plan.trim[1] - 1.0 / fps))
    out_path.parent.mkdir(parents=True, exist_ok=True)
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
        "-ss",
        str(seek_at),
        "-i",
        str(info.path),
        "-filter_complex",
        _cover_filter(info, plan, target, index),
        "-map",
        "[v]",
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(out_path),
    ]
    subprocess.run(command, check=True, capture_output=True)
    if not out_path.is_file():
        raise RuntimeError(f"ffmpeg decoded no cover frame at {seek_at:.3f} s")
    return out_path
