"""The /postkitty command text."""

from __future__ import annotations

from .engine import platforms
from .engine.pipeline import ALIASES


def targets_overview(filter_text: str = "") -> str:
    """Text for the /postkitty command: what postkitty does, then every target with its size and main limits."""
    header = """postkitty: one post in, every platform out.
Give Hermes a draft, photos or a landscape video. postkitty fixes the wording and writes a
version for each platform, crops photos and reframes video with every face in frame, and
checks every file against the platform's limits. It never posts, uploads or schedules; you
upload the files in ready/ yourself.

Try saying:
  Fix my wording and write this for X, LinkedIn and Threads: [your draft]
  Make team.jpg ready for Instagram and Bluesky, and keep everyone in the picture.
  Turn talk.mp4 into vertical clips for TikTok, Reels and Shorts.
  In the TikTok clip, cut to whoever is talking.
  Will this file upload to TikTok? [path to the file]

Targets (size, main limits). Type /postkitty tiktok to see one platform.
"""
    want = {ALIASES.get(w, w) for w in filter_text.lower().split() if w != "platforms"}
    lines = []
    for name, plat in platforms.load_platforms().items():
        if want and name not in want:
            continue
        limit = plat.text.get("limit")
        text = f"text {limit.value} {limit.unit}" if limit else "no text limit"
        lines.append(f"{plat.label}: {text}")
        for t in plat.targets.values():
            extras = [f"{k.replace('_max', '')} <= {t.limits[k].value}" for k in ("duration_max", "bytes_max") if k in t.limits]
            lines.append(f"  {t.id}: {t.width}x{t.height} {t.kind}" + (f" ({', '.join(extras)})" if extras else ""))
    if not lines:
        return "No matching platform."
    return ("" if want else header) + "\n".join(lines)
