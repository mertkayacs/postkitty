"""Platform copy counting, folding and thread splitting.

All counting rules are deterministic and independent from Hermes. The X weighted count follows
twitter-text v3 (``config/v3.json``): weight 100 for the listed ranges, 200 elsewhere, every URL
counts as 23, and one Twemoji emoji sequence counts as 200 no matter how many code points it uses.
"""

from __future__ import annotations

import functools
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass, field

from .. import platforms

# twitter-text v3 config/v3.json, fetched 2026-11-08.
_X_RANGES = (
    (0, 4351, 100),
    (8192, 8205, 100),
    (8208, 8223, 100),
    (8242, 8247, 100),
)
_X_SCALE = 100
_X_DEFAULT_WEIGHT = 200
_X_URL_LENGTH = 23

THREAD_PLATFORMS = frozenset({"x", "threads", "bluesky"})

# twitter-text js/src/regexp character groups. The port leaves out the "i" flag because Python's
# IGNORECASE also folds the Turkish "ı" and "İ" into ASCII letters, which JavaScript does not.
_X_SPACES = r"\x09-\x0D\x20\x85\xA0\u1680\u180E\u2000-\u200A\u2028\u2029\u202F\u205F\u3000"
_X_PUNCT = r"!'#%&()*+,\\\-./:;<=>?@\[\]\^_{|}~$"
_X_INVALID = r"\uFFFE\uFEFF\uFFFF"
_X_DIRECTIONAL = r"\u202A-\u202E\u061C\u200E\u200F\u2066-\u2069"
_X_LATIN = (
    r"\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u024F\u0253\u0254\u0256\u0257\u0259\u025B\u0263\u0268\u026F\u0272\u0289"
    r"\u028B\u02BB\u0300-\u036F\u1E00-\u1EFF"
)
_X_CYRILLIC = r"\u0400-\u04FF"
_X_MAX_URL_LENGTH = 4096
_X_MAX_TCO_SLUG_LENGTH = 40
# Letters Python folds into "i", "s" and "k" inside a case-insensitive group. They are swapped for
# caseless letters of the same character groups before matching, so "BİLGİ.İNFO" stays plain text.
_X_CASE_SHIELD = str.maketrans("\u0131\u0130\u017f\u212a", "\u0138\u0138\u0138\u2135")

_HASHTAG_RE = re.compile(r"(?<![\w#])#\w+")
_MENTION_RE = re.compile(r"(?<![\w@])@\w+")

def _weight(cp: int) -> int:
    for start, end, weight in _X_RANGES:
        if start <= cp <= end:
            return weight
    return _X_DEFAULT_WEIGHT


def _prefix_tree(words: list[str]) -> str:
    """One regex for ``words`` that shares their prefixes, so a failed match costs a few steps however long the list is.

    The lists put a longer word before its own prefix, which is the order the optional tail keeps.
    """
    tails: dict[str, list[str]] = {}
    for word in words:
        if word:
            tails.setdefault(word[0], []).append(word[1:])
    branches = "|".join(re.escape(head) + _prefix_tree(rest) for head, rest in tails.items())
    if not branches:
        return ""
    return f"(?:{branches}){'?' if '' in words else ''}"


@functools.cache
def _x_url_patterns() -> tuple[re.Pattern[str], ...]:
    """twitter-text's extractUrl, validAsciiDomain and validTcoUrl regexes, plus two that find where to try them."""
    domain_char = f"[^{_X_PUNCT}{_X_SPACES}{_X_INVALID}{_X_DIRECTIONAL}]"
    tlds = _prefix_tree((_X_GTLDS + "|" + _X_CCTLDS).split("|"))
    tld = f"(?:(?i:{tlds})(?=[^0-9a-zA-Z@+-]|\\Z)|[xX][nN]--[\\-0-9a-zA-Z]+)"
    subdomain = f"(?:(?:{domain_char}(?:[_-]|{domain_char})*)?{domain_char}\\.)"
    domain_name = f"(?:(?:{domain_char}(?:-|{domain_char})*)?{domain_char}\\.)"
    path_char = f"[a-zA-Z{_X_CYRILLIC}0-9!*';:=+,.$/%#\\[\\]\\-\u2013_~@|&{_X_LATIN}]"
    parens = f"\\((?:{path_char}+|{path_char}*\\({path_char}+\\){path_char}*)\\)"
    # The library splices its path ending "[...]|(parens)" in without a group, so a lone "(...)" is its own branch.
    path_end = f"[+\\-a-zA-Z{_X_CYRILLIC}0-9=_#/{_X_LATIN}]"
    path = f"(?:{path_char}*(?:{parens}{path_char}*)*{path_end}|{parens}|@{path_char}+/)"
    query = r"\?[a-zA-Z0-9!?*'@();:&=+$/%#\[\]\-_.,~|]*[a-zA-Z0-9\-_&=#/]"
    before = f"[^A-Za-z0-9@\uff20$#\uff03{_X_INVALID}]|[{_X_DIRECTIONAL}]"
    url = re.compile(
        f"(?P<before>{before}|^)"
        f"(?P<url>(?P<protocol>[hH][tT][tT][pP][sS]?://)?(?P<domain>{subdomain}*{domain_name}{tld})"
        f"(?::[0-9]+)?(?P<path>/{path}*)?(?:{query})?)"
    )
    ascii_domain = re.compile(f"(?:[\\-a-zA-Z0-9{_X_LATIN}]+\\.)+{tld}")
    tco = re.compile(f"[hH][tT][tT][pP][sS]?://[tT]\\.[cC][oO]/([a-zA-Z0-9]+)(?:{query})?")
    label_run = re.compile(f"(?:{domain_char}|[_-])+")
    label_start = re.compile(f"(?:{before})(?={domain_char})")
    return url, ascii_domain, tco, label_run, label_start


def _x_match_starts(view: str, start: int, end: int, pos: int, label_start: re.Pattern[str]) -> Iterator[int]:
    """Offsets where a link can begin inside one run of domain characters, given the scan is at ``pos``.

    twitter-text tries its pattern at every offset, which takes quadratic time on long unspaced text such as
    Japanese. A domain label always ends where its run ends, so every start in a run meets the same rest of
    the pattern. Only the first start can win, or the first one after the last underscore, because the label
    next to the top-level domain takes no underscore.
    """
    if view.startswith("://", end):
        scheme = 5 if view[end - 1] in "sS" else 4
        if end - scheme >= start:
            yield max(end - scheme - 1, 0)
        return
    if not view.startswith(".", end):
        return
    first = None
    for low in (max(start, pos + 1 if pos else 0), view.rfind("_", start, end) + 1):
        if first is not None and low <= first:
            return
        if low == 0 and view[0] not in "_-":
            first = 0
        else:
            found = label_start.search(view, max(low - 1, 0), end)
            if found is None:
                return
            first = found.end()
        yield max(first - 1, 0)


def _x_domain_is_valid(domain: str, ascii_domain: re.Pattern[str]) -> bool:
    """twitter-text idna.toAscii: every label is 1 to 63 characters once Punycode encoded."""
    if domain[:4] == "xn--" and not ascii_domain.search(domain):
        return False
    for label in domain.split("."):
        encoded = label if label.isascii() else "xn--" + label.encode("punycode").decode("ascii")
        if not 1 <= len(encoded) <= 63:
            return False
    return True


def _url_spans(text: str) -> list[tuple[int, int]]:
    """Start and end of every URL X would shorten, following twitter-text extractUrlsWithIndices."""
    if "." not in text:
        return []
    # twitter-text matches UTF-16 code units, so a link may start between the two units of an emoji, as in
    # "#" + emoji + ".example.com". Match on the same units and map the offsets back to code points.
    units: list[str] = []
    offsets: list[int] = []
    for index, char in enumerate(text.translate(_X_CASE_SHIELD)):
        code = ord(char) - 0x10000
        pair = char if code < 0 else chr(0xD800 + (code >> 10)) + chr(0xDC00 + (code & 0x3FF))
        units.append(pair)
        offsets.extend([index] * len(pair))
    offsets.append(len(text))

    view = "".join(units)
    url_re, ascii_domain_re, tco_re, label_run_re, label_start_re = _x_url_patterns()
    spans: list[tuple[int, int]] = []
    pos = 0
    dead = -1  # where the next label of a dotted chain starts once a try from an earlier label of it failed
    for run in label_run_re.finditer(view):
        start, end = run.span()
        dotted = view.startswith(".", end)
        if start == dead and dotted and "_" not in run[0] and view[start] != "-" and view[end - 1] != "-":
            dead = end + 1  # every start in this label meets the rest of the chain that already failed
            continue
        dead = -1
        match = None
        for at in _x_match_starts(view, start, end, pos, label_start_re):
            if at < pos:
                continue
            match = url_re.match(view, at)
            if match:
                break
            if dotted and view[end - 1] not in "_-":
                dead = end + 1
        if match is None:
            continue
        dead = -1
        pos = match.end()
        url, protocol, domain = match["url"], match["protocol"], match["domain"]
        start = match.start("url")
        if not _x_domain_is_valid(domain, ascii_domain_re):
            continue
        if len(protocol or "https://") + len(url) > _X_MAX_URL_LENGTH:
            continue
        if protocol:
            tco = tco_re.match(url)
            if tco:
                if len(tco[1]) > _X_MAX_TCO_SLUG_LENGTH:
                    continue
                url = tco[0]
            spans.append((start, start + len(url)))
            continue
        if match["before"] in ("-", "_", ".", "/"):
            continue
        # Without a protocol only the ASCII part of the domain links, and the path belongs to the last one.
        found = [(start + part.start(), start + part.end()) for part in ascii_domain_re.finditer(domain)]
        if found and match["path"]:
            last_start, last_end = found[-1]
            found[-1] = (last_start, last_end + len(url) - len(domain))
        spans.extend(found)
    return [(offsets[a], offsets[b]) for a, b in spans]


@functools.cache
def _x_emoji_pattern() -> re.Pattern[str]:
    return re.compile(_X_EMOJI)


def x_weighted_length(text: str) -> int:
    """Weighted X length as twitter-text parseTweet counts it: a URL is 23 and a Twemoji emoji is 2."""
    text = unicodedata.normalize("NFC", text)
    urls = dict(_url_spans(text))
    emoji = {match.start(): match.end() for match in _x_emoji_pattern().finditer(text)}
    weight = 0
    i = 0
    while i < len(text):
        if i in urls:
            weight += _X_URL_LENGTH * _X_SCALE
            i = urls[i]
        elif i in emoji:
            weight += _X_DEFAULT_WEIGHT
            i = emoji[i]
        else:
            weight += _weight(ord(text[i]))
            i += 1
    return weight // _X_SCALE


def _grapheme_count(text: str) -> int:
    import regex

    return len(regex.findall(r"\X", text))


@functools.cache
def _threads_patterns():
    import regex

    emoji = r"[\p{Extended_Pictographic}\p{Emoji_Modifier}\p{Regional_Indicator}\uFE0F\u20E3]"
    return regex.compile(r"\X"), regex.compile(emoji)


def _threads_length(text: str) -> int:
    """Threads length: a character counts one, and a character that holds an emoji counts its UTF-8 bytes.

    Meta states the byte rule and leaves open what it treats as an emoji, so every cluster with a pictograph,
    a flag letter, a skin tone, a keycap or the emoji selector counts in bytes. This can overcount an unusual
    symbol and cannot undercount an emoji.
    """
    clusters, emoji = _threads_patterns()
    return sum(len(c.encode("utf-8")) if emoji.search(c) else len(c) for c in clusters.findall(text))


def _utf16_units(text: str) -> int:
    return sum(2 if ord(char) > 0xFFFF else 1 for char in text)


_UNIT_WORDS = {
    "codepoints": "characters",
    "graphemes": "characters",
    "utf16": "UTF-16 units",
    "utf8_bytes": "UTF-8 bytes",
    "x_weighted": "weighted characters",
    "threads": "characters (an emoji counts as its UTF-8 bytes)",
}


def unit_words(unit: str) -> str:
    """The counting unit in words a person reads, for messages."""
    return _UNIT_WORDS[unit]


def count_text(text: str, unit: str) -> int:
    """Count ``text`` in one of the platform units."""
    if unit == "x_weighted":
        return x_weighted_length(text)
    if unit == "graphemes":
        return _grapheme_count(text)
    if unit == "utf16":
        return _utf16_units(text)
    if unit == "threads":
        return _threads_length(text)
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


def _separator(text: str, position: int) -> str:
    """The whitespace to keep before the atom starting at ``position``: a space, or the paragraph break."""
    start = position
    while start > 0 and text[start - 1].isspace():
        start -= 1
    newlines = text[start:position].count("\n")
    return "\n\n" if newlines >= 2 else "\n" if newlines == 1 else " "


def _atoms(text: str) -> list[tuple[str, str]]:
    """Sentences, lines and URLs, each with the separator that preceded it in the draft."""
    spans = {start: end for start, end in _url_spans(text)}
    atoms: list[tuple[str, str]] = []
    segment_start = 0
    i = 0

    def flush(end: int) -> None:
        nonlocal segment_start
        raw = text[segment_start:end]
        chunk = raw.strip()
        if chunk:
            atoms.append((chunk, _separator(text, segment_start + len(raw) - len(raw.lstrip()))))
        segment_start = end

    while i < len(text):
        end = spans.get(i)
        if end is not None:
            flush(i)
            atoms.append((text[i:end], _separator(text, i)))
            i = segment_start = end
            continue
        char = text[i]
        i += 1
        if char in ".!?\u2026":
            while i < len(text) and text[i] in "\"')]}\u00bb":
                i += 1
            if i >= len(text) or text[i].isspace():
                flush(i)
        elif char == "\n":
            flush(i)
    flush(len(text))
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


def _pack(units: list[tuple[str, str]], fits) -> list[str]:
    parts: list[str] = []
    current = ""
    for unit, separator in units:
        candidate = unit if not current else f"{current}{separator}{unit}"
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


_MAX_THREAD_PARTS = 50


def split_for_limit(text: str, rules: TextRules, max_parts: int = _MAX_THREAD_PARTS) -> list[str]:
    """Split ``text`` on sentence boundaries, never inside a URL, with ``1/n`` suffixes.

    Returns ``[text]`` unchanged when it fits, when the platform has no threads, or when no split of at most
    ``max_parts`` posts exists (a single word longer than a post, or too much text).
    """
    if _fits(text, rules) or rules.platform not in THREAD_PLATFORMS:
        return [text]
    units = _atoms(text)
    for digits in range(1, len(str(max_parts)) + 1):
        widest = f" {'9' * digits}/{'9' * digits}"  # room for the longest counter of this width

        def fits_with_counter(candidate: str, suffix: str = widest) -> bool:
            return _fits(candidate + suffix, rules)

        parts = _pack(units, fits_with_counter)
        if len(parts) <= min(10**digits - 1, max_parts):
            numbered = [f"{part} {index}/{len(parts)}" for index, part in enumerate(parts, start=1)]
            return numbered if all(_fits(part, rules) for part in numbered) else [text]
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
    """Return (shown text, shown length, fold limit) for the advisory fold note.

    The cut falls on a space when there is one, and never inside an emoji or an accented letter.
    """
    limit = _FOLD_LIMITS.get(platform) or rules_for(platform).limit
    if len(text) <= limit:
        return text, len(text), limit
    import regex

    cut = ""
    for cluster in regex.findall(r"\X", text[: limit + 64]):
        if len(cut) + len(cluster) > limit:
            break
        cut += cluster
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
    hard: bool = True


def fit(platform: str, draft: str | list[str], split_threads: bool = True) -> CopyReport:
    """Count one draft, splitting a thread platform's over-limit text when allowed."""
    rules = rules_for(platform)
    notes: list[str] = []
    split = unsplittable = False
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
            unsplittable = not split
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
        notes.append(f"{platform} allows {rules.limit} {unit_words(rules.unit)}; the draft is {max(counts)}, {overflow} over.")
    largest = max(len(part.encode("utf-8")) for part in parts)
    if rules.bytes_max is not None and largest > rules.bytes_max:
        notes.append(f"{platform} allows {rules.bytes_max} UTF-8 bytes in one post; the draft uses {largest}.")
    if rules.hashtags_max is not None and hashtags > rules.hashtags_max:
        notes.append(f"{platform} allows {rules.hashtags_max} hashtags; the draft has {hashtags}.")
    if rules.mentions_max is not None and mentions > rules.mentions_max:
        notes.append(f"{platform} allows {rules.mentions_max} mentions; the draft has {mentions}.")
    if split:
        notes.append(f"Split into {len(parts)} parts.")
    if unsplittable:
        notes.append(
            f"The draft cannot be split into a thread of at most {_MAX_THREAD_PARTS} posts. "
            "Shorten it, or break up a word that is longer than one post."
        )

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
        hard=rules.hard,
    )


def check_text(text: str, platform_names: list[str] | None = None, split_threads: bool = True) -> dict[str, dict]:
    """Count ``text`` for each platform and report limit, fit, fold and thread parts. Needs no job folder.

    ``platform_names`` defaults to every platform in the platform file. Raises ``ValueError`` for a text that
    cannot be a post (empty, whitespace only, or holding half of a surrogate pair) and ``KeyError`` for an
    unknown platform name.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("text holds half of a surrogate pair, which is no valid character") from None
    result: dict[str, dict] = {}
    for name in platform_names or platforms.platform_names():
        report = fit(name, text, split_threads=split_threads)
        result[name] = {
            "unit": report.unit,
            "limit": report.limit,
            "count": max(report.counts),
            "ok": report.ok,
            "hard": report.hard,
            "overflow": report.overflow,
            "split": report.split,
            "parts": [{"text": part, "count": count} for part, count in zip(report.parts, report.counts, strict=True)],
            "fold": report.fold,
            "fold_limit": report.fold_limit,
            "hashtags": report.hashtags,
            "mentions": report.mentions,
            "urls": report.urls,
            "notes": report.notes,
        }
    return result


# Data copied from the libraries X publishes, so the count matches the composer.
# twitter-text js/src/regexp/validGTLD.js and validCCTLD.js (Apache 2.0, Twitter, Inc.), in the library's order.
_X_GTLDS = (
    "삼성|닷컴|닷넷|香格里拉|餐厅|食品|飞利浦|電訊盈科|集团|通販|购物|谷歌|诺基亚|联通|网络|网站|网店|网址|组织机构|移动|"
    "珠宝|点看|游戏|淡马锡|机构|書籍|时尚|新闻|政府|政务|招聘|手表|手机|我爱你|慈善|微博|广东|工行|家電|娱乐|天主教|大拿|"
    "大众汽车|在线|嘉里大酒店|嘉里|商标|商店|商城|公益|公司|八卦|健康|信息|佛山|企业|中文网|中信|世界|ポイント|"
    "ファッション|セール|ストア|コム|グーグル|クラウド|みんな|คอม|संगठन|नेट|कॉम|همراه|موقع|"
    "موبايلي|كوم|كاثوليك|عرب|شبكة|بيتك|بازار|العليان|ارامكو|اتصالات|"
    "ابوظبي|קום|сайт|рус|орг|онлайн|москва|ком|католик|дети|zuerich|zone|"
    "zippo|zip|zero|zara|zappos|yun|youtube|you|yokohama|yoga|yodobashi|yandex|yamaxun|yahoo|yachts|xyz|xxx|xperia|xin|"
    "xihuan|xfinity|xerox|xbox|wtf|wtc|wow|world|works|work|woodside|wolterskluwer|wme|winners|wine|windows|win|"
    "williamhill|wiki|wien|whoswho|weir|weibo|wedding|wed|website|weber|webcam|weatherchannel|weather|watches|watch|"
    "warman|wanggou|wang|walter|walmart|wales|vuelos|voyage|voto|voting|vote|volvo|volkswagen|vodka|vlaanderen|vivo|viva|"
    "vistaprint|vista|vision|visa|virgin|vip|vin|villas|viking|vig|video|viajes|vet|versicherung|vermögensberatung|"
    "vermögensberater|verisign|ventures|vegas|vanguard|vana|vacations|ups|uol|uno|university|unicom|uconnect|ubs|ubank|"
    "tvs|tushu|tunes|tui|tube|trv|trust|travelersinsurance|travelers|travelchannel|travel|training|trading|trade|toys|"
    "toyota|town|tours|total|toshiba|toray|top|tools|tokyo|today|tmall|tkmaxx|tjx|tjmaxx|tirol|tires|tips|tiffany|tienda|"
    "tickets|tiaa|theatre|theater|thd|teva|tennis|temasek|telefonica|telecity|tel|technology|tech|team|tdk|tci|taxi|tax|"
    "tattoo|tatar|tatamotors|target|taobao|talk|taipei|tab|systems|symantec|sydney|swiss|swiftcover|swatch|suzuki|"
    "surgery|surf|support|supply|supplies|sucks|style|study|studio|stream|store|storage|stockholm|stcgroup|stc|statoil|"
    "statefarm|statebank|starhub|star|staples|stada|srt|srl|spreadbetting|spot|sport|spiegel|space|soy|sony|song|"
    "solutions|solar|sohu|software|softbank|social|soccer|sncf|smile|smart|sling|skype|sky|skin|ski|site|singles|sina|"
    "silk|shriram|showtime|show|shouji|shopping|shop|shoes|shiksha|shia|shell|shaw|sharp|shangrila|sfr|sexy|sex|sew|"
    "seven|ses|services|sener|select|seek|security|secure|seat|search|scot|scor|scjohnson|science|schwarz|schule|school|"
    "scholarships|schmidt|schaeffler|scb|sca|sbs|sbi|saxo|save|sas|sarl|sapo|sap|sanofi|sandvikcoromant|sandvik|samsung|"
    "samsclub|salon|sale|sakura|safety|safe|saarland|ryukyu|rwe|run|ruhr|rugby|rsvp|room|rogers|rodeo|rocks|rocher|rmit|"
    "rip|rio|ril|rightathome|ricoh|richardli|rich|rexroth|reviews|review|restaurant|rest|republican|report|repair|"
    "rentals|rent|ren|reliance|reit|reisen|reise|rehab|redumbrella|redstone|red|recipes|realty|realtor|realestate|read|"
    "raid|radio|racing|qvc|quest|quebec|qpon|pwc|pub|prudential|pru|protection|property|properties|promo|progressive|"
    "prof|productions|prod|pro|prime|press|praxi|pramerica|post|porn|politie|poker|pohl|pnc|plus|plumbing|playstation|"
    "play|place|pizza|pioneer|pink|ping|pin|pid|pictures|pictet|pics|piaget|physio|photos|photography|photo|phone|"
    "philips|phd|pharmacy|pfizer|pet|pccw|pay|passagens|party|parts|partners|pars|paris|panerai|panasonic|pamperedchef|"
    "page|ovh|ott|otsuka|osaka|origins|orientexpress|organic|org|orange|oracle|open|ooo|onyourside|online|onl|ong|one|"
    "omega|ollo|oldnavy|olayangroup|olayan|okinawa|office|off|observer|obi|nyc|ntt|nrw|nra|nowtv|nowruz|now|norton|"
    "northwesternmutual|nokia|nissay|nissan|ninja|nikon|nike|nico|nhk|ngo|nfl|nexus|nextdirect|next|news|newholland|new|"
    "neustar|network|netflix|netbank|net|nec|nba|navy|natura|nationwide|name|nagoya|nadex|nab|mutuelle|mutual|museum|mtr|"
    "mtpc|mtn|msd|movistar|movie|mov|motorcycles|moto|moscow|mortgage|mormon|mopar|montblanc|monster|money|monash|mom|"
    "moi|moe|moda|mobily|mobile|mobi|mma|mls|mlb|mitsubishi|mit|mint|mini|mil|microsoft|miami|metlife|merckmsd|meo|menu|"
    "men|memorial|meme|melbourne|meet|media|med|mckinsey|mcdonalds|mcd|mba|mattel|maserati|marshalls|marriott|markets|"
    "marketing|market|map|mango|management|man|makeup|maison|maif|madrid|macys|luxury|luxe|lupin|lundbeck|ltda|ltd|"
    "lplfinancial|lpl|love|lotto|lotte|london|lol|loft|locus|locker|loans|loan|llp|llc|lixil|living|live|lipsy|link|"
    "linde|lincoln|limo|limited|lilly|like|lighting|lifestyle|lifeinsurance|life|lidl|liaison|lgbt|lexus|lego|legal|"
    "lefrak|leclerc|lease|lds|lawyer|law|latrobe|latino|lat|lasalle|lanxess|landrover|land|lancome|lancia|lancaster|"
    "lamer|lamborghini|ladbrokes|lacaixa|kyoto|kuokgroup|kred|krd|kpn|kpmg|kosher|komatsu|koeln|kiwi|kitchen|kindle|"
    "kinder|kim|kia|kfh|kerryproperties|kerrylogistics|kerryhotels|kddi|kaufen|juniper|juegos|jprs|jpmorgan|joy|jot|"
    "joburg|jobs|jnj|jmp|jll|jlc|jio|jewelry|jetzt|jeep|jcp|jcb|java|jaguar|iwc|iveco|itv|itau|istanbul|ist|ismaili|"
    "iselect|irish|ipiranga|investments|intuit|international|intel|int|insure|insurance|institute|ink|ing|info|infiniti|"
    "industries|inc|immobilien|immo|imdb|imamat|ikano|iinet|ifm|ieee|icu|ice|icbc|ibm|hyundai|hyatt|hughes|htc|hsbc|how|"
    "house|hotmail|hotels|hoteles|hot|hosting|host|hospital|horse|honeywell|honda|homesense|homes|homegoods|homedepot|"
    "holiday|holdings|hockey|hkt|hiv|hitachi|hisamitsu|hiphop|hgtv|hermes|here|helsinki|help|healthcare|health|hdfcbank|"
    "hdfc|hbo|haus|hangout|hamburg|hair|guru|guitars|guide|guge|gucci|guardian|group|grocery|gripe|green|gratis|graphics|"
    "grainger|gov|got|gop|google|goog|goodyear|goodhands|goo|golf|goldpoint|gold|godaddy|gmx|gmo|gmbh|gmail|globo|global|"
    "gle|glass|glade|giving|gives|gifts|gift|ggee|george|genting|gent|gea|gdn|gbiz|gay|garden|gap|games|game|gallup|"
    "gallo|gallery|gal|fyi|futbol|furniture|fund|fun|fujixerox|fujitsu|ftr|frontier|frontdoor|frogans|frl|fresenius|free|"
    "fox|foundation|forum|forsale|forex|ford|football|foodnetwork|food|foo|fly|flsmidth|flowers|florist|flir|flights|"
    "flickr|fitness|fit|fishing|fish|firmdale|firestone|fire|financial|finance|final|film|fido|fidelity|fiat|ferrero|"
    "ferrari|feedback|fedex|fast|fashion|farmers|farm|fans|fan|family|faith|fairwinds|fail|fage|extraspace|express|"
    "exposed|expert|exchange|everbank|events|eus|eurovision|etisalat|esurance|estate|esq|erni|ericsson|equipment|epson|"
    "epost|enterprises|engineering|engineer|energy|emerck|email|education|edu|edeka|eco|eat|earth|dvr|dvag|durban|dupont|"
    "duns|dunlop|duck|dubai|dtv|drive|download|dot|doosan|domains|doha|dog|dodge|doctor|docs|dnp|diy|dish|discover|"
    "discount|directory|direct|digital|diet|diamonds|dhl|dev|design|desi|dentist|dental|democrat|delta|deloitte|dell|"
    "delivery|degree|deals|dealer|deal|dds|dclk|day|datsun|dating|date|data|dance|dad|dabur|cyou|cymru|cuisinella|csc|"
    "cruises|cruise|crs|crown|cricket|creditunion|creditcard|credit|cpa|courses|coupons|coupon|country|corsica|coop|cool|"
    "cookingchannel|cooking|contractors|contact|consulting|construction|condos|comsec|computer|compare|company|community|"
    "commbank|comcast|com|cologne|college|coffee|codes|coach|clubmed|club|cloud|clothing|clinique|clinic|click|cleaning|"
    "claims|cityeats|city|citic|citi|citadel|cisco|circle|cipriani|church|chrysler|chrome|christmas|chloe|chintai|cheap|"
    "chat|chase|charity|channel|chanel|cfd|cfa|cern|ceo|center|ceb|cbs|cbre|cbn|cba|catholic|catering|cat|casino|cash|"
    "caseih|case|casa|cartier|cars|careers|career|care|cards|caravan|car|capitalone|capital|capetown|canon|"
    "cancerresearch|camp|camera|cam|calvinklein|call|cal|cafe|cab|bzh|buzz|buy|business|builders|build|bugatti|budapest|"
    "brussels|brother|broker|broadway|bridgestone|bradesco|box|boutique|bot|boston|bostik|bosch|boots|booking|book|boo|"
    "bond|bom|bofa|boehringer|boats|bnpparibas|bnl|bmw|bms|blue|bloomberg|blog|blockbuster|blanco|blackfriday|black|biz|"
    "bio|bingo|bing|bike|bid|bible|bharti|bet|bestbuy|best|berlin|bentley|beer|beauty|beats|bcn|bcg|bbva|bbt|bbc|bayern|"
    "bauhaus|basketball|baseball|bargains|barefoot|barclays|barclaycard|barcelona|bar|bank|band|bananarepublic|banamex|"
    "baidu|baby|azure|axa|aws|avianca|autos|auto|author|auspost|audio|audible|audi|auction|attorney|athleta|associates|"
    "asia|asda|arte|art|arpa|army|archi|aramco|arab|aquarelle|apple|app|apartments|aol|anz|anquan|android|analytics|"
    "amsterdam|amica|amfam|amex|americanfamily|americanexpress|alstom|alsace|ally|allstate|allfinanz|alipay|alibaba|"
    "alfaromeo|akdn|airtel|airforce|airbus|aigo|aig|agency|agakhan|africa|afl|afamilycompany|aetna|aero|aeg|adult|ads|"
    "adac|actor|active|aco|accountants|accountant|accenture|academy|abudhabi|abogado|able|abc|abbvie|abbott|abb|abarth|"
    "aarp|aaa|onion"
)

_X_CCTLDS = (
    "한국|香港|澳門|新加坡|台灣|台湾|中國|中国|გე|ລາວ|ไทย|ලංකා|ഭാരതം|ಭಾರತ|భారత్|"
    "சிங்கப்பூர்|இலங்கை|இந்தியா|ଭାରତ|ભારત|ਭਾਰਤ|ভাৰত|ভারত|বাংলা|"
    "भारोत|भारतम्|भारत|ڀارت|پاکستان|موريتانيا|مليسيا|مصر|قطر|فلسطين|"
    "عمان|عراق|سورية|سودان|تونس|بھارت|بارت|ایران|امارات|المغرب|"
    "السعودية|الجزائر|البحرين|الاردن|հայ|қаз|укр|срб|рф|мон|мкд|ею|"
    "бел|бг|ευ|ελ|zw|zm|za|yt|ye|ws|wf|vu|vn|vi|vg|ve|vc|va|uz|uy|us|um|uk|ug|ua|tz|tw|tv|tt|tr|tp|to|tn|tm|tl|"
    "tk|tj|th|tg|tf|td|tc|sz|sy|sx|sv|su|st|ss|sr|so|sn|sm|sl|sk|sj|si|sh|sg|se|sd|sc|sb|sa|rw|ru|rs|ro|re|qa|py|pw|pt|"
    "ps|pr|pn|pm|pl|pk|ph|pg|pf|pe|pa|om|nz|nu|nr|np|no|nl|ni|ng|nf|ne|nc|na|mz|my|mx|mw|mv|mu|mt|ms|mr|mq|mp|mo|mn|mm|"
    "ml|mk|mh|mg|mf|me|md|mc|ma|ly|lv|lu|lt|ls|lr|lk|li|lc|lb|la|kz|ky|kw|kr|kp|kn|km|ki|kh|kg|ke|jp|jo|jm|je|it|is|ir|"
    "iq|io|in|im|il|ie|id|hu|ht|hr|hn|hm|hk|gy|gw|gu|gt|gs|gr|gq|gp|gn|gm|gl|gi|gh|gg|gf|ge|gd|gb|ga|fr|fo|fm|fk|fj|fi|"
    "eu|et|es|er|eh|eg|ee|ec|dz|do|dm|dk|dj|de|cz|cy|cx|cw|cv|cu|cr|co|cn|cm|cl|ck|ci|ch|cg|cf|cd|cc|ca|bz|by|bw|bv|bt|"
    "bs|br|bq|bo|bn|bm|bl|bj|bi|bh|bg|bf|be|bd|bb|ba|az|ax|aw|au|at|as|ar|aq|ao|an|am|al|ai|ag|af|ae|ad|ac"
)

# twemoji-parser 14.0.0 src/lib/regex.js (MIT, Twitter, Inc.) with surrogate pairs written as code points.
_X_EMOJI = (
    r"(?:\U0001F468\U0001F3FB\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F468"
    r"\U0001F3FC\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F468\U0001F3FD\u200D\u2764"
    r"\uFE0F\u200D\U0001F48B\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F468\U0001F3FE\u200D\u2764\uFE0F\u200D\U0001F48B"
    r"\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F468\U0001F3FF\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F468["
    r"\U0001F3FB-\U0001F3FF]|\U0001F469\U0001F3FB\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F468[\U0001F3FB-\U0001F3FF]"
    r"|\U0001F469\U0001F3FB\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F469[\U0001F3FB-\U0001F3FF]|\U0001F469\U0001F3FC"
    r"\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F469\U0001F3FC\u200D\u2764\uFE0F"
    r"\u200D\U0001F48B\u200D\U0001F469[\U0001F3FB-\U0001F3FF]|\U0001F469\U0001F3FD\u200D\u2764\uFE0F\u200D\U0001F48B\u200D"
    r"\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F469\U0001F3FD\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F469[\U0001F3FB-"
    r"\U0001F3FF]|\U0001F469\U0001F3FE\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F469"
    r"\U0001F3FE\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F469[\U0001F3FB-\U0001F3FF]|\U0001F469\U0001F3FF\u200D\u2764"
    r"\uFE0F\u200D\U0001F48B\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F469\U0001F3FF\u200D\u2764\uFE0F\u200D\U0001F48B"
    r"\u200D\U0001F469[\U0001F3FB-\U0001F3FF]|\U0001F9D1\U0001F3FB\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F9D1["
    r"\U0001F3FC-\U0001F3FF]|\U0001F9D1\U0001F3FC\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F9D1[\U0001F3FB\U0001F3FD-"
    r"\U0001F3FF]|\U0001F9D1\U0001F3FD\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F9D1[\U0001F3FB\U0001F3FC\U0001F3FE"
    r"\U0001F3FF]|\U0001F9D1\U0001F3FE\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F9D1[\U0001F3FB-\U0001F3FD\U0001F3FF]|"
    r"\U0001F9D1\U0001F3FF\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F9D1[\U0001F3FB-\U0001F3FE]|\U0001F468\U0001F3FB"
    r"\u200D\u2764\uFE0F\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F468\U0001F3FB\u200D\U0001F91D\u200D\U0001F468["
    r"\U0001F3FC-\U0001F3FF]|\U0001F468\U0001F3FC\u200D\u2764\uFE0F\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F468"
    r"\U0001F3FC\u200D\U0001F91D\u200D\U0001F468[\U0001F3FB\U0001F3FD-\U0001F3FF]|\U0001F468\U0001F3FD\u200D\u2764\uFE0F"
    r"\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F468\U0001F3FD\u200D\U0001F91D\u200D\U0001F468[\U0001F3FB\U0001F3FC"
    r"\U0001F3FE\U0001F3FF]|\U0001F468\U0001F3FE\u200D\u2764\uFE0F\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F468"
    r"\U0001F3FE\u200D\U0001F91D\u200D\U0001F468[\U0001F3FB-\U0001F3FD\U0001F3FF]|\U0001F468\U0001F3FF\u200D\u2764\uFE0F"
    r"\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F468\U0001F3FF\u200D\U0001F91D\u200D\U0001F468[\U0001F3FB-\U0001F3FE]|"
    r"\U0001F469\U0001F3FB\u200D\u2764\uFE0F\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F469\U0001F3FB\u200D\u2764\uFE0F"
    r"\u200D\U0001F469[\U0001F3FB-\U0001F3FF]|\U0001F469\U0001F3FB\u200D\U0001F91D\u200D\U0001F468[\U0001F3FC-\U0001F3FF]|"
    r"\U0001F469\U0001F3FB\u200D\U0001F91D\u200D\U0001F469[\U0001F3FC-\U0001F3FF]|\U0001F469\U0001F3FC\u200D\u2764\uFE0F"
    r"\u200D\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F469\U0001F3FC\u200D\u2764\uFE0F\u200D\U0001F469[\U0001F3FB-\U0001F3FF"
    r"]|\U0001F469\U0001F3FC\u200D\U0001F91D\u200D\U0001F468[\U0001F3FB\U0001F3FD-\U0001F3FF]|\U0001F469\U0001F3FC\u200D"
    r"\U0001F91D\u200D\U0001F469[\U0001F3FB\U0001F3FD-\U0001F3FF]|\U0001F469\U0001F3FD\u200D\u2764\uFE0F\u200D\U0001F468["
    r"\U0001F3FB-\U0001F3FF]|\U0001F469\U0001F3FD\u200D\u2764\uFE0F\u200D\U0001F469[\U0001F3FB-\U0001F3FF]|\U0001F469"
    r"\U0001F3FD\u200D\U0001F91D\u200D\U0001F468[\U0001F3FB\U0001F3FC\U0001F3FE\U0001F3FF]|\U0001F469\U0001F3FD\u200D"
    r"\U0001F91D\u200D\U0001F469[\U0001F3FB\U0001F3FC\U0001F3FE\U0001F3FF]|\U0001F469\U0001F3FE\u200D\u2764\uFE0F\u200D"
    r"\U0001F468[\U0001F3FB-\U0001F3FF]|\U0001F469\U0001F3FE\u200D\u2764\uFE0F\u200D\U0001F469[\U0001F3FB-\U0001F3FF]|"
    r"\U0001F469\U0001F3FE\u200D\U0001F91D\u200D\U0001F468[\U0001F3FB-\U0001F3FD\U0001F3FF]|\U0001F469\U0001F3FE\u200D"
    r"\U0001F91D\u200D\U0001F469[\U0001F3FB-\U0001F3FD\U0001F3FF]|\U0001F469\U0001F3FF\u200D\u2764\uFE0F\u200D\U0001F468["
    r"\U0001F3FB-\U0001F3FF]|\U0001F469\U0001F3FF\u200D\u2764\uFE0F\u200D\U0001F469[\U0001F3FB-\U0001F3FF]|\U0001F469"
    r"\U0001F3FF\u200D\U0001F91D\u200D\U0001F468[\U0001F3FB-\U0001F3FE]|\U0001F469\U0001F3FF\u200D\U0001F91D\u200D"
    r"\U0001F469[\U0001F3FB-\U0001F3FE]|\U0001F9D1\U0001F3FB\u200D\u2764\uFE0F\u200D\U0001F9D1[\U0001F3FC-\U0001F3FF]|"
    r"\U0001F9D1\U0001F3FB\u200D\U0001F91D\u200D\U0001F9D1[\U0001F3FB-\U0001F3FF]|\U0001F9D1\U0001F3FC\u200D\u2764\uFE0F"
    r"\u200D\U0001F9D1[\U0001F3FB\U0001F3FD-\U0001F3FF]|\U0001F9D1\U0001F3FC\u200D\U0001F91D\u200D\U0001F9D1[\U0001F3FB-"
    r"\U0001F3FF]|\U0001F9D1\U0001F3FD\u200D\u2764\uFE0F\u200D\U0001F9D1[\U0001F3FB\U0001F3FC\U0001F3FE\U0001F3FF]|"
    r"\U0001F9D1\U0001F3FD\u200D\U0001F91D\u200D\U0001F9D1[\U0001F3FB-\U0001F3FF]|\U0001F9D1\U0001F3FE\u200D\u2764\uFE0F"
    r"\u200D\U0001F9D1[\U0001F3FB-\U0001F3FD\U0001F3FF]|\U0001F9D1\U0001F3FE\u200D\U0001F91D\u200D\U0001F9D1[\U0001F3FB-"
    r"\U0001F3FF]|\U0001F9D1\U0001F3FF\u200D\u2764\uFE0F\u200D\U0001F9D1[\U0001F3FB-\U0001F3FE]|\U0001F9D1\U0001F3FF\u200D"
    r"\U0001F91D\u200D\U0001F9D1[\U0001F3FB-\U0001F3FF]|\U0001F468\u200D\u2764\uFE0F\u200D\U0001F48B\u200D\U0001F468|"
    r"\U0001F469\u200D\u2764\uFE0F\u200D\U0001F48B\u200D[\U0001F468\U0001F469]|\U0001FAF1\U0001F3FB\u200D\U0001FAF2["
    r"\U0001F3FC-\U0001F3FF]|\U0001FAF1\U0001F3FC\u200D\U0001FAF2[\U0001F3FB\U0001F3FD-\U0001F3FF]|\U0001FAF1\U0001F3FD"
    r"\u200D\U0001FAF2[\U0001F3FB\U0001F3FC\U0001F3FE\U0001F3FF]|\U0001FAF1\U0001F3FE\u200D\U0001FAF2[\U0001F3FB-"
    r"\U0001F3FD\U0001F3FF]|\U0001FAF1\U0001F3FF\u200D\U0001FAF2[\U0001F3FB-\U0001F3FE]|\U0001F468\u200D\u2764\uFE0F\u200D"
    r"\U0001F468|\U0001F469\u200D\u2764\uFE0F\u200D[\U0001F468\U0001F469]|\U0001F9D1\u200D\U0001F91D\u200D\U0001F9D1|"
    r"\U0001F46B[\U0001F3FB-\U0001F3FF]|\U0001F46C[\U0001F3FB-\U0001F3FF]|\U0001F46D[\U0001F3FB-\U0001F3FF]|\U0001F48F["
    r"\U0001F3FB-\U0001F3FF]|\U0001F491[\U0001F3FB-\U0001F3FF]|\U0001F91D[\U0001F3FB-\U0001F3FF]|[\U0001F46B-\U0001F46D"
    r"\U0001F48F\U0001F491]|\U0001F91D)|(?:[\U0001F468\U0001F469]|\U0001F9D1)(?:[\U0001F3FB-\U0001F3FF])?\u200D(?:\u2695"
    r"\uFE0F|\u2696\uFE0F|\u2708\uFE0F|[\U0001F33E\U0001F373\U0001F37C\U0001F384\U0001F393\U0001F3A4\U0001F3A8\U0001F3EB"
    r"\U0001F3ED]|[\U0001F4BB\U0001F4BC\U0001F527\U0001F52C\U0001F680\U0001F692]|[\U0001F9AF-\U0001F9B3\U0001F9BC"
    r"\U0001F9BD])|(?:[\U0001F3CB\U0001F3CC]|[\U0001F574\U0001F575]|\u26F9)((?:[\U0001F3FB-\U0001F3FF]|\uFE0F)\u200D["
    r"\u2640\u2642]\uFE0F)|(?:[\U0001F3C3\U0001F3C4\U0001F3CA]|[\U0001F46E\U0001F470\U0001F471\U0001F473\U0001F477"
    r"\U0001F481\U0001F482\U0001F486\U0001F487\U0001F645-\U0001F647\U0001F64B\U0001F64D\U0001F64E\U0001F6A3\U0001F6B4-"
    r"\U0001F6B6]|[\U0001F926\U0001F935\U0001F937-\U0001F939\U0001F93D\U0001F93E\U0001F9B8\U0001F9B9\U0001F9CD-\U0001F9CF"
    r"\U0001F9D4\U0001F9D6-\U0001F9DD])(?:[\U0001F3FB-\U0001F3FF])?\u200D[\u2640\u2642]\uFE0F|(?:\U0001F468\u200D"
    r"\U0001F468\u200D\U0001F466\u200D\U0001F466|\U0001F468\u200D\U0001F468\u200D\U0001F467\u200D[\U0001F466\U0001F467]|"
    r"\U0001F468\u200D\U0001F469\u200D\U0001F466\u200D\U0001F466|\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D["
    r"\U0001F466\U0001F467]|\U0001F469\u200D\U0001F469\u200D\U0001F466\u200D\U0001F466|\U0001F469\u200D\U0001F469\u200D"
    r"\U0001F467\u200D[\U0001F466\U0001F467]|\U0001F468\u200D\U0001F466\u200D\U0001F466|\U0001F468\u200D\U0001F467\u200D["
    r"\U0001F466\U0001F467]|\U0001F468\u200D\U0001F468\u200D[\U0001F466\U0001F467]|\U0001F468\u200D\U0001F469\u200D["
    r"\U0001F466\U0001F467]|\U0001F469\u200D\U0001F466\u200D\U0001F466|\U0001F469\u200D\U0001F467\u200D[\U0001F466"
    r"\U0001F467]|\U0001F469\u200D\U0001F469\u200D[\U0001F466\U0001F467]|\U0001F3F3\uFE0F\u200D\u26A7\uFE0F|\U0001F3F3"
    r"\uFE0F\u200D\U0001F308|\U0001F636\u200D\U0001F32B\uFE0F|\u2764\uFE0F\u200D\U0001F525|\u2764\uFE0F\u200D\U0001FA79|"
    r"\U0001F3F4\u200D\u2620\uFE0F|\U0001F415\u200D\U0001F9BA|\U0001F43B\u200D\u2744\uFE0F|\U0001F441\u200D\U0001F5E8|"
    r"\U0001F468\u200D[\U0001F466\U0001F467]|\U0001F469\u200D[\U0001F466\U0001F467]|\U0001F46F\u200D\u2640\uFE0F|"
    r"\U0001F46F\u200D\u2642\uFE0F|\U0001F62E\u200D\U0001F4A8|\U0001F635\u200D\U0001F4AB|\U0001F93C\u200D\u2640\uFE0F|"
    r"\U0001F93C\u200D\u2642\uFE0F|\U0001F9DE\u200D\u2640\uFE0F|\U0001F9DE\u200D\u2642\uFE0F|\U0001F9DF\u200D\u2640\uFE0F|"
    r"\U0001F9DF\u200D\u2642\uFE0F|\U0001F408\u200D\u2B1B)|[#*0-9]\uFE0F?\u20E3|(?:[©®\u2122\u265F]\uFE0F)|(?:[\U0001F004"
    r"\U0001F170\U0001F171\U0001F17E\U0001F17F\U0001F202\U0001F21A\U0001F22F\U0001F237\U0001F321\U0001F324-\U0001F32C"
    r"\U0001F336\U0001F37D\U0001F396\U0001F397\U0001F399-\U0001F39B\U0001F39E\U0001F39F\U0001F3CD\U0001F3CE\U0001F3D4-"
    r"\U0001F3DF\U0001F3F3\U0001F3F5\U0001F3F7]|[\U0001F43F\U0001F441\U0001F4FD\U0001F549\U0001F54A\U0001F56F\U0001F570"
    r"\U0001F573\U0001F576-\U0001F579\U0001F587\U0001F58A-\U0001F58D\U0001F5A5\U0001F5A8\U0001F5B1\U0001F5B2\U0001F5BC"
    r"\U0001F5C2-\U0001F5C4\U0001F5D1-\U0001F5D3\U0001F5DC-\U0001F5DE\U0001F5E1\U0001F5E3\U0001F5E8\U0001F5EF\U0001F5F3"
    r"\U0001F5FA\U0001F6CB\U0001F6CD-\U0001F6CF\U0001F6E0-\U0001F6E5\U0001F6E9\U0001F6F0\U0001F6F3]|[\u203C\u2049\u2139"
    r"\u2194-\u2199\u21A9\u21AA\u231A\u231B\u2328\u23CF\u23ED-\u23EF\u23F1\u23F2\u23F8-\u23FA\u24C2\u25AA\u25AB\u25B6"
    r"\u25C0\u25FB-\u25FE\u2600-\u2604\u260E\u2611\u2614\u2615\u2618\u2620\u2622\u2623\u2626\u262A\u262E\u262F\u2638-"
    r"\u263A\u2640\u2642\u2648-\u2653\u2660\u2663\u2665\u2666\u2668\u267B\u267F\u2692-\u2697\u2699\u269B\u269C\u26A0\u26A1"
    r"\u26A7\u26AA\u26AB\u26B0\u26B1\u26BD\u26BE\u26C4\u26C5\u26C8\u26CF\u26D1\u26D3\u26D4\u26E9\u26EA\u26F0-\u26F5\u26F8"
    r"\u26FA\u26FD\u2702\u2708\u2709\u270F\u2712\u2714\u2716\u271D\u2721\u2733\u2734\u2744\u2747\u2757\u2763\u2764\u27A1"
    r"\u2934\u2935\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u3030\u303D\u3297\u3299])(?:\uFE0F|(?!\uFE0E))|(?:(?:[\U0001F3CB"
    r"\U0001F3CC]|[\U0001F574\U0001F575\U0001F590]|[\u261D\u26F7\u26F9\u270C\u270D])(?:\uFE0F|(?!\uFE0E))|(?:[\U0001F385"
    r"\U0001F3C2-\U0001F3C4\U0001F3C7\U0001F3CA]|[\U0001F442\U0001F443\U0001F446-\U0001F450\U0001F466-\U0001F469\U0001F46E"
    r"\U0001F470-\U0001F478\U0001F47C\U0001F481-\U0001F483\U0001F485-\U0001F487\U0001F4AA\U0001F57A\U0001F595\U0001F596"
    r"\U0001F645-\U0001F647\U0001F64B-\U0001F64F\U0001F6A3\U0001F6B4-\U0001F6B6\U0001F6C0\U0001F6CC]|[\U0001F90C\U0001F90F"
    r"\U0001F918-\U0001F91C\U0001F91E\U0001F91F\U0001F926\U0001F930-\U0001F939\U0001F93D\U0001F93E\U0001F977\U0001F9B5"
    r"\U0001F9B6\U0001F9B8\U0001F9B9\U0001F9BB\U0001F9CD-\U0001F9CF\U0001F9D1-\U0001F9DD\U0001FAC3-\U0001FAC5\U0001FAF0-"
    r"\U0001FAF6]|[\u270A\u270B]))(?:[\U0001F3FB-\U0001F3FF])?|(?:\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E"
    r"\U000E0067\U000E007F|\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F|\U0001F3F4\U000E0067"
    r"\U000E0062\U000E0077\U000E006C\U000E0073\U000E007F|\U0001F1E6[\U0001F1E8-\U0001F1EC\U0001F1EE\U0001F1F1\U0001F1F2"
    r"\U0001F1F4\U0001F1F6-\U0001F1FA\U0001F1FC\U0001F1FD\U0001F1FF]|\U0001F1E7[\U0001F1E6\U0001F1E7\U0001F1E9-\U0001F1EF"
    r"\U0001F1F1-\U0001F1F4\U0001F1F6-\U0001F1F9\U0001F1FB\U0001F1FC\U0001F1FE\U0001F1FF]|\U0001F1E8[\U0001F1E6\U0001F1E8"
    r"\U0001F1E9\U0001F1EB-\U0001F1EE\U0001F1F0-\U0001F1F5\U0001F1F7\U0001F1FA-\U0001F1FF]|\U0001F1E9[\U0001F1EA\U0001F1EC"
    r"\U0001F1EF\U0001F1F0\U0001F1F2\U0001F1F4\U0001F1FF]|\U0001F1EA[\U0001F1E6\U0001F1E8\U0001F1EA\U0001F1EC\U0001F1ED"
    r"\U0001F1F7-\U0001F1FA]|\U0001F1EB[\U0001F1EE-\U0001F1F0\U0001F1F2\U0001F1F4\U0001F1F7]|\U0001F1EC[\U0001F1E6"
    r"\U0001F1E7\U0001F1E9-\U0001F1EE\U0001F1F1-\U0001F1F3\U0001F1F5-\U0001F1FA\U0001F1FC\U0001F1FE]|\U0001F1ED[\U0001F1F0"
    r"\U0001F1F2\U0001F1F3\U0001F1F7\U0001F1F9\U0001F1FA]|\U0001F1EE[\U0001F1E8-\U0001F1EA\U0001F1F1-\U0001F1F4\U0001F1F6-"
    r"\U0001F1F9]|\U0001F1EF[\U0001F1EA\U0001F1F2\U0001F1F4\U0001F1F5]|\U0001F1F0[\U0001F1EA\U0001F1EC-\U0001F1EE"
    r"\U0001F1F2\U0001F1F3\U0001F1F5\U0001F1F7\U0001F1FC\U0001F1FE\U0001F1FF]|\U0001F1F1[\U0001F1E6-\U0001F1E8\U0001F1EE"
    r"\U0001F1F0\U0001F1F7-\U0001F1FB\U0001F1FE]|\U0001F1F2[\U0001F1E6\U0001F1E8-\U0001F1ED\U0001F1F0-\U0001F1FF]|"
    r"\U0001F1F3[\U0001F1E6\U0001F1E8\U0001F1EA-\U0001F1EC\U0001F1EE\U0001F1F1\U0001F1F4\U0001F1F5\U0001F1F7\U0001F1FA"
    r"\U0001F1FF]|\U0001F1F4\U0001F1F2|\U0001F1F5[\U0001F1E6\U0001F1EA-\U0001F1ED\U0001F1F0-\U0001F1F3\U0001F1F7-"
    r"\U0001F1F9\U0001F1FC\U0001F1FE]|\U0001F1F6\U0001F1E6|\U0001F1F7[\U0001F1EA\U0001F1F4\U0001F1F8\U0001F1FA\U0001F1FC]|"
    r"\U0001F1F8[\U0001F1E6-\U0001F1EA\U0001F1EC-\U0001F1F4\U0001F1F7-\U0001F1F9\U0001F1FB\U0001F1FD-\U0001F1FF]|"
    r"\U0001F1F9[\U0001F1E6\U0001F1E8\U0001F1E9\U0001F1EB-\U0001F1ED\U0001F1EF-\U0001F1F4\U0001F1F7\U0001F1F9\U0001F1FB"
    r"\U0001F1FC\U0001F1FF]|\U0001F1FA[\U0001F1E6\U0001F1EC\U0001F1F2\U0001F1F3\U0001F1F8\U0001F1FE\U0001F1FF]|\U0001F1FB["
    r"\U0001F1E6\U0001F1E8\U0001F1EA\U0001F1EC\U0001F1EE\U0001F1F3\U0001F1FA]|\U0001F1FC[\U0001F1EB\U0001F1F8]|\U0001F1FD"
    r"\U0001F1F0|\U0001F1FE[\U0001F1EA\U0001F1F9]|\U0001F1FF[\U0001F1E6\U0001F1F2\U0001F1FC]|[\U0001F0CF\U0001F18E"
    r"\U0001F191-\U0001F19A\U0001F1E6-\U0001F1FF\U0001F201\U0001F232-\U0001F236\U0001F238-\U0001F23A\U0001F250\U0001F251"
    r"\U0001F300-\U0001F320\U0001F32D-\U0001F335\U0001F337-\U0001F37C\U0001F37E-\U0001F384\U0001F386-\U0001F393\U0001F3A0-"
    r"\U0001F3C1\U0001F3C5\U0001F3C6\U0001F3C8\U0001F3C9\U0001F3CF-\U0001F3D3\U0001F3E0-\U0001F3F0\U0001F3F4\U0001F3F8-"
    r"\U0001F3FF]|[\U0001F400-\U0001F43E\U0001F440\U0001F444\U0001F445\U0001F451-\U0001F465\U0001F46A\U0001F46F\U0001F479-"
    r"\U0001F47B\U0001F47D-\U0001F480\U0001F484\U0001F488-\U0001F48E\U0001F490\U0001F492-\U0001F4A9\U0001F4AB-\U0001F4FC"
    r"\U0001F4FF-\U0001F53D\U0001F54B-\U0001F54E\U0001F550-\U0001F567\U0001F5A4\U0001F5FB-\U0001F644\U0001F648-\U0001F64A"
    r"\U0001F680-\U0001F6A2\U0001F6A4-\U0001F6B3\U0001F6B7-\U0001F6BF\U0001F6C1-\U0001F6C5\U0001F6D0-\U0001F6D2\U0001F6D5-"
    r"\U0001F6D7\U0001F6DD-\U0001F6DF\U0001F6EB\U0001F6EC\U0001F6F4-\U0001F6FC\U0001F7E0-\U0001F7EB\U0001F7F0]|[\U0001F90D"
    r"\U0001F90E\U0001F910-\U0001F917\U0001F920-\U0001F925\U0001F927-\U0001F92F\U0001F93A\U0001F93C\U0001F93F-\U0001F945"
    r"\U0001F947-\U0001F976\U0001F978-\U0001F9B4\U0001F9B7\U0001F9BA\U0001F9BC-\U0001F9CC\U0001F9D0\U0001F9DE-\U0001F9FF"
    r"\U0001FA70-\U0001FA74\U0001FA78-\U0001FA7C\U0001FA80-\U0001FA86\U0001FA90-\U0001FAAC\U0001FAB0-\U0001FABA\U0001FAC0-"
    r"\U0001FAC2\U0001FAD0-\U0001FAD9\U0001FAE0-\U0001FAE7]|[\u23E9-\u23EC\u23F0\u23F3\u267E\u26CE\u2705\u2728\u274C\u274E"
    r"\u2753-\u2755\u2795-\u2797\u27B0\u27BF\uE50A])|\uFE0F"
)
