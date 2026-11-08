import pytest

from engine import platforms

TARGET_IDS = {
    "instagram_reel", "instagram_feed", "instagram_story", "tiktok", "youtube_shorts", "x_video", "x_image",
    "linkedin_video", "linkedin_image", "threads_video", "threads_image", "bluesky_video", "bluesky_image",
    "facebook_reel", "facebook_feed",
}


def test_all_spec_targets_exist():
    assert set(platforms.target_ids()) == TARGET_IDS


def test_every_hard_limit_cites_a_source():
    for plat in platforms.load_platforms().values():
        for spec in plat.text.values():
            if spec.enforcement == "hard":
                assert spec.source_url and spec.source_scope and spec.checked_on, plat.name
        for target in plat.targets.values():
            for key, spec in target.limits.items():
                assert spec.enforcement in {"hard", "recommendation"}, (target.id, key)


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
