"""Make the repository root importable as the package ``postkitty`` (Hermes imports it that way).

Engine modules use relative imports, so tests that touch ``tools`` or the plugin entry point import them
as ``postkitty.engine.*``. The repository root is also put on ``sys.path`` for tests that import ``engine.*``.
"""

import importlib.util
import os
import sys
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


@pytest.fixture(autouse=True)
def _no_local_face_detector(monkeypatch, tmp_path):
    monkeypatch.setenv("POSTKITTY_FACES_CACHE", str(tmp_path / "shared-faces"))
    if os.environ.get("POSTKITTY_REAL_DETECTOR") == "1":
        return
    import importlib

    for name in ("engine.faces", "postkitty.engine.faces"):
        module = importlib.import_module(name)
        if hasattr(module, "get_detector"):
            monkeypatch.setattr(module, "get_detector", lambda cache_dir: _BlindDetector())
