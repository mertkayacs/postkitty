import hashlib
import json
import os
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image
from postkitty import tools
from postkitty.engine import checks, repair

LONG_X = " ".join(f"Sentence number {i} is here." for i in range(40))


def call(handler, **args):
    return json.loads(handler(args))


@pytest.fixture
def text_job(out_dir):
    return call(tools.scan, text=LONG_X)["job"]


def test_every_handler_returns_json_error_instead_of_raising(out_dir):
    assert "error" in call(tools.scan)
    assert "error" in call(tools.copy)
    assert "error" in call(tools.make, job="missing")
    assert "error" in call(tools.redo, job="missing", target="tiktok", layout="pad")
    assert "error" in call(tools.check)
    assert json.loads(tools.scan(None))["error"]
    assert "unknown platform" in call(tools.scan, text="hi", platforms=["myspace"])["error"]


def test_text_only_scan(out_dir):
    out = call(tools.scan, text="Big news #launch @friend https://example.com", platforms=["x", "bluesky"])
    assert Path(out["job_dir"]).is_dir() and out["inputs"] == [] and out["plan"] == []
    assert out["text"]["hashtags"] == 1 and out["text"]["urls"] == 1
    assert set(out["fit"]) == {"x", "bluesky"} and out["peek"] is None
    manifest = json.loads((Path(out["job_dir"]) / "manifest.json").read_text())
    assert manifest["text"]["chars"] == len("Big news #launch @friend https://example.com")


def test_text_only_scan_then_copy_end_to_end(out_dir, text_job):
    advice = {"topic": "Sentences", "audience": "testers", "tone": "dry", "key_message": "Counting works",
              "ranking": [{"platform": "x", "reason": "short text"}], "tips": ["Keep it short"]}
    out = call(tools.copy, job=text_job, advice=advice,
               drafts={"x": LONG_X, "linkedin": "A short note for LinkedIn."})
    job = out_dir / text_job
    x = out["platforms"]["x"]
    assert x["ok"] and x["split"] and len(x["parts"]) >= 2 and x["unit"] == "x_weighted" and x["limit"] == 280
    assert all(p["count"] <= 280 for p in x["parts"])
    thread = (job / "ready/x/thread.txt").read_text().split("\n\n---\n\n")
    assert len(thread) == len(x["parts"]) and thread[0].rstrip().endswith(f"1/{len(thread)}")
    assert not (job / "ready/x/post.txt").exists()
    assert (job / "ready/linkedin/post.txt").read_text().strip() == "A short note for LinkedIn."
    assert out["all_ok"] is True and (job / "advice.md").is_file()
    manifest = json.loads((job / "manifest.json").read_text())
    assert manifest["copy"]["x"]["ok"] and manifest["advice"]["topic"] == "Sentences"
    assert "## Key message" in (job / "advice.md").read_text()


def test_copy_reports_overflow_and_writes_no_ready_file(out_dir, text_job):
    out = call(tools.copy, job=text_job, drafts={"x": LONG_X}, split_threads=False)
    x = out["platforms"]["x"]
    assert not x["ok"] and x["overflow"] > 0 and x["files"] == [] and out["all_ok"] is False
    assert not (out_dir / text_job / "ready/x/post.txt").exists()


def test_rewrite_removes_stale_thread(out_dir, text_job):
    call(tools.copy, job=text_job, drafts={"x": LONG_X})
    assert (out_dir / text_job / "ready/x/thread.txt").exists()
    call(tools.copy, job=text_job, drafts={"x": "short now"})
    assert not (out_dir / text_job / "ready/x/thread.txt").exists()
    assert (out_dir / text_job / "ready/x/post.txt").read_text().strip() == "short now"


def test_instagram_hashtag_cap_blocks_ready(out_dir, text_job):
    out = call(tools.copy, job=text_job, drafts={"instagram": " ".join(f"#t{i}" for i in range(31))})
    assert out["platforms"]["instagram"]["ok"] is False and out["platforms"]["instagram"]["hashtags"] == 31


def test_recommendation_only_limit_still_writes_file(out_dir, text_job):
    out = call(tools.copy, job=text_job, drafts={"youtube": "T" * 120})
    yt = out["platforms"]["youtube"]
    assert yt["ok"] is False and yt["enforcement"] == "recommendation" and yt["files"] and out["all_ok"] is True


def test_platform_aliases_map_to_the_canonical_name(out_dir, text_job):
    out = call(tools.copy, job=text_job, drafts={"twitter": ["only one"], "ig": "hello"})
    assert set(out["platforms"]) == {"x", "instagram"}


def test_drafts_are_per_platform_not_per_target(out_dir, text_job):
    assert "per platform" in call(tools.copy, job=text_job, drafts={"x_video": "hi"})["error"]


def test_alt_text_by_target_and_file(out_dir, text_job):
    job = out_dir / text_job
    (job / "ready/instagram").mkdir(parents=True, exist_ok=True)
    (job / "ready/instagram/feed.jpg").write_bytes(b"x")
    out = call(tools.copy, job=text_job, alt_text={"x_image": "A red door.", "feed.jpg": "A cat on a sofa.", "nope": "?"})
    assert out["alt_text_unmatched"] == ["nope"]
    assert "A red door." in (job / "ready/x/alt.txt").read_text()
    assert "A cat on a sofa." in (job / "ready/instagram/alt.txt").read_text()


def test_make_on_text_only_job_explains(out_dir, text_job):
    assert "no media targets" in call(tools.make, job=text_job)["error"]


def test_image_scan_plans_every_image_target(out_dir, tmp_path):
    photo = tmp_path / "photo.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    out = call(tools.scan, inputs=[str(photo)], text="Hello", platforms=["instagram", "x"])
    assert out["inputs"][0]["kind"] == "image" and out["inputs"][0]["width"] == 1600
    assert {p["id"] for p in out["plan"]} == {"instagram_feed", "instagram_story", "x_image"}
    assert out["peek"] and Path(out["peek"]).is_file()
    assert not any("image engine" in n for n in out["notes"])


def test_bad_input_file_is_reported(out_dir, tmp_path):
    out = call(tools.scan, inputs=[str(tmp_path / "missing.jpg")])
    assert "not found" in out["error"]


def test_check_reports_dimension_failure(out_dir, tmp_path):
    photo = tmp_path / "p.jpg"
    Image.new("RGB", (1000, 1000), "red").save(photo)
    out = call(tools.check, path=str(photo), target="instagram_feed")
    failed = {c["id"] for c in out["checks"] if c["status"] == "fail"}
    assert out["pass"] is False and failed & {"image.width", "image.height"}
    ok = tmp_path / "ok.jpg"
    Image.new("RGB", (1080, 1350), "red").save(ok)
    assert call(tools.check, path=str(ok), target="instagram_feed")["pass"] is True
    assert "target" in call(tools.check, path=str(ok))["error"]


# --- media flow with stub engines (no OpenCV, no models) ---------------------------------------------------

@dataclass
class FakeLayout:
    mode: str
    note: str = "stub"
    boxes: tuple = ()


@pytest.fixture
def stub_image_engine(monkeypatch):
    """Install fake faces, image_make and checks_image modules under postkitty.engine."""
    renders = []

    faces = types.ModuleType("postkitty.engine.faces")
    faces.get_detector = lambda cache_dir: object()
    faces.detect_image = lambda info, detector, cache_dir: {"frames": [{"t": 0.0, "faces": [{"x": 1}, {"x": 2}]}]}

    image_make = types.ModuleType("postkitty.engine.image_make")
    image_make.plan_image = lambda info, faces_doc, target, override=None: FakeLayout(
        (override or {}).get("layout") or "crop")

    def render_image(info, layout, target, out_path):
        renders.append((target.id, layout.mode))
        Image.new("RGB", (target.width, target.height), "green").save(out_path, quality=90)
        return checks.RenderResult(target.id, out_path, target.width, target.height, None, out_path.stat().st_size,
                                   {"mode": layout.mode, "note": layout.note}, 1.0, {})

    image_make.render_image = render_image
    checks_image = types.ModuleType("postkitty.engine.checks_image")
    for name, mod in (("faces", faces), ("image_make", image_make), ("checks_image", checks_image)):
        monkeypatch.setitem(sys.modules, f"postkitty.engine.{name}", mod)
        monkeypatch.setattr(sys.modules["postkitty.engine"], name, mod, raising=False)
    monkeypatch.setattr(checks, "_CHECKERS", {"image": [], "video": []})
    monkeypatch.setattr(repair, "_STRATEGIES", {})
    return renders


def test_image_flow_make_redo_check(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    scan = call(tools.scan, inputs=[str(photo)], platforms=["instagram", "x"])
    assert scan["inputs"][0]["people"] == 2 and scan["notes"] == []
    assert {p["id"]: p["layout"] for p in scan["plan"]}["x_image"] == "crop"
    job = scan["job"]

    made = call(tools.make, job=job)
    table = {row["target"]: row for row in made["targets"]}
    assert set(table) == {"instagram_feed", "instagram_story", "x_image"}
    assert all(row["status"] == "ready" for row in table.values()), table
    assert table["x_image"]["file"] == "ready/x/image.jpg" and table["x_image"]["size"] == "1600x900"
    assert (out_dir / job / "ready/instagram/feed.jpg").is_file()
    assert "board_note" in made  # the board lane is not merged in this worktree
    manifest = json.loads((out_dir / job / "manifest.json").read_text())
    assert {t["id"] for t in manifest["targets"]} == set(table)
    assert manifest["targets"][0]["checks"] and manifest["targets"][0]["layout"]["mode"] == "crop"

    redone = call(tools.redo, job=job, target="x_image", layout="pad")
    assert redone["targets"][0]["layout"]["mode"] == "pad" and redone["targets"][0]["status"] == "ready"
    again = json.loads((out_dir / job / "manifest.json").read_text())
    assert next(t for t in again["targets"] if t["id"] == "x_image")["override"] == {"layout": "pad"}
    assert len(again["targets"]) == 3

    assert call(tools.check, job=job)["all_pass"] is True
    assert "give at least one" in call(tools.redo, job=job, target="x_image")["error"]


def test_make_subset_and_failed_target_stays_out_of_ready(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]

    def failing(res, target):
        return [checks.Check("image.bytes_max", target.id, "fail", True, 9, 1, "too big")]

    checks.register_checker("image", failing)
    made = call(tools.make, job=job, targets=["x"])
    row = made["targets"][0]
    assert row["status"] == "failed" and row["problems"] == ["too big"] and row.get("file") is None
    assert not (out_dir / job / "ready/x/image.jpg").exists()
    assert (out_dir / job / "work/failed/x_image.jpg").is_file()


def test_repair_marks_target_repaired(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]
    seen = {}

    def checker(res, target):
        bad = res.layout["mode"] != "pad"
        return [checks.Check("frame.subjects_inside", target.id, "fail" if bad else "pass", True, 0, 1, "cut")]

    def to_pad(res, target, check, rerender):
        seen["keys"] = sorted(rerender)
        return rerender["render"]({"layout": "pad"})

    checks.register_checker("image", checker)
    repair.register("frame.subjects_inside", to_pad)
    row = call(tools.make, job=job)["targets"][0]
    assert row["status"] == "repaired" and row["layout"]["mode"] == "pad" and row["repairs"]
    assert seen["keys"] == ["info", "job", "overrides", "render"]


def test_same_size_targets_share_one_master_render(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["instagram_feed", "instagram_story", "threads_image"])["job"]
    call(tools.make, job=job)
    rendered = [t for t, _ in stub_image_engine]
    assert sorted(rendered) == ["instagram_feed", "instagram_story"]  # threads_image copies the feed render
    assert (out_dir / job / "ready/threads/image.jpg").is_file()


def test_missing_video_engine_skips_video_targets(out_dir, tmp_path, monkeypatch):
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg not installed")
    clip = tmp_path / "c.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1", "-pix_fmt",
                    "yuv420p", str(clip)], check=True)
    monkeypatch.setitem(sys.modules, "postkitty.engine.video_scan", None)  # simulate a missing module
    scan = call(tools.scan, inputs=[str(clip)], platforms=["tiktok"])
    assert scan["inputs"][0]["kind"] == "video" and scan["notes"] and scan["plan"][0]["id"] == "tiktok"
    made = call(tools.make, job=scan["job"])
    assert made["targets"][0]["status"] == "skipped" and "video engine" in made["targets"][0]["reason"]


def test_slash_command_text():
    text = tools.targets_overview("")
    assert "tiktok: 1080x1920 video" in text and "X: text 280 x_weighted" in text
    assert tools.targets_overview("platforms x").count("X:") == 1 and "TikTok" not in tools.targets_overview("x")
    assert tools.targets_overview("zzz") == "No matching platform."


def test_scan_reuses_shared_detections_without_building_a_detector(out_dir, tmp_path, monkeypatch):
    photo = tmp_path / "group.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    sha = hashlib.sha256(photo.read_bytes()).hexdigest()
    shared = Path(os.environ["POSTKITTY_FACES_CACHE"])
    shared.mkdir(parents=True, exist_ok=True)
    face = {"x": 700.0, "y": 300.0, "w": 200.0, "h": 240.0, "score": 0.93, "landmarks": []}
    doc = {"schema": "postkitty.faces/1", "source_sha256": sha, "detector": "yunet-2023mar", "width": 1600,
           "height": 1200, "fps": None, "sample_fps": None, "frames": [{"t": 0.0, "faces": [face]}]}
    (shared / f"{sha}.json").write_text(json.dumps(doc))

    def refuse(cache_dir):
        raise AssertionError("a shared cache hit must not build a detector")

    monkeypatch.setattr(sys.modules["postkitty.engine.faces"], "get_detector", refuse)
    out = call(tools.scan, inputs=[str(photo)], platforms=["instagram"])
    assert out["inputs"][0]["people"] == 1
