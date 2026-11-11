from dataclasses import replace
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


def test_split_copy_is_reported_as_a_thread_not_as_fitting():
    text = " ".join(f"Sentence number {i} is here." for i in range(16))
    facts = advise.fit_facts([], text)
    x = facts["x"]
    assert x["text"]["ok"] and x["text"]["split"] and x["text"]["parts"] == 2
    assert not any(fact.startswith("Copy fits") for fact in x["facts"])
    assert any("thread of 2 posts" in fact for fact in x["facts"]), x["facts"]


def test_video_facts_flag_trim_and_vertical_hint():
    facts = advise.fit_facts([info("video", 1920, 1080, 200.0)], None)
    x_video = facts["x"]["targets"][0]
    assert x_video["id"] == "x_video" and x_video["trim"] == [0.0, 140.0] and x_video["layout_hint"] == "crop"
    tiktok = facts["tiktok"]["targets"][0]
    assert tiktok["layout_hint"] == "pad" and tiktok["source_aspect"] == round(1920 / 1080, 4)


def test_only_a_hard_length_limit_proposes_a_trim():
    facts = advise.fit_facts([info("video", 1080, 1920, 90.0)], None, ["instagram_story", "instagram_reel"])
    targets = {target["id"]: target for target in facts["instagram"]["targets"]}
    story, reel = targets["instagram_story"], targets["instagram_reel"]
    assert story["duration_max"] == 60 and story["trim"] == [0.0, 90.0]  # 60 s is a recommendation: nothing is cut
    assert "Trim" not in story["note"]
    long = advise.fit_facts([info("video", 1080, 1920, 1000.0)], None, ["instagram_reel"])["instagram"]["targets"][0]
    assert long["trim"] == [0.0, 900.0] and "Trim the first 900.0 s" in long["note"]  # the reel limit is hard
    assert reel["trim"] == [0.0, 90.0]


def test_video_facts_flag_short_clips_and_low_frame_rates():
    short = advise.fit_facts([info("video", 1920, 1080, 0.5)], None, ["instagram_reel", "linkedin_video"])
    reel = short["instagram"]["targets"][0]
    assert reel["id"] == "instagram_reel" and reel["duration_min"] == 3
    assert any("0.5 s" in fact and "at least 3 s" in fact for fact in short["instagram"]["facts"]), short["instagram"]
    assert any("at least 3 s" in fact for fact in short["linkedin"]["facts"])

    slow = replace(info("video", 1920, 1080, 4.0), fps=15.0)
    facts = advise.fit_facts([slow], None, ["tiktok"])
    assert facts["tiktok"]["targets"][0]["fps_min"] == 23
    assert any("15 fps" in fact and "at least 23 fps" in fact for fact in facts["tiktok"]["facts"]), facts["tiktok"]


def test_fit_facts_use_the_actual_scan_plan_layout():
    plans = [{"id": "tiktok", "layout": "split"}]

    facts = advise.fit_facts([info("video", 1920, 1080, 15.0)], None, plans=plans)

    assert facts["tiktok"]["targets"][0]["layout_hint"] == "split"


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
