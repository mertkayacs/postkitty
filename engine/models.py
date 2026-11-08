"""YuNet model retrieval for local face detection.

Model: OpenCV Zoo face_detection_yunet_2023mar.onnx
Version: 2023mar from opencv_zoo commit 48b10fa505aeb51fbd127fc60a5c660040e823b7
URL: https://github.com/opencv/opencv_zoo/raw/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
License: MIT, Copyright (c) 2020 Shiqi Yu
Purpose: detect face boxes and five facial landmarks for subject-aware framing.
"""

from __future__ import annotations

import hashlib
import tempfile
import urllib.request
from pathlib import Path

YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"
YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
YUNET_SIZE = 232_589
YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/"
    "48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_detection_yunet/"
    f"{YUNET_FILENAME}"
)


def model_cache_dir() -> Path:
    try:
        from plugins.plugin_storage import plugin_data_dir
    except ImportError:
        return Path.home() / ".cache" / "postkitty" / "models"
    return plugin_data_dir("postkitty") / "models"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_yunet(path: Path) -> bool:
    return path.stat().st_size == YUNET_SIZE and file_sha256(path) == YUNET_SHA256


def get_yunet_model(cache_dir: Path | None = None) -> Path:
    directory = cache_dir or model_cache_dir()
    path = directory / YUNET_FILENAME
    if path.exists():
        if verify_yunet(path):
            return path
        raise ValueError(f"YuNet model checksum mismatch: {path}")

    directory.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(YUNET_URL, headers={"User-Agent": "postkitty/0.1"})
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=directory, prefix=f".{YUNET_FILENAME}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            with urllib.request.urlopen(request, timeout=60) as response:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    handle.write(chunk)
        if not verify_yunet(temporary):
            raise ValueError("downloaded YuNet model failed checksum verification")
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return path
