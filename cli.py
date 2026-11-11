"""The ``hermes postkitty`` terminal command: the scriptable path for cron jobs and release automation.

It calls ``engine.pipeline`` directly, so it needs no model. ``make`` uses the text as given: it counts
and splits it per platform and never rewrites it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import command, tools
from .engine import doctor, pipeline, probe
from .engine.detect import models
from .engine.text import fit

USAGE = "Usage: hermes postkitty <make|check|platforms|doctor> ..., see hermes postkitty --help"


def setup(subparser: argparse.ArgumentParser) -> None:
    subs = subparser.add_subparsers(dest="postkitty_command")
    subs.add_parser("doctor", help="Check the setup: Python packages, ffmpeg, the face model, the output folder")
    listing = subs.add_parser("platforms", help="List every target with its size and limits")
    listing.add_argument("name", nargs="?", default="", help="One platform, for example tiktok")
    check = subs.add_parser("check", help="Check a file against one target without rendering")
    check.add_argument("file")
    check.add_argument("--target", help="Target id or platform name, for example tiktok")
    make = subs.add_parser("make", help="Make and check every file for one post")
    make.add_argument("files", nargs="*", help="Photos or a landscape video")
    text = make.add_mutually_exclusive_group()
    text.add_argument("--text", help="The post text, used as given")
    text.add_argument("--text-file", help="A UTF-8 file that holds the post text")
    make.add_argument("--platforms", help="Comma-separated platform names, for example x,linkedin")
    make.add_argument("--layout", choices=pipeline.LAYOUTS, help="One layout for every target")
    make.add_argument("--focus", help="auto, person:N, left, center, right or x:0.0-1.0")
    make.add_argument("--captions", help="An .srt or .vtt file to burn into every video target")
    make.add_argument("--out", help="Folder for the job; default: the output folder setting")


def run(args: argparse.Namespace) -> int:
    """Run one subcommand, print the result and return the exit code (0 only when everything is ready)."""
    try:
        with tools.session(), pipeline.scoped(output_dir=getattr(args, "out", None)):
            sub = getattr(args, "postkitty_command", None)
            if sub == "platforms":
                print(command.targets(args.name))
                return 0
            if sub == "doctor":
                report = doctor.report(pipeline.jobs_dir())
                print(doctor.render_text(report))
                return 0 if report["ok"] else 1
            if sub == "check":
                return _check(args)
            if sub == "make":
                return _make(args)
    except (ValueError, KeyError, FileNotFoundError, probe.ProbeError, pipeline.Unavailable, models.ModelUnavailable) as exc:
        print(f"postkitty: {tools.message(exc)}", file=sys.stderr)
        return 2
    print(USAGE)
    return 2


def _check(args: argparse.Namespace) -> int:
    target = args.target
    if not target:
        options = pipeline.check_targets(args.file)
        if len(options) != 1:
            print(f"Give --target, one of: {', '.join(options)}", file=sys.stderr)
            return 2
        target = options[0]
    result = pipeline.check({"path": args.file, "target": target})
    print(command.check_text(result))
    return 0 if result["pass"] else 1


def _make(args: argparse.Namespace) -> int:
    text = Path(args.text_file).expanduser().read_text(encoding="utf-8") if args.text_file else (args.text or "")
    wanted = [name.strip() for name in (args.platforms or "").split(",") if name.strip()]
    scan = pipeline.scan({"inputs": args.files, "text": text, "platforms": wanted})
    ready = True
    for note in scan["notes"]:
        print(f"note: {note}")
    if text.strip():
        written = pipeline.write({"job": scan["job"], "drafts": dict.fromkeys(scan["fit"], text)})
        for name, report in written["platforms"].items():
            fits = report["ok"] or report["enforcement"] != "hard"
            state = "ready" if fits else f"over by {report['overflow']} {fit.unit_words(report['unit'])}"
            print(f"{name + ' text':<20} {state:<10} {', '.join(report['files'])}")
            ready = ready and fits
    override = {key: value for key in ("layout", "focus") if (value := getattr(args, key))}
    videos = {entry["id"] for entry in scan["inputs"] if entry["kind"] == "video"}
    overrides = {}
    for plan in scan["plan"]:
        captions = {"captions": args.captions} if args.captions and plan["input"] in videos else {}
        if override or captions:
            overrides[plan["id"]] = {**override, **captions}
    made = pipeline.make({"job": scan["job"], "overrides": overrides})
    for row in made["targets"]:
        detail = row.get("file") or row.get("reason") or "; ".join(row.get("problems", []))
        print(f"{row['target']:<20} {row['status']:<10} {detail}")
        ready = ready and row["status"] in {"ready", "repaired"}
    print(f"job folder: {scan['job_dir']}")
    return 0 if ready else 1
