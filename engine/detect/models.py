"""YuNet model retrieval for local face detection.

Model: OpenCV Zoo face_detection_yunet_2023mar.onnx
Version: 2023mar from opencv_zoo commit 48b10fa505aeb51fbd127fc60a5c660040e823b7
URL: https://github.com/opencv/opencv_zoo/raw/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
License: MIT, Copyright (c) 2020 Shiqi Yu
Purpose: detect face boxes and five facial landmarks for subject-aware framing.
"""

from __future__ import annotations

import hashlib
import http.client
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from .. import __version__

YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"
YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
YUNET_SIZE = 232_589
YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/"
    "48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_detection_yunet/"
    f"{YUNET_FILENAME}"
)
# GitHub's file host sometimes answers 5xx, times out or drops a transfer for a minute; those are retried.
RETRY_DELAYS = (2.0, 5.0, 10.0)


class ModelUnavailable(RuntimeError):
    """The face model is not cached and could not be downloaded. The message is written for the user."""


_data_dir: Path | None = None


def set_data_dir(path: str | Path) -> None:
    """Name the folder postkitty keeps its downloads in. The host passes its per-plugin data folder."""
    global _data_dir
    _data_dir = Path(path).expanduser()


def model_cache_dir() -> Path:
    return (_data_dir or Path.home() / ".cache" / "postkitty") / "models"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_yunet(path: Path) -> bool:
    return path.stat().st_size == YUNET_SIZE and file_sha256(path) == YUNET_SHA256


def get_yunet_model(cache_dir: Path | None = None) -> Path:
    """Path of the verified face model, downloaded into the cache on first use.

    A cached file that fails its checksum is never returned; a fresh download replaces it.
    Raises ModelUnavailable when the model is neither cached nor downloadable.
    """
    directory = cache_dir or model_cache_dir()
    path = directory / YUNET_FILENAME
    if path.is_file() and verify_yunet(path):
        return path
    try:
        directory.mkdir(parents=True, exist_ok=True)
        for delay in (*RETRY_DELAYS, None):
            try:
                _download(directory, path)
                break
            except (OSError, http.client.HTTPException) as error:
                if delay is None or not _transient(error):
                    raise
                time.sleep(delay)
    except (OSError, http.client.HTTPException, ValueError) as error:
        raise ModelUnavailable(
            f"The face model is not on this machine and the download failed ({error}). postkitty fetches it "
            f"once from github.com (about 230 KB): connect to the internet and ask again, or save {YUNET_URL} "
            f"into {directory}. Text posts work without it."
        ) from error
    return path


def _transient(error: Exception) -> bool:
    """Worth another try: the host answered 429 or 5xx, timed out or dropped the transfer.

    No route to the host (offline, DNS, refused) fails at once, so an offline scan does not stall.
    """
    if isinstance(error, urllib.error.HTTPError):
        return error.code == 429 or error.code >= 500
    reason = getattr(error, "reason", error)
    return isinstance(reason, (TimeoutError, ConnectionResetError)) or isinstance(error, http.client.HTTPException)


def _download(directory: Path, path: Path) -> None:
    request = urllib.request.Request(YUNET_URL, headers={"User-Agent": f"postkitty/{__version__}"})
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
            raise ValueError("the downloaded file failed checksum verification")
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
