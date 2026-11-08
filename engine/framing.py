from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


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

    @property
    def area(self) -> float:
        return max(0.0, self.w) * max(0.0, self.h)

    def union(self, other: Box) -> Box:
        left = min(self.x, other.x)
        top = min(self.y, other.y)
        right = max(self.x2, other.x2)
        bottom = max(self.y2, other.y2)
        return Box(left, top, right - left, bottom - top)

    def intersect(self, other: Box) -> Box:
        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = max(left, min(self.x2, other.x2))
        bottom = max(top, min(self.y2, other.y2))
        return Box(left, top, right - left, bottom - top)

    def contains(self, other: Box, tol: float = 0.0) -> bool:
        return (
            other.x >= self.x - tol
            and other.y >= self.y - tol
            and other.x2 <= self.x2 + tol
            and other.y2 <= self.y2 + tol
        )

    def expand(self, fx: float, fy: float) -> Box:
        extra_w = self.w * fx
        extra_h = self.h * fy
        return Box(
            self.x - extra_w / 2,
            self.y - extra_h / 2,
            self.w + extra_w,
            self.h + extra_h,
        )

    def clamp(self, width: int, height: int) -> Box:
        left = min(max(0.0, self.x), float(width))
        top = min(max(0.0, self.y), float(height))
        right = min(max(left, self.x2), float(width))
        bottom = min(max(top, self.y2), float(height))
        return Box(left, top, right - left, bottom - top)

    def to_int(self) -> Box:
        left = math.floor(self.x)
        top = math.floor(self.y)
        right = math.ceil(self.x2)
        bottom = math.ceil(self.y2)
        return Box(left, top, right - left, bottom - top)


@dataclass(frozen=True)
class CropFit:
    box: Box
    fits_all: bool
    cut: list[int]


@dataclass(frozen=True)
class Layout:
    mode: Literal["crop", "split", "seam", "pad"]
    boxes: list[Box]
    note: str


def subject_box(face: Box, width: int, height: int) -> Box:
    return Box(
        face.cx - face.w * 1.1,
        face.y - face.h * 0.6,
        face.w * 2.2,
        face.h * 4.0,
    ).clamp(width, height)


def _window_size(width: int, height: int, aspect: float) -> tuple[float, float]:
    if width <= 0 or height <= 0:
        raise ValueError("frame dimensions must be positive")
    if aspect <= 0 or not math.isfinite(aspect):
        raise ValueError("aspect must be positive and finite")
    if width / height >= aspect:
        return height * aspect, float(height)
    return float(width), width / aspect


def _origin(desired: float, size: float, limit: float, low: float, high: float) -> float:
    frame_high = max(0.0, limit - size)
    low = min(max(0.0, low), frame_high)
    high = min(max(low, high), frame_high)
    return min(max(desired, low), high)


def fit_crop(
    width: int,
    height: int,
    aspect: float,
    keep: list[Box],
    anchor: tuple[float, float] | None = None,
    headroom: bool = True,
) -> CropFit:
    crop_width, crop_height = _window_size(width, height, aspect)
    if anchor is not None:
        if not all(0.0 <= value <= 1.0 for value in anchor):
            raise ValueError("anchor values must be between 0 and 1")
        desired_x = width * anchor[0] - crop_width / 2
        desired_y = height * anchor[1] - crop_height / 2
    elif keep:
        combined = keep[0]
        for box in keep[1:]:
            combined = combined.union(box)
        desired_x = combined.cx - crop_width / 2
        if headroom and len(keep) == 1:
            eye_y = keep[0].y + keep[0].h * 0.4
            desired_y = eye_y - crop_height / 3
        else:
            desired_y = combined.cy - crop_height / 2
    else:
        desired_x = (width - crop_width) / 2
        desired_y = (height - crop_height) / 2

    if keep and anchor is None:
        combined = keep[0]
        for box in keep[1:]:
            combined = combined.union(box)
        x = _origin(
            desired_x,
            crop_width,
            width,
            combined.x2 - crop_width,
            combined.x,
        )
        y = _origin(
            desired_y,
            crop_height,
            height,
            combined.y2 - crop_height,
            combined.y,
        )
    else:
        x = min(max(0.0, desired_x), width - crop_width)
        y = min(max(0.0, desired_y), height - crop_height)

    crop = Box(x, y, crop_width, crop_height)
    cut = [index for index, box in enumerate(keep) if not crop.contains(box, 1e-6)]
    return CropFit(crop, not cut, cut)


def choose_layout(
    width: int,
    height: int,
    aspect: float,
    subjects: list[Box],
    allow_seam: bool,
) -> Layout:
    fit = fit_crop(width, height, aspect, subjects)
    if fit.fits_all:
        return Layout("crop", [fit.box], "all subjects fit in one crop")
    if aspect < 1 and len(subjects) == 2:
        boxes = [fit_crop(width, height, aspect * 2, [box]).box for box in subjects]
        return Layout("split", boxes, "two subjects need separate vertical panels")
    target_width = height * aspect
    removable = width - target_width
    if allow_seam and 0 < removable <= width * 0.25:
        return Layout("seam", subjects.copy(), "seam removal preserves separated subjects")
    return Layout("pad", [Box(0.0, 0.0, float(width), float(height))], "crop would cut a subject")
