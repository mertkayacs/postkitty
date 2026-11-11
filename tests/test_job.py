import json

import pytest

from engine import job as jobs


def test_slugify():
    assert jobs.slugify("My Holiday Photo!!.jpg") == "my-holiday-photo-jpg"
    assert jobs.slugify("") == "post"
    assert len(jobs.slugify("x" * 100)) <= 32


def test_slugify_folds_turkish_and_german_letters_to_ascii():
    assert jobs.slugify("bugün İstanbul'da çay") == "bugun-istanbul-da-cay"
    assert jobs.slugify("Straße Köln Übung") == "strasse-koln-ubung"
    assert jobs.slugify("Işık Şöğüç") == "isik-soguc"


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


def test_default_out_dir_uses_config(tmp_path, monkeypatch):
    assert jobs.default_out_dir(str(tmp_path / "abs")) == tmp_path / "abs"
    assert jobs.default_out_dir("rel", base=tmp_path / "session") == tmp_path / "session" / "rel"
    assert jobs.default_out_dir("", base=tmp_path / "session") == tmp_path / "session" / "postkitty"
    monkeypatch.chdir(tmp_path)
    assert jobs.default_out_dir("rel") == tmp_path / "rel" and jobs.default_out_dir("") == tmp_path / "postkitty"


@pytest.mark.parametrize("job_id", ["../outside", "/etc/passwd", "..", "a/../../b", "C:\\Windows\\x", "~/x"])
def test_a_job_id_never_leaves_the_output_folder(tmp_path, job_id):
    out = tmp_path / "out"
    job = jobs.create_job(out, [], "", job_id=job_id)
    assert job.root.parent == out and job.root.is_dir()
    assert jobs.open_job(out, job_id).root == job.root
    assert [path.name for path in tmp_path.iterdir()] == ["out"]


def test_a_job_folder_that_links_outside_the_output_folder_is_refused(tmp_path):
    out, elsewhere = tmp_path / "out", tmp_path / "elsewhere"
    out.mkdir()
    elsewhere.mkdir()
    (out / "linked").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(ValueError, match="outside the output folder"):
        jobs.open_job(out, "linked")
    with pytest.raises(ValueError, match="outside the output folder"):
        jobs.create_job(out, [], "", job_id="linked")
    assert list(elsewhere.iterdir()) == []


def test_a_linked_output_folder_still_works(tmp_path):
    real = tmp_path / "disk"
    real.mkdir()
    (tmp_path / "out").symlink_to(real, target_is_directory=True)
    job = jobs.create_job(tmp_path / "out", [], "hello")
    assert jobs.open_job(tmp_path / "out", job.id).root == job.root and (real / job.id).is_dir()


@pytest.mark.parametrize("name", ["../../escape", "/abs", "..", "a/b", ""])
def test_a_platform_folder_name_stays_inside_ready(tmp_path, name):
    job = jobs.create_job(tmp_path, [], "x")
    with pytest.raises(ValueError, match="platform folder"):
        jobs.ready_dir(job, name)
    assert [path.name for path in tmp_path.iterdir()] == [job.id]


def test_two_scans_in_the_same_moment_get_separate_folders(tmp_path, monkeypatch):
    first = jobs.create_job(tmp_path, [], "same text")
    real_exists, looked = jobs.Path.exists, []

    def not_there_yet(self, *args, **kwargs):
        # The second scan looks for the folder just before the first scan creates it.
        if self == first.root and not looked:
            looked.append(self)
            return False
        return real_exists(self, *args, **kwargs)

    monkeypatch.setattr(jobs.Path, "exists", not_there_yet)
    second = jobs.create_job(tmp_path, [], "same text")
    assert second.id != first.id and second.root != first.root


def test_a_folder_with_spaces_and_non_ascii_letters_holds_a_job(tmp_path):
    out = tmp_path / "çıktı klasörü 写真"
    job = jobs.create_job(out, [out / "Doğum günü 🎂.jpg"])
    manifest = jobs.load_manifest(job)
    manifest["text"] = {"note": "İyi ki doğdun, 日本"}
    jobs.save_manifest(job, manifest)
    assert job.id.endswith("-dogum-gunu") and job.root.parent == out
    assert jobs.load_manifest(jobs.open_job(out, job.id))["text"] == {"note": "İyi ki doğdun, 日本"}


@pytest.mark.parametrize("content", [b"", b'{"schema": "postkitty.manifest/1", "tar', b"\xff\xfe\x00{"],
                         ids=["empty", "cut-short", "not-utf8"])
def test_a_damaged_manifest_gives_a_clear_error(tmp_path, content):
    job = jobs.create_job(tmp_path, [], "hello")
    job.manifest_path.write_bytes(content)
    with pytest.raises(ValueError, match=r"manifest\.json is damaged.*postkitty_scan"):
        jobs.load_manifest(job)


def test_a_failed_write_keeps_the_old_manifest(tmp_path):
    job = jobs.create_job(tmp_path, [], "hello")
    before = job.manifest_path.read_text(encoding="utf-8")
    with pytest.raises(TypeError):
        jobs.save_manifest(job, {"targets": [object()]})
    assert job.manifest_path.read_text(encoding="utf-8") == before
    assert sorted(path.name for path in job.root.iterdir()) == ["manifest.json", "ready", "work"]


def test_prune_work_drops_renders_and_keeps_what_redo_needs(tmp_path):
    job = jobs.create_job(tmp_path, [], "x")
    kept = ["scan.json", "peek.jpg", "faces/abc.json", "scenes/abc.json", "speakers/key.npz", "failed/x_video.mp4"]
    dropped = ["render/tiktok_video-0.mp4", "render/tiktok_video-1.mp4", "render/reuse-1f.mp4",
               "render/reuse-1f.commands", "render/tmpab12/carved.png", "failed/tiktok_video.mp4"]
    for relative in kept + dropped:
        path = job.work / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    manifest = {"targets": [{"id": "x_video", "status": "failed", "failed_file": "work/failed/x_video.mp4"},
                            {"id": "tiktok_video", "status": "ready", "file": "ready/tiktok/video.mp4"}]}

    jobs.prune_work(job, manifest)

    left = sorted(path.relative_to(job.work).as_posix() for path in job.work.rglob("*") if path.is_file())
    assert left == sorted(kept)
    assert (job.work / "render").is_dir()
