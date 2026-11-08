from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from .framing import Box
from .models import get_yunet_model

SUBJECT_MIN_SCORE = 0.75

if TYPE_CHECKING:
    import numpy as np

    from .probe import InputInfo


@dataclass(frozen=True)
class Face:
    box: Box
    score: float
    landmarks: tuple[tuple[float, float], ...] = ()


class Detector(Protocol):
    name: str

    def detect(self, image_bgr: np.ndarray) -> list[Face]: ...


class YuNetDetector:
    name = "yunet-2023mar"

    def __init__(
        self,
        model_path: Path | None = None,
        score_threshold: float = 0.6,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
    ) -> None:
        import cv2

        model = model_path or get_yunet_model()
        self._detector = cv2.FaceDetectorYN.create(
            str(model),
            "",
            (320, 320),
            score_threshold,
            nms_threshold,
            top_k,
        )

    def detect(self, image_bgr: np.ndarray) -> list[Face]:
        height, width = image_bgr.shape[:2]
        self._detector.setInputSize((width, height))
        _, rows = self._detector.detect(image_bgr)
        if rows is None:
            return []
        return [
            Face(
                Box(*(float(value) for value in row[:4])),
                float(row[14]),
                tuple(
                    (float(row[index]), float(row[index + 1]))
                    for index in range(4, 14, 2)
                ),
            )
            for row in rows
        ]


class ReplayDetector:
    def __init__(
        self, source: Path | dict, source_sha256: str | None = None
    ) -> None:
        self.document = load_faces(source) if isinstance(source, Path) else source
        recorded_sha256 = self.document.get("source_sha256")
        if source_sha256 is not None and recorded_sha256 != source_sha256:
            raise ValueError("recorded detections do not match the source sha256")
        self.name = str(self.document.get("detector", "replay"))
        self._index = 0

    def detect(self, image_bgr: np.ndarray) -> list[Face]:
        del image_bgr
        frames = self.document.get("frames", [])
        if not frames:
            return []
        frame = frames[min(self._index, len(frames) - 1)]
        self._index += 1
        return _parse_faces(frame.get("faces", []))

    def at(self, t: float) -> list[Face]:
        return faces_at(self.document, t)


class FakeDetector:
    name = "fake"

    def __init__(self, detect: Callable[[np.ndarray], list[Face]]) -> None:
        self._detect = detect

    def detect(self, image_bgr: np.ndarray) -> list[Face]:
        return self._detect(image_bgr)


def _parse_faces(items: list[dict]) -> list[Face]:
    return [
        Face(
            Box(
                float(item["x"]),
                float(item["y"]),
                float(item["w"]),
                float(item["h"]),
            ),
            float(item["score"]),
            tuple((float(x), float(y)) for x, y in item.get("landmarks", [])),
        )
        for item in items
    ]


def _face_dict(face: Face) -> dict:
    return {
        "x": face.box.x,
        "y": face.box.y,
        "w": face.box.w,
        "h": face.box.h,
        "score": face.score,
        "landmarks": [list(point) for point in face.landmarks],
    }


def saliency_box(image_bgr: np.ndarray) -> Box | None:
    import cv2

    algorithm = cv2.saliency.StaticSaliencySpectralResidual_create()
    success, saliency = algorithm.computeSaliency(image_bgr)
    if not success:
        return None
    saliency_u8 = (saliency * 255).astype("uint8")
    _, binary = cv2.threshold(
        saliency_u8, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
    )
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 1:
        return None
    index = 1 + max(range(count - 1), key=lambda item: int(stats[item + 1, 4]))
    x, y, width, height, area = (int(value) for value in stats[index])
    if area == 0:
        return None
    return Box(float(x), float(y), float(width), float(height))


def load_faces(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != "postkitty.faces/1":
        raise ValueError(f"unsupported faces schema: {document.get('schema')}")
    return document


def faces_at(document: dict, t: float) -> list[Face]:
    frames = document.get("frames", [])
    if not frames:
        return []
    frame = min(frames, key=lambda item: abs(float(item["t"]) - t))
    return _parse_faces(frame.get("faces", []))


def detect_image(info: InputInfo, detector: Detector, cache_dir: Path) -> dict:
    cache_path = cache_dir / f"{info.sha256}.json"
    if cache_path.exists():
        try:
            document = load_faces(cache_path)
        except (ValueError, OSError):
            # A truncated or foreign cache file is worth no more than a missing one: detect again.
            document = {}
        if document.get("source_sha256") == info.sha256:
            return document

    import cv2
    import numpy as np

    from .image_make import load_srgb

    image_bgr = cv2.cvtColor(np.asarray(load_srgb(info.path).convert("RGB")), cv2.COLOR_RGB2BGR)
    detected = detector.detect(image_bgr)
    document = {
        "schema": "postkitty.faces/1",
        "source_sha256": info.sha256,
        "detector": detector.name,
        "width": image_bgr.shape[1],
        "height": image_bgr.shape[0],
        "fps": None,
        "sample_fps": None,
        "frames": [{"t": 0.0, "faces": [_face_dict(face) for face in detected]}],
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    temporary.replace(cache_path)
    return document


def get_detector(cache_dir: Path) -> Detector:
    replay_path = os.environ.get("POSTKITTY_DETECTIONS")
    if replay_path:
        return ReplayDetector(Path(replay_path))
    # cache_dir holds this job's detections; the model lives in the shared model cache, fetched once.
    del cache_dir
    return YuNetDetector(get_yunet_model())
