from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from engine.detect.faces import (
    Face,
    FakeDetector,
    ReplayDetector,
    YuNetDetector,
    detect_image,
    faces_at,
    get_detector,
    load_faces,
    saliency_box,
)
from engine.photo.framing import Box


@dataclass(frozen=True)
class InputInfo:
    path: Path
    sha256: str


def _document() -> dict:
    return {
        "schema": "postkitty.faces/1",
        "source_sha256": "abc123",
        "detector": "recorded",
        "width": 100,
        "height": 100,
        "fps": 5.0,
        "sample_fps": 5.0,
        "frames": [
            {
                "t": 0.0,
                "faces": [
                    {
                        "x": 10,
                        "y": 20,
                        "w": 30,
                        "h": 40,
                        "score": 0.9,
                        "landmarks": [[15, 30], [30, 30]],
                    }
                ],
            },
            {"t": 1.0, "faces": []},
        ],
    }


def test_load_faces_and_nearest_frame(tmp_path: Path) -> None:
    path = tmp_path / "faces.json"
    path.write_text(json.dumps(_document()), encoding="utf-8")

    document = load_faces(path)
    face = faces_at(document, 0.2)[0]

    assert face == Face(Box(10, 20, 30, 40), 0.9, ((15, 30), (30, 30)))
    assert faces_at(document, 0.8) == []


def test_replay_detector_returns_recorded_frames() -> None:
    detector = ReplayDetector(_document(), "abc123")
    image = np.zeros((100, 100, 3), dtype=np.uint8)

    assert len(detector.detect(image)) == 1
    assert detector.detect(image) == []
    with pytest.raises(ValueError, match="sha256"):
        ReplayDetector(_document(), "different")


def test_yunet_result_mapping_without_running_model() -> None:
    class Backend:
        def setInputSize(self, size: tuple[int, int]) -> None:
            assert size == (100, 80)

        def detect(self, image: np.ndarray) -> tuple[None, np.ndarray]:
            del image
            return None, np.array(
                [[10, 20, 30, 40, 15, 30, 30, 30, 22, 40, 17, 50, 28, 50, 0.95]],
                dtype=np.float32,
            )

    detector = YuNetDetector.__new__(YuNetDetector)
    detector._detector = Backend()

    face = detector.detect(np.zeros((80, 100, 3), dtype=np.uint8))[0]

    assert face.box == Box(10, 20, 30, 40)
    assert face.score == pytest.approx(0.95)
    assert len(face.landmarks) == 5


def test_detect_image_caches_fake_results(tmp_path: Path) -> None:
    path = tmp_path / "source.png"
    Image.new("RGB", (100, 80), "navy").save(path)
    calls = 0

    def detection(image: np.ndarray) -> list[Face]:
        nonlocal calls
        calls += 1
        assert image.shape == (80, 100, 3)
        return [Face(Box(10, 10, 20, 30), 0.95)]

    info = InputInfo(path, "source-hash")
    cache = tmp_path / "faces"
    first = detect_image(info, FakeDetector(detection), cache)
    second = detect_image(info, FakeDetector(detection), cache)

    assert first == second
    assert calls == 1
    assert faces_at(first, 0.0)[0].box == Box(10, 10, 20, 30)


@pytest.mark.parametrize(
    "content",
    ["", '{"schema": "postkitty.faces/1", "fra', '{"schema": "something/9"}', "[]"],
    ids=["empty", "truncated", "other-schema", "not-an-object"],
)
def test_detect_image_redetects_over_a_corrupt_cache(tmp_path: Path, content: str) -> None:
    path = tmp_path / "source.png"
    Image.new("RGB", (100, 80), "navy").save(path)
    info = InputInfo(path, "source-hash")
    cache = tmp_path / "faces"
    cache.mkdir()
    (cache / "source-hash.json").write_text(content, encoding="utf-8")

    document = detect_image(
        info, FakeDetector(lambda image: [Face(Box(10, 10, 20, 30), 0.95)]), cache
    )

    assert faces_at(document, 0.0)[0].box == Box(10, 10, 20, 30)
    assert load_faces(cache / "source-hash.json") == document


def test_detect_image_scales_16_bit_sources_before_detection(tmp_path: Path) -> None:
    path = tmp_path / "scan.png"
    ramp = np.linspace(0, 65535, 100 * 80, dtype=np.float64).reshape(80, 100)
    Image.fromarray(ramp.astype(np.uint16)).save(path)
    seen: list[float] = []

    def detection(image: np.ndarray) -> list[Face]:
        seen.append(float(image.mean()))
        return []

    detect_image(InputInfo(path, "scan-hash"), FakeDetector(detection), tmp_path / "faces")

    assert seen and 110 < seen[0] < 145


def test_saliency_finds_bright_object() -> None:
    image = np.zeros((200, 300, 3), dtype=np.uint8)
    cv2.rectangle(image, (190, 60), (260, 150), (255, 255, 255), -1)

    salient = saliency_box(image)

    assert salient is not None
    assert salient.intersect(Box(190, 60, 70, 90)).area > 0


def test_get_detector_uses_recording(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "faces.json"
    path.write_text(json.dumps(_document()), encoding="utf-8")
    monkeypatch.setenv("POSTKITTY_DETECTIONS", str(path))

    detector = get_detector(tmp_path)

    assert isinstance(detector, ReplayDetector)


def test_get_detector_loads_the_shared_model_not_a_per_job_copy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from engine.detect import faces as faces_module

    requested: list[object] = []

    def fake_model(cache_dir: Path | None = None) -> Path:
        requested.append(cache_dir)
        return tmp_path / "shared" / "model.onnx"

    class Stub:
        name = "stub"

        def __init__(self, model_path: Path | None = None) -> None:
            requested.append(model_path)

    monkeypatch.delenv("POSTKITTY_DETECTIONS", raising=False)
    monkeypatch.setattr(faces_module, "get_yunet_model", fake_model)
    monkeypatch.setattr(faces_module, "YuNetDetector", Stub)
    job_faces = tmp_path / "job" / "work" / "faces"

    get_detector(job_faces)

    assert job_faces not in requested
    assert requested[0] is None


@pytest.mark.real_detector
@pytest.mark.skipif(
    os.environ.get("POSTKITTY_REAL_DETECTOR") != "1",
    reason="real detector runs only in CI",
)
def test_real_detector_api_on_blank_image() -> None:
    detector = YuNetDetector()
    image = np.zeros((320, 320, 3), dtype=np.uint8)

    assert detector.detect(image) == []
