from pathlib import Path

from engine import advise
from engine.probe import InputInfo


def info(kind, w, h, duration=None, iid="in1"):
    return InputInfo(id=iid, path=Path("x"), kind=kind, sha256="0" * 64, width=w, height=h, duration=duration,
                     fps=30.0 if duration else None, has_audio=bool(duration), rotation=0, has_alpha=False)


def test_text_only_gives_text_facts_for_every_platform():
    facts = advise.fit_facts([], "hello " * 100)
    assert set(facts) >= {"x", "bluesky", "instagram", "tiktok"}
    assert facts["x"]["text"]["split"] is True and facts["x"]["targets"] == []
    assert facts["instagram"]["text"]["ok"] is True


def test_video_facts_flag_trim_and_vertical_hint():
    facts = advise.fit_facts([info("video", 1920, 1080, 200.0)], None)
    x_video = facts["x"]["targets"][0]
    assert x_video["id"] == "x_video" and x_video["trim"] == [0.0, 140.0] and x_video["layout_hint"] == "crop"
    tiktok = facts["tiktok"]["targets"][0]
    assert tiktok["layout_hint"] == "pad" and tiktok["source_aspect"] == round(1920 / 1080, 4)


def test_image_only_input_skips_video_targets():
    facts = advise.fit_facts([info("image", 3000, 2000)], None)
    ids = {t["id"] for p in facts.values() for t in p["targets"]}
    assert "x_image" in ids and "tiktok" not in ids and "instagram_story" in ids


def test_source_for_prefers_matching_kind():
    from engine.platforms import get_target

    video, image = info("video", 1920, 1080, 5.0, "in1"), info("image", 100, 100, iid="in2")
    assert advise.source_for([video, image], get_target("x_image")) is image
    assert advise.source_for([video, image], get_target("instagram_story")) is video
    assert advise.source_for([image], get_target("tiktok")) is None
