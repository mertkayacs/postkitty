"""ffprobe and Pillow probing, sha256 and media kind."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".avif"}
_VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".mts", ".m2ts"}
_ALPHA_PIX_FMTS = {"rgba", "argb", "abgr", "bgra", "ya8", "ya16le", "ya16be"}
_INSTALL_HINT = "Install ffmpeg (which provides ffprobe) and retry."


class ProbeError(RuntimeError):
    """The file could not be probed; the message is user-facing."""


@dataclass
class InputInfo:
    id: str
    path: Path
    kind: Literal["image", "video"]
    sha256: str
    width: int
    height: int
    duration: float | None = None
    fps: float | None = None
    has_audio: bool = False
    rotation: int = 0
    has_alpha: bool = False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_video_pix_fmt(pix_fmt: str) -> bool:
    pix_fmt = (pix_fmt or "").lower()
    return pix_fmt in _ALPHA_PIX_FMTS or pix_fmt.startswith("yuva") or pix_fmt.endswith("a")


def _ratio(raw: str | None) -> float | None:
    if not raw or raw in {"0/0", "N/A"}:
        return None
    try:
        if "/" in raw:
            numerator, denominator = raw.split("/", 1)
            denominator_value = float(denominator)
            if denominator_value == 0:
                return None
            return float(numerator) / denominator_value
        return float(raw)
    except (TypeError, ValueError):
        return None


def _image_info(path: Path, input_id: str, sha: str) -> InputInfo:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ProbeError("Pillow is not installed; image probing needs Pillow.") from exc

    try:
        with Image.open(path) as image:
            width, height = image.size
            mode = image.mode
            bands = image.getbands()
            has_alpha = (
                mode in {"RGBA", "LA", "PA", "RGBa", "La"}
                or "A" in bands
                or (mode == "P" and "transparency" in image.info)
            )
            try:
                orientation = int(image.getexif().get(274, 1))
            except Exception:
                orientation = 1
    except Exception as exc:
        raise ProbeError(f"Could not read image {path.name}: {exc}") from exc

    rotation = 0
    if orientation == 3:
        rotation = 180
    elif orientation in (5, 6):
        rotation = 90
    elif orientation in (7, 8):
        rotation = 270
    if orientation in (5, 6, 7, 8):
        width, height = height, width

    return InputInfo(
        id=input_id,
        path=path,
        kind="image",
        sha256=sha,
        width=int(width),
        height=int(height),
        duration=None,
        fps=None,
        has_audio=False,
        rotation=rotation,
        has_alpha=has_alpha,
    )


def _video_info(path: Path, input_id: str, sha: str) -> InputInfo:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise ProbeError(f"ffprobe was not found. {_INSTALL_HINT}")

    command = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=180, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise ProbeError(f"ffprobe timed out on {path.name}.") from exc
    except OSError as exc:
        raise ProbeError(f"ffprobe could not run: {exc}. {_INSTALL_HINT}") from exc
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        raise ProbeError(
            f"ffprobe could not read {path.name}: {detail[-1] if detail else 'unknown error'}"
        )
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ProbeError(f"ffprobe returned invalid JSON for {path.name}.") from exc

    streams = data.get("streams") or []
    # Cover art in an audio file is listed as a video stream; it is not a video.
    video = next(
        (
            stream
            for stream in streams
            if stream.get("codec_type") == "video"
            and not (stream.get("disposition") or {}).get("attached_pic")
        ),
        None,
    )
    if video is None:
        raise ProbeError(f"{path.name} has no video stream.")
    audio = any(stream.get("codec_type") == "audio" for stream in streams)

    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    rotation = 0
    tags = video.get("tags") or {}
    if tags.get("rotate") is not None:
        try:
            rotation = int(float(tags["rotate"]))
        except (TypeError, ValueError):
            rotation = 0
    for side_data in video.get("side_data_list") or []:
        if side_data.get("rotation") is not None:
            try:
                rotation = int(float(side_data["rotation"]))
            except (TypeError, ValueError):
                pass
            break
    rotation %= 360
    if rotation % 180 == 90:
        width, height = height, width

    fps = _ratio(video.get("avg_frame_rate")) or _ratio(video.get("r_frame_rate"))
    duration_raw = (data.get("format") or {}).get("duration") or video.get("duration")
    try:
        duration = float(duration_raw) if duration_raw is not None else None
    except (TypeError, ValueError):
        duration = None

    return InputInfo(
        id=input_id,
        path=path,
        kind="video",
        sha256=sha,
        width=width,
        height=height,
        duration=duration,
        fps=fps,
        has_audio=audio,
        rotation=rotation,
        has_alpha=_is_video_pix_fmt(video.get("pix_fmt") or ""),
    )


def probe(path: Path, input_id: str) -> InputInfo:
    """Probe one input file. Raises ``FileNotFoundError`` or ``ProbeError``."""
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"input file not found: {path}")
    suffix = path.suffix.lower()
    sha = sha256_file(path)
    if suffix in _VIDEO_SUFFIXES:
        return _video_info(path, input_id, sha)
    if suffix in _IMAGE_SUFFIXES:
        return _image_info(path, input_id, sha)
    raise ProbeError(
        f"unsupported input type {suffix or '(no extension)'}; use a JPEG, PNG, WebP image "
        "or an MP4, MOV, WebM video."
    )
