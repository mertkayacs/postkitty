"""Seam carving: reshape a photo by removing the paths of pixels that carry the least detail.

Protected boxes (the people) keep their shape while the background between them shrinks. The ``caire``
binary does the work when it is on PATH; otherwise a forward-energy carver in NumPy runs.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .framing import Box

_ENGINES: dict[Path, str] = {}


def seam_engine(path: Path) -> str | None:
    return _ENGINES.get(path.resolve())


def _protect_mask(size: tuple[int, int], boxes: list[Box]) -> np.ndarray:
    width, height = size
    mask = np.zeros((height, width), dtype=np.uint8)
    for box in boxes:
        bounded = box.clamp(width, height).to_int()
        left = max(0, int(bounded.x))
        top = max(0, int(bounded.y))
        right = min(width, int(bounded.x2))
        bottom = min(height, int(bounded.y2))
        mask[top:bottom, left:right] = 255
    return mask


def _remove_seam(array: np.ndarray, seam: np.ndarray) -> np.ndarray:
    height, width = array.shape[:2]
    keep = np.ones((height, width), dtype=bool)
    keep[np.arange(height), seam] = False
    tail = array.shape[2:] if array.ndim > 2 else ()
    return array[keep].reshape((height, width - 1, *tail))


def _forward_seam(image: np.ndarray, protect: np.ndarray) -> np.ndarray:
    gray = (
        image[..., 0].astype(np.float64) * 0.299
        + image[..., 1].astype(np.float64) * 0.587
        + image[..., 2].astype(np.float64) * 0.114
    )
    height, width = gray.shape
    cumulative = np.zeros_like(gray)
    parents = np.zeros((height, width), dtype=np.int8)
    cumulative[0] = protect[0].astype(np.float64) * 1_000_000
    columns = np.arange(width)
    for row in range(1, height):
        left = gray[row, np.maximum(columns - 1, 0)]
        right = gray[row, np.minimum(columns + 1, width - 1)]
        up = gray[row - 1]
        cost_up = np.abs(right - left)
        cost_left = cost_up + np.abs(up - left)
        cost_right = cost_up + np.abs(up - right)
        previous = cumulative[row - 1]
        candidates = np.stack(
            (
                np.r_[np.inf, previous[:-1]] + cost_left,
                previous + cost_up,
                np.r_[previous[1:], np.inf] + cost_right,
            )
        )
        choice = np.argmin(candidates, axis=0)
        cumulative[row] = (
            candidates[choice, columns]
            + protect[row].astype(np.float64) * 1_000_000
        )
        parents[row] = choice.astype(np.int8) - 1

    seam = np.empty(height, dtype=np.int32)
    seam[-1] = int(np.argmin(cumulative[-1]))
    for row in range(height - 1, 0, -1):
        seam[row - 1] = seam[row] + int(parents[row, seam[row]])
    return seam


def _carve(
    image: np.ndarray, target_width: int, protect: np.ndarray
) -> tuple[np.ndarray, list[np.ndarray]]:
    seams: list[np.ndarray] = []
    index_map = np.broadcast_to(
        np.arange(image.shape[1], dtype=np.int32), image.shape[:2]
    ).copy()
    while image.shape[1] > target_width:
        seam = _forward_seam(image, protect)
        seams.append(index_map[np.arange(image.shape[0]), seam].copy())
        image = _remove_seam(image, seam)
        protect = _remove_seam(protect, seam)
        index_map = _remove_seam(index_map, seam)
    return image, seams


def _mapped_remove(
    source: np.ndarray, seams: list[np.ndarray], analysis_width: int, target_width: int
) -> np.ndarray:
    height, source_width = source.shape[:2]
    remove_count = source_width - target_width
    remove = np.zeros((height, source_width), dtype=bool)
    if not seams or remove_count <= 0:
        return source
    for row in range(height):
        analysis_row = min(len(seams[0]) - 1, round(row * len(seams[0]) / height))
        centers = [
            round((seam[analysis_row] + 0.5) * source_width / analysis_width - 0.5)
            for seam in seams
        ]
        selected: set[int] = set()
        radius = 0
        while len(selected) < remove_count:
            for center in centers:
                for column in {center - radius, center + radius}:
                    if 0 <= column < source_width:
                        selected.add(column)
                        if len(selected) == remove_count:
                            break
                if len(selected) == remove_count:
                    break
            radius += 1
        remove[row, list(selected)] = True
    tail = source.shape[2:] if source.ndim > 2 else ()
    return source[~remove].reshape((height, target_width, *tail))


def _python_resize(
    image: Image.Image,
    width: int,
    height: int,
    protect_boxes: list[Box],
) -> Image.Image:
    source = np.asarray(image.convert("RGB"))
    source_height, source_width = source.shape[:2]
    if width > source_width or height > source_height:
        raise ValueError("python seam carving cannot enlarge an image")
    if height < source_height and width == source_width:
        # Seams run top to bottom, so carve rows by working on the transposed image.
        transposed = _python_resize(
            image.transpose(Image.Transpose.TRANSPOSE),
            height,
            width,
            [Box(box.y, box.x, box.h, box.w) for box in protect_boxes],
        )
        return transposed.transpose(Image.Transpose.TRANSPOSE)
    mask = _protect_mask((source_width, source_height), protect_boxes)
    if source_width > 1000:
        analysis_width = 1000
        analysis_height = max(1, round(source_height * analysis_width / source_width))
        analysis = np.asarray(
            image.convert("RGB").resize(
                (analysis_width, analysis_height), Image.Resampling.LANCZOS
            )
        )
        analysis_mask = np.asarray(
            Image.fromarray(mask).resize(
                (analysis_width, analysis_height), Image.Resampling.NEAREST
            )
        )
        analysis_target = max(
            1,
            min(
                analysis_width - 1,
                round(width * analysis_width / source_width),
            ),
        )
        _, seams = _carve(analysis, analysis_target, analysis_mask)
        carved = _mapped_remove(source, seams, analysis_width, width)
    else:
        carved, _ = _carve(source, width, mask)
    result = Image.fromarray(carved)
    if result.height != height:
        result = result.resize((width, height), Image.Resampling.LANCZOS)
    return result


def seam_resize(
    image_path: Path,
    out_path: Path,
    width: int,
    height: int,
    protect_boxes: list[Box],
) -> Path:
    if width <= 0 or height <= 0:
        raise ValueError("output dimensions must be positive")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        source_size = image.size
        caire = shutil.which("caire")
        if caire:
            with tempfile.TemporaryDirectory(dir=out_path.parent) as directory:
                scratch = Path(directory)
                normalized = scratch / "source.png"
                mask_path = scratch / "protect.png"
                temporary = scratch / "result.png"
                image.save(normalized, format="PNG")
                Image.fromarray(_protect_mask(source_size, protect_boxes)).save(mask_path)
                subprocess.run(
                    [
                        caire,
                        "-in",
                        str(normalized),
                        "-out",
                        str(temporary),
                        "-width",
                        str(width),
                        "-height",
                        str(height),
                        "-mask",
                        str(mask_path),
                        "-preview=false",
                    ],
                    check=True,
                    capture_output=True,
                )
                with Image.open(temporary) as rendered:
                    rendered.convert("RGB").save(out_path)
            engine = "caire"
        else:
            _python_resize(image, width, height, protect_boxes).save(out_path)
            engine = "python-forward-energy"
    _ENGINES[out_path.resolve()] = engine
    return out_path
