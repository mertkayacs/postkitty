from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from .checks import Check
except ImportError:

    @dataclass
    class Check:
        id: str
        target: str
        status: str
        hard: bool
        measured: Any
        expected: Any
        message: str
        source_url: str | None = None
        source_scope: str | None = None
        checked_on: str | None = None


# Output pixels per source pixel above which an enlarged image reads as blurry.
UPSCALE_SOFT = 1.5


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
    passing: str,
    failing: str,
    spec: Any | None = None,
) -> Check:
    hard = _hard(spec)
    return Check(
        id=check_id,
        target=target.id,
        status="pass" if passed else "fail" if hard else "advisory",
        hard=hard,
        measured=measured,
        expected=expected,
        message=passing if passed else failing,
        source_url=getattr(spec, "source_url", None),
        source_scope=getattr(spec, "source_scope", None),
        checked_on=getattr(spec, "checked_on", None),
    )


def _metadata_stripped(path: Path) -> bool:
    with Image.open(path) as image:
        allowed = {"jfif", "jfif_version", "jfif_unit", "jfif_density"}
        return not image.getexif() and not (set(image.info) - allowed)


def check_image(result: Any, target: Any) -> list[Check]:
    with Image.open(result.file) as image:
        width, height = image.size
        image_format = str(image.format).lower()
    checks = [
        _check(
            "image.width",
            target,
            width,
            target.width,
            width == target.width,
            "The image width is exact.",
            "The image width is not exact.",
        ),
        _check(
            "image.height",
            target,
            height,
            target.height,
            height == target.height,
            "The image height is exact.",
            "The image height is not exact.",
        ),
    ]
    measured_aspect = width / height
    expected_aspect = target.width / target.height
    aspect_ok = abs(measured_aspect - expected_aspect) / expected_aspect <= 0.005
    checks.append(
        _check(
            "image.aspect",
            target,
            measured_aspect,
            expected_aspect,
            aspect_ok,
            "The image aspect ratio is exact.",
            "The image aspect ratio differs by more than 0.5%.",
        )
    )

    formats_spec = _spec(target, "formats")
    formats = [str(value).lower() for value in _value(formats_spec, ["jpeg", "png"])]
    checks.append(
        _check(
            "image.format",
            target,
            image_format,
            formats,
            image_format in formats,
            "The image format is allowed.",
            "The image format is not allowed.",
            formats_spec,
        )
    )

    bytes_spec = _spec(target, "bytes_max")
    if bytes_spec is not None:
        measured_bytes = result.file.stat().st_size
        maximum = int(_value(bytes_spec))
        checks.append(
            _check(
                "image.bytes_max",
                target,
                measured_bytes,
                maximum,
                measured_bytes <= maximum,
                "The image file size is within the limit.",
                "The image file size exceeds the limit.",
                bytes_spec,
            )
        )

    subjects_inside = result.subjects_inside
    if subjects_inside is None:
        # A file postkitty did not frame (postkitty_check on any upload) has no subject plan to compare.
        checks.append(
            Check(
                id="frame.subjects_inside",
                target=target.id,
                status="skipped",
                hard=False,
                measured=None,
                expected=1.0,
                message="Subject framing data is unavailable for this file.",
            )
        )
    else:
        checks.append(
            _check(
                "frame.subjects_inside",
                target,
                subjects_inside,
                1.0,
                subjects_inside >= 1.0,
                "Every kept subject is inside the image.",
                "At least one kept subject is cut.",
            )
        )
    upscale = (result.extra or {}).get("upscale")
    if isinstance(upscale, (int, float)):
        # Advisory only: a soft image still uploads, but the user should know before posting it.
        soft = float(upscale) > UPSCALE_SOFT
        checks.append(
            Check(
                id="image.upscale_max",
                target=target.id,
                status="advisory" if soft else "pass",
                hard=False,
                measured=round(float(upscale), 2),
                expected=UPSCALE_SOFT,
                message=(
                    f"The source window is enlarged {float(upscale):.1f} times; the image will look soft."
                    if soft
                    else "The source is large enough for this size."
                ),
            )
        )
    stripped = _metadata_stripped(result.file)
    if subjects_inside is None:
        # A user's own file: platforms accept EXIF, so this is a privacy heads-up, never a failure.
        checks.append(
            Check(
                id="image.metadata_stripped",
                target=target.id,
                status="pass" if stripped else "advisory",
                hard=False,
                measured=stripped,
                expected=True,
                message=(
                    "Image metadata is stripped."
                    if stripped
                    else "The file carries EXIF or other metadata, which can include the camera and location."
                ),
            )
        )
        return checks
    checks.append(
        _check(
            "image.metadata_stripped",
            target,
            stripped,
            True,
            stripped,
            "Image metadata is stripped.",
            "Image metadata remains in the output.",
        )
    )
    return checks


def _call_rerender(rerender: dict[str, Any], updates: dict[str, Any]) -> Any | None:
    callback: Callable[..., Any] | None = rerender.get("render") or rerender.get(
        "rerender"
    )
    if callback is None:
        return None
    current = dict(rerender.get("overrides", {}))
    current.update(updates)
    try:
        return callback(current)
    except TypeError:
        return callback(overrides=current)


def repair_image_size(
    result: Any, target: Any, check: Check, rerender: dict[str, Any]
) -> Any | None:
    del target, check, rerender
    with Image.open(result.file) as opened:
        if str(opened.format).lower() != "jpeg":
            return None
        image = opened.convert("RGB")
    current = int(result.extra.get("quality") or 70)
    quality = max(40, current - 10)
    temporary = result.file.with_name(f".{result.file.name}.quality-{quality}.tmp")
    try:
        image.save(temporary, format="JPEG", quality=quality, optimize=True)
        temporary.replace(result.file)
    finally:
        temporary.unlink(missing_ok=True)
    extra = dict(result.extra)
    extra["quality"] = quality
    return replace(result, bytes=result.file.stat().st_size, extra=extra)


def repair_image_subjects(
    result: Any, target: Any, check: Check, rerender: dict[str, Any]
) -> Any | None:
    del result, target, check
    return _call_rerender(rerender, {"layout": "pad"})


def register_image_checker() -> bool:
    try:
        from .checks import register_checker
    except ImportError:
        return False
    register_checker("image", check_image)
    return True


def register_image_repairs() -> bool:
    try:
        from .repair import register
    except ImportError:
        return False
    register("image.bytes_max", repair_image_size)
    register("frame.subjects_inside", repair_image_subjects)
    return True


register_image_checker()
register_image_repairs()
