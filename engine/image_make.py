from __future__ import annotations

import io
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageCms, ImageEnhance, ImageFilter, ImageOps

from .faces import faces_at, saliency_box
from .framing import Box, Layout, choose_layout, fit_crop, subject_box
from .seams import seam_engine, seam_resize


@dataclass
class _FallbackRenderResult:
    target: str
    file: Path
    width: int
    height: int
    duration: float | None
    bytes: int
    layout: dict[str, Any]
    subjects_inside: float | None
    extra: dict[str, Any]


def _limit(target: Any, key: str, default: Any = None) -> Any:
    spec = target.limits.get(key)
    return default if spec is None else getattr(spec, "value", spec)


def _subjects(info: Any, document: dict) -> list[Box]:
    faces = sorted(
        (face for face in faces_at(document, 0.0) if face.score >= 0.6),
        key=lambda face: face.box.cx,
    )
    if faces:
        return [subject_box(face.box, info.width, info.height) for face in faces]

    with Image.open(info.path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    salient = saliency_box(bgr)
    return [salient] if salient is not None else []


def _focus(
    value: str, subjects: list[Box]
) -> tuple[list[Box], tuple[float, float] | None]:
    if value == "auto":
        return subjects, None
    if value.startswith("person:"):
        try:
            index = int(value.removeprefix("person:")) - 1
        except ValueError as error:
            raise ValueError("focus person must be a positive integer") from error
        if index < 0 or index >= len(subjects):
            raise ValueError("focus person is not present")
        return [subjects[index]], None
    anchors = {"left": 0.0, "center": 0.5, "right": 1.0}
    if value in anchors:
        return subjects, (anchors[value], 0.5)
    if value.startswith("x:"):
        try:
            x = float(value.removeprefix("x:"))
        except ValueError as error:
            raise ValueError("focus x must be between 0 and 1") from error
        if not 0.0 <= x <= 1.0:
            raise ValueError("focus x must be between 0 and 1")
        return subjects, (x, 0.5)
    raise ValueError(f"unsupported focus: {value}")


def plan_image(
    info: Any,
    faces: dict,
    target: Any,
    override: dict[str, Any] | None = None,
) -> Layout:
    override = override or {}
    subjects = _subjects(info, faces)
    focus = str(override.get("focus", "auto"))
    selected, anchor = _focus(focus, subjects)
    requested = str(override.get("layout", "auto"))
    allow_seam = bool(override.get("seam", True))

    if requested == "auto" and focus == "auto":
        return choose_layout(info.width, info.height, target.aspect, subjects, allow_seam)
    if requested in {"auto", "crop"}:
        fit = fit_crop(info.width, info.height, target.aspect, selected, anchor=anchor)
        cuts = sum(not fit.box.contains(subject) for subject in subjects)
        note = "focus override crop" if focus != "auto" else "crop override"
        if cuts:
            note += f" cuts {cuts} subject(s)"
        return Layout("crop", [fit.box], note)
    if requested == "pad":
        return Layout(
            "pad",
            [Box(0.0, 0.0, float(info.width), float(info.height))],
            "pad override",
        )
    if requested == "split":
        if target.aspect >= 1 or len(subjects) != 2:
            raise ValueError("split layout requires exactly two subjects and a vertical target")
        boxes = [
            fit_crop(info.width, info.height, target.aspect * 2, [subject]).box
            for subject in subjects
        ]
        return Layout("split", boxes, "split override")
    if requested == "seam":
        return Layout("seam", subjects, "seam override")
    raise ValueError(f"unsupported image layout: {requested}")


def _srgb(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A") if "A" in image.getbands() else None
    rgb = image.convert("RGB")
    profile = image.info.get("icc_profile")
    if profile:
        try:
            rgb = ImageCms.profileToProfile(
                rgb,
                ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                ImageCms.createProfile("sRGB"),
                outputMode="RGB",
            )
        except (ImageCms.PyCMSError, OSError):
            pass
    if alpha is not None:
        rgb.putalpha(alpha)
    return rgb


def _crop(image: Image.Image, box: Box, size: tuple[int, int]) -> Image.Image:
    bounded = box.clamp(*image.size).to_int()
    return image.crop(
        (int(bounded.x), int(bounded.y), int(bounded.x2), int(bounded.y2))
    ).resize(size, Image.Resampling.LANCZOS)


def _dominant_color(image: Image.Image) -> tuple[int, int, int]:
    reduced = image.convert("RGB").resize((64, 64), Image.Resampling.BOX)
    quantized = reduced.quantize(colors=8)
    colors = quantized.getcolors() or []
    index = max(colors, default=(0, 0))[1]
    palette = quantized.getpalette()
    assert palette is not None
    start = index * 3
    return tuple(palette[start : start + 3])


def _pad(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    background = ImageOps.fit(
        image.convert("RGB"), size, method=Image.Resampling.LANCZOS
    )
    background = background.filter(ImageFilter.GaussianBlur(radius=24))
    background = ImageEnhance.Brightness(background).enhance(0.65)
    foreground = ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)
    left = (size[0] - foreground.width) // 2
    top = (size[1] - foreground.height) // 2
    if "A" in foreground.getbands():
        background = background.convert("RGBA")
        background.alpha_composite(foreground, (left, top))
    else:
        background.paste(foreground, (left, top))
    return background


def _split(image: Image.Image, boxes: list[Box], size: tuple[int, int]) -> Image.Image:
    gap = 6
    top_height = (size[1] - gap) // 2
    bottom_height = size[1] - gap - top_height
    mode = "RGBA" if "A" in image.getbands() else "RGB"
    color = _dominant_color(image)
    fill = (*color, 255) if mode == "RGBA" else color
    result = Image.new(mode, size, fill)
    result.paste(_crop(image, boxes[0], (size[0], top_height)), (0, 0))
    result.paste(
        _crop(image, boxes[1], (size[0], bottom_height)),
        (0, top_height + gap),
    )
    return result


def _render_pixels(
    image: Image.Image,
    info: Any,
    layout: Layout,
    target: Any,
    out_path: Path,
) -> tuple[Image.Image, str | None]:
    size = (target.width, target.height)
    if layout.mode == "crop":
        return _crop(image, layout.boxes[0], size), None
    if layout.mode == "pad":
        return _pad(image, size), None
    if layout.mode == "split":
        return _split(image, layout.boxes, size), None

    target_width = min(info.width, max(1, round(info.height * target.aspect)))
    with tempfile.TemporaryDirectory(dir=out_path.parent) as directory:
        source = Path(directory) / "oriented.png"
        carved = Path(directory) / "carved.png"
        image.convert("RGB").save(source, format="PNG")
        seam_resize(source, carved, target_width, info.height, layout.boxes)
        engine = seam_engine(carved)
        with Image.open(carved) as opened:
            result = opened.convert("RGB").resize(size, Image.Resampling.LANCZOS)
    return result, engine


def _save(
    image: Image.Image, out_path: Path, use_png: bool, bytes_max: int | None
) -> int | None:
    if use_png:
        image.save(out_path, format="PNG", optimize=True)
        return None
    image = image.convert("RGB")
    selected = 70
    for quality in (92, 85, 78, 70):
        image.save(out_path, format="JPEG", quality=quality, optimize=True)
        selected = quality
        if bytes_max is None or out_path.stat().st_size <= bytes_max:
            break
    return selected


def _result_type() -> type:
    try:
        from .checks import RenderResult
    except ImportError:
        return _FallbackRenderResult
    return RenderResult


def render_image(
    info: Any,
    layout: Layout,
    target: Any,
    out_path: Path,
) -> Any:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(info.path) as opened:
        oriented = ImageOps.exif_transpose(opened)
        has_alpha = bool(getattr(info, "has_alpha", "A" in oriented.getbands()))
        image = _srgb(oriented)
    rendered, engine = _render_pixels(image, info, layout, target, out_path)
    quality = _save(
        rendered,
        out_path,
        has_alpha,
        _limit(target, "bytes_max"),
    )
    with Image.open(out_path) as output:
        width, height = output.size
        output_format = str(output.format).lower()
        metadata_stripped = not output.getexif() and not {
            key for key in output.info if key not in {"jfif", "jfif_version", "jfif_unit", "jfif_density"}
        }
    result_type = _result_type()
    return result_type(
        target=target.id,
        file=out_path,
        width=width,
        height=height,
        duration=None,
        bytes=out_path.stat().st_size,
        layout={"mode": layout.mode, "note": layout.note},
        subjects_inside=0.0 if " cuts " in layout.note else 1.0,
        extra={
            "metadata_stripped": metadata_stripped,
            "format": output_format,
            "quality": quality,
            "seam_engine": engine,
        },
    )
