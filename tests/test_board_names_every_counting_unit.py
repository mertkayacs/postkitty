"""The review board says what a text limit counts in words a person reads, for every unit a platform uses."""

import pytest

from engine import platforms
from engine.board.board import count_line


@pytest.mark.xfail(strict=True, reason="the board has no name for the unit 'threads'; see NOTES-qa.md, defect 2")
def test_copy_card_never_prints_a_raw_unit_name():
    units = {plat.text["limit"].unit for plat in platforms.load_platforms().values() if plat.text.get("limit")}

    raw = sorted(unit for unit in units if count_line(23, 500, unit) == f"23 of 500 {unit}")

    assert raw == []
