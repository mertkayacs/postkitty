from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from engine.framing import Box, Layout
from engine.image_make import plan_image, render_image


@dataclass(frozen=True)
class Spec:
    value: Any


@dataclass(frozen=True)
class Target:
    id: str
    width: int
    height: int
    limits: dict[str, Spec] = field(default_factory=dict)

    @property
    def aspect(self) -> float:
        return self.width / self.height


@dataclass(frozen=True)
class InputInfo:
    path: Path
    sha256: str
    width: int
    height: int
    has_alpha: bool = False


def _faces(boxes: list[Box]) -> dict:
    return {
        "schema": "postkitty.faces/1",
        "frames": [
            {
                "t": 0.0,
                "faces": [
                    {
                        "x": box.x,
                        "y": box.y,
                        "w": box.w,
                        "h": box.h,
                        "score": 0.99,
                        "landmarks": [],
                    }
                    for box in boxes
                ],
            }
        ],
    }


def _scene(path: Path, boxes: list[Box], size: tuple[int, int] = (800, 450)) -> None:
    image = Image.new("RGB", size, "#18304a")
    draw = ImageDraw.Draw(image)
    for box in boxes:
        draw.ellipse((box.x, box.y, box.x2, box.y2), fill="#d8a47f")
    image.save(path)


def test_plan_selects_crop_split_and_pad(tmp_path: Path) -> None:
    source = tmp_path / "scene.png"
    one = [Box(350, 100, 80, 100)]
    two = [Box(30, 100, 80, 100), Box(690, 100, 80, 100)]
    five = [Box(20 + index * 155, 120, 60, 80) for index in range(5)]
    _scene(source, five)
    info = InputInfo(source, "scene", 800, 450)

    assert plan_image(info, _faces(one), Target("square", 400, 400)).mode == "crop"
    assert plan_image(info, _faces(two), Target("story", 360, 640)).mode == "split"
    assert plan_image(info, _faces(five), Target("feed", 400, 500)).mode == "pad"


def test_plan_uses_saliency_without_faces(tmp_path: Path) -> None:
    source = tmp_path / "salient.png"
    image = Image.new("RGB", (300, 200), "black")
    ImageDraw.Draw(image).rectangle((200, 50, 280, 160), fill="white")
    image.save(source)
    info = InputInfo(source, "salient", 300, 200)

    plan = plan_image(info, _faces([]), Target("square", 200, 200))

    assert plan.mode == "crop"
    assert plan.boxes[0].cx > 150


def test_render_crop_is_exact_jpeg_and_strips_metadata(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    image = Image.new("RGB", (400, 300), "navy")
    exif = Image.Exif()
    exif[315] = "fixture author"
    image.save(source, exif=exif)
    info = InputInfo(source, "source", 400, 300)
    target = Target("feed", 200, 250)
    layout = Layout("crop", [Box(80, 0, 240, 300)], "test crop")

    result = render_image(info, layout, target, tmp_path / "render.jpg")

    with Image.open(result.file) as rendered:
        assert rendered.size == (200, 250)
        assert rendered.format == "JPEG"
        assert not rendered.getexif()
    assert result.extra["metadata_stripped"]


def test_render_split_has_six_pixel_background_gap(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    boxes = [Box(60, 80, 80, 100), Box(660, 80, 80, 100)]
    _scene(source, boxes)
    info = InputInfo(source, "split", 800, 450)
    target = Target("story", 180, 320)
    layout = plan_image(info, _faces(boxes), target)

    result = render_image(info, layout, target, tmp_path / "split.jpg")

    with Image.open(result.file) as rendered:
        pixels = np.asarray(rendered)
        gap_start = (target.height - 6) // 2
        assert rendered.size == (180, 320)
        assert pixels[gap_start : gap_start + 6].std(axis=(0, 1)).max() < 8


def test_render_pad_and_jpeg_quality_ladder(tmp_path: Path) -> None:
    source = tmp_path / "noise.png"
    random = np.random.default_rng(7)
    Image.fromarray(random.integers(0, 256, (400, 400, 3), dtype=np.uint8)).save(source)
    info = InputInfo(source, "noise", 400, 400)
    target = Target("limited", 400, 500, {"bytes_max": Spec(100_000)})
    layout = Layout("pad", [Box(0, 0, 400, 400)], "test pad")

    result = render_image(info, layout, target, tmp_path / "limited.jpg")

    assert result.width == 400
    assert result.height == 500
    assert result.extra["quality"] in {85, 78, 70}
    assert result.bytes <= 100_000


def test_transparent_input_exports_png(tmp_path: Path) -> None:
    source = tmp_path / "alpha.png"
    image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((20, 20, 80, 80), fill=(255, 0, 0, 255))
    image.save(source)
    info = InputInfo(source, "alpha", 100, 100, has_alpha=True)

    result = render_image(
        info,
        Layout("crop", [Box(0, 0, 100, 100)], "alpha"),
        Target("alpha", 80, 80),
        tmp_path / "alpha-output.png",
    )

    with Image.open(result.file) as rendered:
        assert rendered.format == "PNG"
        assert rendered.mode == "RGBA"


def test_exif_orientation_is_applied_before_crop(tmp_path: Path) -> None:
    source = tmp_path / "rotated.jpg"
    image = Image.new("RGB", (100, 50), "blue")
    ImageDraw.Draw(image).rectangle((0, 0, 49, 49), fill="red")
    exif = Image.Exif()
    exif[274] = 6
    image.save(source, quality=100, exif=exif)
    info = InputInfo(source, "rotated", 50, 100)

    result = render_image(
        info,
        Layout("crop", [Box(0, 0, 50, 100)], "oriented"),
        Target("story", 50, 100),
        tmp_path / "oriented.jpg",
    )

    with Image.open(result.file) as rendered:
        array = np.asarray(rendered)
        assert array[:40, :, 0].mean() > array[-40:, :, 0].mean() + 100
