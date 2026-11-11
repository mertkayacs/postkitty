from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np

from .camera import build_camera_path
from .captions import Captions, ass_document, load_captions
from .scan import VideoScan, read_exact

# Platforms take one or two audio channels, so surround sources are mixed down and mono stays mono.
_STEREO_AT_MOST = "aformat=channel_layouts=mono|stereo"


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
    captions: Captions | None = None
    cut_to_duration_max: bool = False


@cache
def _filters() -> frozenset[str]:
    try:
        listing = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        return frozenset()
    return frozenset(re.findall(r"^\s*\S+\s+(\S+)\s+\S*->", listing, re.MULTILINE))


def has_filter(name: str) -> bool:
    """Whether this ffmpeg build has the filter ``name``; minimal builds leave out libass and zimg."""
    return name in _filters()


def run_ffmpeg(command: list[str], doing: str) -> None:
    """Run an ffmpeg command. A failure says what was being made and quotes ffmpeg's last lines."""
    try:
        subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"could not start ffmpeg while {doing}: {exc}; install ffmpeg and retry") from exc
    except subprocess.CalledProcessError as exc:
        lines = (exc.stderr or b"").decode(errors="replace").strip().splitlines()
        detail = " | ".join(lines[-3:]) or f"exit code {exc.returncode}"
        raise RuntimeError(f"ffmpeg failed while {doing}: {detail}") from exc


@cache
def _hdr_transfer(path: Path, sha256: str) -> str | None:
    """The transfer curve of an HDR source (PQ or HLG), else ``None``. Cached by content hash."""
    probed = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "V:0", "-show_entries", "stream=color_transfer",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return probed if probed in {"smpte2084", "arib-std-b67"} else None


def _to_sdr(info: Any) -> str:
    """Filters that tone-map an HDR frame to 8-bit BT.709, or nothing for an SDR source.

    Without this the 8-bit output keeps the BT.2020 and HLG or PQ tags and plays washed out.
    """
    transfer = _hdr_transfer(Path(info.path), info.sha256)
    if transfer is None:
        return ""
    if not has_filter("zscale"):
        raise ValueError(
            f"{Path(info.path).name} is HDR video and this ffmpeg build has no zscale filter to convert it; "
            "install an ffmpeg build with libzimg or export the clip as SDR"
        )
    return (
        f",zscale=tin={transfer}:min=bt2020nc:pin=bt2020:t=linear:npl=100,format=gbrpf32le,"
        "zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
    )


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
            raw = read_exact(process.stdout, frame_size)
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
    captions = load_captions(override["captions"]) if override.get("captions") else None
    if captions is not None and not has_filter("ass"):
        raise ValueError(
            "this ffmpeg build has no libass, so it cannot burn captions in; "
            "install an ffmpeg build with libass or leave out the captions override"
        )
    if "trim" in override:
        trim = tuple(float(value) for value in override["trim"])
        if len(trim) != 2 or trim[0] < 0 or trim[1] <= trim[0]:
            raise ValueError(f"trim must be [start, end] in seconds with 0 <= start < end, got {list(trim)}")
        if trim[0] >= info.duration:
            raise ValueError(f"trim starts at {trim[0]:g} s but the video is {info.duration:g} s long")
        trim = (trim[0], min(trim[1], info.duration))
    else:
        # Only a cap the platform enforces may cut the user's video. A recommended length is left to the check.
        cap = target.limits.get("duration_max")
        enforced = cap is not None and getattr(cap, "enforcement", "hard") == "hard"
        trim = _best_trim(scan, info.duration, float(_limit(target, "duration_max")) if enforced else info.duration)
    cut = "trim" not in override and trim[1] - trim[0] < info.duration

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
            raise ValueError(
                f"cover_at {cover_at:g} s is outside the trim ({trim[0]:g} s to {trim[1]:g} s)"
            )
    else:
        cover_at = _sharpest_cover(info, scan, trim)
    # Room tone at -70 dBFS must not be boosted 55 dB to the platform loudness.
    levels = [dbfs for t, dbfs in scan.audio_rms if trim[0] <= t < trim[1]]
    return VideoPlan(
        target=target.id,
        layout=camera.layout,
        trim=trim,
        cover_at=cover_at,
        note=(
            f"{camera.note} The video is cut to the {trim[1] - trim[0]:g} s {target.id} allows, "
            f"from {trim[0]:g} s to {trim[1]:g} s."
        ).strip()
        if cut
        else camera.note,
        windows=camera.windows,
        subjects_inside=camera.subjects_inside,
        normalize_audio=not levels or max(levels) >= -50.0,
        captions=captions,
        cut_to_duration_max=cut,
    )


def _even(value: float) -> int:
    return max(2, round(value / 2) * 2)


def _position(value: float, maximum: int) -> int:
    return min(max(0, round(value)), maximum)


def _escape_filter_path(path: Path) -> str:
    """``path`` as a filter option value that the caller wraps in single quotes.

    The option parser reads backslash, colon and quote as syntax. A quoted graph string cannot hold
    a quote, so each one closes the string, adds an escaped quote and opens it again.
    """
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "'\\\\\\''")


def _window_values(window: Any, width: int, height: int) -> tuple[int, int, int, int]:
    crop_width = min(_even(window.w), width - width % 2)
    crop_height = min(_even(window.h), height - height % 2)
    x = _position(window.x, width - crop_width)
    y = _position(window.y, height - crop_height)
    return crop_width, crop_height, x, y


def _source(info: Any, fps: float | None) -> str:
    """Head of every video graph: the source as square pixels at the probed display size.

    Camera windows are in display coordinates, so an anamorphic source is resampled to that size
    first. For square-pixel sources the scale has nothing to do and ffmpeg passes frames through.
    """
    timing = "" if fps is None else f"setpts=PTS-STARTPTS,fps={fps},"
    return f"[0:v]{timing}scale={info.width}:{info.height},setsar=1"


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
    fps: float | None,
    commands_path: Path | None,
    index: int = 0,
) -> str:
    """Graph for the crop, speaker and split layouts.

    A render moves the windows over time through the commands file. A cover has no commands and
    holds the windows of frame ``index``.
    """
    prefix = _source(info, fps)
    if commands_path is not None:
        prefix += f",sendcmd=f='{_escape_filter_path(commands_path)}'"
    if plan.layout == "split":
        top = _window_values(plan.windows[index][0], info.width, info.height)
        bottom = _window_values(plan.windows[index][1], info.width, info.height)
        # 4:2:0 frames need even panel heights; ffmpeg 6.1 corrupts its heap scaling to an odd height (1350 / 2).
        panel_height = _even(target.height / 2)
        return (
            f"{prefix},split=2[topin][bottomin];"
            f"[topin]crop@top={top[0]}:{top[1]}:{top[2]}:{top[3]},"
            f"scale={target.width}:{panel_height}:flags=lanczos[top];"
            f"[bottomin]crop@bottom={bottom[0]}:{bottom[1]}:{bottom[2]}:{bottom[3]},"
            f"scale={target.width}:{target.height - panel_height}:flags=lanczos[bottom];"
            "[top][bottom]vstack=inputs=2,setsar=1"
        )
    window = _window_values(plan.windows[index], info.width, info.height)
    return (
        f"{prefix},crop@c={window[0]}:{window[1]}:{window[2]}:{window[3]},"
        f"scale={target.width}:{target.height}:flags=lanczos,setsar=1"
    )


def _pad_filter(info: Any, target: Any, fps: float | None) -> str:
    # The fit and fill sizes are worked out here: every scale needs an even size, and the scale
    # options that would round for us are missing from older ffmpeg builds.
    fit = min(target.width / info.width, target.height / info.height)
    fill = max(target.width / info.width, target.height / info.height)
    front = (min(target.width, _even(info.width * fit)), min(target.height, _even(info.height * fit)))
    back = tuple(
        max(wanted, math.ceil(round(size * fill, 3) / 2) * 2)
        for wanted, size in ((target.width, info.width), (target.height, info.height))
    )
    return (
        f"{_source(info, fps)},split=2[background][foreground];"
        f"[background]scale={back[0]}:{back[1]}:flags=lanczos,"
        f"crop={target.width}:{target.height},boxblur=20:10,"
        "eq=brightness=-0.25[fill];"
        f"[foreground]scale={front[0]}:{front[1]}:flags=lanczos[front];"
        "[fill][front]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1"
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
    info: Any, plan: VideoPlan, target: Any, loudness_lufs: float, audio_bitrate: str | None, subtitles: str
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
            "subtitles": subtitles,
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
    plan: VideoPlan, target: Any, path: Path, probe: dict[str, Any], captions_shown: int
) -> Any:
    from ..verify.checks import RenderResult

    video = next(
        stream for stream in probe["streams"] if stream["codec_type"] == "video"
    )
    extra = {
        "trim": list(plan.trim),
        "probe": probe,
        "quiet_audio": not plan.normalize_audio,
        "cut_to_duration_max": plan.cut_to_duration_max,
    }
    if plan.captions is not None:
        extra["captions"] = {"file": str(plan.captions.file), "shown": captions_shown}
    return RenderResult(
        target=target.id,
        file=path,
        width=int(video["width"]),
        height=int(video["height"]),
        duration=float(probe["format"]["duration"]),
        bytes=int(probe["format"]["size"]),
        layout={"mode": plan.layout, "note": plan.note},
        subjects_inside=plan.subjects_inside,
        extra=extra,
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
    subtitles, captions_shown = "", 0
    if plan.captions is not None:
        subtitles, captions_shown = ass_document(plan.captions, target, plan.trim)
    key = _plan_key(info, plan, target, loudness_lufs, audio_bitrate, subtitles if captions_shown else "")
    master = render_dir / f"reuse-{key}.mp4"
    commands_path = render_dir / f"reuse-{key}.commands"
    if not master.exists():
        if plan.layout == "pad":
            filter_graph = _pad_filter(info, target, fps)
        else:
            _write_commands(plan, info, fps, commands_path)
            filter_graph = _crop_filter(info, plan, target, fps, commands_path)
        filter_graph += _to_sdr(info)
        if captions_shown:
            subtitles_path = render_dir / f"reuse-{key}.ass"
            subtitles_path.write_text(subtitles, encoding="utf-8")
            filter_graph += f",ass=f='{_escape_filter_path(subtitles_path)}'"
        filter_graph += ",format=yuv420p[v]"

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
                else f";[0:a]loudnorm=I={loudness_lufs:g}:TP=-1.5:LRA=11,aresample=48000,{_STEREO_AT_MOST}[a]"
                if plan.normalize_audio
                else f";[0:a]aresample=48000,{_STEREO_AT_MOST}[a]"
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
            run_ffmpeg(command, f"rendering {target.id}")
            temporary.replace(master)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.resolve() != master.resolve():
        shutil.copy2(master, out_path)
    probe = _probe_render(out_path)
    return _render_result(plan, target, out_path, probe, captions_shown)


def export_cover(info: Any, plan: VideoPlan, target: Any, out_path: Path) -> Path:
    fps = min(float(info.fps), 60.0)
    index = min(
        len(plan.windows) - 1,
        max(0, round((plan.cover_at - plan.trim[0]) * fps)),
    )
    # A seek at or past the last frame decodes nothing and ffmpeg still exits 0 without a file.
    seek_at = max(plan.trim[0], min(plan.cover_at, plan.trim[1] - 1.0 / fps))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # The cover is written into ready/, so a failed export must not leave a partial image there.
    temporary = out_path.with_name(f"{out_path.stem}.tmp{out_path.suffix}")
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
        (
            _pad_filter(info, target, None)
            if plan.layout == "pad"
            else _crop_filter(info, plan, target, None, None, index)
        )
        + _to_sdr(info)
        + "[v]",
        "-map",
        "[v]",
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(temporary),
    ]
    try:
        run_ffmpeg(command, f"writing the cover of {target.id}")
        if not temporary.is_file():
            raise RuntimeError(f"ffmpeg decoded no cover frame at {seek_at:.3f} s")
        temporary.replace(out_path)
    finally:
        temporary.unlink(missing_ok=True)
    return out_path
