from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image, ImageCms, ImageDraw, PngImagePlugin

from engine.photo import render as image_make
from engine.photo import seams
from engine.photo.framing import Box, Layout, subject_box
from engine.photo.render import plan_image, render_image


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


def _faces(boxes: list[Box], score: float = 0.99) -> dict:
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
                        "score": score,
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


def test_seam_layout_is_explicit_only(tmp_path: Path) -> None:
    source = tmp_path / "wide.png"
    faces = [Box(80, 200, 80, 100), Box(1840, 200, 80, 100)]
    _scene(source, faces, size=(2000, 1000))
    info = InputInfo(source, "wide", 2000, 1000)
    target = Target("wide", 1600, 1000)

    automatic = plan_image(info, _faces(faces), target)
    explicit = plan_image(info, _faces(faces), target, {"layout": "seam"})

    assert automatic.mode == "pad"
    assert explicit.mode == "seam"


def test_speaker_layout_is_rejected_for_images(tmp_path: Path) -> None:
    source = tmp_path / "wide.png"
    faces = [Box(80, 200, 80, 100), Box(1840, 200, 80, 100)]
    _scene(source, faces, size=(2000, 1000))
    info = InputInfo(source, "wide", 2000, 1000)
    target = Target("story", 1080, 1920)

    with pytest.raises(ValueError, match="speaker"):
        plan_image(info, _faces(faces), target, {"layout": "speaker"})


def test_focus_on_one_person_keeps_that_person_and_may_drop_the_others(tmp_path: Path) -> None:
    source = tmp_path / "pair.png"
    faces = [Box(100, 200, 80, 100), Box(1400, 200, 80, 100)]
    _scene(source, faces, size=(1600, 900))
    info = InputInfo(source, "pair", 1600, 900)
    target = Target("square", 400, 400)

    layout = plan_image(info, _faces(faces), target, {"focus": "person:2"})
    result = render_image(info, layout, target, tmp_path / "second.jpg")

    assert layout.mode == "crop"
    assert layout.boxes[0].contains(subject_box(faces[1], 1600, 900))
    assert not layout.boxes[0].intersect(faces[0]).area
    assert result.subjects_inside == 1.0


def test_crop_override_that_cuts_a_kept_person_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "pair.png"
    faces = [Box(100, 200, 80, 100), Box(1400, 200, 80, 100)]
    _scene(source, faces, size=(1600, 900))
    info = InputInfo(source, "pair", 1600, 900)
    target = Target("square", 400, 400)

    layout = plan_image(info, _faces(faces), target, {"layout": "crop"})
    result = render_image(info, layout, target, tmp_path / "both.jpg")

    assert result.subjects_inside == 0.0


def test_plan_uses_saliency_without_faces(tmp_path: Path) -> None:
    source = tmp_path / "salient.png"
    image = Image.new("RGB", (300, 200), "black")
    ImageDraw.Draw(image).rectangle((200, 50, 280, 160), fill="white")
    image.save(source)
    info = InputInfo(source, "salient", 300, 200)

    plan = plan_image(info, _faces([]), Target("square", 200, 200))

    assert plan.mode == "crop"
    assert plan.boxes[0].cx > 150


def test_low_score_detection_uses_saliency_crop(
    monkeypatch: object, tmp_path: Path
) -> None:
    source = tmp_path / "product.png"
    image = Image.new("RGB", (400, 300), "black")
    ImageDraw.Draw(image).rectangle((150, 100, 250, 200), fill="white")
    image.save(source)
    info = InputInfo(source, "product", 400, 300)
    false_face = Box(340, 0, 60, 150)
    monkeypatch.setattr(
        image_make, "saliency_box", lambda image_bgr: Box(150, 100, 100, 100)
    )

    plan = plan_image(
        info,
        _faces([false_face], score=0.61),
        Target("x_image", 320, 180),
    )

    assert plan.mode == "crop"
    assert abs(plan.boxes[0].cy - 150) < 20


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


_JFIF_KEYS = {"jfif", "jfif_version", "jfif_unit", "jfif_density"}


def _gps_exif() -> Image.Exif:
    exif = Image.Exif()
    exif[0x010F] = "Camera Maker"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2] = "N", (40.0, 26.0, 46.0)
    gps[3], gps[4] = "W", (79.0, 58.0, 56.0)
    return exif


def test_jpeg_output_carries_no_gps_comment_or_xmp_from_the_source(tmp_path: Path) -> None:
    source = tmp_path / "phone.jpg"
    Image.new("RGB", (400, 300), "navy").save(
        source,
        exif=_gps_exif(),
        comment=b"shot at home",
        xmp=b'<x:xmpmeta xmlns:x="adobe:ns:meta/" exif:GPSLatitude="40,26.76N"/>',
        dpi=(300, 300),
    )
    with Image.open(source) as opened:
        assert opened.getexif().get_ifd(0x8825) and {"comment", "xmp"} <= set(opened.info)
    info = InputInfo(source, "phone", 400, 300)

    result = render_image(
        info, Layout("crop", [Box(0, 0, 400, 300)], "full"), Target("x_image", 400, 300), tmp_path / "out.jpg"
    )

    with Image.open(result.file) as rendered:
        assert not rendered.getexif()
        assert set(rendered.info) <= _JFIF_KEYS
    data = result.file.read_bytes()
    assert b"shot at home" not in data and b"GPSLatitude" not in data and b"Exif" not in data
    assert result.extra["metadata_stripped"]


def test_png_output_carries_no_profile_gps_or_text_from_the_source(tmp_path: Path) -> None:
    source = tmp_path / "screenshot.png"
    text = PngImagePlugin.PngInfo()
    text.add_text("Author", "A. Person")
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGBA", (200, 200), (10, 120, 200, 128)).save(
        source, icc_profile=profile, exif=_gps_exif(), pnginfo=text
    )
    info = InputInfo(source, "screenshot", 200, 200, has_alpha=True)

    result = render_image(
        info, Layout("crop", [Box(0, 0, 200, 200)], "full"), Target("x_image", 200, 200), tmp_path / "out.png"
    )

    with Image.open(result.file) as rendered:
        assert rendered.format == "PNG"
        assert not rendered.getexif()
        assert not rendered.info
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


def test_split_windows_isolate_faces_and_limit_zoom(tmp_path: Path) -> None:
    source = tmp_path / "podcast.png"
    faces = [Box(180, 100, 70, 100), Box(550, 100, 70, 100)]
    _scene(source, faces)
    info = InputInfo(source, "podcast", 800, 450)

    layout = plan_image(info, _faces(faces), Target("feed", 400, 500))

    assert layout.mode == "split"
    for index, window in enumerate(layout.boxes):
        face = faces[index]
        other = faces[1 - index]
        eye_y = face.y + face.h * 0.4
        assert window.contains(face)
        assert not window.intersect(other).area
        assert 2.4 <= window.h / face.h <= 4.0
        assert abs((eye_y - window.y) / window.h - 1 / 3) < 0.05


def test_split_panels_have_even_heights(monkeypatch: object) -> None:
    heights: list[int] = []

    def crop(image: Image.Image, box: Box, size: tuple[int, int]) -> Image.Image:
        del image, box
        heights.append(size[1])
        return Image.new("RGB", size, "red")

    monkeypatch.setattr(image_make, "_crop", crop)
    image_make._split(
        Image.new("RGB", (800, 450), "navy"),
        [Box(0, 0, 400, 450), Box(400, 0, 400, 450)],
        (180, 320),
    )

    assert heights and all(height % 2 == 0 for height in heights)


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


def test_pad_uses_tight_subject_crop(tmp_path: Path) -> None:
    source = tmp_path / "group.png"
    faces = [
        Box(250, 100, 80, 100),
        Box(360, 100, 80, 100),
        Box(470, 100, 80, 100),
    ]
    _scene(source, faces)
    info = InputInfo(source, "group", 800, 450)

    layout = plan_image(info, _faces(faces), Target("feed", 400, 500))

    assert layout.mode == "pad"
    assert layout.boxes[0].w < info.width * 0.75
    assert all(
        layout.boxes[0].contains(subject_box(face, info.width, info.height))
        for face in faces
    )


def test_pad_enlarges_subject_and_feathers_seam(tmp_path: Path) -> None:
    source = tmp_path / "subject.png"
    image = Image.new("RGBA", (800, 450), "black")
    ImageDraw.Draw(image).rectangle((300, 75, 499, 374), fill="white")
    image.save(source)
    info = InputInfo(source, "subject", 800, 450, has_alpha=True)
    layout = Layout("pad", [Box(300, 75, 200, 300)], "tight pad")

    result = render_image(info, layout, Target("feed", 400, 500), tmp_path / "pad.png")

    with Image.open(result.file) as rendered:
        pixels = np.asarray(rendered.convert("RGB"))
    white = np.all(pixels > 235, axis=2)
    transition = pixels[250, 20:55, 0]
    assert np.count_nonzero(white) > 100_000
    assert len(np.unique(transition)) > 5


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


def test_transparent_input_flattens_to_jpeg_when_png_is_not_allowed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "alpha.png"
    image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((20, 20, 80, 80), fill=(255, 0, 0, 255))
    image.save(source)
    info = InputInfo(source, "alpha", 100, 100, has_alpha=True)
    target = Target("instagram_feed", 80, 100, {"formats": Spec(["jpeg"])})

    result = render_image(
        info, Layout("crop", [Box(0, 0, 80, 100)], "alpha"), target, tmp_path / "feed.png"
    )

    assert result.file.suffix == ".jpg"
    with Image.open(result.file) as rendered:
        assert rendered.format == "JPEG"
        assert rendered.getpixel((2, 2)) == (255, 255, 255)
    assert result.extra["format"] == "jpeg"


def test_transparent_input_over_the_byte_cap_falls_back_to_jpeg(tmp_path: Path) -> None:
    source = tmp_path / "noise.png"
    random = np.random.default_rng(3)
    Image.fromarray(random.integers(0, 256, (300, 300, 4), dtype=np.uint8), "RGBA").save(source)
    info = InputInfo(source, "noise", 300, 300, has_alpha=True)
    target = Target("bluesky_image", 300, 300, {"bytes_max": Spec(120_000)})

    result = render_image(
        info, Layout("crop", [Box(0, 0, 300, 300)], "noise"), target, tmp_path / "image.png"
    )

    assert result.file.suffix == ".jpg"
    assert result.bytes <= 120_000
    assert not (tmp_path / "image.png").exists()
    with Image.open(result.file) as rendered:
        assert rendered.format == "JPEG"


def test_palette_png_keeps_its_transparency(tmp_path: Path) -> None:
    source = tmp_path / "logo.png"
    image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((20, 20, 80, 80), fill=(255, 0, 0, 255))
    image.convert("P", palette=Image.Palette.ADAPTIVE).save(source)
    with Image.open(source) as palette:
        assert palette.mode == "P" and "transparency" in palette.info
    info = InputInfo(source, "logo", 100, 100, has_alpha=True)

    result = render_image(
        info, Layout("crop", [Box(0, 0, 100, 100)], "logo"), Target("logo", 100, 100), tmp_path / "logo-out.png"
    )

    with Image.open(result.file) as rendered:
        assert rendered.format == "PNG"
        assert rendered.mode == "RGBA"
        assert rendered.getpixel((2, 2))[3] == 0
        assert rendered.getpixel((50, 50))[:3] == (255, 0, 0)


def test_sixteen_bit_grayscale_keeps_its_tones(tmp_path: Path) -> None:
    source = tmp_path / "scan.png"
    ramp = np.linspace(0, 65535, 200 * 100, dtype=np.float64).reshape(100, 200)
    Image.fromarray(ramp.astype(np.uint16)).save(source)
    with Image.open(source) as opened:
        assert opened.mode == "I;16"
    info = InputInfo(source, "scan", 200, 100)

    result = render_image(
        info, Layout("crop", [Box(0, 0, 200, 100)], "ramp"), Target("x", 200, 100), tmp_path / "scan.jpg"
    )

    with Image.open(result.file) as rendered:
        pixels = np.asarray(rendered.convert("L"))
    assert pixels[0, 0] < 10
    assert pixels[-1, -1] > 245
    assert 110 < pixels[50, 100] < 145


def test_seam_carves_height_when_the_source_is_taller_than_the_target(
    monkeypatch: object, tmp_path: Path
) -> None:
    source = tmp_path / "square.png"
    image = Image.new("RGB", (400, 400), "navy")
    ImageDraw.Draw(image).ellipse((175, 60, 224, 109), fill="red")
    image.save(source)
    monkeypatch.setattr(seams.shutil, "which", lambda name: None)
    info = InputInfo(source, "square", 400, 400)
    target = Target("x_image", 320, 180)
    layout = plan_image(info, _faces([Box(175, 60, 50, 50)]), target, {"layout": "seam"})

    result = render_image(info, layout, target, tmp_path / "seam.jpg")

    with Image.open(result.file) as rendered:
        pixels = np.asarray(rendered)
    red = (pixels[..., 0] > 150) & (pixels[..., 1] < 100)
    rows, columns = np.nonzero(red)
    width = columns.max() - columns.min() + 1
    height = rows.max() - rows.min() + 1
    assert layout.mode == "seam"
    assert 0.9 <= width / height <= 1.1
    assert 34 <= width <= 46


def test_render_reports_how_much_the_source_window_is_upscaled(tmp_path: Path) -> None:
    source = tmp_path / "tiny.png"
    Image.new("RGB", (64, 64), "green").save(source)
    info = InputInfo(source, "tiny", 64, 64)

    tiny = render_image(
        info, Layout("crop", [Box(0, 0, 64, 64)], "tiny"), Target("square", 1080, 1080), tmp_path / "tiny.jpg"
    )
    same = render_image(
        info, Layout("crop", [Box(0, 0, 64, 64)], "same"), Target("small", 64, 64), tmp_path / "same.jpg"
    )

    assert abs(tiny.extra["upscale"] - 1080 / 64) < 0.01
    assert same.extra["upscale"] == 1.0


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


def test_upscale_is_one_when_no_window_has_an_area() -> None:
    image = Image.new("RGB", (100, 100))
    outside = Layout("crop", [Box(500.0, 500.0, 10.0, 10.0)], "window outside the frame")

    assert image_make._upscale(image, outside, (1080, 1350)) == 1.0
