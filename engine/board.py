"""Review board: board.html, board-inline.html and contact.png for a postkitty job.

Only the standard library and Pillow are used. Every value that comes from the
manifest is passed through html.escape before it reaches the page.
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
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

PUCCI_SVG = (
    '<svg viewBox="168 8 688 688" xmlns="http://www.w3.org/2000/svg" '
    'width="688" height="688" aria-label="Pucci, the postkitty mascot">'
    '<title>Pucci, the postkitty mascot</title>'
    '<g transform="translate(61 54) scale(.88)" stroke="#1E2A44" stroke-width="14" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<g id="body">'
    '<path d="M300 715C244 747 216 798 226 859C182 865 149 903 157 947C168 1002 '
    '239 1027 318 1026C366 1025 403 1005 402 974L441 988C478 1002 534 1001 565 988 '
    'C608 1001 664 996 689 979C713 961 700 933 688 917C732 858 711 796 670 757L659 '
    '657Z" fill="#E8814D" />'
    '<path d="M667 767C674 825 663 884 654 924" fill="none" />'
    '<path d="M252 761C295 759 340 786 352 819C361 847 341 833 322 822C295 804 264 '
    '799 235 803Z" fill="#C8643A" stroke="none" />'
    '<path d="M229 837C266 830 312 847 327 869C342 891 314 881 293 877C272 873 251 '
    '874 231 881Z" fill="#C8643A" stroke="none" />'
    '<path d="M178 899C202 875 225 880 244 893C204 916 192 945 198 974L172 952Z" '
    'fill="#C8643A" stroke="none" />'
    '<path d="M275 914C244 945 230 981 246 1017L285 1025C265 985 280 952 312 927Z" '
    'fill="#C8643A" stroke="none" />'
    '<path d="M344 937C314 961 305 995 321 1025C370 1026 402 1005 402 974C400 957 '
    '375 942 344 937Z" fill="#C8643A" stroke="none" />'
    '<path d="M387 758C430 803 433 855 420 908L433 938" fill="none" stroke-width="11" />'
    '<path d="M515 690C526 760 538 841 547 924" fill="none" />'
    '<path d="M425 925C457 898 512 902 544 927C565 945 577 975 562 990C536 1005 '
    '469 1006 438 994C451 966 441 942 425 925Z" fill="#F7F1E5" />'
    '<path d="M558 928C585 902 632 901 662 916C691 931 705 960 692 978C666 996 '
    '598 997 562 985C570 965 565 946 558 928Z" fill="#F7F1E5" />'
    '<path d="M486 952Q503 977 493 997M530 952Q545 975 538 996M610 950Q622 970 613 '
    '990M652 949Q665 967 658 987" fill="none" stroke-width="7" />'
    '<path d="M352 933C379 914 410 918 429 940C448 960 451 982 438 994C420 1005 '
    '389 1005 372 1000" fill="#F7F1E5" />'
    '<path d="M404 959Q417 982 407 1000" fill="none" stroke-width="7" />'
    '<path d="M226 859C229 900 258 915 304 920C350 926 393 939 400 968C410 1006 '
    '371 1027 318 1026C242 1027 169 1003 157 947C149 903 182 866 226 859" fill="none" />'
    '</g>'
    '<g id="arms">'
    '<path d="M300 531C259 563 251 640 278 683C305 728 368 732 411 699C435 680 457 '
    '646 463 607Z" fill="#E8814D" />'
    '<path d="M267 617C294 642 326 645 356 632C379 623 362 658 342 670C316 687 286 '
    '677 277 666Z" fill="#C8643A" stroke="none" />'
    '<path d="M602 601C614 646 625 704 666 721C720 741 775 694 796 636L815 551L736 '
    '526Z" fill="#E8814D" />'
    '<path d="M721 618C746 638 770 644 794 631C786 657 773 676 755 686C732 685 714 '
    '666 705 643C697 622 702 606 721 618Z" fill="#C8643A" stroke="none" />'
    '</g>'
    '<path id="bib" d="M481 605C454 622 437 661 448 684C453 695 469 679 480 667 '
    'C469 699 475 739 490 752C501 764 508 734 513 725C519 771 529 815 538 843C564 '
    '816 582 780 589 746L596 769C621 750 635 704 623 674C643 713 651 681 641 650 '
    'C633 623 610 608 594 597Z" fill="#F7F1E5" stroke="none" />'
    '<g id="head">'
    '<path d="M205 342C170 280 166 190 179 126C189 77 203 47 236 48C293 47 354 84 '
    '397 119C443 98 494 88 547 92C586 38 645 -31 681 -23C721 -13 777 92 794 225 '
    'C823 266 853 321 852 371C851 443 800 493 731 536C652 586 542 615 432 607C349 '
    '602 260 589 220 546C165 489 164 410 205 342Z" fill="#E8814D" />'
    '<path d="M199 325C174 261 178 163 194 112C203 83 218 65 243 76C280 93 313 130 '
    '336 168C279 210 235 264 199 325Z" fill="#F2B8A2" stroke="none" />'
    '<path d="M558 92C602 35 649 -10 676 -7C646 23 632 66 624 109Z" fill="#E8814D" '
    'stroke="none" />'
    '<path d="M624 109C637 56 654 4 676 -7C715 7 765 109 780 206C736 157 684 126 '
    '624 109Z" fill="#F2B8A2" stroke="none" />'
    '<path d="M243 76C285 96 315 129 343 169C281 215 239 271 209 326M624 109C636 57 '
    '654 12 672 4" fill="none" stroke-width="9" />'
    '<path d="M390 133C419 156 443 183 466 214C487 239 495 223 487 198C478 163 458 '
    '132 438 111Z" fill="#C8643A" stroke="none" />'
    '<path d="M472 99C504 129 520 167 540 210C553 238 571 229 568 196C565 153 548 '
    '117 527 93Z" fill="#C8643A" stroke="none" />'
    '<path d="M562 94C583 122 592 149 601 175C611 202 627 188 628 159C630 135 624 '
    '119 617 108Z" fill="#C8643A" stroke="none" />'
    '<path d="M190 377C237 348 287 346 322 363C343 373 336 384 318 386C265 391 221 '
    '411 181 439Z" fill="#C8643A" stroke="none" />'
    '<path d="M191 480C224 452 266 438 293 443C315 447 300 459 283 469C247 491 219 '
    '519 214 537Z" fill="#C8643A" stroke="none" />'
    '<path d="M822 307C795 310 776 323 773 339C771 351 805 340 839 356Z" '
    'fill="#C8643A" stroke="none" />'
    '<path d="M844 384C818 370 787 372 784 384C780 394 816 408 825 436C838 418 845 '
    '403 844 384Z" fill="#C8643A" stroke="none" />'
    '<path d="M327 482C358 457 401 459 437 448C488 433 514 372 559 371C602 369 619 '
    '401 654 401C699 385 741 401 756 436C780 484 725 530 675 553C596 591 512 610 '
    '432 601C380 597 330 585 310 561Z" fill="#F7F1E5" stroke="none" />'
    '<path d="M383 410C382 360 422 319 465 333C506 344 527 393 509 430C488 470 426 '
    '466 400 438Z" fill="#F7F1E5" stroke="none" />'
    '<path d="M385 410C384 369 420 326 461 330" fill="none" />'
    '<ellipse cx="475" cy="392" rx="52" ry="59" fill="#1E2A44" stroke="none" />'
    '<circle cx="487" cy="365" r="17" fill="#F7F1E5" stroke="none" />'
    '<ellipse cx="691" cy="338" rx="53" ry="62" transform="rotate(-16 691 338)" '
    'fill="#F7F1E5" stroke="none" />'
    '<ellipse cx="675" cy="345" rx="44" ry="58" transform="rotate(-16 675 345)" '
    'fill="#1E2A44" stroke="none" />'
    '<circle cx="663" cy="319" r="16" fill="#F7F1E5" stroke="none" />'
    '<path d="M410 303Q437 273 469 290M628 219Q650 195 678 215" fill="none" '
    'stroke-width="11" />'
    '<ellipse cx="414" cy="487" rx="41" ry="17" transform="rotate(-8 414 487)" '
    'fill="#F2B8A2" stroke="none" />'
    '<ellipse cx="724" cy="422" rx="34" ry="16" transform="rotate(-7 724 422)" '
    'fill="#F2B8A2" stroke="none" />'
    '<path d="M579 401C591 390 619 388 628 396C631 407 618 423 608 424C594 423 '
    '570 414 579 401Z" fill="#E07A5F" stroke="none" />'
    '<path d="M568 453C582 490 602 509 621 494C637 481 641 452 642 437C624 446 612 '
    '438 607 432C596 449 584 455 568 453Z" fill="#E07A5F" stroke-width="7" />'
    '<path d="M608 423L607 432C593 454 574 460 558 449M607 432C624 443 643 441 650 '
    '430" fill="none" stroke-width="7" />'
    '</g>'
    '<g id="viewfinder" fill="none" stroke-width="27">'
    '<path d="M336 324V263H402" />'
    '<path d="M667 263H732V322" stroke="#F7F1E5" stroke-width="35" />'
    '<path d="M667 263H732V322" />'
    '<path d="M337 486V548H404" />'
    '<path d="M732 479V543H667" />'
    '</g>'
    '<g id="paws" fill="#F7F1E5">'
    '<path d="M363 548C365 519 340 503 313 513C277 523 255 554 263 589C268 618 '
    '292 638 321 638C349 638 365 619 360 597C382 578 383 560 363 548Z" />'
    '<path d="M794 518C770 508 744 517 723 538C707 554 706 574 721 584C705 602 '
    '716 626 742 631C778 639 808 617 820 588C832 556 820 531 794 518Z" />'
    '<path d="M305 559C325 544 346 543 363 548M360 597L340 603M721 554C739 543 757 '
    '549 772 559M721 584C732 579 745 582 754 589" fill="none" stroke-width="8" />'
    '</g>'
    '</g>'
    '</svg>'
)

CREAM = "#F7F1E5"
NAVY = "#1E2A44"
GINGER = "#E8814D"
TERRACOTTA = "#E07A5F"
MUTED = "#5B6478"

INK = "#243046"
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

UNIT_NAMES = {
    "codepoints": "characters",
    "x_weighted": "weighted characters",
    "utf16": "UTF-16 units",
    "graphemes": "characters",
}

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


def load_css() -> str:
    return (TEMPLATES / "board.css").read_text(encoding="utf-8")


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def esc_attr(value: Any) -> str:
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


def format_duration(seconds: Any) -> str:
    try:
        total = float(seconds)
    except (TypeError, ValueError):
        return ""
    total = max(0.0, total)
    minutes = int(total // 60)
    secs = int(round(total % 60))
    if minutes:
        return f"{minutes}:{secs:02d}"
    return f"{secs} s"


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
        if status == "fail" or (status == "advisory" and row["status"] == "pass"):
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
        f'<span class="pill {esc_attr(key)}">'
        f'<svg viewBox="0 0 12 12" aria-hidden="true">{ICONS[key]}</svg>'
        f'{esc(STATUS_LABELS.get(status, str(status).title()))}</span>'
    )


def target_frame_class(target: dict) -> str:
    width = int(target.get("width") or 0)
    height = int(target.get("height") or 0)
    if width > 0 and height > 0 and (width / height) < 0.9:
        return "phone"
    return "feed"


def safe_area_bands(checks: list[dict]) -> str:
    for check in checks:
        measured = check.get("measured")
        if isinstance(measured, dict) and {"top", "bottom", "side"} <= set(measured):
            top = float(measured["top"])
            bottom = float(measured["bottom"])
            side = float(measured["side"])
            return (
                '<div class="safe" style="'
                f"--top: {top * 100:.2f}%; --bottom: {bottom * 100:.2f}%; --side: {side * 100:.2f}%;"
                '"><i class="t"></i><i class="b"></i><i class="l"></i><i class="r"></i></div>'
            )
    return ""


def ImageOps_exif_transpose(image: Image.Image) -> Image.Image:
    try:
        from PIL import ImageOps
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
            image = ImageOps_exif_transpose(image)
            image = image.convert("RGB")
            image.thumbnail((max_side, max_side), Image.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
        result = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return ""
    cache[key] = result
    return result


def copy_info(manifest: dict, platform: str) -> dict:
    return (manifest.get("copy") or {}).get(platform, {}) or {}


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
            img = (f'<img src="{esc_attr(poster)}" width="{width}" height="{height}" '
                   f'alt="Poster frame, {esc_attr(label)}">' if poster else "")
            return f'<div class="frame video" style="{style}">{img}{PLAY_SVG}{overlay}</div>'
        mime = mimetypes.guess_type(file_rel)[0] or "video/mp4"
        poster_attr = f' poster="{esc_attr(cover_rel)}"' if cover_rel else ""
        return (
            f'<div class="frame video" style="{style}">'
            f'<video controls muted playsinline preload="metadata"{poster_attr} '
            f'aria-label="{esc_attr(label)} video">'
            f'<source src="{esc_attr(file_rel)}" type="{esc_attr(mime)}"></video>{overlay}</div>'
        )
    if kind == "image" and file_rel:
        src = (image_data_uri_capped(ctx.job_dir / file_rel, ctx.cache, ctx.max_side,
                                     ctx.quality) if ctx.inline else file_rel)
        return (
            f'<div class="frame image" style="{style}">'
            f'<img src="{esc_attr(src)}" width="{width}" height="{height}" '
            f'alt="{esc_attr(alt or "Preview, " + label)}" loading="lazy">{overlay}</div>'
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
            f'source (<a href="{esc_attr(row["source_url"])}" rel="noopener">'
            f'{esc(source_label(str(row["source_url"])))}</a>{esc(when)})'
        )
    mono_html = f'<div class="mono">{" · ".join(mono)}</div>' if mono else ""
    return (
        f'<li title="{esc_attr(", ".join(row["ids"]))}">'
        f'<span class="dot {esc_attr(row["status"])}"></span>'
        f'<div><div class="msg">{esc(text)}</div>{mono_html}</div></li>'
    )


def checks_html(checks: list[dict]) -> str:
    rows = merge_checks(checks)
    if not rows:
        return ""
    bad = [r for r in rows if r["status"] != "pass"]
    hard_fail = any(r["hard"] and r["status"] == "fail" for r in rows)
    if bad:
        head = f"{len(bad)} need attention" if len(bad) > 1 else "1 needs attention"
        if len(rows) > len(bad):
            head += f", {len(rows) - len(bad)} passed"
    else:
        head = f"{len(rows)} checks passed" if len(rows) > 1 else "1 check passed"
    attn = ' class="attn"' if bad else ""
    return (
        f'<details class="checks"{" open" if hard_fail else ""}>'
        f'<summary{attn}>{esc(head)}</summary>'
        f'<ul class="check-list">{"".join(check_row_html(r) for r in rows)}</ul></details>'
    )


def redo_prompt(ctx: Ctx, target: dict, what: str) -> str:
    return f"Use postkitty_redo on job {ctx.job_id} target {target.get('id', '')} with {what}"


def adjust_html(target: dict, ctx: Ctx) -> str:
    width, height = target_dims(target)
    mode = (target.get("layout") or {}).get("mode")
    people = int((ctx.inputs.get(str(target.get("input"))) or {}).get("people") or 0)
    options: list[tuple[str, str]] = []
    if people > 1:
        for n in range(1, min(people, 8) + 1):
            options.append((f"Focus person {n}", f"focus person:{n}"))
    if people == 2 and height > width and mode != "split":
        options.append(("Split screen", "layout split"))
    if mode != "pad":
        options.append(("Fit whole frame", "layout pad"))
    trim = target.get("trim")
    if target.get("kind") == "video" and isinstance(trim, (list, tuple)) and len(trim) == 2:
        options.append(("Trim", f"trim {float(trim[0])}, {float(trim[1])}"))
    if not options:
        return ""
    buttons = "".join(
        f'<button type="button" class="btn tiny" '
        f'data-hermes-send="{esc_attr(redo_prompt(ctx, target, what))}">{esc(label)}</button>'
        for label, what in options
    )
    return (f'<details class="adjust"><summary>Adjust</summary>'
            f'<div class="adjust-menu">{buttons}</div></details>')


LAYOUT_NAMES = {"split": "Split screen", "pad": "Whole frame", "crop": "Cropped",
                "seam": "Seam squeeze"}


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

    bands = safe_area_bands(checks)
    toggle = ('<button type="button" class="btn tiny safe-toggle" data-toggle-safe-area>'
              'Show safe area</button>' if bands else "")
    note = layout_note(target.get("layout") or {})
    note_html = f'<p class="note">{esc(note)}</p>' if note else ""
    alt_html = f'<p class="alt"><b>Alt text</b> {esc(alt)}</p>' if alt else ""
    actions = []
    if file_rel:
        actions.append(f'<a class="btn" href="{esc_attr(file_rel)}">Open</a>')
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
        f'{note_html}{repairs_html(target.get("repairs") or [])}{alt_html}{checks_html(checks)}'
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
        f'<div class="pucci-mark">{PUCCI_SVG}</div>'
        '<div class="title-group">'
        f'<h1>{esc(board_title(manifest))}</h1>'
        f'<p class="meta">{esc(meta_text)}</p>'
        f'<div class="path-chip"><code>{esc(path)}</code>'
        f'<button type="button" class="btn tiny" data-copy-text="{esc_attr(path)}">Copy</button></div>'
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


def count_line(count: Any, limit: Any, unit: str) -> str:
    name = UNIT_NAMES.get(unit, unit)
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
        summary = f"{len(parts)} parts, limit {limit} {UNIT_NAMES.get(unit, unit)} each" \
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
        links = f' <a href="{esc_attr(post)}">post.txt</a>'
    return (
        '<article class="copy-card">'
        f'<div class="copy-head"><h3>{esc(PLATFORM_COPY_NAMES.get(platform, platform_name(platform)))}</h3>'
        f'<span class="counts{" over" if over else ""}">{esc(summary)}</span></div>'
        f'{meter}<div class="parts">{"".join(rendered)}</div>'
        f'<p class="tags">{esc(tag_line + fold_note)}{links}</p>'
        f'<button type="button" class="btn primary" data-copy-text="{esc_attr(joined)}">Copy text</button>'
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
        f'<div class="pucci-mark">{PUCCI_SVG}</div>'
        '<span>Made with postkitty</span>'
        f'<nav aria-label="Job files">{"".join(links)}</nav>'
        '</div></footer>'
    )


def render_page(ctx: Ctx) -> tuple[str, int]:
    title = esc(board_title(ctx.manifest)) + " - postkitty review board"
    if ctx.inline:
        title += " (inline)"
    body = [
        HTML_HEAD.format(title=title, css=load_css()),
        build_header(ctx),
        "<main><div class=\"wrap\">",
        build_advice(ctx.manifest),
        build_files(ctx),
        build_copy(ctx),
        "</div></main>",
        build_footer(ctx),
        _script(),
        "\n</body>\n</html>",
    ]
    text = "".join(body)
    return text, len(text.encode("utf-8"))


def render_board_html(job_dir: Path, manifest: dict, inline: bool, cache: dict) -> str:
    return render_page(Ctx(job_dir, manifest, inline, cache))[0]


def _script() -> str:
    return """\
<script>
(function () {
  var toast = document.createElement("div");
  toast.className = "toast";
  toast.setAttribute("role", "status");
  document.body.appendChild(toast);
  var timer;
  function show(message) {
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(timer);
    timer = setTimeout(function () { toast.classList.remove("show"); }, 2200);
  }
  function copy(text, done) {
    function fallback() {
      var area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try { document.execCommand("copy"); done(); } catch (e) { show("Copy failed."); }
      document.body.removeChild(area);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else {
      fallback();
    }
  }
  document.body.addEventListener("click", function (event) {
    var button = event.target.closest("[data-copy-text]");
    if (button) {
      event.preventDefault();
      copy(button.getAttribute("data-copy-text"), function () { show("Copied."); });
      return;
    }
    button = event.target.closest("[data-hermes-send]");
    if (button) {
      event.preventDefault();
      var prompt = button.getAttribute("data-hermes-send");
      var status = button.closest(".actions").querySelector(".hermes-status");
      if (window.hermes && typeof window.hermes.send === "function") {
        status.textContent = "Sending to Hermes...";
        window.hermes.send(prompt).then(function (result) {
          status.textContent = "Sent. " + String(result);
        }).catch(function () { status.textContent = "Send failed."; });
      } else {
        copy(prompt, function () {
          show("Copied. Paste it to Hermes.");
          status.textContent = "Copied to clipboard.";
        });
      }
      return;
    }
    button = event.target.closest("[data-toggle-safe-area]");
    if (button) {
      var area = button.closest(".stage").querySelector(".safe");
      if (area) {
        area.classList.toggle("show");
        button.textContent = area.classList.contains("show") ? "Hide safe area" : "Show safe area";
      }
    }
  });
})();
</script>
"""


def write_contact_png(job_dir: Path, manifest: dict, mark_path: Path) -> Path:
    targets = manifest.get("targets") or []
    job_name = manifest.get("job", "Review board")
    created = manifest.get("created", "")
    width = 1600
    gap = 24
    margin = 40
    cols = 3 if targets else 1
    tile_w = (width - 2 * margin - (cols - 1) * gap) // cols
    mark_size = 40

    def thumb_box(aspect: float) -> tuple[int, int]:
        max_h = 240
        h = min(max_h, tile_w * aspect)
        w = h / aspect if aspect else tile_w
        return int(w), int(h)

    rows = 0
    row_heights: list[int] = []
    index = 0
    while index < len(targets):
        row_max = 0
        for _ in range(min(cols, len(targets) - index)):
            target = targets[index]
            aspect = 1.0
            try:
                aspect = int(target.get("width") or 0) / int(target.get("height") or 1) or 1.0
            except (TypeError, ValueError, ZeroDivisionError):
                aspect = 1.0
            w, h = thumb_box(aspect)
            row_max = max(row_max, h + 104)
            index += 1
        row_heights.append(row_max)
        rows += 1

    title_h = 120
    height = (title_h + gap + sum(row_heights) + (rows - 1) * gap + 60) if rows else (title_h + 80)
    image = Image.new("RGB", (width, height), CREAM)
    draw = ImageDraw.Draw(image)

    font_job = ImageFont.load_default(size=22)
    font_small = ImageFont.load_default(size=16)
    font_badge = ImageFont.load_default(size=15)

    mark = None
    if mark_path.is_file():
        try:
            mark = Image.open(mark_path).convert("RGBA")
        except Exception:
            mark = None

    cx = margin
    if mark is not None:
        mark_s = mark.resize((mark_size, mark_size), Image.LANCZOS)
        image.paste(mark_s, (cx, (title_h - mark_size) // 2), mark_s)
        cx += mark_size + 16
    draw.text((cx, 30), str(job_name), font=font_job, fill=NAVY)
    draw.text((cx, 64), str(created), font=font_small, fill=MUTED)

    y = title_h + gap
    index = 0
    for row_h in row_heights:
        x = margin
        row_targets = targets[index:index + cols]
        index += len(row_targets)
        for target in row_targets:
            kind = target.get("kind")
            aspect = 1.0
            try:
                aspect = int(target.get("width") or 0) / int(target.get("height") or 1) or 1.0
            except (TypeError, ValueError, ZeroDivisionError):
                aspect = 1.0
            tw, th = thumb_box(aspect)
            tx = x + (tile_w - tw) // 2
            card_bg = SURFACE
            draw.rounded_rectangle([x, y, x + tile_w, y + row_h], radius=12, fill=card_bg, outline=BORDER, width=1)
            thumb = None
            file_rel = target.get("file") or ""
            cover_rel = target.get("cover")
            source = cover_rel if kind == "video" and cover_rel else file_rel
            full_source = job_dir / source if source and not os.path.isabs(source) \
                else Path(source)
            if source and full_source.is_file():
                try:
                    with Image.open(full_source) as img:
                        img = ImageOps_exif_transpose(img).convert("RGB")
                        img.thumbnail((tw, th), Image.LANCZOS)
                        thumb = img
                except Exception:
                    thumb = None
            if thumb is not None:
                image.paste(thumb, (tx, y + 14))
            else:
                draw.rounded_rectangle([tx, y + 14, tx + tw, y + 14 + th], radius=8, fill="#1E2A44")
                draw.text((tx + 6, y + 14 + th / 2 - 8), "media", font=font_small, fill="#F7F1E5")
            ly = y + 14 + th + 12
            draw.text((x + 12, ly), platform_name(str(target.get("platform", ""))), font=font_badge, fill=NAVY)
            draw.text((x + 12, ly + 20), str(target.get("id", "")), font=font_small, fill=MUTED)
            size_text = f"{int(target.get('width') or 0)}x{int(target.get('height') or 0)}"
            dur = format_duration(target.get("duration"))
            meta = size_text + (f"  {dur}" if dur else "")
            draw.text((x + 12, ly + 40), meta, font=font_small, fill=MUTED)
            status = str(target.get("status", "unknown"))
            color = STATUS_COLORS.get(status, "#5B6478")
            label = STATUS_LABELS.get(status, status)
            bw = draw.textlength(label, font=font_badge) + 16
            draw.rounded_rectangle([x + 12, ly + 64, x + 12 + bw, ly + 64 + 22], radius=11, fill=color)
            draw.text((x + 20, ly + 68), label, font=font_badge, fill="#FFFFFF")
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

    board_html = render_board_html(job_dir, manifest, False, cache)
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
