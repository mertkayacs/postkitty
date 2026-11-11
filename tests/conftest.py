"""Make the repository root importable as the package ``postkitty`` (Hermes imports it that way).

Engine modules use relative imports, so tests that touch ``tools`` or the plugin entry point import them
as ``postkitty.engine.*``. The repository root is also put on ``sys.path`` for tests that import ``engine.*``.
"""

import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load_package(name: str = "postkitty"):
    spec = importlib.util.spec_from_file_location(name, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if "postkitty" not in sys.modules:
    load_package()
# When the checkout directory is not a valid identifier (for example a git worktree named a-core), pytest imports
# the root __init__.py as a top-level module named "__init__" while setting up the Package node. Hand it the
# package we already loaded instead of letting the relative imports fail.
sys.modules.setdefault("__init__", sys.modules["postkitty"])


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    """Job output directory for tool handler tests."""
    target = tmp_path / "out"
    monkeypatch.setenv("POSTKITTY_OUTPUT_DIR", str(target))
    return target


class _BlindDetector:
    """Stands in for YuNet in local tests: the face detector must never run on a dev box without consent."""

    name = "test-blind"

    def detect(self, image):
        return []


@dataclass(frozen=True)
class SpeakerMedia:
    info: object
    scan: object
    work: Path


class SpeakerDetector:
    """Returns the two synthetic face boxes without running a model."""

    name = "test-speakers"

    def detect(self, image):
        from engine.detect.faces import Face
        from engine.photo.framing import Box

        height, width = image.shape[:2]
        x_scale = width / 1280
        y_scale = height / 720
        return [
            Face(Box(80 * x_scale, 150 * y_scale, 240 * x_scale, 300 * y_scale), 0.99),
            Face(Box(960 * x_scale, 150 * y_scale, 240 * x_scale, 300 * y_scale), 0.99),
        ]


def make_speaker_clip(root: Path) -> Path:
    import cv2
    import numpy as np

    root.mkdir(parents=True, exist_ok=True)
    video_only = root / "speaker-video-only.mp4"
    output = root / "speaker.mp4"
    command = [
        "nice", "-n", "10", "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-nostdin", "-threads", "4", "-y", "-f", "rawvideo", "-pix_fmt",
        "bgr24", "-s", "1280x720", "-r", "15", "-i", "pipe:0", "-an",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(video_only),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdin is not None
    for index in range(9 * 15):
        t = index / 15
        frame = np.full((720, 1280, 3), 42, dtype=np.uint8)
        for center_x in (200, 1080):
            cv2.ellipse(frame, (center_x, 300), (120, 150), 0, 0, 360, (210, 210, 210), -1)
            cv2.circle(frame, (center_x - 42, 255), 12, (28, 28, 28), -1)
            cv2.circle(frame, (center_x + 42, 255), 12, (28, 28, 28), -1)
        first_open = (t < 3 or 6 <= t < 8) and index % 3 != 0
        second_open = (3 <= t < 8) and index % 3 != 0
        for center_x, is_open in ((200, first_open), (1080, second_open)):
            mouth_height = 48 if is_open else 6
            cv2.rectangle(
                frame,
                (center_x - 58, 390 - mouth_height // 2),
                (center_x + 58, 390 + mouth_height // 2),
                (22, 22, 22),
                -1,
            )
        process.stdin.write(frame.tobytes())
    process.stdin.close()
    stderr = process.stderr.read() if process.stderr is not None else b""
    assert process.wait() == 0, stderr.decode(errors="replace")

    subprocess.run(
        [
            "nice", "-n", "10", "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-nostdin", "-threads", "4", "-y", "-i", str(video_only), "-f",
            "lavfi", "-i", "sine=frequency=220:sample_rate=16000:duration=8",
            "-filter_complex", "[1:a]apad=pad_dur=1[a]", "-map", "0:v", "-map",
            "[a]", "-c:v", "copy", "-c:a", "aac", "-t", "9", str(output),
        ],
        check=True,
        capture_output=True,
    )
    return output


@pytest.fixture(scope="session")
def speaker_media(tmp_path_factory):
    from engine.probe import probe
    from engine.video.scan import scan_video

    root = tmp_path_factory.mktemp("speaker-media")
    info = probe(make_speaker_clip(root), "speaker")
    work = root / "work"
    scan = scan_video(info, SpeakerDetector(), work)
    return SpeakerMedia(info, scan, work)


@pytest.fixture(autouse=True)
def _no_local_face_detector(monkeypatch, tmp_path):
    monkeypatch.setenv("POSTKITTY_FACES_CACHE", str(tmp_path / "shared-faces"))
    if os.environ.get("POSTKITTY_REAL_DETECTOR") == "1":
        return
    import importlib

    for name in ("engine.detect.faces", "postkitty.engine.detect.faces"):
        module = importlib.import_module(name)
        if hasattr(module, "get_detector"):
            monkeypatch.setattr(module, "get_detector", lambda cache_dir: _BlindDetector())
