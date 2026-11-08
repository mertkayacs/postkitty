"""Platform copy counting, folding and thread splitting.

All counting rules are deterministic and independent from Hermes. The X weighted count follows
twitter-text v3 (``config/v3.json``): weight 100 for the listed ranges, 200 elsewhere, every URL
counts as 23, and one emoji sequence counts as 200 no matter how many code points it uses.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field

from . import platforms

# twitter-text v3 config/v3.json, fetched 2026-11-08.
_X_RANGES = (
    (0, 4351, 100),
    (8192, 8205, 100),
    (8208, 8223, 100),
    (8242, 8247, 100),
)
_X_DEFAULT_WEIGHT = 200
_X_URL_LENGTH = 23

THREAD_PLATFORMS = frozenset({"x", "threads", "bluesky"})

_TLDS = frozenset(
    "com org net io dev ai app co me tv edu gov xyz info social video blog news link ly gl be to "
    "us uk de fr tr ca au in jp cn ru br es it nl se no fi dk pl pt ch at ie nz za mx ar cl kr sg "
    "hk tw".split()
)

_URL_RE = re.compile(
    r"""(?ix)
    (?: https?://[^\s<>"']+
      | www\.[^\s<>"']+
      | (?<![\w@]) (?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,24} (?:/[^\s<>"']*)?
    )
    """
)
_CANDIDATE_URL_RE = re.compile(r"(?i)(?:https?://|www\.)[^\s<>\"']+|(?<![\w@])(?:[a-z0-9-]+\.)+[a-z]{2,24}(?:/[^\s<>\"']*)?")
_HASHTAG_RE = re.compile(r"(?<![\w#])#\w+")
_MENTION_RE = re.compile(r"(?<![\w@])@\w+")

_EMOJI_BASE_RANGES = (
    (0x1F000, 0x1FAFF),
    (0x1F1E6, 0x1F1FF),
    (0x2600, 0x27BF),
    (0x2300, 0x23FF),
    (0x2B00, 0x2BFF),
)
_MODIFIER_RANGES = ((0x1F3FB, 0x1F3FF),)
_VS16 = "\ufe0f"
_ZWJ = "\u200d"
_KEYCAP = "\u20e3"
_TAG_END = 0xE007F


def _in_ranges(cp: int, ranges: Iterable[tuple[int, int, int]]) -> bool:
    for start, end, _weight in ranges:
        if start <= cp <= end:
            return True
    return False


def _weight(cp: int) -> int:
    for start, end, weight in _X_RANGES:
        if start <= cp <= end:
            return weight
    return _X_DEFAULT_WEIGHT


def _is_emoji_base(cp: int) -> bool:
    for start, end in _EMOJI_BASE_RANGES:
        if start <= cp <= end:
            return True
    for start, end in _MODIFIER_RANGES:
        if start <= cp <= end:
            return True
    return cp in {0x203C, 0x2049, 0x2122, 0x2139, 0x3030, 0x303D, 0x3297, 0x3299}


def _url_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in _CANDIDATE_URL_RE.finditer(text):
        raw = match.group(0)
        stripped = raw.rstrip(".,!?;:)]}'\"")
        if not stripped:
            continue
        low = stripped.lower()
        if not (low.startswith("http://") or low.startswith("https://") or low.startswith("www.")):
            domain = low.split("/", 1)[0]
            tld = domain.rsplit(".", 1)[-1]
            if tld not in _TLDS:
                continue
        end = match.start() + len(stripped)
        spans.append((match.start(), end))
    spans.sort()
    return spans


def _emoji_span(text: str, i: int) -> int | None:
    cp = ord(text[i])
    if text[i] in "0123456789#*":
        j = i + 1
        if j < len(text) and text[j] == _VS16:
            j += 1
        if j < len(text) and text[j] == _KEYCAP:
            return j + 1
        return None
    if 0x1F1E6 <= cp <= 0x1F1FF:
        if i + 1 < len(text) and 0x1F1E6 <= ord(text[i + 1]) <= 0x1F1FF:
            return i + 2
        return i + 1
    if cp == 0x1F3F4:
        j = i + 1
        while j < len(text) and 0xE0020 <= ord(text[j]) <= 0xE007E:
            j += 1
        if j < len(text) and ord(text[j]) == _TAG_END:
            return j + 1
    if not _is_emoji_base(cp):
        return None
    j = i + 1
    if j < len(text) and text[j] == _VS16:
        j += 1
    if j < len(text) and 0x1F3FB <= ord(text[j]) <= 0x1F3FF:
        j += 1
    while j + 1 < len(text) and text[j] == _ZWJ and _is_emoji_base(ord(text[j + 1])):
        j += 2
        if j < len(text) and text[j] == _VS16:
            j += 1
        if j < len(text) and 0x1F3FB <= ord(text[j]) <= 0x1F3FF:
            j += 1
    return j


def x_weighted_length(text: str) -> int:
    """Weighted X length in characters: ASCII 1, other ranges 2, URL 23, emoji sequence 2."""
    spans = _url_spans(text)
    span_at = {start: end for start, end in spans}
    total = 0
    i = 0
    while i < len(text):
        end = span_at.get(i)
        if end is not None:
            total += _X_URL_LENGTH
            i = end
            continue
        emoji_end = _emoji_span(text, i)
        if emoji_end is not None:
            total += 2
            i = emoji_end
            continue
        total += _weight(ord(text[i])) // 100
        i += 1
    return total


def _grapheme_count(text: str) -> int:
    try:
        import regex

        return len(regex.findall(r"\X", text))
    except Exception:
        return _fallback_graphemes(text)


def _fallback_graphemes(text: str) -> int:
    count = 0
    i = 0
    while i < len(text):
        count += 1
        i += 1
        while i < len(text):
            cp = ord(text[i])
            prev = ord(text[i - 1])
            if unicodedata.combining(text[i]) or cp == 0xFE0F or 0x1F3FB <= cp <= 0x1F3FF:
                i += 1
                continue
            if prev == 0x200D:
                i += 1
                continue
            if cp == 0x200D:
                i += 1
                continue
            break
    return count


def _utf16_units(text: str) -> int:
    return sum(2 if ord(char) > 0xFFFF else 1 for char in text)


def count_text(text: str, unit: str) -> int:
    """Count ``text`` in one of the platform units."""
    if unit == "x_weighted":
        return x_weighted_length(text)
    if unit == "graphemes":
        return _grapheme_count(text)
    if unit == "utf16":
        return _utf16_units(text)
    if unit == "codepoints":
        return len(text)
    if unit == "utf8_bytes":
        return len(text.encode("utf-8"))
    raise ValueError(f"unknown text unit {unit!r}")


def count_hashtags(text: str) -> int:
    return len(_HASHTAG_RE.findall(text))


def count_mentions(text: str) -> int:
    return len(_MENTION_RE.findall(text))


def count_urls(text: str) -> int:
    return len(_url_spans(text))


def text_stats(text: str) -> dict:
    return {
        "chars": len(text),
        "x_weighted": x_weighted_length(text),
        "graphemes": _grapheme_count(text),
        "utf16": _utf16_units(text),
        "utf8_bytes": len(text.encode("utf-8")),
        "hashtags": count_hashtags(text),
        "mentions": count_mentions(text),
        "urls": count_urls(text),
    }


@dataclass
class TextRules:
    platform: str
    unit: str
    limit: int
    hashtags_max: int | None = None
    mentions_max: int | None = None
    bytes_max: int | None = None
    hard: bool = True


def rules_for(platform: str) -> TextRules:
    limits = platforms.text_limits(platform)
    if "limit" not in limits:
        raise KeyError(f"platform {platform!r} has no text limit")
    limit_spec = limits["limit"]
    unit = limit_spec.unit or "codepoints"
    hashtags = limits.get("hashtags_max")
    mentions = limits.get("mentions_max")
    bytes_spec = limits.get("bytes_max")
    return TextRules(
        platform=platform,
        unit=unit,
        limit=int(limit_spec.value),
        hashtags_max=int(hashtags.value) if hashtags else None,
        mentions_max=int(mentions.value) if mentions else None,
        bytes_max=int(bytes_spec.value) if bytes_spec else None,
        hard=limit_spec.enforcement == "hard",
    )


def _fits(text: str, rules: TextRules) -> bool:
    if count_text(text, rules.unit) > rules.limit:
        return False
    if rules.bytes_max is not None and len(text.encode("utf-8")) > rules.bytes_max:
        return False
    return True


def _atoms(text: str) -> list[str]:
    spans = {start: end for start, end in _url_spans(text)}
    atoms: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(text):
        end = spans.get(i)
        if end is not None:
            chunk = "".join(buf).strip()
            if chunk:
                atoms.append(chunk)
            buf = []
            atoms.append(text[i:end])
            i = end
            continue
        char = text[i]
        buf.append(char)
        i += 1
        if char in ".!?\u2026":
            while i < len(text) and text[i] in "\"')]}\u00bb":
                buf.append(text[i])
                i += 1
            if i >= len(text) or text[i].isspace():
                chunk = "".join(buf).strip()
                if chunk:
                    atoms.append(chunk)
                buf = []
        elif char == "\n":
            chunk = "".join(buf).strip()
            if chunk:
                atoms.append(chunk)
            buf = []
    chunk = "".join(buf).strip()
    if chunk:
        atoms.append(chunk)
    return atoms


def _split_long_unit(unit: str) -> list[str]:
    if any(unit.startswith(prefix) for prefix in ("http://", "https://", "www.")):
        return [unit]
    if not _url_spans(unit):
        return unit.split()
    protected = {start: end for start, end in _url_spans(unit)}
    pieces: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(unit):
        end = protected.get(i)
        if end is not None:
            chunk = "".join(buf).strip()
            if chunk:
                pieces.append(chunk)
            buf = []
            pieces.append(unit[i:end])
            i = end
            continue
        if unit[i].isspace():
            chunk = "".join(buf).strip()
            if chunk:
                pieces.append(chunk)
            buf = []
        else:
            buf.append(unit[i])
        i += 1
    chunk = "".join(buf).strip()
    if chunk:
        pieces.append(chunk)
    return pieces


def _pack(units: list[str], fits) -> list[str]:
    parts: list[str] = []
    current = ""
    for unit in units:
        candidate = unit if not current else f"{current} {unit}"
        if fits(candidate):
            current = candidate
            continue
        if current:
            parts.append(current)
            current = ""
        if fits(unit):
            current = unit
            continue
        for piece in _split_long_unit(unit):
            candidate = piece if not current else f"{current} {piece}"
            if fits(candidate):
                current = candidate
            else:
                if current:
                    parts.append(current)
                current = piece
    if current:
        parts.append(current)
    return parts


def split_for_limit(text: str, rules: TextRules, max_parts: int = 50) -> list[str]:
    """Split ``text`` on sentence boundaries, never inside a URL, with ``1/n`` suffixes."""
    if _fits(text, rules):
        return [text]
    if rules.platform not in THREAD_PLATFORMS:
        return [text]
    units = _atoms(text)
    for count in range(2, max_parts + 1):
        worst_suffix = f" {count}/{count}"

        def fits_candidate(candidate: str, suffix: str = worst_suffix) -> bool:
            return _fits(candidate + suffix, rules)

        parts = _pack(units, fits_candidate)
        if len(parts) > count:
            continue
        with_suffix = [f"{part} {index + 1}/{len(parts)}" for index, part in enumerate(parts)]
        if all(_fits(part, rules) for part in with_suffix):
            return with_suffix
    return [text]


_FOLD_LIMITS = {
    "x": 280,
    "threads": 500,
    "bluesky": 300,
    "instagram": 125,
    "linkedin": 210,
    "tiktok": 150,
    "facebook": 480,
}


def fold_for(platform: str, text: str) -> tuple[str, int, int]:
    """Return (shown text, shown length, fold limit) for the advisory fold note."""
    limit = _FOLD_LIMITS.get(platform, 280)
    if len(text) <= limit:
        return text, len(text), limit
    cut = text[:limit]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut, len(cut), limit


@dataclass
class CopyReport:
    platform: str
    unit: str
    limit: int
    ok: bool
    parts: list[str]
    counts: list[int]
    overflow: int
    split: bool
    fold: str
    fold_chars: int
    fold_limit: int
    hashtags: int
    mentions: int
    urls: int
    bytes_count: int
    notes: list[str] = field(default_factory=list)


def fit(platform: str, draft: str | list[str], split_threads: bool = True) -> CopyReport:
    """Count one draft, splitting a thread platform's over-limit text when allowed."""
    rules = rules_for(platform)
    notes: list[str] = []
    split = False
    if isinstance(draft, list):
        parts = [str(part) for part in draft]
        if not parts:
            parts = [""]
    else:
        text = str(draft)
        if _fits(text, rules):
            parts = [text]
        elif split_threads and platform in THREAD_PLATFORMS:
            parts = split_for_limit(text, rules)
            split = len(parts) > 1
        else:
            parts = [text]

    counts = [count_text(part, rules.unit) for part in parts]
    overflow = max((max(count - rules.limit, 0) for count in counts), default=0)
    joined = "\n\n".join(parts)
    hashtags = count_hashtags(joined)
    mentions = count_mentions(joined)
    urls = count_urls(joined)
    bytes_count = len(joined.encode("utf-8"))

    if overflow:
        notes.append(
            f"{platform} allows {rules.limit} {rules.unit}; the draft is {max(counts)}."
        )
    if rules.bytes_max is not None and bytes_count > rules.bytes_max:
        notes.append(f"{platform} allows {rules.bytes_max} UTF-8 bytes; the draft uses {bytes_count}.")
    if rules.hashtags_max is not None and hashtags > rules.hashtags_max:
        notes.append(f"{platform} allows {rules.hashtags_max} hashtags; the draft has {hashtags}.")
    if rules.mentions_max is not None and mentions > rules.mentions_max:
        notes.append(f"{platform} allows {rules.mentions_max} mentions; the draft has {mentions}.")
    if split:
        notes.append(f"Split into {len(parts)} parts.")

    ok = (
        all(_fits(part, rules) for part in parts)
        and (rules.hashtags_max is None or hashtags <= rules.hashtags_max)
        and (rules.mentions_max is None or mentions <= rules.mentions_max)
    )
    fold, fold_chars, fold_limit = fold_for(platform, joined)
    return CopyReport(
        platform=platform,
        unit=rules.unit,
        limit=rules.limit,
        ok=ok,
        parts=parts,
        counts=counts,
        overflow=overflow,
        split=split,
        fold=fold,
        fold_chars=fold_chars,
        fold_limit=fold_limit,
        hashtags=hashtags,
        mentions=mentions,
        urls=urls,
        bytes_count=bytes_count,
        notes=notes,
    )


def rules_dict(rules: TextRules) -> dict:
    return {
        "unit": rules.unit,
        "limit": rules.limit,
        "hashtags_max": rules.hashtags_max,
        "mentions_max": rules.mentions_max,
        "bytes_max": rules.bytes_max,
    }
