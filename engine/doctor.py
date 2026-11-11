"""Setup check behind ``/postkitty doctor``: what is installed, what is missing and how to fix it.

``report`` only looks. It downloads nothing, runs no model and leaves no file behind.
"""

from __future__ import annotations

import importlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .detect import models

MIN_PYTHON = (3, 11)
# ImageFont.load_default(size=...) on the contact sheet arrived in Pillow 10.1.
MIN_PILLOW = (10, 1)

_FFMPEG_FIX = (
    "Install ffmpeg and restart Hermes. macOS: brew install ffmpeg. Ubuntu or Debian: sudo apt install ffmpeg. "
    "Windows: winget install ffmpeg."
)
# Homebrew's ffmpeg formula is built without libass; ffmpeg-full has it and is not linked into PATH.
_LIBASS_FIX = (
    "Captions need an ffmpeg built with libass. macOS: brew install ffmpeg-full and put its bin folder first in "
    "PATH. Ubuntu or Debian: sudo apt install ffmpeg. Windows: winget install ffmpeg."
)
_WORKS = ("text", "photos", "video", "captions")


def report(output_dir: str | Path | None = None) -> dict:
    """Check the setup and return ``{"ok", "items", "works"}``.

    Each item has ``id``, ``label``, ``ok`` and ``detail``, plus a one-line ``fix`` when it is not ok.
    ``works`` says which of text, photos, video and captions can run now. Pass the folder jobs are
    written to as ``output_dir`` to have it checked too.
    """
    ffmpeg = _tool("ffmpeg")
    items = [
        _python(),
        ffmpeg,
        _tool("ffprobe"),
        _captions(ffmpeg),
        _opencv(),
        _module("pillow", "Pillow", "PIL", "Pillow", MIN_PILLOW),
        _module("numpy", "NumPy", "numpy", "numpy"),
        _module("regex", "regex", "regex", "regex"),
        _module("yaml", "ruamel.yaml", "ruamel.yaml", "ruamel.yaml"),
        _face_model(),
    ]
    if output_dir is not None:
        items.append(_output_dir(Path(output_dir).expanduser()))
    return {"ok": all(item["ok"] for item in items), "items": items, "works": _works(items)}


def render_text(report: dict) -> str:
    """The report as an aligned plain list, ending with one line that says what works now."""
    items = report["items"]
    width = max(len(item["label"]) for item in items)
    lines = ["postkitty doctor", ""]
    for item in items:
        lines.append(f"{'ok' if item['ok'] else 'no'}  {item['label']:<{width}}  {item['detail']}")
        if not item["ok"]:
            lines.append(f"    fix: {item['fix']}")
    works = [name for name in _WORKS if report["works"][name]]
    waiting = [name for name in _WORKS if not report["works"][name]]
    summary = f"Works now: {', '.join(works) or 'nothing yet'}."
    if waiting:
        summary += f" Not yet: {', '.join(waiting)}."
    model = next(item for item in items if item["id"] == "face_model")
    if report["works"]["photos"] and not model["cached"]:
        summary += " The first photo or video needs internet once for the face model."
    return "\n".join([*lines, "", summary])


def _item(key: str, label: str, ok: bool, detail: str, fix: str, **facts: Any) -> dict:
    item = {"id": key, "label": label, "ok": ok, "detail": detail, **facts}
    if not ok:
        item["fix"] = fix
    return item


def _works(items: list[dict]) -> dict[str, bool]:
    passed = {item["id"]: item["ok"] for item in items}

    def ok(*keys: str) -> bool:
        return all(passed.get(key, True) for key in keys)

    text = ok("python", "regex", "yaml", "output_dir")
    photos = text and ok("pillow", "numpy", "opencv")
    video = photos and ok("ffmpeg", "ffprobe")
    return {"text": text, "photos": photos, "video": video, "captions": video and ok("captions")}


def _python() -> dict:
    version = ".".join(str(part) for part in sys.version_info[:3])
    needed = ".".join(str(part) for part in MIN_PYTHON)
    return _item(
        "python", "Python", sys.version_info[:2] >= MIN_PYTHON, version,
        f"postkitty needs Python {needed} or newer. Install it from python.org and reinstall Hermes with it.",
        version=version,
    )


def _run(command: list[str]) -> str:
    try:
        done = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=15)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout


def _tool(name: str) -> dict:
    path = shutil.which(name)
    if not path:
        return _item(name, name, False, "not found", _FFMPEG_FIX)
    found = re.search(rf"{name} version (\S+)", _run([path, "-version"]))
    if not found:
        return _item(name, name, False, f"found at {path} but it does not start", _FFMPEG_FIX, path=path)
    return _item(name, name, True, f"{found.group(1)} at {path}", "", path=path, version=found.group(1))


def _captions(ffmpeg: dict) -> dict:
    if not ffmpeg["ok"]:
        return _item("captions", "Captions", False, "need ffmpeg", _FFMPEG_FIX)
    filters = _run([ffmpeg["path"], "-hide_banner", "-filters"])
    libass = re.search(r"^\s*\S+\s+ass\s", filters, re.MULTILINE) is not None
    detail = "ffmpeg has libass" if libass else "this ffmpeg was built without libass"
    return _item("captions", "Captions", libass, detail, _LIBASS_FIX)


def _pip_fix(package: str) -> str:
    return f'Install it into the Python that runs Hermes: "{sys.executable}" -m pip install -U {package}'


def _import(module: str) -> tuple[Any, str]:
    try:
        return importlib.import_module(module), ""
    except ImportError:
        return None, "not installed"
    except Exception as error:  # a broken binary wheel can raise anything while it loads
        return None, f"installed but it does not load ({type(error).__name__})"


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version)[:2])


def _module(key: str, label: str, module: str, package: str, minimum: tuple[int, ...] = ()) -> dict:
    found, problem = _import(module)
    if found is None:
        return _item(key, label, False, problem, _pip_fix(package))
    version = str(getattr(found, "__version__", "unknown"))
    if minimum and _version_tuple(version) < minimum:
        needed = ".".join(str(part) for part in minimum)
        return _item(key, label, False, f"{version} is older than {needed}", _pip_fix(package), version=version)
    return _item(key, label, True, version, "", version=version)


def _opencv() -> dict:
    package = "opencv-contrib-python-headless"
    cv2, problem = _import("cv2")
    if cv2 is None:
        return _item("opencv", "OpenCV", False, problem, _pip_fix(package), face_detector=False)
    version = str(getattr(cv2, "__version__", "unknown"))
    face_detector = hasattr(cv2, "FaceDetectorYN")
    detail = f"{version}, face detector present" if face_detector else f"{version} has no face detector"
    return _item("opencv", "OpenCV", face_detector, detail, _pip_fix(package), version=version,
                 face_detector=face_detector)


def _face_model() -> dict:
    path = models.model_cache_dir() / models.YUNET_FILENAME
    try:
        cached = path.is_file() and models.verify_yunet(path)
    except OSError:
        cached = False
    if cached:
        detail = f"cached at {path}"
    elif path.is_file():
        detail = f"the cached copy is damaged, the next photo or video downloads it again ({path})"
    else:
        detail = f"not downloaded yet, the first photo or video fetches it ({path})"
    # Never a fault: postkitty fetches the model itself, so there is nothing for the user to install.
    return _item("face_model", "Face model", True, detail, "", path=str(path), cached=cached)


def _output_dir(path: Path) -> dict:
    # A folder that does not exist yet is created by the first scan, so its nearest parent decides.
    parent = path
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    try:
        with tempfile.TemporaryFile(dir=parent):
            writable = True
    except OSError:
        writable = False
    exists = path.is_dir()
    if writable:
        detail = f"{path} ({'writable' if exists else 'will be created'})"
    else:
        detail = f"{path} cannot be written"
    return _item(
        "output_dir", "Output folder", writable, detail,
        "Choose a folder you can write to: the postkitty setting output_dir or the POSTKITTY_OUTPUT_DIR variable.",
        path=str(path), exists=exists,
    )
