from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image


def _install_stub(name: str) -> Any:
    path = Path(__file__).parent / "_stubs" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"engine.{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checks_stub = _install_stub("checks")
repair_stub = _install_stub("repair")

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
    return checks_stub.RenderResult(
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


def test_size_repair_lowers_jpeg_quality(tmp_path: Path) -> None:
    path = tmp_path / "noise.jpg"
    Image.effect_noise((300, 300), 100).convert("RGB").save(path, quality=92)
    result = _result(path)
    before = path.stat().st_size
    check = checks_stub.Check(
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
    check = checks_stub.Check(
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
    assert checks_stub.CHECKERS["image"] is check_image
    assert repair_stub.REPAIRS["image.bytes_max"] is repair_image_size
