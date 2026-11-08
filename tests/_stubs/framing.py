from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass(frozen=True)
class CropFit:
    box: Box
    fits_all: bool
    cut: list[int]


def subject_box(face: Box, width: int, height: int) -> Box:
    x = max(0.0, face.cx - face.w * 1.1)
    y = max(0.0, face.y - face.h * 0.6)
    x2 = min(float(width), face.cx + face.w * 1.1)
    y2 = min(float(height), face.y2 + face.h * 1.4)
    return Box(x, y, x2 - x, y2 - y)


def fit_crop(
    width: int,
    height: int,
    aspect: float,
    keep: list[Box],
    anchor: tuple[float, float] | None = None,
    headroom: bool = True,
) -> CropFit:
    if width / height >= aspect:
        crop_width, crop_height = height * aspect, float(height)
    else:
        crop_width, crop_height = float(width), width / aspect
    if anchor is not None:
        center_x = width * anchor[0]
        center_y = height * anchor[1]
    elif keep:
        left = min(box.x for box in keep)
        right = max(box.x2 for box in keep)
        top = min(box.y for box in keep)
        bottom = max(box.y2 for box in keep)
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
    else:
        center_x, center_y = width / 2, height / 2
    x = min(max(0.0, center_x - crop_width / 2), width - crop_width)
    y = min(max(0.0, center_y - crop_height / 2), height - crop_height)
    crop = Box(x, y, crop_width, crop_height)
    cut = [
        index
        for index, box in enumerate(keep)
        if not (
            box.x >= crop.x
            and box.y >= crop.y
            and box.x2 <= crop.x2
            and box.y2 <= crop.y2
        )
    ]
    return CropFit(crop, not cut, cut)
