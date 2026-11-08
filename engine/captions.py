from __future__ import annotations

import re
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any


def _timestamp(value: str) -> float:
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    if len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError(f"invalid caption timestamp: {value}")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_captions(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    entries: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0] == "WEBVTT":
            continue
        if "-->" not in lines[0] and len(lines) > 1:
            lines = lines[1:]
        if not lines or "-->" not in lines[0]:
            continue
        start_text, end_text = lines[0].split("-->", 1)
        end_text = end_text.strip().split()[0]
        # WebVTT inline tags (<i>, <c.class>, <00:01.000> word timings) are styling, never caption text.
        caption = " ".join(re.sub(r"<[^>]*>", "", line) for line in lines[1:]).strip()
        if not caption:
            continue
        start = _timestamp(start_text)
        end = _timestamp(end_text)
        if end <= start:
            raise ValueError("caption end must be after its start")
        entries.append({"start": start, "end": end, "text": caption})
    return entries


def _split_text(text: str, maximum: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and len(candidate) > maximum:
            chunks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def _normalize_entries(
    words: list[dict[str, Any]] | Path, target: Any
) -> list[dict[str, Any]]:
    entries = parse_captions(words) if isinstance(words, Path) else words
    line_width = 30 if target.width / target.height < 0.8 else 42
    maximum = line_width * 2
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        start = float(entry["start"])
        end = float(entry["end"])
        text = " ".join(str(entry["text"]).split())
        if end <= start:
            raise ValueError("caption end must be after its start")
        chunks = _split_text(text, maximum)
        for index, chunk in enumerate(chunks):
            chunk_start = start + (end - start) * index / len(chunks)
            chunk_end = start + (end - start) * (index + 1) / len(chunks)
            lines = textwrap.wrap(
                chunk,
                width=line_width,
                break_long_words=True,
                break_on_hyphens=False,
            )
            if len(lines) > 2:
                lines = [lines[0], " ".join(lines[1:])]
            normalized.append(
                {"start": chunk_start, "end": chunk_end, "text": "\\N".join(lines)}
            )
    return normalized


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{fraction:02d}"


def _escape_ass(text: str) -> str:
    escaped = [
        part.replace("\\", "\\\\").replace("{", r"\{").replace("}", r"\}")
        for part in text.split("\\N")
    ]
    return "\\N".join(escaped)


def _ass_document(words: list[dict[str, Any]] | Path, target: Any) -> str:
    safe_spec = target.limits.get("safe_area")
    safe = getattr(safe_spec, "value", safe_spec) if safe_spec is not None else None
    side = float(safe.get("side", 0.0)) if safe else 0.05
    bottom = float(safe.get("bottom", 0.0)) if safe else 0.25
    margin_x = round(target.width * side)
    margin_y = round(target.height * bottom)
    font_size = max(18, round(target.height * 0.045))
    outline = max(2, round(font_size * 0.09))
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
    dialogues = [
        "Dialogue: 0,"
        f"{_ass_time(entry['start'])},{_ass_time(entry['end'])},"
        f"Default,,0,0,0,,{_escape_ass(entry['text'])}"
        for entry in _normalize_entries(words, target)
    ]
    return header + "\n".join(dialogues) + "\n"


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def burn_captions(
    video: Path,
    words: list[dict[str, Any]] | Path,
    target: Any,
    out: Path,
) -> Path:
    if video.resolve() == out.resolve():
        raise ValueError("caption output must differ from the input")
    out.parent.mkdir(parents=True, exist_ok=True)
    document = _ass_document(words, target)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".ass",
        prefix="postkitty-",
        dir=out.parent,
        delete=False,
    ) as handle:
        handle.write(document)
        ass_path = Path(handle.name)
    try:
        command = [
            "nice",
            "-n",
            "10",
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-threads",
            "4",
            "-y",
            "-i",
            str(video),
            "-vf",
            f"ass=filename='{_escape_filter_path(ass_path)}'",
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-profile:v",
            "high",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(out),
        ]
        subprocess.run(command, check=True, capture_output=True)
    finally:
        ass_path.unlink(missing_ok=True)
    return out
