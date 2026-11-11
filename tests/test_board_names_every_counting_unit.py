"""The review board says what a text limit counts in words a person reads, for every unit a platform uses."""

from engine import platforms
from engine.board.board import count_line


def test_copy_card_never_prints_a_raw_unit_name():
    units = {plat.text["limit"].unit for plat in platforms.load_platforms().values() if plat.text.get("limit")}

    raw = sorted(unit for unit in units if count_line(23, 500, unit) == f"23 of 500 {unit}")

    assert raw == []


def test_a_unit_the_text_engine_does_not_know_is_shown_as_it_is():
    assert count_line(23, 500, "syllables") == "23 of 500 syllables"
