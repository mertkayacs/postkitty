"""The /postkitty slash command. It runs without the model and returns the text to show."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from . import tools
from .engine import doctor, pipeline, platforms

DOCS = "https://postkitty.mertkayacs.com/docs/"
CHECK_USAGE = "Usage: /postkitty check <file> [target], for example /postkitty check clip.mp4 tiktok"
OVERVIEW = f"""postkitty: one post in, every platform out.
Give Hermes a draft, photos or a landscape video, or only the draft. You get the text fixed and
written for each platform, photos cropped and video reframed with every face in frame, and
every file checked against the platform's limits. Video needs ffmpeg. postkitty never posts,
uploads or schedules; you upload the files in ready/ yourself.

Try saying:
  Fix my wording and write this for X, LinkedIn and Threads: [your draft]
  Make team.jpg ready for Instagram and Bluesky, and keep everyone in the picture.
  Turn talk.mp4 into vertical clips for TikTok, Reels and Shorts.
  In the TikTok clip, cut to whoever is talking.
  Will this file upload to TikTok? [path to the file]

To change a result, say what you want: a shorter text, another person in focus, another
layout, a different trim or cover frame.

Commands: /postkitty <platform> shows one platform, /postkitty check <file> [target] checks
a file, /postkitty doctor checks the setup. Docs: {DOCS}

Targets (size, main limits):
"""


def handle(raw_args: str = "", **kwargs) -> str:
    """``/postkitty``, ``/postkitty <platform>``, ``/postkitty doctor`` or ``/postkitty check <file> [target]``."""
    try:
        words = shlex.split(raw_args or "")
    except ValueError:  # an unbalanced quote
        words = (raw_args or "").split()
    try:
        if words and words[0].lower() == "check":
            return check_file(words[1:])
        if [word.lower() for word in words] == ["doctor"]:
            tools.apply_settings()
            # The rows align in a monospace font, which chats give only to a code block.
            return f"```\n{doctor.render_text(doctor.report(pipeline.jobs_dir()))}\n```"
        return targets_overview(raw_args or "")
    except Exception as exc:  # Hermes does not catch a command handler's exception
        return f"postkitty could not answer: {exc}"


def targets_overview(filter_text: str = "") -> str:
    """What postkitty does, then every target; a platform name shows only that platform's targets."""
    names = [word for word in filter_text.lower().split() if word != "platforms"]
    return targets(" ".join(names)) if names else OVERVIEW + targets()


def targets(filter_text: str = "") -> str:
    """Every target with its size and main limits, or only those of the platforms named."""
    want = {pipeline.ALIASES.get(w, w) for w in filter_text.lower().split()}
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
    return "\n".join(lines) or "No matching platform."


def check_file(words: list[str]) -> str:
    """Check one file against a target. The last word is the target when it names one; the rest is the path."""
    if not words:
        return CHECK_USAGE
    known = {*platforms.platform_names(), *platforms.target_ids(), *pipeline.ALIASES}
    target = words[-1].lower() if len(words) > 1 and words[-1].lower() in known else None
    path = " ".join(words[:-1] if target else words)
    tools.apply_settings()  # relative paths start at the session folder
    if target is None:
        try:
            options = pipeline.check_targets(path)
        except Exception as exc:
            return str(exc)
        target = tools.ask_choice(f"Check {Path(path).name} against which target?", options)
        if target not in options:
            return f"{CHECK_USAGE}\nTargets that take this file: {', '.join(options)}"
    return check_text(json.loads(tools.check({"path": path, "target": target})))


def check_text(result: dict) -> str:
    """A check result in plain words: the verdict, what fails, and what is only advice."""
    if "error" in result:
        return result["error"]
    name = Path(result["file"]).name
    found = result["checks"] if isinstance(result["checks"], list) else []
    fails = [c["message"] for c in found if c["status"] == "fail" and c["hard"]]
    advice = [c["message"] for c in found if c["status"] == "advisory"]
    verdict = "passes every check that blocks an upload" if result["pass"] else "does not pass"
    lines = [f"{name} {verdict} for {result['target']}."]
    lines += [f"  Fix: {message}" for message in fails]
    lines += [f"  Advice: {message}" for message in advice]
    return "\n".join(lines)
