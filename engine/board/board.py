"""Review board: board.html, board-inline.html and contact.png for a postkitty job.

Uses the standard library and Pillow. The stylesheet, the page script and the logo mark live in
templates/. Every value that comes from the manifest goes through ``esc`` before it reaches the page.
"""

from __future__ import annotations

import base64
import html
import io
import mimetypes
import os
import re
from datetime import datetime
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .. import platforms
from ..text.fit import unit_words

CREAM = "#F7F1E5"
NAVY = "#1E2A44"
MUTED = "#5B6478"
BORDER = "#D9CFA9"
SURFACE = "#FFFFFF"

STATUS_COLORS = {
    "ready": "#14532d",
    "repaired": "#92400e",
    "advisory": "#715711",
    "failed": "#7f1d1d",
    "skipped": "#5B6478",
}
STATUS_LABELS = {
    "ready": "Ready",
    "repaired": "Repaired",
    "advisory": "Advisory",
    "failed": "Failed",
    "skipped": "Skipped",
}

PLATFORM_NAMES = {
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "x": "X",
    "linkedin": "LinkedIn",
    "threads": "Threads",
    "bluesky": "Bluesky",
    "facebook": "Facebook",
}
PLATFORM_COPY_NAMES = {**PLATFORM_NAMES, "youtube": "YouTube Shorts"}

# Where each platform cuts a post behind a "more" link. Approximate. A
# manifest copy entry may carry its own "fold" to override these.
FOLD_AT = {"instagram": 125, "linkedin": 210, "tiktok": 150, "facebook": 480}

SOURCE_NAMES = (
    ("postman.com/meta", "Meta"),
    ("github.com/bluesky-social", "Bluesky"),
    ("help.x.com", "X"),
    ("developer.x.com", "X"),
    ("developers.google.com", "Google"),
    ("support.google.com", "Google"),
    ("tiktok.com", "TikTok"),
    ("linkedin.com", "LinkedIn"),
)

PASS_TEXT = {
    "video.container": "The container format is supported.",
    "video.codec": "The video codec is supported.",
    "video.profile": "The H.264 profile is supported.",
    "video.pix_fmt": "The pixel format is supported.",
    "video.width": "The width is exact.",
    "video.height": "The height is exact.",
    "video.fps": "The frame rate is within limits.",
    "video.duration": "The length is within limits.",
    "video.bytes": "The file size is within limits.",
    "video.bitrate": "The video bitrate is within the limit.",
    "audio.sample_rate": "The audio sample rate is exact.",
    "audio.bitrate": "The audio bitrate is within the limit.",
    "frame.subjects_inside": "Everyone stays inside the frame.",
    "image.width": "The width is exact.",
    "image.height": "The height is exact.",
    "image.aspect": "The aspect ratio is exact.",
    "image.format": "The image format is supported.",
    "image.metadata_stripped": "Image metadata is stripped.",
    "image.upscale": "The source is large enough for this size.",
    "image.bytes": "The file size is within the limit.",
}

ICONS = {
    "ready": '<path d="M2.5 6.5l2.4 2.4 4.6-5.3" fill="none" stroke="currentColor" '
             'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "repaired": '<path d="M7.5 2.2a2.6 2.6 0 0 0-2.4 3.5L2 8.8l1.3 1.3 3.1-3.1a2.6 2.6 0 0 0 '
                '3.5-2.4l-1.5 1.5-1.2-.3-.3-1.2z" fill="currentColor"/>',
    "advisory": '<path d="M6 2.2l4.2 7.6H1.8z" fill="none" stroke="currentColor" stroke-width="1.5" '
                'stroke-linejoin="round"/><path d="M6 5.4v2" stroke="currentColor" stroke-width="1.5" '
                'stroke-linecap="round"/>',
    "failed": '<path d="M3 3l6 6M9 3l-6 6" fill="none" stroke="currentColor" stroke-width="1.8" '
              'stroke-linecap="round"/>',
    "skipped": '<path d="M2.5 6h7" fill="none" stroke="currentColor" stroke-width="1.8" '
               'stroke-linecap="round"/>',
}

PLAY_SVG = (
    '<svg class="play" viewBox="0 0 32 32" aria-hidden="true">'
    '<circle cx="16" cy="16" r="15" fill="#1E2A44" opacity="0.82"/>'
    '<path d="M12.5 10.5l9 5.5-9 5.5z" fill="#F7F1E5"/></svg>'
)

HTML_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
"""

INLINE_CAP = 6 * 1024 * 1024
TEMPLATES = Path(__file__).resolve().parent / "templates"


@cache
def _template(name: str) -> str:
    """A file from templates/: the stylesheet, the page script or the logo mark."""
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _mark() -> str:
    return f'<div class="pucci-mark">{_template("mark.svg").strip()}</div>'


def esc(value: Any) -> str:
    """Escape a manifest value for HTML text or a quoted attribute."""
    return html.escape(str(value), quote=True)


def platform_name(platform: str) -> str:
    return PLATFORM_NAMES.get(platform, str(platform).replace("_", " ").title())


def target_label(target: dict) -> str:
    platform = str(target.get("platform") or "")
    tid = str(target.get("id") or "")
    suffix = tid[len(platform) + 1:] if tid.startswith(platform + "_") else ""
    name = platform_name(platform)
    if suffix:
        return f"{name} · {suffix.replace('_', ' ').title()}"
    return name


def clock(seconds: Any) -> str:
    """m:ss for durations on the cards and in the check lines."""
    try:
        total = int(round(max(0.0, float(seconds))))
    except (TypeError, ValueError):
        return ""
    return f"{total // 60}:{total % 60:02d}"


def fmt_num(value: float, places: int = 1) -> str:
    text = f"{value:.{places}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def fmt_bytes(value: Any) -> str:
    n = float(value)
    if n >= 1e9:
        return f"{fmt_num(n / 1e9, 2)} GB"
    if n >= 1e6:
        return f"{fmt_num(n / 1e6)} MB"
    if n >= 1e3:
        return f"{fmt_num(n / 1e3, 0)} KB"
    return f"{int(n)} B"


def fmt_bitrate(value: Any) -> str:
    n = float(value)
    if n >= 1e6:
        return f"{fmt_num(n / 1e6)} Mbps"
    return f"{fmt_num(n / 1e3, 0)} kbps"


def fmt_ratio(value: float) -> str:
    frac = Fraction(value).limit_denominator(20)
    if abs(float(frac) - value) < 0.005 and frac.numerator > 0:
        return f"{frac.numerator}:{frac.denominator}"
    return fmt_num(value, 2)


def check_stem(check_id: str) -> str:
    for suffix in ("_min", "_max"):
        if check_id.endswith(suffix):
            return check_id[: -len(suffix)]
    return check_id


def fmt_value(stem: str, value: Any) -> str:
    """Human text for one measured or expected value of a check."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        return ", ".join(fmt_value(stem, v) for v in value)
    if isinstance(value, dict):
        if {"width", "height"} <= set(value):
            return f"{value['width']} × {value['height']}"
        return ", ".join(f"{k} {fmt_value(stem, v)}" for k, v in value.items())
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        if stem.endswith("bytes"):
            return fmt_bytes(value)
        if stem.endswith("bitrate"):
            return fmt_bitrate(value)
        if stem.endswith("duration"):
            return clock(value)
        if stem.endswith("fps"):
            return f"{fmt_num(float(value))} fps"
        if stem.endswith((".width", ".height")):
            return f"{fmt_num(float(value), 0)} px"
        if stem.endswith("sample_rate"):
            return f"{fmt_num(float(value) / 1000, 1)} kHz"
        if stem.endswith("aspect"):
            return fmt_ratio(float(value))
        if stem.endswith("subjects_inside"):
            return f"{fmt_num(float(value) * 100, 0)}%"
        return fmt_num(float(value), 2)
    return str(value)


def merge_checks(checks: list[dict]) -> list[dict]:
    """Fold fooX_min and fooX_max into one row with a "low to high" limit."""
    rows: list[dict] = []
    by_stem: dict[str, dict] = {}
    for check in checks:
        cid = str(check.get("id") or "")
        stem = check_stem(cid)
        side = "min" if cid.endswith("_min") else "max" if cid.endswith("_max") else "exact"
        row = by_stem.get(stem) if side != "exact" else None
        if row is None:
            row = {"stem": stem, "ids": [], "status": "pass", "hard": False,
                   "measured": check.get("measured"), "limits": {}, "message": "",
                   "bad_messages": [], "source_url": None, "checked_on": None,
                   "exact": side == "exact", "expected": check.get("expected")}
            rows.append(row)
            if side != "exact":
                by_stem[stem] = row
        row["ids"].append(cid)
        if side in ("min", "max"):
            row["limits"][side] = check.get("expected")
        status = check.get("status") or "pass"
        if status == "fail" or (status in ("advisory", "skipped") and row["status"] == "pass"):
            row["status"] = status
        if status != "pass" and check.get("message"):
            row["bad_messages"].append(str(check["message"]))
        row["hard"] = row["hard"] or bool(check.get("hard"))
        if check.get("message") and not row["message"]:
            row["message"] = str(check["message"])
        if check.get("source_url") and not row["source_url"]:
            row["source_url"] = check["source_url"]
            row["checked_on"] = check.get("checked_on")
    return rows


def limit_text(row: dict) -> str:
    stem = row["stem"]
    if row["exact"]:
        expected = row["expected"]
        if isinstance(expected, (list, tuple)):
            return "allowed " + fmt_value(stem, expected)
        if stem.endswith("metadata_stripped"):
            return ""
        return "required " + fmt_value(stem, expected)
    lo, hi = row["limits"].get("min"), row["limits"].get("max")
    if lo is not None and hi is not None:
        low, high = fmt_value(stem, lo), fmt_value(stem, hi)
        if " " in low and low.rsplit(" ", 1)[1] == high.rsplit(" ", 1)[-1]:
            low = low.rsplit(" ", 1)[0]
        return f"limit {low} to {high}"
    if hi is not None:
        return f"limit up to {fmt_value(stem, hi)}"
    if lo is not None:
        return f"limit at least {fmt_value(stem, lo)}"
    return ""


def source_label(url: str) -> str:
    for needle, name in SOURCE_NAMES:
        if needle in url:
            return name
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    return host or "source"


def long_date(value: Any) -> str:
    text = str(value or "")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return text
    return f"{stamp.day} {stamp:%b %Y}"


def job_stamp(value: Any) -> str:
    text = str(value or "")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return text
    return f"{stamp.day} {stamp:%b %Y}, {stamp:%H:%M}"


def pill(status: str) -> str:
    key = status if status in ICONS else "skipped"
    return (
        f'<span class="pill {esc(key)}">'
        f'<svg viewBox="0 0 12 12" aria-hidden="true">{ICONS[key]}</svg>'
        f'{esc(STATUS_LABELS.get(status, str(status).title()))}</span>'
    )


@cache
def _safe_area_bands(target_id: str) -> str:
    try:
        spec = platforms.get_target(target_id).limits.get("safe_area")
    except KeyError:
        return ""
    area = getattr(spec, "value", spec) or {}
    # A safe area gives one inset for both sides, or a left and a right one where the buttons sit on one side.
    edges = {edge: area.get(edge, area.get("side") if edge in ("left", "right") else 0) or 0
             for edge in ("top", "bottom", "left", "right")}
    if not any(edges.values()):
        return ""
    style = " ".join(f"--{edge}: {float(inset) * 100:.2f}%;" for edge, inset in edges.items())
    return f'<div class="safe" style="{style}"><i class="t"></i><i class="b"></i><i class="l"></i><i class="r"></i></div>'


def safe_area_bands(target: dict) -> str:
    """Bands over the parts of the frame where the platform draws its own buttons and text."""
    return _safe_area_bands(str(target.get("id") or ""))


def _upright(image: Image.Image) -> Image.Image:
    """Apply the EXIF rotation; an image with broken EXIF is shown as stored."""
    try:
        return ImageOps.exif_transpose(image)
    except Exception:
        return image


def image_data_uri_capped(path: Any, cache: dict, max_side: int, quality: int) -> str:
    if not path:
        return ""
    key = ("inline", str(path), max_side, quality)
    if key in cache:
        return cache[key]
    full = Path(path)
    if not full.is_file():
        return ""
    mime, _ = mimetypes.guess_type(str(full))
    if not (mime or "").startswith("image/"):
        return ""
    try:
        with Image.open(full) as image:
            image = _upright(image)
            image = image.convert("RGB")
            image.thumbnail((max_side, max_side), Image.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
        result = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return ""
    cache[key] = result
    return result


class Ctx:
    """Everything one render pass needs."""

    def __init__(self, job_dir: Path, manifest: dict, inline: bool, cache: dict,
                 max_side: int = 720, quality: int = 80, drop_dupes: bool = False,
                 drop_all_posters: bool = False) -> None:
        self.job_dir = job_dir
        self.manifest = manifest
        self.inline = inline
        self.cache = cache
        self.max_side = max_side
        self.quality = quality
        self.drop_dupes = drop_dupes
        self.drop_all_posters = drop_all_posters
        self.seen_posters: set[str] = set()
        self.inputs = {str(i.get("id")): i for i in manifest.get("inputs") or []
                       if isinstance(i, dict)}
        self.alt_texts = manifest.get("alt_text") or {}
        self.job_id = str(manifest.get("job") or "job")


def target_dims(target: dict) -> tuple[int, int]:
    try:
        width, height = int(target.get("width") or 0), int(target.get("height") or 0)
    except (TypeError, ValueError):
        width = height = 0
    return (width, height) if width > 0 and height > 0 else (16, 9)


def media_html(target: dict, ctx: Ctx, alt: str, overlay: str = "") -> str:
    """One media frame with the target's exact aspect; previews are never cropped."""
    width, height = target_dims(target)
    kind = target.get("kind")
    file_rel = target.get("file") or ""
    cover_rel = target.get("cover")
    style = f"--ar: {width} / {height}; --ar-n: {width / height:.5f}"
    label = target_label(target)
    if kind == "video" and file_rel:
        if ctx.inline:
            poster = ""
            dupe = cover_rel in ctx.seen_posters
            if cover_rel and not ctx.drop_all_posters and not (ctx.drop_dupes and dupe):
                poster = image_data_uri_capped(ctx.job_dir / cover_rel, ctx.cache,
                                               ctx.max_side, ctx.quality)
            if cover_rel:
                ctx.seen_posters.add(cover_rel)
            img = (f'<img src="{esc(poster)}" width="{width}" height="{height}" '
                   f'alt="Poster frame, {esc(label)}">' if poster else "")
            return f'<div class="frame video" style="{style}">{img}{PLAY_SVG}{overlay}</div>'
        mime = mimetypes.guess_type(file_rel)[0] or "video/mp4"
        poster_attr = f' poster="{esc(cover_rel)}"' if cover_rel else ""
        return (
            f'<div class="frame video" style="{style}">'
            f'<video controls muted playsinline preload="metadata"{poster_attr} '
            f'aria-label="{esc(label)} video">'
            f'<source src="{esc(file_rel)}" type="{esc(mime)}"></video>{overlay}</div>'
        )
    if kind == "image" and file_rel and (ctx.job_dir / file_rel).is_file():
        src = (image_data_uri_capped(ctx.job_dir / file_rel, ctx.cache, ctx.max_side,
                                     ctx.quality) if ctx.inline else file_rel)
        if not src:
            return f'<div class="frame" style="{style}">{overlay}</div>'
        return (
            f'<div class="frame image" style="{style}">'
            f'<img src="{esc(src)}" width="{width}" height="{height}" '
            f'alt="{esc(alt or "Preview, " + label)}" loading="lazy">{overlay}</div>'
        )
    return f'<div class="frame" style="{style}">{overlay}</div>'


def file_size(target: dict, ctx: Ctx) -> int | None:
    rel = target.get("file")
    if rel:
        try:
            return (ctx.job_dir / rel).stat().st_size
        except OSError:
            pass
    for check in target.get("checks") or []:
        if str(check.get("id", "")).endswith("bytes_max") and isinstance(
                check.get("measured"), (int, float)):
            return int(check["measured"])
    return None


def spec_line(target: dict, ctx: Ctx) -> str:
    bits = []
    if target.get("width") and target.get("height"):
        bits.append(f"{target['width']} × {target['height']}")
    if target.get("kind") == "video" and target.get("duration"):
        bits.append(clock(target["duration"]))
    size = file_size(target, ctx)
    if size:
        bits.append(fmt_bytes(size))
    return " · ".join(bits)


def effective_status(target: dict) -> str:
    status = str(target.get("status") or "unknown")
    checks = target.get("checks") or []
    if any(c.get("hard") and c.get("status") == "fail" for c in checks):
        return "failed"
    if status == "ready" and any(c.get("status") == "advisory" for c in checks):
        return "advisory"
    return status


def check_row_html(row: dict) -> str:
    stem = row["stem"]
    text = (" ".join(row["bad_messages"]) if row["status"] != "pass"
            else PASS_TEXT.get(stem) or row["message"])
    mono = []
    measured = row["measured"]
    if measured is not None and not isinstance(measured, bool):
        mono.append(esc("measured " + fmt_value(stem, measured)))
    limit = limit_text(row)
    if limit:
        mono.append(esc(limit))
    if row["source_url"]:
        when = f", checked {long_date(row['checked_on'])}" if row["checked_on"] else ""
        mono.append(
            f'source (<a href="{esc(row["source_url"])}" rel="noopener">'
            f'{esc(source_label(str(row["source_url"])))}</a>{esc(when)})'
        )
    mono_html = f'<div class="mono">{" · ".join(mono)}</div>' if mono else ""
    return (
        f'<li title="{esc(", ".join(row["ids"]))}">'
        f'<span class="dot {esc(row["status"])}"></span>'
        f'<div><div class="msg">{esc(text)}</div>{mono_html}</div></li>'
    )


def checks_html(checks: list[dict]) -> str:
    rows = merge_checks(checks)
    if not rows:
        return ""
    bad = [r for r in rows if r["status"] not in ("pass", "skipped")]
    skipped = sum(1 for r in rows if r["status"] == "skipped")
    passed = len(rows) - len(bad) - skipped
    hard_fail = any(r["hard"] and r["status"] == "fail" for r in rows)
    if bad:
        head = f"{len(bad)} need attention" if len(bad) > 1 else "1 needs attention"
        if passed:
            head += f", {passed} passed"
    else:
        head = f"{passed} checks passed" if passed != 1 else "1 check passed"
    if skipped:
        head += f", {skipped} skipped"
    attn = ' class="attn"' if bad else ""
    return (
        f'<details class="checks"{" open" if hard_fail else ""}>'
        f'<summary{attn}>{esc(head)}</summary>'
        f'<ul class="check-list">{"".join(check_row_html(r) for r in rows)}</ul></details>'
    )


def adjust_request(ctx: Ctx, target: dict, request: str, setting: str) -> str:
    """The sentence a reader sends to change one file: plain words, then the exact setting in brackets."""
    return f"In job {ctx.job_id}, change {target.get('id', '')}: {request} ({setting})."


def adjust_html(target: dict, ctx: Ctx) -> str:
    width, height = target_dims(target)
    mode = (target.get("layout") or {}).get("mode")
    people = int((ctx.inputs.get(str(target.get("input"))) or {}).get("people") or 0)
    options: list[tuple[str, str, str]] = []
    if people > 1:
        for n in range(1, min(people, 8) + 1):
            options.append((f"Focus person {n}", f"focus on person {n}", f"focus person:{n}"))
    if people == 2 and height > width and mode != "split":
        options.append(("Split screen", "stack the two people in a split screen", "layout split"))
    if mode != "pad":
        options.append(("Fit whole frame", "keep the whole frame", "layout pad"))
    trim = target.get("trim")
    if target.get("kind") == "video" and isinstance(trim, (list, tuple)) and len(trim) == 2:
        start, end = float(trim[0]), float(trim[1])
        options.append(("Trim", f"cut it to another part, now {start:g} s to {end:g} s", f"trim {start}, {end}"))
    if not options:
        return ""
    buttons = ""
    for label, request, setting in options:
        sentence = esc(adjust_request(ctx, target, request, setting))
        buttons += (f'<button type="button" class="btn tiny" title="{sentence}" '
                    f'data-hermes-send="{sentence}">{esc(label)}</button>')
    return (f'<details class="adjust"><summary>Adjust</summary>'
            f'<div class="adjust-menu">{buttons}</div></details>')


LAYOUT_NAMES = {"split": "Split screen", "speaker": "Follows the speaker",
                "pad": "Whole frame", "crop": "Cropped", "seam": "Seam squeeze"}


def layout_note(layout: dict) -> str:
    note = str(layout.get("note") or "").strip()
    name = LAYOUT_NAMES.get(str(layout.get("mode") or ""), "")
    if not note:
        return ""
    if name and not note.lower().startswith(name.lower().split()[0]):
        text = f"{name}: {note}"
    else:
        text = note
    return text if text.endswith(".") else text + "."


def repairs_html(repairs: list[dict]) -> str:
    if not repairs:
        return ""
    lines = []
    for repair in repairs:
        action = str(repair.get("action", "")).strip()
        check = str(repair.get("check", "")).strip()
        text = action[:1].upper() + action[1:] if action else "Repaired"
        if check:
            text += f" ({check})"
        text += "." if repair.get("ok") else ", not resolved."
        lines.append(f"<li>{esc(text)}</li>")
    return f'<ul class="repairs">{"".join(lines)}</ul>'


def build_card(target: dict, ctx: Ctx) -> str:
    checks = target.get("checks") or []
    status = effective_status(target)
    file_rel = target.get("file") or ""
    alt = (ctx.alt_texts.get(target.get("id"))
           or ctx.alt_texts.get(os.path.basename(file_rel)) or "")

    hard = [c for c in checks if c.get("hard") and c.get("status") == "fail"]
    banner = ""
    if hard:
        banner = ('<div class="banner" role="alert">'
                  + esc(" ".join(str(c.get("message", "")) for c in hard)) + "</div>")

    bands = safe_area_bands(target)
    toggle = ('<button type="button" class="btn tiny safe-toggle" data-toggle-safe-area>'
              'Show safe area</button>' if bands else "")
    note = layout_note(target.get("layout") or {})
    note_html = f'<p class="note">{esc(note)}</p>' if note else ""
    reason = str(target.get("reason") or "").strip()
    reason_html = f'<p class="note">{esc(reason)}</p>' if reason else ""
    alt_html = f'<p class="alt"><b>Alt text</b> {esc(alt)}</p>' if alt else ""
    actions = []
    if file_rel:
        actions.append(f'<a class="btn" href="{esc(file_rel)}">Open</a>')
    actions.append(adjust_html(target, ctx))
    actions.append('<span class="hermes-status" role="status"></span>')

    return (
        '<article class="card">'
        f'<div class="plabel">{esc(target_label(target))}</div>'
        '<div class="body">'
        f'<div class="stage">{toggle}{media_html(target, ctx, alt, bands)}</div>'
        '<div class="info">'
        f'{banner}'
        f'<div class="specs"><span class="dims">{esc(spec_line(target, ctx))}</span>{pill(status)}</div>'
        f'{note_html}{reason_html}{repairs_html(target.get("repairs") or [])}{alt_html}{checks_html(checks)}'
        f'<div class="actions">{"".join(actions)}</div>'
        '</div></div></article>'
    )


def status_tally(targets: list[dict]) -> dict[str, int]:
    tally = {"ready": 0, "repaired": 0, "advisory": 0, "failed": 0}
    for target in targets:
        status = effective_status(target)
        if status in tally:
            tally[status] += 1
    return tally


def board_title(manifest: dict) -> str:
    advice = manifest.get("advice") or {}
    topic = str(advice.get("topic") or "").strip()
    if topic:
        return topic
    names = []
    for item in manifest.get("inputs") or []:
        name = os.path.basename(str(item.get("path") or "")) if isinstance(item, dict) else ""
        if name:
            names.append(name)
    return " + ".join(names) or str(manifest.get("job") or "Review board")


def build_header(ctx: Ctx) -> str:
    manifest = ctx.manifest
    targets = manifest.get("targets") or []
    tally = status_tally(targets)
    files = sum(1 for t in targets if t.get("file"))
    meta = [job_stamp(manifest.get("created")), f"{files} file{'s' if files != 1 else ''}",
            f"job {manifest.get('job', '')}"]
    meta_text = " · ".join(m for m in meta if m.strip())
    chips = []
    for key, label in (("ready", "ready"), ("repaired", "repaired"),
                       ("advisory", "advisory"), ("failed", "failed")):
        count = tally[key]
        cls = "zero" if count == 0 else "bad" if key == "failed" else "ok" if key == "ready" else ""
        chips.append(f'<div class="chip {cls}"><span class="num">{count}</span>'
                     f'<span class="lbl">{label}</span></div>')
    path = str(ctx.job_dir.resolve())
    return (
        '<header class="header"><div class="wrap">'
        f'{_mark()}'
        '<div class="title-group">'
        f'<h1>{esc(board_title(manifest))}</h1>'
        f'<p class="meta">{esc(meta_text)}</p>'
        f'<div class="path-chip"><code>{esc(path)}</code>'
        f'<button type="button" class="btn tiny" data-copy-text="{esc(path)}">Copy</button></div>'
        '</div>'
        f'<div class="chips" role="group" aria-label="Summary">{"".join(chips)}</div>'
        '</div></header>'
    )


def build_advice(manifest: dict) -> str:
    advice = manifest.get("advice") or {}
    if not advice:
        return ""
    topic = str(advice.get("topic") or "").strip()
    facts = []
    for key, label in (("audience", "Audience"), ("tone", "Tone")):
        if advice.get(key):
            facts.append(f"<dt>{label}</dt><dd>{esc(advice[key])}</dd>")
    about = ['<div class="about"><h3 class="eyebrow">About this post</h3>']
    if topic:
        about.append(f'<p class="topic">{esc(topic)}</p>')
    if facts:
        about.append(f'<dl class="facts">{"".join(facts)}</dl>')
    if advice.get("key_message"):
        about.append(f'<blockquote class="quote">{esc(advice["key_message"])}</blockquote>')
    about.append("</div>")

    ranking = [r for r in advice.get("ranking") or [] if isinstance(r, dict)]
    where = ""
    if ranking:
        items = "".join(
            f'<li><div><strong>{esc(platform_name(str(r.get("platform") or "")))}</strong>'
            f'<span>{esc(r.get("reason") or "")}</span></div></li>'
            for r in ranking
        )
        where = (f'<div class="where"><h3 class="eyebrow">Where it fits</h3>'
                 f'<ol class="rank">{items}</ol></div>')
    tips = [str(t) for t in advice.get("tips") or [] if str(t).strip()]
    tips_html = ""
    if tips:
        tips_html = ('<div class="tips"><h3 class="eyebrow">Tips</h3><ul>'
                     + "".join(f"<li>{esc(t)}</li>" for t in tips) + "</ul></div>")
    return (f'<section class="section" aria-label="Advice"><div class="advice">'
            f'{"".join(about)}{where}{tips_html}</div></section>')


def split_at_fold(text: str, fold: int) -> tuple[str, str]:
    if fold <= 0 or len(text) <= fold:
        return text, ""
    cut = text[:fold]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut, text[len(cut):].lstrip(" ")


def unit_name(unit: str) -> str:
    """The counting unit in the text engine's words; a unit it does not know is shown as it is."""
    try:
        return unit_words(unit)
    except KeyError:
        return unit


def count_line(count: Any, limit: Any, unit: str) -> str:
    name = unit_name(unit)
    if limit is None:
        return f"{count} {name}"
    return f"{count} of {limit} {name}"


def build_copy_card(platform: str, info: dict, ctx: Ctx) -> str:
    parts = [str(p) for p in info.get("parts") or []]
    if not parts:
        return ""
    counts = info.get("counts") or []
    limit = info.get("limit")
    unit = str(info.get("unit") or "")
    ok = info.get("ok") is not False
    fold = info.get("fold") if isinstance(info.get("fold"), int) else FOLD_AT.get(platform)
    rendered = []
    for index, text in enumerate(parts):
        head, tail = split_at_fold(text, fold or 0) if index == 0 else (text, "")
        body = esc(head)
        if tail:
            body += f'<span class="more"></span><span class="tail">{esc(tail)}</span>'
        count = counts[index] if index < len(counts) else len(text)
        part_head = ""
        if len(parts) > 1:
            part_head = (f'<div class="part-head"><span>Part {index + 1} of {len(parts)}</span>'
                         f'<span>{esc(count_line(count, limit, unit))}</span></div>')
        rendered.append(f'<div class="part">{part_head}<p class="text-part">{body}</p></div>')
    total = max((int(c) for c in counts if isinstance(c, (int, float))), default=0)
    over = not ok or (isinstance(limit, (int, float)) and total > limit)
    if len(parts) > 1:
        summary = f"{len(parts)} parts, limit {limit} {unit_name(unit)} each" \
            if limit is not None else f"{len(parts)} parts"
    else:
        summary = count_line(total, limit, unit)
    meter = ""
    if isinstance(limit, (int, float)) and limit > 0:
        pct = min(100.0, 100.0 * total / limit)
        meter = f'<div class="meter{" over" if over else ""}"><i style="width:{pct:.1f}%"></i></div>'
    joined = "\n\n".join(parts)
    tags = len(re.findall(r"(?<!\w)#\w+", joined))
    mentions = len(re.findall(r"(?<!\w)@\w+", joined))
    tag_line = (f'{tags} hashtag{"" if tags == 1 else "s"} · '
                f'{mentions} mention{"" if mentions == 1 else "s"}')
    fold_note = ""
    if fold and any(len(p) > fold for p in parts[:1]):
        fold_note = f" · cut after about {fold} characters"
    links = ""
    post = f"ready/{platform}/post.txt"
    if (ctx.job_dir / post).is_file():
        links = f' <a href="{esc(post)}">post.txt</a>'
    return (
        '<article class="copy-card">'
        f'<div class="copy-head"><h3>{esc(PLATFORM_COPY_NAMES.get(platform, platform_name(platform)))}</h3>'
        f'<span class="counts{" over" if over else ""}">{esc(summary)}</span></div>'
        f'{meter}<div class="parts">{"".join(rendered)}</div>'
        f'<p class="tags">{esc(tag_line + fold_note)}{links}</p>'
        f'<button type="button" class="btn primary" data-copy-text="{esc(joined)}">Copy text</button>'
        '</article>'
    )


def build_copy(ctx: Ctx) -> str:
    copy = ctx.manifest.get("copy") or {}
    order = []
    for target in ctx.manifest.get("targets") or []:
        platform = target.get("platform")
        if platform in copy and platform not in order:
            order.append(platform)
    order += [p for p in copy if p not in order]
    cards = [build_copy_card(p, copy[p], ctx) for p in order if isinstance(copy[p], dict)]
    cards = [c for c in cards if c]
    if not cards:
        return ""
    return ('<section class="section" aria-label="Copy"><h2>Copy</h2>'
            f'<div class="copy-grid">{"".join(cards)}</div></section>')


def build_files(ctx: Ctx) -> str:
    targets = ctx.manifest.get("targets") or []
    if not targets:
        return '<section class="section"><p>No targets yet.</p></section>'
    cards = "".join(build_card(t, ctx) for t in targets)
    return (f'<section class="section" aria-label="Files"><h2>Files '
            f'<small>{len(targets)} targets</small></h2><div class="grid">{cards}</div></section>')


def build_footer(ctx: Ctx) -> str:
    links = []
    for name in ("manifest.json", "contact.png", "advice.md"):
        if name == "contact.png" or (ctx.job_dir / name).is_file():
            links.append(f'<a href="{name}">{name}</a>')
    return (
        '<footer class="footer"><div class="wrap">'
        f'{_mark()}'
        '<span>Made with postkitty</span>'
        f'<nav aria-label="Job files">{"".join(links)}</nav>'
        '</div></footer>'
    )


def render_page(ctx: Ctx) -> tuple[str, int]:
    title = esc(board_title(ctx.manifest)) + " - postkitty review board"
    if ctx.inline:
        title += " (inline)"
    body = [
        HTML_HEAD.format(title=title, css=_template("board.css")),
        build_header(ctx),
        "<main><div class=\"wrap\">",
        build_advice(ctx.manifest),
        build_files(ctx),
        build_copy(ctx),
        "</div></main>",
        build_footer(ctx),
        f'<script>\n{_template("board.js")}</script>\n',
        "\n</body>\n</html>",
    ]
    text = "".join(body)
    return text, len(text.encode("utf-8"))


def _aspect(target: dict) -> float:
    """Width over height of a target; 1.0 when the manifest has no usable size."""
    try:
        return int(target.get("width") or 0) / int(target.get("height") or 1) or 1.0
    except (TypeError, ValueError, ZeroDivisionError):
        return 1.0


def write_contact_png(job_dir: Path, manifest: dict, mark_path: Path) -> Path:
    """Draw contact.png: one tile per target with its thumbnail, size and status."""
    targets = manifest.get("targets") or []
    width, gap, margin, title_h, mark_size = 1600, 24, 40, 120, 40
    cols = 3 if targets else 1
    tile_w = (width - 2 * margin - (cols - 1) * gap) // cols

    def thumb_box(aspect: float) -> tuple[int, int]:
        # A landscape target gets a wide box, a portrait one a tall box.
        height = min(240, (tile_w - 28) / aspect)
        return int(height * aspect), int(height)

    rows = [targets[index:index + cols] for index in range(0, len(targets), cols)]
    # Under each thumbnail: the platform, the target id, the size and the status badge, with 14 px of padding.
    row_heights = [max(thumb_box(_aspect(target))[1] for target in row) + 126 for row in rows]
    height = (title_h + gap + sum(row_heights) + (len(rows) - 1) * gap + 60) if rows else (title_h + 80)
    image = Image.new("RGB", (width, height), CREAM)
    draw = ImageDraw.Draw(image)
    font_job = ImageFont.load_default(size=22)
    font_small = ImageFont.load_default(size=16)
    font_badge = ImageFont.load_default(size=15)

    cx = margin
    if mark_path.is_file():
        try:
            mark = Image.open(mark_path).convert("RGBA").resize((mark_size, mark_size), Image.LANCZOS)
        except Exception:
            mark = None
        if mark is not None:
            image.paste(mark, (cx, (title_h - mark_size) // 2), mark)
            cx += mark_size + 16
    draw.text((cx, 30), str(manifest.get("job", "Review board")), font=font_job, fill=NAVY)
    draw.text((cx, 64), job_stamp(manifest.get("created", "")), font=font_small, fill=MUTED)

    y = title_h + gap
    for row, row_h in zip(rows, row_heights, strict=True):
        x = margin
        for target in row:
            tw, th = thumb_box(_aspect(target))
            tx = x + (tile_w - tw) // 2
            draw.rounded_rectangle([x, y, x + tile_w, y + row_h], radius=12, fill=SURFACE, outline=BORDER, width=1)
            source = target.get("file") or ""
            if target.get("kind") == "video" and target.get("cover"):
                source = target["cover"]
            thumb = None
            if source and (job_dir / source).is_file():
                try:
                    with Image.open(job_dir / source) as opened:
                        thumb = _upright(opened).convert("RGB")
                        thumb.thumbnail((tw, th), Image.LANCZOS)
                except Exception:
                    thumb = None
            if thumb is not None:
                image.paste(thumb, (tx, y + 14))
            else:
                draw.rounded_rectangle([tx, y + 14, tx + tw, y + 14 + th], radius=8, fill=NAVY)
                draw.text((tx + 6, y + 14 + th / 2 - 8), "media", font=font_small, fill=CREAM)
            ly = y + 14 + th + 12
            draw.text((x + 12, ly), platform_name(str(target.get("platform", ""))), font=font_badge, fill=NAVY)
            draw.text((x + 12, ly + 20), str(target.get("id", "")), font=font_small, fill=MUTED)
            facts = []
            if target.get("width") and target.get("height"):
                facts.append(f"{target['width']}x{target['height']}")
            if target.get("kind") == "video" and target.get("duration"):
                facts.append(clock(target["duration"]))
            draw.text((x + 12, ly + 40), "  ".join(facts), font=font_small, fill=MUTED)
            status = effective_status(target)
            label = STATUS_LABELS.get(status, status)
            badge_w = draw.textlength(label, font=font_badge) + 16
            draw.rounded_rectangle([x + 12, ly + 64, x + 12 + badge_w, ly + 64 + 22], radius=11,
                                   fill=STATUS_COLORS.get(status, MUTED))
            draw.text((x + 20, ly + 68), label, font=font_badge, fill=SURFACE)
            x += tile_w + gap
        y += row_h + gap
    out_path = job_dir / "contact.png"
    image.save(out_path, format="PNG", optimize=True)
    return out_path


def render_inline_html(job_dir: Path, manifest: dict, cache: dict) -> tuple[str, int]:
    """Same design as board.html, fully self-contained with data URIs.

    Honors the 6 MB cap: start at JPEG 720 px / quality 80, fall back to
    480 px / quality 70, then drop posters that repeat, then drop all posters.
    Returns the final variant and its byte size.
    """
    levels = [
        (720, 80, False, False),
        (480, 70, False, False),
        (480, 70, True, False),
        (480, 70, True, True),
    ]
    html_text, inline_size = "", 0
    for max_side, quality, drop_dupes, drop_all in levels:
        ctx = Ctx(job_dir, manifest, True, cache, max_side, quality, drop_dupes, drop_all)
        html_text, inline_size = render_page(ctx)
        if inline_size <= INLINE_CAP:
            break
    return html_text, inline_size


def write_board(job_dir: Path, manifest: dict) -> dict:
    """Writes board.html, board-inline.html and contact.png into job_dir.

    Returns a dict with absolute paths for board, board_inline and contact,
    plus board_inline_size (final byte size of the inlined board).
    """
    job_dir = Path(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    mark_path = TEMPLATES / "pucci-mark-64.png"

    cache: dict = {}

    board_html = render_page(Ctx(job_dir, manifest, False, cache))[0]
    board_path = job_dir / "board.html"
    board_path.write_text(board_html, encoding="utf-8")

    contact_path = write_contact_png(job_dir, manifest, mark_path)

    inline_html, inline_size = render_inline_html(job_dir, manifest, cache)
    inline_path = job_dir / "board-inline.html"
    inline_path.write_text(inline_html, encoding="utf-8")

    return {
        "board": str(board_path.resolve()),
        "board_inline": str(inline_path.resolve()),
        "contact": str(contact_path.resolve()),
        "board_inline_size": inline_size,
    }
