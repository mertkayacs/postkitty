import hashlib
import importlib
import json
import os
import shutil
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from postkitty import schemas, tools
from postkitty.engine import pipeline
from postkitty.engine.verify import checks, repair

LONG_X = " ".join(f"Sentence number {i} is here." for i in range(40))


def call(handler, **args):
    return json.loads(handler(args))


@pytest.fixture
def text_job(out_dir):
    return call(tools.scan, text=LONG_X)["job"]


def test_every_handler_returns_json_error_instead_of_raising(out_dir):
    assert "error" in call(tools.scan)
    assert "error" in call(tools.write)
    assert "error" in call(tools.make, job="missing")
    assert "error" in call(tools.redo, job="missing", target="tiktok", layout="pad")
    assert "error" in call(tools.check)
    assert json.loads(tools.scan(None))["error"]
    assert "unknown platform" in call(tools.scan, text="hi", platforms=["myspace"])["error"]


def test_wrong_argument_types_name_the_argument(out_dir, tmp_path, text_job):
    photo = tmp_path / "p.jpg"
    Image.new("RGB", (100, 100), "red").save(photo)
    cases = [
        (tools.scan, {"inputs": str(photo)}, "inputs"),
        (tools.scan, {"text": "hi", "platforms": "instagram"}, "platforms"),
        (tools.scan, {"text": ["a", "b"]}, "text"),
        (tools.write, {"job": text_job, "drafts": "hello"}, "drafts"),
        (tools.write, {"job": text_job, "alt_text": "hello"}, "alt_text"),
        (tools.write, {"job": text_job, "advice": "hello"}, "advice"),
        (tools.write, {"job": text_job, "drafts": {"x": "a"}, "split_threads": "no"}, "split_threads"),
        (tools.make, {"job": text_job, "targets": "x"}, "targets"),
        (tools.make, {"job": text_job, "overrides": ["x_image"]}, "overrides"),
    ]
    for handler, args, name in cases:
        out = call(handler, **args)
        assert f"'{name}'" in out["error"] and "Error:" not in out["error"], (name, out)
        assert "Unexpected" not in out["hint"], (name, out)


def test_text_only_scan(out_dir):
    out = call(tools.scan, text="Big news #launch @friend https://example.com", platforms=["x", "bluesky"])
    assert Path(out["job_dir"]).is_dir() and out["inputs"] == [] and out["plan"] == []
    assert out["text"]["hashtags"] == 1 and out["text"]["urls"] == 1
    assert set(out["fit"]) == {"x", "bluesky"} and out["peek"] is None
    manifest = json.loads((Path(out["job_dir"]) / "manifest.json").read_text())
    assert manifest["text"]["chars"] == len("Big news #launch @friend https://example.com")


def test_full_frame_plan_uses_same_shape_note():
    info = pipeline.probe.InputInfo("in1", Path("video.mp4"), "video", "0" * 64, 1920, 1080, 5.0, 30.0, True, 0, False)
    window = SimpleNamespace(x=0.0, y=0.0, w=1920.0, h=1080.0)
    plan = SimpleNamespace(layout="crop", note="single-subject camera path", windows=[window], trim=(0.0, 5.0))

    summary = pipeline._plan_summary(info, plan, pipeline.platforms.get_target("x_video"))

    assert summary["note"] == "Same shape as the source; the full frame is kept."


def test_text_only_scan_then_copy_end_to_end(out_dir, text_job):
    advice = {"topic": "Sentences", "audience": "testers", "tone": "dry", "key_message": "Counting works",
              "ranking": [{"platform": "x", "reason": "short text"}], "tips": ["Keep it short"]}
    out = call(tools.write, job=text_job, advice=advice,
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
    out = call(tools.write, job=text_job, drafts={"x": LONG_X}, split_threads=False)
    x = out["platforms"]["x"]
    assert not x["ok"] and x["overflow"] > 0 and x["files"] == [] and out["all_ok"] is False
    assert not (out_dir / text_job / "ready/x/post.txt").exists()


def test_rewrite_removes_stale_thread(out_dir, text_job):
    call(tools.write, job=text_job, drafts={"x": LONG_X})
    assert (out_dir / text_job / "ready/x/thread.txt").exists()
    call(tools.write, job=text_job, drafts={"x": "short now"})
    assert not (out_dir / text_job / "ready/x/thread.txt").exists()
    assert (out_dir / text_job / "ready/x/post.txt").read_text().strip() == "short now"


def test_instagram_hashtag_cap_blocks_ready(out_dir, text_job):
    out = call(tools.write, job=text_job, drafts={"instagram": " ".join(f"#t{i}" for i in range(31))})
    assert out["platforms"]["instagram"]["ok"] is False and out["platforms"]["instagram"]["hashtags"] == 31


def test_recommendation_only_limit_still_writes_file(out_dir, text_job):
    out = call(tools.write, job=text_job, drafts={"facebook": "T" * 63207})
    fb = out["platforms"]["facebook"]
    assert fb["ok"] is False and fb["enforcement"] == "recommendation" and fb["files"] and out["all_ok"] is True


def test_youtube_title_over_the_limit_writes_no_file(out_dir, text_job):
    out = call(tools.write, job=text_job, drafts={"youtube": "T" * 101})
    yt = out["platforms"]["youtube"]
    assert yt["ok"] is False and yt["enforcement"] == "hard" and yt["files"] == [] and out["all_ok"] is False


def test_platform_aliases_map_to_the_canonical_name(out_dir, text_job):
    out = call(tools.write, job=text_job, drafts={"twitter": ["only one"], "ig": "hello"})
    assert set(out["platforms"]) == {"x", "instagram"}


def test_drafts_accept_targets_and_prefer_platform_keys(out_dir, text_job):
    out = call(tools.write, job=text_job, drafts={"x_video": "target", "x": "platform"})

    assert out["platforms"]["x"]["parts"][0]["text"] == "platform"
    assert out["platforms"]["x"]["notes"] == ["Used the x platform draft instead of the x_video target draft."]
    assert "fold" not in out["platforms"]["x"]
    assert "fold_note" not in out["platforms"]["x"]


def test_two_target_drafts_for_one_platform_say_which_one_was_ignored(out_dir, text_job):
    out = call(tools.write, job=text_job, drafts={"x_video": "first", "x_image": "second"})
    x = out["platforms"]["x"]
    assert x["parts"][0]["text"] == "second"
    assert x["notes"] == ["Used the x_image target draft for x; the x_video draft was ignored."]


def test_redo_without_target_names_the_missing_argument(out_dir, text_job):
    out = call(tools.redo, job=text_job, layout="pad")
    assert "'target' is required" in out["error"]


def test_redo_rejects_the_unknown_seam_key(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]
    assert "seam" not in pipeline.OVERRIDE_KEYS
    assert "unknown argument 'seam'" in call(tools.redo, job=job, target="x_image", seam=0.5)["error"]


def test_check_on_a_job_without_ready_media_says_so(out_dir, text_job):
    out = call(tools.check, job=text_job)
    assert out["targets"] == {} and out["all_pass"] is False and "no ready media" in out["note"]


def test_alt_text_by_target_and_file(out_dir, text_job):
    job = out_dir / text_job
    (job / "ready/instagram").mkdir(parents=True, exist_ok=True)
    (job / "ready/instagram/feed.jpg").write_bytes(b"x")
    out = call(tools.write, job=text_job, alt_text={"x_image": "A red door.", "feed.jpg": "A cat on a sofa.", "nope": "?"})
    assert out["alt_text_unmatched"] == ["nope"]
    assert "A red door." in (job / "ready/x/alt.txt").read_text()
    assert (job / "ready/instagram/alt.txt").read_text() == "instagram_feed:\nA cat on a sofa.\n"
    manifest = json.loads((job / "manifest.json").read_text())
    assert set(manifest["alt_text"]) == {"x_image", "instagram_feed"}


def test_alt_text_accepts_input_name_and_ready_path(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "team.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]
    call(tools.make, job=job)
    ready = out_dir / job / "ready/x/image.jpg"

    by_input = call(tools.write, job=job, alt_text={"team.jpg": "A team photo."})
    by_ready = call(tools.write, job=job, alt_text={str(ready): "A generated crop."})

    assert by_input["alt_text_unmatched"] is None
    assert by_ready["alt_text_unmatched"] is None
    assert "x_image:\nA generated crop." in (ready.parent / "alt.txt").read_text()


def test_make_on_text_only_job_lists_the_copy_files_without_an_error(out_dir, text_job):
    call(tools.write, job=text_job, drafts={"x": LONG_X, "linkedin": "A short note."})
    out = call(tools.make, job=text_job)
    assert "error" not in out and out["targets"] == [] and out["job_dir"] == str(out_dir / text_job)
    assert sorted(out["files"]) == ["ready/linkedin/post.txt", "ready/x/thread.txt"]
    assert "text only" in out["note"] and "ready/" in out["note"]


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


def test_failed_scan_leaves_no_job_folder_behind(out_dir, tmp_path):
    (tmp_path / "notes.txt").write_text("hello")
    assert "error" in call(tools.scan, inputs=[str(tmp_path / "missing.jpg")], text="hi")
    assert "error" in call(tools.scan, inputs=[str(tmp_path / "notes.txt")])
    assert not out_dir.exists() or list(out_dir.iterdir()) == []


def test_directory_input_is_named_as_such(out_dir, tmp_path):
    out = call(tools.scan, inputs=[str(tmp_path)])
    assert "is a directory" in out["error"] and "not found" not in out["error"]
    out = call(tools.check, path=str(tmp_path), target="x_image")
    assert "is a directory" in out["error"]


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


def test_check_reuses_framing_data_for_job_and_ready_path(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]

    def framing(res, target):
        status = "skipped" if res.subjects_inside is None else "pass"
        return [checks.Check("frame.subjects_inside", target.id, status, True, res.subjects_inside, 1.0, "framing")]

    checks.register_checker("image", framing)
    call(tools.make, job=job)
    ready = out_dir / job / "ready/x/image.jpg"
    manifest = json.loads((out_dir / job / "manifest.json").read_text())

    assert manifest["targets"][0]["subjects_inside"] == 1.0
    assert call(tools.check, job=job)["targets"]["x_image"]["checks"] == "all checks pass"
    assert call(tools.check, path=str(ready))["checks"] == "all checks pass"


def test_check_explains_skipped_framing_for_external_file(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "external.jpg"
    Image.new("RGB", (1600, 900), "orange").save(photo)

    def framing(res, target):
        return [checks.Check("frame.subjects_inside", target.id, "skipped", False, None, 1.0, "old message")]

    checks.register_checker("image", framing)
    result = call(tools.check, path=str(photo), target="x_image")
    frame = next(item for item in result["checks"] if item["id"] == "frame.subjects_inside")

    assert frame["message"] == "Subject framing was skipped because this file was not made by postkitty."


# --- media flow with stub engines (no OpenCV, no models) ---------------------------------------------------

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
    assert "board" in made and "board_inline" in made and "contact" in made
    assert Path(made["board"]).is_file()
    assert Path(made["board_inline"]).is_file()
    assert Path(made["contact"]).is_file()
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


def test_make_keeps_overrides_stored_by_redo(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x", "linkedin"])["job"]
    assert call(tools.redo, job=job, target="x_image", layout="pad")["targets"][0]["layout"]["mode"] == "pad"

    made = {row["target"]: row for row in call(tools.make, job=job)["targets"]}
    assert made["x_image"]["layout"]["mode"] == "pad" and made["linkedin_image"]["layout"]["mode"] == "crop"
    manifest = json.loads((out_dir / job / "manifest.json").read_text())
    assert next(t for t in manifest["targets"] if t["id"] == "x_image")["override"] == {"layout": "pad"}

    call(tools.make, job=job, overrides={"x_image": {"focus": "left"}})
    manifest = json.loads((out_dir / job / "manifest.json").read_text())
    assert next(t for t in manifest["targets"] if t["id"] == "x_image")["override"] == {"layout": "pad", "focus": "left"}


def test_photo_scanned_for_a_video_platform_explains_the_mismatch(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    scan = call(tools.scan, inputs=[str(photo)], platforms=["tiktok", "youtube_shorts"])
    assert scan["plan"] == []
    assert "tiktok takes video; the inputs are photos" in scan["notes"]
    assert "youtube_shorts takes video; the inputs are photos" in scan["notes"]
    made = call(tools.make, job=scan["job"])
    assert "tiktok takes video" in made["error"] and "text only" not in made["error"]


def test_copy_rejects_empty_and_non_string_drafts(out_dir, text_job):
    for value in (None, {"text": "hi"}, 42, "", "   ", [1, 2], [], ["ok", ""]):
        out = call(tools.write, job=text_job, drafts={"x": value})
        assert "draft for 'x'" in out["error"], (value, out)
    assert not (out_dir / text_job / "ready/x/post.txt").exists()
    assert call(tools.write, job=text_job, drafts={"x": ["first", "second"]})["platforms"]["x"]["ok"]


def test_alt_text_file_name_matching_two_targets_is_ambiguous(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x", "bluesky"])["job"]
    call(tools.make, job=job)
    ready = out_dir / job / "ready/x/image.jpg"

    out = call(tools.write, job=job, alt_text={"image.jpg": "which one?"})
    assert "image.jpg" in out["error"] and "x_image" in out["error"] and "bluesky_image" in out["error"]
    assert not (out_dir / job / "ready/x/alt.txt").exists()

    out = call(tools.write, job=job, alt_text={"x_image": "A door.", str(ready): "A window."})
    assert "x_image" in out["error"] and "twice" in out["error"]

    out = call(tools.write, job=job, alt_text={str(ready): "A door."})
    assert out["alt_text_unmatched"] is None
    manifest = json.loads((out_dir / job / "manifest.json").read_text())
    assert manifest["alt_text"] == {"x_image": "A door."}
    assert (out_dir / job / "ready/x/alt.txt").read_text() == "x_image:\nA door.\n"


def test_override_values_are_validated_before_rendering(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]
    bad = ({"trim": 5}, {"trim": [None, 2]}, {"trim": [3, 1]}, {"trim": "0-2"}, {"cover_at": [1]}, {"cover_at": -1},
           {"focus": "person:0"}, {"focus": 3}, {"focus": "x:1.5"}, {"layout": "blur"})
    for args in bad:
        out = call(tools.redo, job=job, target="x_image", **args)
        assert "error" in out and "Error:" not in out["error"] and "Unexpected" not in out["hint"], (args, out)
        key = next(iter(args))
        assert key in out["error"] or (key == "focus" and "person" in out["error"]), (args, out)
    out = call(tools.make, job=job, overrides={"x_image": {"trim": 5}})
    assert "trim" in out["error"] and "Unexpected" not in out["hint"]

    out = call(tools.redo, job=job, target="x_image", trim=[0, 1], cover_at=0.5)
    assert "video only" in out["error"]
    assert not stub_image_engine, "nothing may render when an override is rejected"


def test_check_names_a_media_kind_mismatch(out_dir, tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg not installed")
    import subprocess

    clip = tmp_path / "c.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1", "-pix_fmt",
                    "yuv420p", str(clip)], check=True)
    photo = tmp_path / "p.jpg"
    Image.new("RGB", (1080, 1920), "red").save(photo)

    out = call(tools.check, path=str(clip), target="x_image")
    assert out["error"] == "c.mp4 is a video; x_image takes photos"
    out = call(tools.check, path=str(photo), target="tiktok")
    assert out["error"] == "p.jpg is a photo; tiktok takes videos"
    assert call(tools.check, path=str(photo), target="instagram_story")["pass"] is True


def test_make_rejects_unknown_override_targets_and_keys(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]

    assert "tik_tok" in call(tools.make, job=job, overrides={"tik_tok": {"layout": "pad"}})["error"]
    assert "x_image" in call(tools.make, job=job, overrides={"x_image": "pad"})["error"]
    assert "person" in call(tools.make, job=job, overrides={"x_image": {"layout": "pad", "person": 2}})["error"]
    assert "instagram_feed" in call(tools.make, job=job, overrides={"instagram_feed": {"layout": "pad"}})["error"]
    made = call(tools.make, job=job, overrides={"X_IMAGE": {"layout": "pad"}})
    assert made["targets"][0]["layout"]["mode"] == "pad"


def test_make_refuses_an_input_that_changed_since_the_scan(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]
    Image.new("RGB", (900, 900), "blue").save(photo)

    out = call(tools.make, job=job)
    assert "changed since the scan" in out["error"] and "postkitty_scan" in out["hint"]
    assert "changed since the scan" in call(tools.redo, job=job, target="x_image", layout="pad")["error"]
    photo.unlink()
    assert "missing" in call(tools.make, job=job)["error"]


def test_rescan_with_new_inputs_drops_stale_targets_and_ready_media(out_dir, tmp_path, stub_image_engine):
    first, second = tmp_path / "a.jpg", tmp_path / "b.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(first)
    Image.new("RGB", (1200, 1600), "blue").save(second)
    job = call(tools.scan, inputs=[str(first)], platforms=["x"])["job"]
    call(tools.make, job=job)
    call(tools.write, job=job, drafts={"x": "keep me"})
    assert (out_dir / job / "ready/x/image.jpg").is_file()

    out = call(tools.scan, job=job, inputs=[str(second)], platforms=["instagram_feed"])

    assert out["job"] == job and [p["id"] for p in out["plan"]] == ["instagram_feed"]
    manifest = json.loads((out_dir / job / "manifest.json").read_text())
    assert manifest["targets"] == [] and manifest["inputs"][0]["path"] == str(second)
    assert not (out_dir / job / "ready/x/image.jpg").exists()
    assert (out_dir / job / "ready/x/post.txt").read_text().strip() == "keep me"
    assert call(tools.check, job=job)["targets"] == {}


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


def test_failed_redo_keeps_the_previous_ready_file(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]
    assert call(tools.make, job=job)["targets"][0]["status"] == "ready"
    ready = out_dir / job / "ready/x/image.jpg"
    before = ready.read_bytes()

    def failing(res, target):
        return [checks.Check("image.bytes_max", target.id, "fail", True, 9, 1, "too big")]

    checks.register_checker("image", failing)
    row = call(tools.redo, job=job, target="x_image", layout="pad")["targets"][0]

    assert row["status"] == "failed" and row.get("file") is None
    assert ready.read_bytes() == before and row["kept"] == "ready/x/image.jpg"
    manifest = json.loads((out_dir / job / "manifest.json").read_text())
    assert manifest["targets"][0]["status"] == "failed" and manifest["targets"][0]["kept"] == "ready/x/image.jpg"


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


def test_a_missing_package_skips_video_targets_and_names_it(out_dir, tmp_path, monkeypatch):
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg not installed")
    clip = tmp_path / "c.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1", "-pix_fmt",
                    "yuv420p", str(clip)], check=True)
    monkeypatch.delitem(sys.modules, "postkitty.engine.video.scan", raising=False)
    monkeypatch.setitem(sys.modules, "numpy", None)  # a dependency that was never installed
    scan = call(tools.scan, inputs=[str(clip)], platforms=["tiktok"])
    assert scan["inputs"][0]["kind"] == "video" and scan["notes"] and scan["plan"][0]["id"] == "tiktok"
    made = call(tools.make, job=scan["job"])
    assert made["targets"][0]["status"] == "skipped"
    assert "the Python package 'numpy' is missing" in made["targets"][0]["reason"]


def test_the_schemas_offer_exactly_the_layouts_and_override_keys_the_pipeline_takes() -> None:
    redo = schemas.SCHEMAS["postkitty_redo"]["parameters"]["properties"]
    per_target = schemas.SCHEMAS["postkitty_make"]["parameters"]["properties"]["overrides"]["additionalProperties"]
    assert redo["layout"]["enum"] == list(pipeline.LAYOUTS)
    assert set(redo) - {"job", "target"} == set(per_target["properties"]) == set(pipeline.OVERRIDE_KEYS)


def test_speaker_layout_make_returns_ready(out_dir, speaker_media) -> None:
    shared = Path(os.environ["POSTKITTY_FACES_CACHE"])
    shared.mkdir(parents=True, exist_ok=True)
    source = speaker_media.work / "faces" / f"{speaker_media.info.sha256}.json"
    shutil.copyfile(source, shared / source.name)
    scanned = call(
        tools.scan,
        inputs=[str(speaker_media.info.path)],
        platforms=["linkedin_video"],
    )

    made = call(
        tools.make,
        job=scanned["job"],
        overrides={"linkedin_video": {"layout": "speaker", "cover_at": 1.0}},
    )

    assert made["targets"][0]["status"] == "ready"
    assert made["targets"][0]["layout"]["mode"] == "speaker"


def test_people_count_matches_the_persons_focus_can_select(out_dir, tmp_path):
    photo = tmp_path / "pair.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    sha = hashlib.sha256(photo.read_bytes()).hexdigest()
    shared = Path(os.environ["POSTKITTY_FACES_CACHE"])
    shared.mkdir(parents=True, exist_ok=True)
    strong = {"x": 300.0, "y": 300.0, "w": 200.0, "h": 240.0, "score": 0.93, "landmarks": []}
    weak = {"x": 1100.0, "y": 300.0, "w": 200.0, "h": 240.0, "score": 0.5, "landmarks": []}
    doc = {"schema": "postkitty.faces/1", "source_sha256": sha, "detector": "yunet-2023mar", "width": 1600,
           "height": 1200, "fps": None, "sample_fps": None, "frames": [{"t": 0.0, "faces": [strong, weak]}]}
    (shared / f"{sha}.json").write_text(json.dumps(doc))

    scan = call(tools.scan, inputs=[str(photo)], platforms=["x_image"])
    people = scan["inputs"][0]["people"]
    last = call(tools.make, job=scan["job"], overrides={"x_image": {"focus": f"person:{people}"}})
    beyond = call(tools.make, job=scan["job"], overrides={"x_image": {"focus": f"person:{people + 1}"}})

    assert people == 1
    assert last["targets"][0]["status"] in {"ready", "repaired"}, last
    row = beyond["targets"][0]
    assert row["status"] == "failed" and "not present" in row["reason"] and row["kept"] == "ready/x/image.jpg"
    again = call(tools.make, job=scan["job"], overrides={"x_image": {"focus": f"person:{people + 1}"}})
    assert again["targets"][0]["kept"] == "ready/x/image.jpg"


def test_image_peek_keeps_16_bit_tones(tmp_path):
    import numpy as np
    from postkitty.engine import probe

    path = tmp_path / "scan.png"
    ramp = np.linspace(0, 65535, 200 * 100, dtype=np.float64).reshape(100, 200)
    Image.fromarray(ramp.astype(np.uint16)).save(path)
    (tmp_path / "work").mkdir()

    peek = pipeline._image_peek(SimpleNamespace(work=tmp_path / "work"), probe.probe(path, "in1"))

    with Image.open(peek) as image:
        mean = float(np.asarray(image.convert("L")).mean())
    assert 110 < mean < 145


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

    monkeypatch.setattr(sys.modules["postkitty.engine.detect.faces"], "get_detector", refuse)
    out = call(tools.scan, inputs=[str(photo)], platforms=["instagram"])
    assert out["inputs"][0]["people"] == 1


def test_render_reuse_never_puts_jpeg_data_under_a_png_name(out_dir, tmp_path):
    # instagram_feed takes JPEG only, so a transparent photo is flattened to JPEG there; threads_image and
    # bluesky_image share its size and take PNG, and must not receive a copy of that JPEG render.
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (1200, 1500), (200, 40, 40, 128)).save(logo)
    job = call(tools.scan, inputs=[str(logo)], platforms=["instagram", "threads", "bluesky"])["job"]
    result = call(tools.make, job=job)
    assert "error" not in result
    files = [path for path in Path(result["job_dir"], "ready").rglob("*") if path.suffix in {".png", ".jpg"}]
    assert files
    for path in files:
        with Image.open(path) as image:
            assert image.format == {".png": "PNG", ".jpg": "JPEG"}[path.suffix], path


def test_error_messages_keep_their_closing_quote(out_dir, text_job, monkeypatch):
    out = call(tools.redo, job=text_job, target="x_image", cover_at="soon")
    assert out["error"].endswith("got 'soon'")

    def unknown(args):
        raise KeyError("unknown target 'x'")

    monkeypatch.setattr(pipeline, "scan", unknown)
    assert call(tools.scan, text="hi")["error"] == "unknown target 'x'"


def test_only_errors_a_new_scan_fixes_point_to_postkitty_scan(out_dir, tmp_path, text_job, stub_image_engine):
    assert "postkitty_scan" in call(tools.make, job="nope")["hint"]
    assert "postkitty_scan" in call(tools.make)["hint"]
    bad_value = call(tools.redo, job=text_job, target="x_image", layout="sideways")
    assert "postkitty_scan" not in bad_value["hint"] and "layout must be one of" in bad_value["error"]
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]
    photo.unlink()
    gone = call(tools.make, job=job)
    assert "is missing" in gone["error"] and "postkitty_scan" in gone["hint"]


def test_pipeline_messages_do_not_name_hermes_tools():
    assert "postkitty_" not in Path(pipeline.__file__).read_text(encoding="utf-8")


def test_check_takes_a_platform_name_and_picks_its_target_for_the_file(out_dir, tmp_path):
    photo = tmp_path / "wide.jpg"
    Image.new("RGB", (1600, 900), "teal").save(photo)
    assert call(tools.check, path=str(photo), target="x")["target"] == "x_image"
    several = call(tools.check, path=str(photo), target="instagram")["error"]
    assert "instagram_feed" in several and "instagram_story" in several
    assert "tiktok takes videos" in call(tools.check, path=str(photo), target="tiktok")["error"]
    assert "'target' is required" in call(tools.check, path=str(photo))["error"]


def test_one_failing_target_keeps_the_files_of_the_others(out_dir, tmp_path, stub_image_engine, monkeypatch):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x", "instagram"])["job"]
    render = sys.modules["postkitty.engine.photo.render"]
    real = render.render_image

    def flaky(info, layout, target, out_path):
        if target.id == "instagram_story":
            raise RuntimeError("encoder crashed")
        return real(info, layout, target, out_path)

    monkeypatch.setattr(render, "render_image", flaky)
    made = call(tools.make, job=job)
    rows = {row["target"]: row for row in made["targets"]}
    assert rows["instagram_story"]["status"] == "failed" and "encoder crashed" in rows["instagram_story"]["reason"]
    assert rows["x_image"]["status"] == "ready" and (out_dir / job / rows["x_image"]["file"]).is_file()
    manifest = json.loads((out_dir / job / "manifest.json").read_text())
    assert {entry["id"]: entry["status"] for entry in manifest["targets"]}["x_image"] == "ready"


def test_a_board_failure_still_returns_the_finished_files(out_dir, tmp_path, stub_image_engine, monkeypatch):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]

    def broken(root, manifest):
        raise RuntimeError("font missing")

    monkeypatch.setattr(importlib.import_module("postkitty.engine.board.board"), "write_board", broken)
    made = call(tools.make, job=job)
    assert made["targets"][0]["status"] == "ready" and "font missing" in made["board_note"]


def test_two_calls_on_one_job_keep_each_others_changes(out_dir, text_job, monkeypatch):
    import threading

    from postkitty.engine import job as jobs

    both_loaded = threading.Barrier(2, timeout=0.5)
    real = jobs.load_manifest

    def load_then_wait_for_the_other_call(job):
        manifest = real(job)
        try:
            both_loaded.wait()
        except threading.BrokenBarrierError:
            pass
        return manifest

    monkeypatch.setattr(jobs, "load_manifest", load_then_wait_for_the_other_call)
    threads = [threading.Thread(target=call, args=(tools.write,), kwargs={"job": text_job, "drafts": {name: "hello"}})
               for name in ("x", "linkedin")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    manifest = json.loads((out_dir / text_job / "manifest.json").read_text())
    assert set(manifest["copy"]) == {"x", "linkedin"}


def test_a_misspelled_argument_is_an_error_that_lists_the_real_ones(out_dir, text_job):
    out = call(tools.scan, text="hi", platform=["x"])
    assert "unknown argument 'platform'" in out["error"] and "inputs, text, platforms, job" in out["error"]
    assert "unknown argument 'draft'" in call(tools.write, job=text_job, draft={"x": "hi"})["error"]
    assert "unknown argument 'file'" in call(tools.check, file="a.jpg", target="x")["error"]


def test_numbers_sent_as_strings_are_read_as_numbers(out_dir, text_job):
    from postkitty.engine.pipeline import _override

    assert _override({"trim": ["1", "5.5"], "cover_at": "3"}) == {"trim": [1.0, 5.5], "cover_at": 3.0}
    assert "trim must be" in call(tools.redo, job=text_job, target="x_image", trim=["0", "inf"])["error"]
    assert "cover_at must be" in call(tools.redo, job=text_job, target="x_image", cover_at="soon")["error"]


def test_write_with_nothing_to_write_is_an_error(out_dir, text_job):
    assert "give at least one of drafts" in call(tools.write, job=text_job)["error"]


def test_scan_says_which_inputs_it_does_not_use(out_dir, tmp_path, stub_image_engine):
    first, second = tmp_path / "a.jpg", tmp_path / "b.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(first)
    Image.new("RGB", (1600, 1200), "blue").save(second)
    out = call(tools.scan, inputs=[str(first), str(first), str(second)], platforms=["x"])
    assert [entry["id"] for entry in out["inputs"]] == ["in1", "in2"]
    assert any("same file as in1" in note for note in out["notes"])
    assert any(note.startswith("in2 (b.jpg) is not used") for note in out["notes"])


def test_redo_on_a_text_only_job_says_there_is_nothing_to_render(out_dir, text_job):
    assert "text only" in call(tools.redo, job=text_job, target="x_image", layout="pad")["error"]


def test_relative_paths_start_at_the_session_folder(tmp_path, monkeypatch, stub_image_engine):
    session, gateway = tmp_path / "session", tmp_path / "gateway"
    session.mkdir()
    gateway.mkdir()
    Image.new("RGB", (1600, 1200), "orange").save(session / "me.jpg")
    monkeypatch.delenv("POSTKITTY_OUTPUT_DIR", raising=False)
    monkeypatch.chdir(gateway)
    monkeypatch.setattr(tools, "_session_dir", lambda: str(session))
    out = call(tools.scan, inputs=["me.jpg"], platforms=["x"])
    assert out["inputs"][0]["path"] == str(session / "me.jpg")
    assert Path(out["job_dir"]).parent == session / "postkitty"
    assert call(tools.check, path="me.jpg", target="x_image")["file"] == str(session / "me.jpg")


def test_session_folder_comes_from_hermes_and_falls_back_to_the_process_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(sys.modules, "agent", None)
    assert tools._session_dir() == str(tmp_path)
    runtime = types.ModuleType("agent.runtime_cwd")
    runtime.resolve_agent_cwd = lambda: Path("/srv/session")
    monkeypatch.setitem(sys.modules, "agent", types.ModuleType("agent"))
    monkeypatch.setitem(sys.modules, "agent.runtime_cwd", runtime)
    assert tools._session_dir() == "/srv/session"


def test_a_zero_setting_is_kept_and_a_bad_loudness_fails_video_with_the_reason(monkeypatch):
    class Ctx:
        def get_config(self, key, default=None):
            return {"loudness_lufs": 0, "default_platforms": "x, linkedin"}.get(key, default)

    monkeypatch.setattr(tools, "_CTX", Ctx())
    with tools.session():
        assert pipeline._setting("default_platforms", []) == ["x", "linkedin"]
        with pytest.raises(ValueError, match="-70 to -5"):
            pipeline._loudness()
    monkeypatch.setattr(tools, "_CTX", None)
    with tools.session():
        assert pipeline._loudness() == -14.0


def test_handlers_take_context_keywords_and_answer_garbage_with_an_argument_error(out_dir, text_job):
    garbage = [None, [], "text", 7, {"job": []}, {"job": {"a": 1}, "target": 5, "layout": []}, {"inputs": [None, 5]},
               {"text": 5}, {"path": 5, "target": []}, {"job": "x", "drafts": []}, {"job": "x", "overrides": "pad"},
               {"job": text_job, "advice": {"ranking": "x", "tips": 5}}, {"job": text_job, "drafts": {"x": 5}},
               {"job": text_job, "alt_text": {"x_image": None}}, {"job": text_job, "target": "x", "focus": 5},
               {"job": text_job, "targets": [None]}, {"job": text_job, "overrides": {"x_image": None}}]
    for handler in tools.HANDLERS.values():
        for args in garbage:
            raw = handler(args, task_id="t", session_id="s", conversation_id="c", user_task="u", parent_agent=None)
            out = json.loads(raw)
            assert isinstance(raw, str) and isinstance(out, dict)
            assert "Unexpected" not in out.get("hint", ""), (handler.__name__, args, out)


def test_make_and_redo_return_the_lines_hermes_shows(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]
    for out in (call(tools.make, job=job), call(tools.redo, job=job, target="x_image", layout="pad")):
        assert out["media_line"] == f"MEDIA:{out['contact']}" and Path(out["contact"]).is_file()
        assert out["preview_directive"] == f'::preview{{file="{out["board_inline"]}"}}'
        assert "board_inline_size" not in out


def test_make_and_redo_leave_no_renders_behind(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]
    call(tools.make, job=job)
    call(tools.redo, job=job, target="x_image", layout="pad")
    assert list((out_dir / job / "work" / "render").iterdir()) == []
    assert (out_dir / job / "ready/x/image.jpg").is_file()


def test_a_setup_problem_points_to_the_doctor_and_says_text_still_works(out_dir, monkeypatch):
    def no_model(args):
        raise pipeline.models.ModelUnavailable("The face model could not be downloaded.")

    monkeypatch.setattr(pipeline, "make", no_model)
    out = call(tools.make, job="any")
    assert out["error"] == "The face model could not be downloaded." and "/postkitty doctor" in out["hint"]


def test_alt_text_by_a_file_name_two_inputs_share_asks_for_an_id(out_dir, tmp_path, stub_image_engine):
    for folder, color in (("a", "orange"), ("b", "blue")):
        (tmp_path / folder).mkdir()
        Image.new("RGB", (1600, 1200), color).save(tmp_path / folder / "IMG.jpg")
    job = call(tools.scan, inputs=[str(tmp_path / "a/IMG.jpg"), str(tmp_path / "b/IMG.jpg")], platforms=["x"])["job"]
    assert "several inputs (in1, in2)" in call(tools.write, job=job, alt_text={"IMG.jpg": "A team."})["error"]
    assert call(tools.write, job=job, alt_text={"in1": "A team."})["alt_text_unmatched"] is None
    assert "x_image:\nA team." in (out_dir / job / "ready/x/alt.txt").read_text()



def test_a_job_id_cannot_leave_the_output_folder(out_dir):
    out = call(tools.scan, text="hi", job="../../outside")
    assert Path(out["job_dir"]).parent == out_dir
    assert "does not exist" in call(tools.make, job="../../etc")["error"]


def test_a_refused_write_leaves_no_advice_file(out_dir, text_job):
    out = call(tools.write, job=text_job, advice={"topic": "Sentences"}, drafts={"x": ""})
    assert "error" in out and not (out_dir / text_job / "advice.md").exists()


def test_two_sessions_at_once_keep_their_own_working_directory(out_dir, tmp_path, monkeypatch):
    import threading

    for name, size in (("a", (1600, 900)), ("b", (1200, 1200))):
        (tmp_path / name).mkdir()
        Image.new("RGB", size, "teal").save(tmp_path / name / "me.jpg")
    session = threading.local()
    monkeypatch.setattr(tools, "_session_dir", lambda: str(tmp_path / session.name))
    both_configured = threading.Barrier(2, timeout=5)
    real_only = pipeline._only

    def only_after_both_calls_are_configured(args, step, *known):
        both_configured.wait()
        real_only(args, step, *known)

    monkeypatch.setattr(pipeline, "_only", only_after_both_calls_are_configured)
    seen = {}

    def check_in(name):
        session.name = name
        seen[name] = call(tools.check, path="me.jpg", target="x_image").get("file")

    threads = [threading.Thread(target=check_in, args=(name,)) for name in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert seen == {"a": str(tmp_path / "a" / "me.jpg"), "b": str(tmp_path / "b" / "me.jpg")}


def test_captions_take_an_existing_srt_or_vtt_file_and_only_on_video(out_dir, tmp_path, stub_image_engine):
    photo = tmp_path / "me.jpg"
    Image.new("RGB", (1600, 1200), "orange").save(photo)
    job = call(tools.scan, inputs=[str(photo)], platforms=["x"])["job"]
    notes, subtitles = tmp_path / "talk.txt", tmp_path / "talk.srt"
    notes.write_text("hi")
    subtitles.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n")
    assert ".srt or .vtt" in call(tools.redo, job=job, target="x_image", captions=str(notes))["error"]
    assert "not found" in call(tools.redo, job=job, target="x_image", captions=str(tmp_path / "gone.srt"))["error"]
    assert "apply to video only" in call(tools.redo, job=job, target="x_image", captions=str(subtitles))["error"]
    assert pipeline._merged({"captions": str(subtitles), "layout": "pad"}, {"captions": "none"}) == {"layout": "pad"}


def test_captions_are_burned_into_a_video_target_and_reported(out_dir, tmp_path, speaker_media) -> None:
    shared = Path(os.environ["POSTKITTY_FACES_CACHE"])
    shared.mkdir(parents=True, exist_ok=True)
    source = speaker_media.work / "faces" / f"{speaker_media.info.sha256}.json"
    shutil.copyfile(source, shared / source.name)
    subtitles = tmp_path / "talk.srt"
    subtitles.write_text("1\n00:00:00,500 --> 00:00:02,500\nHello from postkitty\n", encoding="utf-8")
    job = call(tools.scan, inputs=[str(speaker_media.info.path)], platforms=["linkedin_video"])["job"]

    made = call(tools.make, job=job, overrides={"linkedin_video": {"captions": str(subtitles)}})

    row = made["targets"][0]
    assert row["status"] in {"ready", "repaired"}, row
    assert row["captions"] == {"file": str(subtitles), "shown": 1}
