from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from engine import doctor
from engine.detect import models

FILTERS_WITH_LIBASS = (
    " ... aresample         A->A       Resample audio data.\n"
    " ... ass               V->V       Render ASS subtitles onto input video using the libass library.\n"
)
FILTERS_WITHOUT_LIBASS = (
    " ... aresample         A->A       Resample audio data.\n"
    " ... bass              A->A       Boost or cut lower frequencies.\n"
)
MODULES = {
    "cv2": SimpleNamespace(__version__="4.12.0", FaceDetectorYN=object),
    "PIL": SimpleNamespace(__version__="11.3.0"),
    "numpy": SimpleNamespace(__version__="2.2.6"),
    "regex": SimpleNamespace(__version__="2025.9.18"),
    "ruamel.yaml": SimpleNamespace(__version__="0.18.15"),
}


@pytest.fixture
def setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
    """A machine where everything is in place; each test breaks one thing."""
    state = SimpleNamespace(
        tools={"ffmpeg": "/usr/bin/ffmpeg", "ffprobe": "/usr/bin/ffprobe"},
        filters=FILTERS_WITH_LIBASS,
        has_font=True,
        modules=dict(MODULES),
        cache=tmp_path / "models",
        out=tmp_path / "out",
    )
    payload = b"model bytes"
    state.cache.mkdir()
    (state.cache / models.YUNET_FILENAME).write_bytes(payload)
    state.out.mkdir()

    def run(command: list[str]) -> str:
        name = Path(command[0]).name
        return state.filters if "-filters" in command else f"{name} version 7.1 Copyright (c) the FFmpeg developers\n"

    def import_module(name: str) -> SimpleNamespace:
        if name not in state.modules:
            raise ModuleNotFoundError(f"No module named {name!r}")
        return state.modules[name]

    def never(*args: object, **kwargs: object) -> None:
        raise AssertionError("the doctor must not download or run the model")

    monkeypatch.setattr(models, "YUNET_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(models, "YUNET_SIZE", len(payload))
    monkeypatch.setattr(models, "model_cache_dir", lambda: state.cache)
    monkeypatch.setattr(models, "get_yunet_model", never)
    monkeypatch.setattr(models.urllib.request, "urlopen", never)
    monkeypatch.setattr(doctor.shutil, "which", lambda name: state.tools.get(name))
    monkeypatch.setattr(doctor, "_run", run)
    monkeypatch.setattr(doctor.caption_files, "has_font", lambda seconds: state.has_font)
    monkeypatch.setattr(doctor.importlib, "import_module", import_module)
    return state


def _items(report: dict) -> dict[str, dict]:
    return {item["id"]: item for item in report["items"]}


def test_a_complete_setup_reports_everything_working(setup: SimpleNamespace) -> None:
    report = doctor.report(setup.out)
    items = _items(report)

    assert list(items) == ["python", "ffmpeg", "ffprobe", "captions", "opencv", "pillow", "numpy", "regex", "yaml",
                           "face_model", "output_dir"]
    assert report["ok"] and all(item["ok"] and "fix" not in item for item in report["items"])
    assert report["works"] == {"text": True, "photos": True, "video": True, "captions": True}
    assert items["ffmpeg"]["version"] == "7.1" and items["ffmpeg"]["path"] == "/usr/bin/ffmpeg"
    assert items["opencv"]["face_detector"] is True
    assert items["face_model"]["path"] == str(setup.cache / models.YUNET_FILENAME)

    text = doctor.render_text(report)
    rows = [line for line in text.splitlines() if line.startswith(("ok  ", "no  "))]
    assert len(rows) == len(report["items"])
    assert len({line.index(items[key]["detail"]) for line, key in zip(rows, items, strict=True)}) == 1
    assert text.splitlines()[-1] == "Works now: text, photos, video, captions."


def test_without_ffmpeg_text_and_photos_still_work(setup: SimpleNamespace) -> None:
    setup.tools.clear()
    report = doctor.report(setup.out)
    items = _items(report)

    assert not report["ok"]
    assert report["works"] == {"text": True, "photos": True, "video": False, "captions": False}
    for key in ("ffmpeg", "ffprobe", "captions"):
        assert not items[key]["ok"]
        assert all(word in items[key]["fix"] for word in ("brew install ffmpeg", "apt install ffmpeg", "winget"))
    text = doctor.render_text(report)
    assert "no  ffmpeg" in text and "    fix: Install ffmpeg" in text
    assert text.splitlines()[-1] == "Works now: text, photos. Not yet: video, captions."


def test_an_ffmpeg_without_libass_makes_video_but_no_captions(setup: SimpleNamespace) -> None:
    setup.filters = FILTERS_WITHOUT_LIBASS
    report = doctor.report(setup.out)

    assert report["works"] == {"text": True, "photos": True, "video": True, "captions": False}
    assert "ffmpeg-full" in _items(report)["captions"]["fix"]


def test_captions_need_a_font_on_the_machine_too(setup: SimpleNamespace) -> None:
    setup.has_font = False
    report = doctor.report(setup.out)
    captions = _items(report)["captions"]

    assert report["works"] == {"text": True, "photos": True, "video": True, "captions": False}
    assert captions["detail"] == "ffmpeg has libass but found no font to draw the text with"
    assert "sudo apt install fonts-dejavu-core" in captions["fix"]


def test_an_ffmpeg_that_does_not_start_counts_as_missing(setup: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "_run", lambda command: "")
    items = _items(doctor.report(setup.out))

    assert not items["ffmpeg"]["ok"] and "does not start" in items["ffmpeg"]["detail"]


def test_without_opencv_only_text_works(setup: SimpleNamespace) -> None:
    del setup.modules["cv2"]
    report = doctor.report(setup.out)
    opencv = _items(report)["opencv"]

    assert report["works"] == {"text": True, "photos": False, "video": False, "captions": False}
    assert opencv["detail"] == "not installed" and "pip install -U opencv-contrib-python-headless" in opencv["fix"]
    assert doctor.render_text(report).splitlines()[-1] == "Works now: text. Not yet: photos, video, captions."


def test_an_opencv_without_the_face_detector_is_not_enough(setup: SimpleNamespace) -> None:
    setup.modules["cv2"] = SimpleNamespace(__version__="4.5.1")
    opencv = _items(doctor.report(setup.out))["opencv"]

    assert not opencv["ok"] and opencv["face_detector"] is False and "4.5.1 has no face detector" in opencv["detail"]


def test_a_library_that_fails_to_load_is_reported(setup: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(name: str) -> SimpleNamespace:
        if name == "numpy":
            raise RuntimeError("module compiled against ABI version 0x1000009")
        return setup.modules[name]

    monkeypatch.setattr(doctor.importlib, "import_module", broken)
    numpy = _items(doctor.report(setup.out))["numpy"]

    assert not numpy["ok"] and "does not load" in numpy["detail"]


def test_a_pillow_too_old_for_the_contact_sheet_is_flagged(setup: SimpleNamespace) -> None:
    setup.modules["PIL"] = SimpleNamespace(__version__="10.0.1")
    pillow = _items(doctor.report(setup.out))["pillow"]

    assert not pillow["ok"] and pillow["detail"] == "10.0.1 is older than 10.1"


def test_a_face_model_not_fetched_yet_is_no_fault_and_is_never_downloaded(setup: SimpleNamespace) -> None:
    (setup.cache / models.YUNET_FILENAME).unlink()
    report = doctor.report(setup.out)
    model = _items(report)["face_model"]

    assert model["ok"] and model["cached"] is False and "not downloaded yet" in model["detail"]
    assert report["ok"] and report["works"]["photos"] is True
    assert doctor.render_text(report).splitlines()[-1] == (
        "Works now: text, photos, video, captions. The first photo or video needs internet once for the face model."
    )
    assert list(setup.cache.iterdir()) == []


def test_a_damaged_face_model_is_told_apart_from_a_missing_one(setup: SimpleNamespace) -> None:
    (setup.cache / models.YUNET_FILENAME).write_bytes(b"cut short")
    model = _items(doctor.report(setup.out))["face_model"]

    assert model["cached"] is False and "damaged" in model["detail"]


def test_an_output_folder_that_does_not_exist_yet_is_fine_and_stays_absent(setup: SimpleNamespace) -> None:
    target = setup.out / "new" / "postkitty"
    folder = _items(doctor.report(target))["output_dir"]

    assert folder["ok"] and folder["exists"] is False and "will be created" in folder["detail"]
    assert not target.exists() and list(setup.out.iterdir()) == []


def test_an_output_folder_that_cannot_be_written_stops_everything(setup: SimpleNamespace) -> None:
    blocked = setup.out / "notes.txt"
    blocked.write_text("a file where the folder should be", encoding="utf-8")
    report = doctor.report(blocked)
    folder = _items(report)["output_dir"]

    assert not folder["ok"] and "output_dir" in folder["fix"]
    assert report["works"] == {"text": False, "photos": False, "video": False, "captions": False}
    assert doctor.render_text(report).splitlines()[-1] == "Works now: nothing yet. Not yet: text, photos, video, captions."


def test_the_output_folder_is_optional(setup: SimpleNamespace) -> None:
    report = doctor.report()

    assert "output_dir" not in _items(report) and report["works"]["text"] is True


def test_the_real_lookups_run_on_this_machine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(models, "model_cache_dir", lambda: tmp_path / "models")
    report = doctor.report(tmp_path)
    items = _items(report)

    # The suite itself needs ffmpeg, OpenCV and Pillow, so the doctor must find them here.
    for key in ("python", "ffmpeg", "ffprobe", "opencv", "pillow", "numpy", "regex", "output_dir"):
        assert items[key]["ok"], items[key]
    assert items["ffmpeg"]["version"] and Path(items["ffmpeg"]["path"]).is_file()
    assert doctor.render_text(report).splitlines()[-1].startswith("Works now: text, photos, video")
