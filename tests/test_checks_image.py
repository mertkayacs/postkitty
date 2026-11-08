from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from engine import checks as checks_mod
from engine import repair as repair_mod
from engine.checks_image import (
    check_image,
    register_image_checker,
    register_image_repairs,
    repair_image_size,
    repair_image_subjects,
)


@dataclass(frozen=True)
class Spec:
    value: Any
    enforcement: str = "hard"
    source_url: str | None = "https://example.test/image"
    source_scope: str | None = "official"
    checked_on: str | None = "2026-11-07"


@dataclass(frozen=True)
class Target:
    id: str
    width: int
    height: int
    limits: dict[str, Spec] = field(default_factory=dict)


def _result(path: Path, subjects_inside: float = 1.0) -> Any:
    return checks_mod.RenderResult(
        target="image",
        file=path,
        width=100,
        height=100,
        duration=None,
        bytes=path.stat().st_size,
        layout={"mode": "crop", "note": "test"},
        subjects_inside=subjects_inside,
        extra={"quality": 92, "metadata_stripped": True},
    )


def test_checker_passes_clean_exact_image(tmp_path: Path) -> None:
    path = tmp_path / "image.jpg"
    Image.new("RGB", (100, 100), "navy").save(path, quality=90)
    target = Target(
        "image",
        100,
        100,
        {"formats": Spec(["jpeg"]), "bytes_max": Spec(100_000)},
    )

    checks = check_image(_result(path), target)

    assert all(check.status == "pass" for check in checks)
    assert next(check for check in checks if check.id == "image.bytes_max").source_scope == "official"


def test_checker_reports_format_size_subject_and_metadata_failures(
    tmp_path: Path,
) -> None:
    path = tmp_path / "image.png"
    exif = Image.Exif()
    exif[315] = "fixture"
    Image.new("RGB", (80, 120), "red").save(path, exif=exif)
    target = Target(
        "image",
        100,
        100,
        {"formats": Spec(["jpeg"]), "bytes_max": Spec(10)},
    )
    result = _result(path, subjects_inside=0.0)

    checks = {check.id: check for check in check_image(result, target)}

    assert checks["image.width"].status == "fail"
    assert checks["image.height"].status == "fail"
    assert checks["image.aspect"].status == "fail"
    assert checks["image.format"].status == "fail"
    assert checks["image.bytes_max"].status == "fail"
    assert checks["frame.subjects_inside"].status == "fail"
    assert checks["image.metadata_stripped"].status == "fail"


def test_checker_warns_about_a_strongly_upscaled_output(tmp_path: Path) -> None:
    path = tmp_path / "image.jpg"
    Image.new("RGB", (100, 100), "navy").save(path, quality=90)
    target = Target("image", 100, 100)

    def upscale_check(extra: dict[str, Any]) -> Any | None:
        result = _result(path)
        result.extra = extra
        return next((c for c in check_image(result, target) if c.id == "image.upscale_max"), None)

    soft = upscale_check({"upscale": 16.9})
    assert soft is not None
    assert soft.status == "advisory" and not soft.hard
    assert "16.9" in soft.message
    assert upscale_check({"upscale": 1.2}).status == "pass"
    assert upscale_check({}) is None


def test_metadata_is_advisory_for_a_file_postkitty_did_not_frame(tmp_path: Path) -> None:
    path = tmp_path / "photo.jpg"
    exif = Image.Exif()
    exif[0x010F] = "Camera Maker"
    Image.new("RGB", (100, 100), "navy").save(path, quality=90, exif=exif)
    target = Target("image", 100, 100)

    def metadata_check(subjects_inside: float | None) -> Any:
        result = _result(path, subjects_inside)
        result.extra = {}
        return next(c for c in check_image(result, target) if c.id == "image.metadata_stripped")

    user_file = metadata_check(None)
    assert user_file.status == "advisory" and not user_file.hard
    assert "EXIF" in user_file.message and "location" in user_file.message
    assert "output" not in user_file.message
    own_render = metadata_check(1.0)
    assert own_render.status == "fail" and own_render.hard


def test_size_repair_lowers_jpeg_quality(tmp_path: Path) -> None:
    path = tmp_path / "noise.jpg"
    Image.effect_noise((300, 300), 100).convert("RGB").save(path, quality=92)
    result = _result(path)
    before = path.stat().st_size
    check = checks_mod.Check(
        "image.bytes_max", "image", "fail", True, before, before // 2, "large"
    )

    repaired = repair_image_size(result, Target("image", 300, 300), check, {})

    assert repaired is not None
    assert repaired.bytes < before
    assert repaired.extra["quality"] == 82


def test_subject_repair_requests_pad(tmp_path: Path) -> None:
    path = tmp_path / "image.jpg"
    Image.new("RGB", (100, 100), "navy").save(path)
    result = _result(path, 0.0)
    check = checks_mod.Check(
        "frame.subjects_inside", "image", "fail", True, 0.0, 1.0, "cut"
    )
    calls: list[dict[str, Any]] = []

    def rerender(overrides: dict[str, Any]) -> Any:
        calls.append(overrides)
        return result

    repaired = repair_image_subjects(
        result, Target("image", 100, 100), check, {"render": rerender}
    )

    assert repaired is result
    assert calls == [{"layout": "pad"}]


def test_registration_functions_are_callable() -> None:
    assert register_image_checker()
    assert register_image_repairs()
    assert check_image in checks_mod._CHECKERS["image"]
    assert repair_mod._STRATEGIES["image.bytes_max"] is repair_image_size
