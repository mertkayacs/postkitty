from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from engine import seams
from engine.framing import Box


def _source(path: Path) -> None:
    image = Image.new("RGB", (80, 40), "navy")
    ImageDraw.Draw(image).rectangle((50, 5, 65, 35), fill="red")
    image.save(path)


def test_python_seam_resize_is_exact_and_protects_subject(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source.png"
    output = tmp_path / "output.png"
    _source(source)
    monkeypatch.setattr(seams.shutil, "which", lambda name: None)

    seams.seam_resize(source, output, 60, 40, [Box(50, 5, 16, 31)])

    with Image.open(output) as image:
        array = np.asarray(image)
        assert image.size == (60, 40)
        assert np.count_nonzero((array[..., 0] > 180) & (array[..., 2] < 100)) > 300
    assert seams.seam_engine(output) == "python-forward-energy"


def test_caire_receives_source_sized_binary_mask_and_fresh_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source.png"
    output = tmp_path / "output.png"
    _source(source)
    observed: dict[str, object] = {}
    monkeypatch.setattr(seams.shutil, "which", lambda name: "/usr/bin/caire")

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        del kwargs
        mask = Path(command[command.index("-mask") + 1])
        temporary = Path(command[command.index("-out") + 1])
        with Image.open(mask) as image:
            observed["mask_size"] = image.size
            observed["mask_values"] = set(np.unique(np.asarray(image)))
        observed["temporary"] = temporary
        Image.new("RGB", (60, 40), "navy").save(temporary)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(seams.subprocess, "run", run)

    seams.seam_resize(source, output, 60, 40, [Box(50, 5, 16, 31)])

    assert observed["mask_size"] == (80, 40)
    assert observed["mask_values"] == {0, 255}
    assert observed["temporary"] != output
    assert seams.seam_engine(output) == "caire"


def test_large_image_small_reduction_is_exact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "large.png"
    output = tmp_path / "reduced.png"
    Image.new("RGB", (1601, 8), "navy").save(source)
    monkeypatch.setattr(seams.shutil, "which", lambda name: None)

    seams.seam_resize(source, output, 1600, 8, [])

    with Image.open(output) as image:
        assert image.size == (1600, 8)
