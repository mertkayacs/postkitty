import json

import pytest

from engine import platforms

TARGET_IDS = {
    "instagram_reel", "instagram_feed", "instagram_story", "tiktok", "youtube_shorts", "x_video", "x_image",
    "linkedin_video", "linkedin_image", "threads_video", "threads_image", "bluesky_video", "bluesky_image",
    "facebook_reel", "facebook_feed",
}

SOURCE = {
    "enforcement": "hard",
    "source_url": "https://example.test/spec",
    "source_scope": "api",
    "checked_on": "2026-11-11",
}


def document() -> dict:
    """The smallest document the loader accepts; each rejection test breaks one thing in it."""
    return {
        "schema": "postkitty.platforms/1",
        "checked_on": "2026-11-11",
        "platforms": {
            "demo": {
                "label": "Demo",
                "text": {"limit": {"value": 100, "unit": "codepoints", **SOURCE}},
                "targets": {
                    "demo_video": {
                        "kind": "video",
                        "width": 1080,
                        "height": 1920,
                        "duration_max": {"value": 60, **SOURCE},
                    },
                },
            },
        },
    }


def load(tmp_path, doc: dict) -> dict[str, platforms.PlatformSpec]:
    path = tmp_path / "platforms.yaml"
    path.write_text(json.dumps(doc), encoding="utf-8")  # JSON is valid YAML
    return platforms.load_platforms(path)


def demo(doc: dict) -> dict:
    return doc["platforms"]["demo"]


def video(doc: dict) -> dict:
    return demo(doc)["targets"]["demo_video"]


def rename(mapping: dict, old: str, new: str) -> None:
    mapping[new] = mapping.pop(old)


def add_twin_platform(doc: dict) -> None:
    doc["platforms"]["twin"] = {"label": "Twin", "targets": {"demo_video": dict(video(doc))}}


BROKEN = {
    "misspelled limit": (lambda d: rename(video(d), "duration_max", "duraton_max"), "demo_video.*'duraton_max'"),
    "misspelled spec field": (
        lambda d: rename(video(d)["duration_max"], "enforcement", "enforcment"),
        "duration_max.*'enforcment'",
    ),
    "misspelled section": (lambda d: rename(demo(d), "targets", "target"), "demo.*'target'"),
    "missing kind": (lambda d: video(d).pop("kind"), "demo_video.*kind"),
    "unknown kind": (lambda d: video(d).update(kind="reel"), "demo_video.*kind"),
    "missing width": (lambda d: video(d).pop("width"), "demo_video.*width"),
    "odd video height": (lambda d: video(d).update(height=1919), "demo_video.*height.*even"),
    "target is not a mapping": (lambda d: demo(d)["targets"].update(demo_video="1080x1920"), "demo_video"),
    "unknown enforcement": (lambda d: video(d)["duration_max"].update(enforcement="soft"), "duration_max.*enforcement"),
    "missing source": (lambda d: video(d)["duration_max"].pop("source_url"), "duration_max.*source_url"),
    "check date is not a date": (
        lambda d: video(d)["duration_max"].update(checked_on="yesterday"),
        "duration_max.*checked_on",
    ),
    "hard limit from a secondary source": (
        lambda d: video(d)["duration_max"].update(source_scope="secondary"),
        "duration_max.*secondary",
    ),
    "limit value of the wrong type": (lambda d: video(d)["duration_max"].update(value="sixty"), "duration_max.*value"),
    "text limit without a unit": (lambda d: demo(d)["text"]["limit"].pop("unit"), "limit.*unit"),
    "unknown text unit": (lambda d: demo(d)["text"]["limit"].update(unit="codepoint"), "limit.*unit"),
    "target id used twice": (add_twin_platform, "demo_video"),
    "wrong schema": (lambda d: d.update(schema="postkitty.platforms/0"), "schema"),
}


def test_minimal_document_loads(tmp_path):
    loaded = load(tmp_path, document())
    target = loaded["demo"].targets["demo_video"]
    assert (target.kind, target.width, target.height) == ("video", 1080, 1920)
    assert loaded["demo"].text["limit"].unit == "codepoints"


@pytest.mark.parametrize("name", BROKEN)
def test_broken_file_fails_at_load_and_names_the_place(tmp_path, name):
    breakage, place = BROKEN[name]
    doc = document()
    breakage(doc)
    with pytest.raises(ValueError, match=place):
        load(tmp_path, doc)


def test_misspelled_key_error_suggests_the_real_key(tmp_path):
    doc = document()
    rename(video(doc), "duration_max", "duraton_max")
    with pytest.raises(ValueError, match="did you mean 'duration_max'"):
        load(tmp_path, doc)


def test_all_spec_targets_exist():
    assert set(platforms.target_ids()) == TARGET_IDS


def test_every_target_cites_a_source():
    for plat in platforms.load_platforms().values():
        for target in plat.targets.values():
            assert any(spec.source_url for spec in target.limits.values()), target.id


def test_target_spec_fields():
    reel = platforms.get_target("instagram_reel")
    assert (reel.platform, reel.kind, reel.width, reel.height) == ("instagram", "video", 1080, 1920)
    assert reel.aspect == pytest.approx(9 / 16)
    assert reel.limits["duration_max"].enforcement == "hard"
    assert reel.limits["duration_max"].source_url


def test_get_target_is_case_insensitive_and_raises():
    assert platforms.get_target("TikTok").id == "tiktok"
    with pytest.raises(KeyError):
        platforms.get_target("myspace")


def test_targets_for_by_kind():
    ids = {t.id for t in platforms.targets_for({"video"}, None)}
    assert "tiktok" in ids and "instagram_reel" in ids and "instagram_story" in ids
    assert "x_image" not in ids and "instagram_feed" not in ids


def test_targets_for_image_only():
    ids = {t.id for t in platforms.targets_for({"image"}, None)}
    assert "instagram_feed" in ids and "x_image" in ids and "instagram_story" in ids
    assert "tiktok" not in ids


def test_targets_for_named_platform_and_target_id():
    assert {t.id for t in platforms.targets_for({"video", "image"}, ["x"])} == {"x_video", "x_image"}
    assert {t.id for t in platforms.targets_for({"video"}, ["x_image"])} == {"x_image"}
    assert {t.id for t in platforms.targets_for({"video"}, ["x"])} == {"x_video"}


def test_text_only_has_no_media_targets():
    assert platforms.targets_for(set(), None) == []
