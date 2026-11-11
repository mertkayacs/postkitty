"""Burned-in captions: read an SRT or WebVTT file and build the ASS overlay for one target."""

from __future__ import annotations

import html
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

_TIME = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,](\d{1,3}))?")
# SRT files carry HTML-like tags and ASS override blocks; WebVTT adds class and word-timing tags.
_MARKUP = re.compile(r"<[^>]*>|\{\\[^}]*\}")
_MAX_LINES = 2
_MAX_COLUMNS = 42


@dataclass(frozen=True)
class Captions:
    file: Path
    cues: tuple[tuple[float, float, str], ...]


def _seconds(raw: str, name: str) -> float:
    match = _TIME.fullmatch(raw.strip())
    if match is None:
        raise ValueError(f"{name}: cannot read the caption time {raw.strip()!r}; use 00:00:01,000 or 00:01.000")
    hours, minutes, seconds, fraction = match.groups()
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + float(f"0.{fraction or 0}")


def _parse(text: str, name: str) -> list[tuple[float, float, str]]:
    cues: list[tuple[float, float, str]] = []
    for block in re.split(r"\n[ \t]*\n", text.replace("\r\n", "\n").replace("\r", "\n")):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing = next((index for index, line in enumerate(lines[:2]) if "-->" in line), None)
        if timing is None:
            continue
        start_raw, _, rest = lines[timing].partition("-->")
        # WebVTT cue settings (line:0 position:50%) follow the end time.
        start, end = _seconds(start_raw, name), _seconds((rest.split() or [""])[0], name)
        words = html.unescape(_MARKUP.sub("", " ".join(lines[timing + 1:])))
        words = " ".join(words.split())
        if words and end > start:
            cues.append((start, end, words))
    return _one_at_a_time(cues)


def _one_at_a_time(cues: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    """Overlapping cues would stack upward out of the safe area, so each one ends when the next starts."""
    merged: list[tuple[float, float, str]] = []
    for start, end, words in sorted(cues):
        if merged and start - merged[-1][0] < 0.05:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end), f"{merged[-1][2]} {words}")
        else:
            if merged and merged[-1][1] > start:
                merged[-1] = (merged[-1][0], start, merged[-1][2])
            merged.append((start, end, words))
    return merged


def load_captions(raw: Any) -> Captions:
    """Read the caption file of a ``captions`` override. Raises ``FileNotFoundError`` or ``ValueError``."""
    path = Path(str(raw)).expanduser()
    if path.suffix.lower() not in {".srt", ".vtt"}:
        raise ValueError(f"captions must be an .srt or .vtt file, got {path.name or str(raw)!r}")
    if not path.is_file():
        raise FileNotFoundError(f"captions file not found: {path}")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"could not read the captions file {path.name}: {exc.strerror}") from exc
    try:
        text = data.decode("utf-16" if data[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.name} is not UTF-8 text; save the captions as UTF-8 and retry") from exc
    cues = _parse(text, path.name)
    if not cues:
        raise ValueError(f"{path.name} has no captions")
    return Captions(path, tuple(cues))


def _columns(text: str) -> int:
    """Rough rendered width in Latin letters: CJK and other wide characters take two, combining marks none."""
    return sum(
        0 if unicodedata.combining(char) else 2 if unicodedata.east_asian_width(char) in "WF" else 1
        for char in text
    )


def _wrap(text: str, limit: int) -> list[str]:
    """Lines of at most ``limit`` columns. A word wider than a line (a URL, unspaced CJK) is cut."""
    lines: list[str] = []
    line = ""
    for word in text.split():
        if line and _columns(line) + 1 + _columns(word) <= limit:
            line = f"{line} {word}"
            continue
        if line:
            lines.append(line)
        line = ""
        for char in word:
            if line and _columns(line + char) > limit:
                lines.append(line)
                line = ""
            line += char
    if line:
        lines.append(line)
    return lines


def _layout(target: Any) -> tuple[int, int, int, int]:
    """Font size, side margin, bottom margin and columns per line for ``target``.

    Captions sit on the bottom edge of the platform's caption-safe area. Targets without a published
    safe area get a default: full-screen vertical feeds draw their own caption and buttons over the
    lower quarter, other shapes only need a title-safe edge.
    """
    spec = target.limits.get("safe_area")
    safe = getattr(spec, "value", spec) or {}
    tall = target.width / target.height < 0.7
    side = float(safe.get("side") or (0.06 if tall else 0.05))
    bottom = float(safe.get("bottom") or (0.25 if tall else 0.08))
    font_size = max(18, round(min(target.height * 0.045, target.width * 0.065)))
    margin_x = round(target.width * side)
    # 0.6 of the font size per letter is wide enough for the fallback fonts fontconfig picks.
    columns = min(_MAX_COLUMNS, max(8, int((target.width - 2 * margin_x) / (font_size * 0.6))))
    return font_size, margin_x, round(target.height * bottom), columns


def _ass_time(centiseconds: int) -> str:
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{fraction:02d}"


def _escape_ass(text: str) -> str:
    # A word joiner after each backslash keeps user text from forming \N, \h or an override tag;
    # libass draws nothing for it.
    return text.replace("\\", "\\⁠").replace("{", r"\{").replace("}", r"\}")


def ass_document(captions: Captions, target: Any, trim: tuple[float, float]) -> tuple[str, int]:
    """The ASS file for ``target`` and how many caption screens it shows.

    Cue times move with the trim and are cut at its ends. A cue longer than two lines becomes
    several screens that share its time by their length.
    """
    font_size, margin_x, margin_y, columns = _layout(target)
    outline = max(2, round(font_size * 0.09))
    duration = trim[1] - trim[0]
    events: list[str] = []
    for cue_start, cue_end, words in captions.cues:
        lines = _wrap(words, columns)
        screens = [lines[index:index + _MAX_LINES] for index in range(0, len(lines), _MAX_LINES)]
        weights = [max(1, sum(_columns(line) for line in screen)) for screen in screens]
        elapsed = 0
        for screen, weight in zip(screens, weights, strict=True):
            start = cue_start + (cue_end - cue_start) * elapsed / sum(weights) - trim[0]
            elapsed += weight
            end = cue_start + (cue_end - cue_start) * elapsed / sum(weights) - trim[0]
            start, end = round(max(0.0, start) * 100), round(min(duration, end) * 100)
            if end > start:
                text = "\\N".join(_escape_ass(line) for line in screen)
                events.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{text}")
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {target.width}
PlayResY: {target.height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&HCC000000,&H80000000,-1,0,0,0,100,100,0,0,1,{outline},0,2,{margin_x},{margin_x},{margin_y},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header + "\n".join(events) + "\n", len(events)


@cache
def libass_available() -> bool:
    """Whether this ffmpeg build can draw ASS subtitles; minimal builds leave libass out."""
    try:
        listing = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        return False
    return re.search(r"^\s*\S+\s+ass\s", listing, re.MULTILINE) is not None
