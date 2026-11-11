"""Burned-in captions: read an SRT or WebVTT file and build the ASS overlay for one target."""

from __future__ import annotations

import html
import re
import subprocess
import tempfile
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..probe import run_tool

_TIME = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,](\d{1,3}))?")
# SRT files carry HTML-like tags and ASS override blocks; WebVTT adds class and word-timing tags.
_MARKUP = re.compile(r"<[^>]*>|\{\\[^}]*\}")
_MAX_LINES = 2
_MAX_COLUMNS = 42
# libass says this each time it meets a character that none of the installed fonts has.
_NO_GLYPH = re.compile(r"failed to find any fallback with glyph 0x([0-9A-Fa-f]+)")
NO_FONT = (
    "ffmpeg found no font on this machine, so captions would come out empty. Install a font and try again. "
    "Debian or Ubuntu: sudo apt install fonts-dejavu-core."
)
_FONT_TEST_FRAME = (320, 180)
# Unicode categories of pictures and decoration (emoji, dingbats, keycaps). A caption reads the same without one.
_SYMBOLS = {"So", "Sk", "Me"}


class FontMissing(ValueError):
    """This machine has no font for the caption text. The message says what to install or take out."""


@dataclass(frozen=True)
class Captions:
    file: Path
    cues: tuple[tuple[float, float, str], ...]
    # Symbols that no installed font has. ``drawable`` took them out of the cues.
    left_out: str = ""


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
        # libass looks a font up for each code point. An accent kept apart from its letter, or a non-breaking
        # hyphen, would count as missing where the composed letter and a plain hyphen draw fine.
        words = unicodedata.normalize("NFC", " ".join(words.split())).replace("\u2011", "-")
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


def _layout(target: Any) -> tuple[int, int, int, int, int]:
    """Font size, left, right and bottom margins, and columns per line for ``target``.

    Captions sit on the bottom edge of the platform's caption-safe area, centred between its side
    insets. A safe area gives one ``side`` inset, or ``left`` and ``right`` where the platform's
    buttons make one side wider. Targets without a published safe area get a default: full-screen
    vertical feeds draw their own caption and buttons over the lower quarter, other shapes only
    need a title-safe edge.
    """
    spec = target.limits.get("safe_area")
    safe = getattr(spec, "value", spec) or {}
    tall = target.width / target.height < 0.7
    side = float(safe.get("side") or (0.06 if tall else 0.05))
    bottom = float(safe.get("bottom") or (0.25 if tall else 0.08))
    font_size = max(18, round(min(target.height * 0.045, target.width * 0.065)))
    left, right = (round(target.width * float(safe.get(edge) or side)) for edge in ("left", "right"))
    # 0.6 of the font size per letter is wide enough for the fallback fonts fontconfig picks.
    columns = min(_MAX_COLUMNS, max(8, int((target.width - left - right) / (font_size * 0.6))))
    return font_size, left, right, round(target.height * bottom), columns


def _ass_time(centiseconds: int) -> str:
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{fraction:02d}"


def _escape_ass(text: str) -> str:
    # A word joiner after each backslash keeps user text from forming \N, \h or an override tag;
    # libass draws nothing for it.
    return text.replace("\\", "\\\u2060").replace("{", r"\{").replace("}", r"\}")


def ass_document(
    captions: Captions, target: Any, trim: tuple[float, float], between_panels: bool = False
) -> tuple[str, int]:
    """The ASS file for ``target`` and how many caption screens it shows.

    Cue times move with the trim and are cut at its ends. A cue longer than two lines becomes
    several screens that share its time by their length. ``between_panels`` is for a split, where
    two people are stacked: the words go on the seam at half the height, because at the bottom of
    the frame they would cover the lower face.
    """
    font_size, margin_left, margin_right, margin_y, columns = _layout(target)
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
    # ASS alignment 2 is bottom centre, 5 is the middle of the frame.
    alignment = 5 if between_panels else 2
    header = _header(target.width, target.height, font_size, outline, margin_left, margin_right, margin_y, alignment)
    return header + "\n".join(events) + "\n", len(events)


def _header(
    width: int, height: int, font_size: int, outline: int, left: int, right: int, bottom: int, alignment: int = 2
) -> str:
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&HCC000000,&H80000000,-1,0,0,0,100,100,0,0,1,{outline},0,{alignment},{left},{right},{bottom},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _without_font(texts: Iterable[str], seconds: float = 120.0) -> list[str] | None:
    """The characters of ``texts`` that no installed font has, or ``None`` when ffmpeg finds no font at all.

    libass draws an empty box for a character that no installed font has, and with no font at all it
    draws nothing. ffmpeg exits cleanly both times, so the video would come out with broken captions
    or with none. Here ffmpeg draws every text once on one black frame: what libass reports names the
    characters, and a frame that stays black means no font. A check that cannot run names nothing
    and stops nothing.
    """
    width, height = _FONT_TEST_FRAME
    texts = list(dict.fromkeys(" ".join(text.split()) for text in texts))
    # Two letters of our own at a fixed place: caption text can be pushed out of the frame.
    lines = [*(_escape_ass(text) for text in texts), rf"{{\pos({width // 2},{height // 2})}}Ag"]
    events = "\n".join(f"Dialogue: 0,{_ass_time(0)},{_ass_time(100)},Default,,0,0,0,,{line}" for line in lines)
    try:
        with tempfile.TemporaryDirectory(prefix="postkitty-", ignore_cleanup_errors=True) as folder:
            Path(folder, "captions.ass").write_text(_header(width, height, 24, 2, 10, 10, 10) + events + "\n", encoding="utf-8")
            drawn = run_tool(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "warning", "-nostdin", "-f", "lavfi",
                    "-i", f"color=c=black:s={width}x{height}:r=1:d=1", "-vf", "ass=captions.ass",
                    "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
                ],
                capture_output=True, check=False, cwd=folder, timeout=seconds,
            )
    except (OSError, subprocess.SubprocessError):
        return []
    if drawn.returncode != 0 or len(drawn.stdout) != width * height:
        return []
    if max(drawn.stdout) < 128:
        return None
    # libass reports the letters of our own sample too when no font has them. Only the captions are answered for.
    asked = {ord(char) for text in texts for char in text}
    codes = {int(code, 16) for code in _NO_GLYPH.findall(drawn.stderr.decode(errors="replace"))} & asked
    return [chr(code) for code in sorted(codes)]


def has_font(seconds: float = 120.0) -> bool:
    """Whether ffmpeg finds a font on this machine to draw captions with. The check gives up after ``seconds``."""
    return _without_font((), seconds) is not None


def _named(char: str) -> str:
    """A character for an error message, with its code point. One that draws nothing readable is the number alone."""
    code = f"U+{ord(char):04X}"
    return code if unicodedata.category(char)[0] in "CMZ" else f"{char} ({code})"


def drawable(captions: Captions) -> Captions:
    """``captions`` as this machine can draw them. Raises ``FontMissing`` when it cannot.

    A symbol that no installed font has (an emoji, mostly) is taken out of the cues and listed in
    ``left_out``. Text that no font has is an error, and so is a machine without any font.
    """
    missing = _without_font(text for _, _, text in captions.cues)
    if missing is None:
        raise FontMissing(NO_FONT)
    text = [char for char in missing if unicodedata.category(char) not in _SYMBOLS]
    if text:
        shown = ", ".join(_named(char) for char in text[:12]) + (f" and {len(text) - 12} more" if len(text) > 12 else "")
        raise FontMissing(
            f"No installed font has these caption characters: {shown}. They would show as empty boxes. "
            "Install a font that has them, or take them out of the captions."
        )
    if not missing:
        return captions
    # An emoji can carry a variation selector or be joined to the next one. Those go with it.
    gone = re.compile("(?:[" + re.escape("".join(missing)) + "][\ufe0e\ufe0f\u200d]*)+")
    cues = tuple(
        (start, end, words) for start, end, text in captions.cues if (words := " ".join(gone.sub(" ", text).split()))
    )
    return Captions(captions.file, cues, " ".join(missing))
