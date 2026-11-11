from pathlib import Path

import pytest

from engine import platforms
from engine.verify import checks, repair


@pytest.fixture(autouse=True)
def clean_registries(monkeypatch):
    monkeypatch.setattr(checks, "_CHECKERS", {"image": [], "video": []})
    monkeypatch.setattr(repair, "_STRATEGIES", {})


def result(tmp_path, name="a.jpg", size=100, width=1080, height=1350, duration=None, target="instagram_feed"):
    path = tmp_path / name
    path.write_bytes(b"x" * size)
    return checks.RenderResult(target=target, file=path, width=width, height=height, duration=duration, bytes=size,
                               layout={"mode": "crop"}, subjects_inside=1.0, extra={})


def test_baseline_dimensions_and_missing_file(tmp_path):
    target = platforms.get_target("instagram_feed")
    good = checks.run_checks(result(tmp_path), target)
    assert checks.hard_pass(good)
    bad = checks.run_checks(result(tmp_path, width=1000), target)
    assert [c.id for c in checks.failures(bad)] == ["image.dimensions"]
    gone = checks.RenderResult("instagram_feed", Path(tmp_path / "gone.jpg"), 1, 1, None, 0, {}, None, {})
    assert checks.run_checks(gone, target)[0].id == "file.exists"


def test_baseline_bytes_and_duration_cite_sources(tmp_path):
    target = platforms.get_target("x_video")
    big = result(tmp_path, "v.mp4", width=1920, height=1080, duration=200.0, target="x_video")
    big.bytes = target.limits["bytes_max"].value + 1
    found = {c.id: c for c in checks.run_checks(big, target)}
    assert found["video.duration_max"].status == "fail" and found["video.duration_max"].source_url
    assert found["video.bytes_max"].hard and found["video.bytes_max"].checked_on
    assert found["media.checks"].status == "skipped"


def test_recommendation_limit_is_advisory(tmp_path):
    target = platforms.get_target("instagram_story")
    long = result(tmp_path, "s.mp4", width=1080, height=1920, duration=90.0, target="instagram_story")
    found = {c.id: c for c in checks.run_checks(long, target)}
    assert found["video.duration_max"].status == "advisory" and checks.hard_pass(list(found.values()))


def test_registered_checker_replaces_baseline(tmp_path):
    seen = []

    def checker(res, target):
        seen.append(res.target)
        return [checks.Check("image.custom", target.id, "pass", True, 1, 1, "ok")]

    checks.register_checker("image", checker)
    found = checks.run_checks(result(tmp_path), platforms.get_target("instagram_feed"))
    assert [c.id for c in found] == ["image.custom"] and seen == ["instagram_feed"]
    with pytest.raises(ValueError):
        checks.register_checker("audio", checker)


def test_repair_loop_fixes_then_stops(tmp_path):
    target = platforms.get_target("instagram_feed")

    def checker(res, tgt):
        failed = res.bytes > 50
        return [checks.Check("image.bytes_max", tgt.id, "fail" if failed else "pass", True, res.bytes, 50, "size")]

    calls = []

    def shrink(res, tgt, check, rerender):
        calls.append(rerender)
        res.bytes -= 30
        return res

    checks.register_checker("image", checker)
    repair.register("image.bytes_max", shrink)
    final, found, repairs = repair.check_and_repair(result(tmp_path, size=100), target, {"overrides": {}})
    assert checks.hard_pass(found) and final.bytes == 40
    assert repairs == [{"check": "image.bytes_max", "action": "shrink", "ok": True}] * 2 and len(calls) == 2


def test_repair_gives_up_after_three_rounds(tmp_path):
    target = platforms.get_target("instagram_feed")
    checks.register_checker("image", lambda r, t: [checks.Check("image.bytes_max", t.id, "fail", True, 1, 0, "m")])
    attempts = []
    repair.register("image.bytes_max", lambda r, t, c, rr: attempts.append(1) or r)
    _, found, repairs = repair.check_and_repair(result(tmp_path), target, {})
    assert not checks.hard_pass(found) and len(attempts) == repair.MAX_ROUNDS == len(repairs)


def test_repair_without_strategy_or_progress_stops_at_once(tmp_path):
    target = platforms.get_target("instagram_feed")
    checks.register_checker("image", lambda r, t: [checks.Check("image.x", t.id, "fail", True, 1, 0, "m")])
    assert repair.check_and_repair(result(tmp_path), target, {})[2] == []
    repair.register("image.x", lambda r, t, c, rr: None)
    _, found, repairs = repair.check_and_repair(result(tmp_path), target, {})
    assert len(repairs) == 1 and repairs[0]["ok"] is False and not checks.hard_pass(found)


def test_strategy_exception_is_recorded_not_raised(tmp_path):
    target = platforms.get_target("instagram_feed")
    checks.register_checker("image", lambda r, t: [checks.Check("image.x", t.id, "fail", True, 1, 0, "m")])

    def boom(*args):
        raise RuntimeError("no luck")

    repair.register("image.x", boom)
    _, _, repairs = repair.check_and_repair(result(tmp_path), target, {})
    assert repairs[0]["ok"] is False and "no luck" in repairs[0]["error"]


def test_copy_checks_report_overflow_and_caps():
    rules = __import__("engine.text.fit", fromlist=["x"]).rules_for("instagram")
    found = checks.copy_checks("instagram", ["a" * 2201, "#t " * 31], rules)
    failing = {c.id for c in found if c.status == "fail"}
    assert failing == {"copy.limit", "copy.hashtags_max"}
    assert all(c.target == "copy:instagram" for c in found)
