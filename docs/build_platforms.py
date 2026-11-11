"""Write docs/platforms.md from data/platforms.yaml. Run from the repo root: python docs/build_platforms.py"""

from pathlib import Path
from urllib.parse import urlparse

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parent.parent
UNITS = {"codepoints": "characters", "x_weighted": "weighted characters", "graphemes": "graphemes",
         "utf16": "UTF-16 units", "utf8_bytes": "UTF-8 bytes"}
LABELS = {"limit": "Length", "hashtags_max": "Hashtags, at most", "mentions_max": "Mentions, at most",
          "bytes_max": "File size, at most", "bytes_min": "File size, at least", "containers": "Container",
          "video_codecs": "Video codec", "formats": "Format", "audio_sample_rate": "Audio sample rate",
          "fps_min": "Frame rate, at least", "fps_max": "Frame rate, at most", "duration_min": "Length, at least",
          "duration_max": "Length, at most", "video_bps_max": "Video bitrate, at most",
          "audio_bps_max": "Audio bitrate, at most", "safe_area": "Keep clear of the edges",
          "aspect_range": "Aspect ratio, from and to", "aspect_options": "Aspect ratio, one of",
          "aspect_min": "Aspect ratio, at least", "aspect_max": "Aspect ratio, at most",
          "dimension_min": "Shorter side, at least", "dimension_max": "Longer side, at most"}
TEXT_LABELS = {"bytes_max": "Size, at most"}
HEADER = "| Applies to | Limit | Value | Kind | Checked | Source |"
KINDS = {"image": ("photo", ".jpg"), "video": ("video", ".mp4"), "image_or_video": ("photo or video", ".jpg or .mp4")}
INTRO = """# Platforms and limits

Every size and limit postkitty checks, with the page it came from and the date it was checked. This page is built
from [data/platforms.yaml](../data/platforms.yaml) by `python docs/build_platforms.py`, so change the data there.

A **required** limit keeps a file out of `ready/` until it passes, and a failure starts a repair. An **advised**
limit is a recommendation: a file that misses it still passes, with a note on the review board. A source marked
secondary is a third-party page, used where the platform publishes no number of its own.

Each file lands in `ready/<platform>/` under the name shown with its target. Photos are saved as JPEG, or as PNG
when the source has transparency and the platform takes PNG.
"""


def size(value: int) -> str:
    for unit, base in (("GB", 10**9), ("MB", 10**6), ("KB", 10**3), ("GB", 2**30), ("MB", 2**20)):
        if value % base == 0:
            return f"{value // base:,} {unit}"
    return f"{value:,} bytes"


def show(key: str, spec: dict) -> str:
    value = spec["value"]
    if spec.get("unit"):
        text = f"{value:,} {UNITS.get(spec['unit'], spec['unit'].replace('_', ' '))}"
    elif key.startswith("bytes"):
        text = size(value)
    elif key.endswith("bps_max"):
        text = f"{value / 10**6:g} Mbps" if value >= 10**6 else f"{value / 10**3:g} kbps"
    elif key.startswith("duration"):
        text = f"{value:,} s"
    elif key.startswith("fps"):
        text = f"{value} fps"
    elif key == "audio_sample_rate":
        text = f"{value / 1000:g} kHz"
    elif key.startswith("dimension"):
        text = f"{value:,} px"
    elif isinstance(value, dict):
        text = ", ".join(f"{side} {amount:.0%}" for side, amount in value.items())
    elif isinstance(value, list):
        text = ", ".join(str(item) for item in value)
    else:
        text = f"{value:,}" if isinstance(value, int) else str(value)
    return f"{text} ({spec['note']})" if spec.get("note") else text


def row(where: str, key: str, spec: dict) -> str:
    host = urlparse(spec["source_url"]).netloc.removeprefix("www.")
    source = f"[{host}]({spec['source_url']})" + (", secondary" if spec.get("source_scope") == "secondary" else "")
    enforced = "required" if spec.get("enforcement", "hard") == "hard" else "advised"
    label = (TEXT_LABELS if where == "Text" else LABELS).get(key) or LABELS.get(key, key.replace("_", " "))
    return f"| {where} | {label} | {show(key, spec)} | {enforced} | {spec.get('checked_on', '')} | {source} |"


def main() -> None:
    data = YAML(typ="safe").load((ROOT / "data" / "platforms.yaml").read_text(encoding="utf-8"))
    out = [INTRO]
    for name, platform in data["platforms"].items():
        out += [f"## {platform['label']}", "", HEADER, "|---|---|---|---|---|---|"]
        out += [row("Text", key, spec) for key, spec in platform.get("text", {}).items()]
        for target_id, target in platform["targets"].items():
            stem = target_id.removeprefix(name + "_")
            kind, suffix = KINDS[target["kind"]]
            where = f"`{target_id}`, {kind}, `ready/{name}/{stem}{suffix}`"
            out.append(f"| {where} | Output size | {target['width']}×{target['height']} | required | | |")
            out += [row("", key, spec) for key, spec in target.items() if key not in ("kind", "width", "height")]
        out.append("")
    (ROOT / "docs" / "platforms.md").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
