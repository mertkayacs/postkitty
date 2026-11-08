from __future__ import annotations

import io
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageCms, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from .faces import SUBJECT_MIN_SCORE, faces_at, saliency_box
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


def _subjects(info: Any, document: dict) -> tuple[list[Box], list[Box]]:
    faces = sorted(
        (
            face
            for face in faces_at(document, 0.0)
            if face.score >= SUBJECT_MIN_SCORE
        ),
        key=lambda face: face.box.cx,
    )
    if faces:
        face_boxes = [face.box for face in faces]
        return (
            [subject_box(box, info.width, info.height) for box in face_boxes],
            face_boxes,
        )

    with Image.open(info.path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    salient = saliency_box(bgr)
    return ([salient] if salient is not None else [], [])


def _split_window(
    width: int,
    height: int,
    aspect: float,
    face: Box,
    other: Box,
) -> Box:
    minimum = min(2.4 * face.h, height, width / aspect)
    maximum = min(4.0 * face.h, height, width / aspect)
    for step in range(33):
        crop_height = maximum - (maximum - minimum) * step / 32
        crop_width = crop_height * aspect
        low = max(0.0, face.x2 - crop_width)
        high = min(width - crop_width, face.x)
        if other.cx < face.cx:
            low = max(low, other.x2)
        else:
            high = min(high, other.x - crop_width)
        if low > high:
            continue
        desired_x = face.cx - crop_width / 2
        x = min(max(desired_x, low), high)
        eye_y = face.y + face.h * 0.4
        desired_y = eye_y - crop_height / 3
        y_low = max(0.0, face.y2 - crop_height)
        y_high = min(height - crop_height, face.y)
        y = min(max(desired_y, y_low), y_high)
        return Box(x, y, crop_width, crop_height)
    return fit_crop(width, height, aspect, [face]).box


def _split_windows(
    info: Any, target: Any, face_boxes: list[Box]
) -> list[Box]:
    panel_height = max(2, ((target.height - 6) // 2) // 2 * 2)
    panel_aspect = target.width / panel_height
    return [
        _split_window(
            info.width,
            info.height,
            panel_aspect,
            face,
            face_boxes[1 - index],
        )
        for index, face in enumerate(face_boxes)
    ]


def _tight_pad_box(
    width: int, height: int, aspect: float, subjects: list[Box]
) -> Box:
    if not subjects:
        return Box(0.0, 0.0, float(width), float(height))
    combined = subjects[0]
    for subject in subjects[1:]:
        combined = combined.union(subject)
    crop_width = min(float(width), combined.w * 1.12)
    crop_height = min(float(height), combined.h * 1.12)
    if crop_width / crop_height > aspect:
        crop_height = min(float(height), crop_width / aspect)
    else:
        crop_width = min(float(width), crop_height * aspect)
    x = min(max(combined.cx - crop_width / 2, 0.0), width - crop_width)
    y = min(max(combined.cy - crop_height / 2, 0.0), height - crop_height)
    return Box(x, y, crop_width, crop_height)


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
    subjects, face_boxes = _subjects(info, faces)
    focus = str(override.get("focus", "auto"))
    selected, anchor = _focus(focus, subjects)
    requested = str(override.get("layout", "auto"))
    if requested == "speaker":
        requested = "auto"

    if requested == "auto" and focus == "auto":
        if subjects and not face_boxes:
            fit = fit_crop(
                info.width,
                info.height,
                target.aspect,
                subjects,
                headroom=False,
            )
            return Layout("crop", [fit.box], "saliency-centered crop")
        layout = choose_layout(
            info.width, info.height, target.aspect, subjects, False
        )
        if layout.mode == "split" and len(face_boxes) == 2:
            return Layout("split", _split_windows(info, target, face_boxes), layout.note)
        if layout.mode == "pad":
            return Layout(
                "pad",
                [_tight_pad_box(info.width, info.height, target.aspect, subjects)],
                layout.note,
            )
        return layout
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
            [_tight_pad_box(info.width, info.height, target.aspect, subjects)],
            "pad override",
        )
    if requested == "split":
        if target.aspect >= 1 or len(face_boxes) != 2:
            raise ValueError("split layout requires exactly two subjects and a vertical target")
        return Layout(
            "split", _split_windows(info, target, face_boxes), "split override"
        )
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


def _pad(image: Image.Image, box: Box, size: tuple[int, int]) -> Image.Image:
    longest = max(size)
    blur_scale = min(1.0, 128 / longest)
    blur_size = (
        max(1, round(size[0] * blur_scale)),
        max(1, round(size[1] * blur_scale)),
    )
    background = ImageOps.fit(
        image.convert("RGB"), blur_size, method=Image.Resampling.LANCZOS
    )
    background = background.filter(
        ImageFilter.GaussianBlur(radius=max(2.0, min(blur_size) / 16))
    ).resize(size, Image.Resampling.LANCZOS)
    background = ImageEnhance.Brightness(background).enhance(0.72)
    bounded = box.clamp(*image.size).to_int()
    cropped = image.crop(
        (int(bounded.x), int(bounded.y), int(bounded.x2), int(bounded.y2))
    )
    foreground = ImageOps.contain(cropped, size, method=Image.Resampling.LANCZOS)
    left = (size[0] - foreground.width) // 2
    top = (size[1] - foreground.height) // 2
    if "A" in foreground.getbands():
        background = background.convert("RGBA")
        foreground_layer = background.copy()
        foreground_layer.alpha_composite(foreground, (left, top))
    else:
        foreground_layer = background.copy()
        foreground_layer.paste(foreground, (left, top))
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rectangle(
        (left, top, left + foreground.width - 1, top + foreground.height - 1),
        fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(radius=12))
    return Image.composite(foreground_layer, background, mask)


def _split(image: Image.Image, boxes: list[Box], size: tuple[int, int]) -> Image.Image:
    gap = 6
    panel_height = ((size[1] - gap) // 2) // 2 * 2
    outer_fill = size[1] - gap - panel_height * 2
    top = outer_fill // 2
    mode = "RGBA" if "A" in image.getbands() else "RGB"
    color = _dominant_color(image)
    fill = (*color, 255) if mode == "RGBA" else color
    result = Image.new(mode, size, fill)
    result.paste(_crop(image, boxes[0], (size[0], panel_height)), (0, top))
    result.paste(
        _crop(image, boxes[1], (size[0], panel_height)),
        (0, top + panel_height + gap),
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
        return _pad(image, layout.boxes[0], size), None
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
        has_alpha = bool(
            getattr(info, "has_alpha", False) or "A" in oriented.getbands()
        )
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
