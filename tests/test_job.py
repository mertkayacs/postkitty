import json

import pytest

from engine import job as jobs


def test_slugify():
    assert jobs.slugify("My Holiday Photo!!.jpg") == "my-holiday-photo-jpg"
    assert jobs.slugify("") == "post"
    assert len(jobs.slugify("x" * 100)) <= 32


def test_create_job_layout_and_manifest(tmp_path):
    job = jobs.create_job(tmp_path, ["/some/where/Beach Day.mp4"])
    assert job.id.endswith("-beach-day") and job.root.parent == tmp_path
    for sub in ("ready", "work", "work/faces", "work/scenes", "work/render", "work/failed"):
        assert (job.root / sub).is_dir()
    manifest = json.loads(job.manifest_path.read_text())
    assert manifest["schema"] == "postkitty.manifest/1" and manifest["job"] == job.id
    assert manifest["inputs"] == [] and manifest["targets"] == []


def test_job_ids_are_unique(tmp_path):
    first = jobs.create_job(tmp_path, [], "same text")
    second = jobs.create_job(tmp_path, [], "same text")
    assert first.id != second.id and second.root.is_dir()


def test_reuse_job_id_keeps_manifest(tmp_path):
    job = jobs.create_job(tmp_path, [], "hello")
    manifest = jobs.load_manifest(job)
    manifest["text"] = {"chars": 5}
    jobs.save_manifest(job, manifest)
    again = jobs.create_job(tmp_path, [], "", job_id=job.id)
    assert again.root == job.root and jobs.load_manifest(again)["text"] == {"chars": 5}


def test_open_job_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        jobs.open_job(tmp_path, "nope")


def test_write_json_is_atomic_and_leaves_no_temp_files(tmp_path):
    path = jobs.write_json(tmp_path / "a" / "b.json", {"k": "é"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"k": "é"}
    assert [p.name for p in path.parent.iterdir()] == ["b.json"]


def test_write_advice(tmp_path):
    job = jobs.create_job(tmp_path, [], "x")
    jobs.write_advice(job, {"topic": "Cats", "audience": "owners", "tone": "warm", "key_message": "Adopt",
                            "ranking": [{"platform": "instagram", "reason": "photo-led"}], "tips": ["Post at noon"]})
    text = job.advice_path.read_text()
    assert "## Topic" in text and "Cats" in text and "1. instagram - photo-led" in text and "- Post at noon" in text


def test_default_out_dir_uses_config(tmp_path):
    assert jobs.default_out_dir(str(tmp_path / "abs")) == tmp_path / "abs"
    assert jobs.default_out_dir("rel").name == "rel"
    assert jobs.default_out_dir("").name == "postkitty"
