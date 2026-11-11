"""First-run check: call the postkitty tools the way Hermes does, from Hermes' own Python.

Run with the interpreter of the Hermes venv after `hermes plugins install mertkayacs/postkitty --enable`.
Plugins are loaded through Hermes' plugin manager and every tool goes through the tool registry, the
same path the agent loop takes (model_tools.handle_function_call -> tools.registry.registry.dispatch).

Phases (one per invocation, so ffmpeg can be installed in between):
  text                 scan a draft, then fit drafts for x, linkedin, threads and bluesky
  novideo <clip>       scan a video while ffmpeg is missing; expect a message that says to install ffmpeg
  photo <image>        scan, write and make for instagram and x
  video <clip>         scan, make for tiktok, youtube_shorts and instagram_reel, redo tiktok as speaker and pad
Every tool result is written to $FIRST_RUN_LOG_DIR/<phase>-<step>.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

LOG_DIR = Path(os.environ.get("FIRST_RUN_LOG_DIR", "first-run-logs"))
TOOLS = ("postkitty_scan", "postkitty_write", "postkitty_make", "postkitty_redo", "postkitty_check")
SIZES = {
    "instagram_feed": (1080, 1350), "instagram_story": (1080, 1920), "x_image": (1600, 900),
    "tiktok": (1080, 1920), "youtube_shorts": (1080, 1920), "instagram_reel": (1080, 1920),
}
DRAFT = ("Our new epsiode is out! We talk abot how to reframe landscape video for vertical feeds and why "
         "every face has to stay in frame. Listen here: https://example.com/episodes/42 #podcast #video \U0001F3A7")
LONG_X = ("Episode 42 is live. " * 20).strip() + " https://example.com/episodes/42"
DRAFTS = {
    "x": LONG_X,
    "linkedin": "Episode 42 is live. We talk about reframing landscape video for vertical feeds and why every "
                "face has to stay in frame. Listen here: https://example.com/episodes/42",
    "threads": "Episode 42 is out. Reframing landscape video for vertical feeds, and why faces matter.",
    "bluesky": "Episode 42 is out. Reframing landscape video for vertical feeds, and why faces matter.",
}

_failures: list[str] = []


def check(condition: bool, message: str) -> None:
    print(("ok   " if condition else "FAIL ") + message)
    if not condition:
        _failures.append(message)


def boot():
    from hermes_cli.plugins import discover_plugins, get_plugin_manager
    from tools.registry import registry

    discover_plugins()
    manager = get_plugin_manager()
    names = sorted(registry.get_tool_names_for_toolset("postkitty"))
    print("tools registered by the postkitty toolset:", names)
    check(names == sorted(TOOLS), "all five postkitty tools are registered")
    loaded = sorted(manager._plugins)
    print("plugins loaded by the manager:", loaded)
    check("postkitty" in loaded, "the plugin manager loaded postkitty")

    def call(tool: str, args: dict, step: str) -> dict:
        raw = registry.dispatch(tool, args, scope=manager.scope_key,
                                task_id="first-run", session_id="first-run", user_task="first run")
        check(isinstance(raw, str), f"{tool} returned a string result")
        result = json.loads(raw)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (LOG_DIR / f"{step}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\n== {step}: {tool} ==")
        print(json.dumps(result, indent=2, ensure_ascii=False)[:3000])
        return result

    return call


def ffprobe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
         "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), {})
    return {"width": video.get("width"), "height": video.get("height"),
            "audio": any(s["codec_type"] == "audio" for s in data["streams"]),
            "duration": float(data.get("format", {}).get("duration") or 0)}


def expect_no_error(result: dict, what: str) -> None:
    check("error" not in result, f"{what} has no error key" + (f": {result.get('error')}" if "error" in result else ""))


def check_rendered(job_dir: Path, rows: list[dict], expected: set[str], *, video: bool, max_duration: float) -> None:
    got = {row["target"] for row in rows}
    check(expected <= got, f"targets rendered include {sorted(expected)} (got {sorted(got)})")
    for row in rows:
        target = row["target"]
        check(row["status"] in ("ready", "repaired"), f"{target} status is ready or repaired (got {row['status']}, "
                                                      f"problems={row.get('problems')}, reason={row.get('reason')})")
        file = row.get("file")
        check(bool(file) and file.startswith("ready/"), f"{target} file sits under ready/ ({file})")
        if not file:
            continue
        path = job_dir / file
        check(path.is_file() and path.stat().st_size > 0, f"{target} file exists and is not empty: {path}")
        if not path.is_file():
            continue
        info = ffprobe(path)
        width, height = SIZES.get(target, (None, None))
        check((info["width"], info["height"]) == (width, height),
              f"{target} ffprobe size is {width}x{height} (got {info['width']}x{info['height']})")
        if video:
            check(3.0 <= info["duration"] <= max_duration,
                  f"{target} duration within 3 s and {max_duration} s (got {info['duration']:.2f} s)")
            check(info["audio"], f"{target} keeps an audio stream")
            cover = row.get("cover")
            check(bool(cover) and (job_dir / cover).is_file(), f"{target} has a cover frame ({cover})")


def phase_text(call) -> None:
    scan = call("postkitty_scan", {"text": DRAFT, "platforms": ["x", "linkedin", "threads", "bluesky"]}, "text-1-scan")
    expect_no_error(scan, "scan")
    check(bool(scan.get("job")), "scan returned a job id")
    stats = scan.get("text") or {}
    check(bool(stats), "scan returned text stats for the draft")
    write = call("postkitty_write", {"job": scan["job"], "drafts": DRAFTS, "advice": {
        "topic": "Episode 42", "audience": "video makers", "tone": "plain", "key_message": "new episode"}},
        "text-2-write")
    expect_no_error(write, "write")
    platforms = write.get("platforms", {})
    for name in DRAFTS:
        check(name in platforms, f"write reported {name}")
    x = platforms.get("x", {})
    check(x.get("split") is True and len(x.get("parts", [])) > 1,
          f"overlong X draft was split into a thread ({len(x.get('parts', []))} parts)")
    check(x.get("ok") is True, "every X thread part fits the weighted limit")
    check(any(f.endswith("thread.txt") for f in x.get("files", [])), "X thread written to thread.txt")
    for name in ("linkedin", "threads", "bluesky"):
        row = platforms.get(name, {})
        check(row.get("ok") is True, f"{name} draft fits ({row.get('count')} {row.get('unit')} of {row.get('limit')})")
        check(any(f.endswith("post.txt") for f in row.get("files", [])), f"{name} post written to post.txt")
    check(write.get("all_ok") is True, "write reports all_ok")
    job_dir = Path(scan["job_dir"])
    for name in DRAFTS:
        for file in platforms.get(name, {}).get("files", []):
            check((job_dir / file).is_file(), f"{file} exists on disk")
    check((job_dir / "advice.md").is_file() or bool(write.get("advice")), "advice file written")


def phase_novideo(call, clip: Path) -> None:
    scan = call("postkitty_scan", {"inputs": [str(clip)], "text": DRAFT}, "novideo-1-scan")
    message = json.dumps(scan, ensure_ascii=False)
    check("error" in scan, "scanning a video without ffmpeg returns an error")
    check("ffprobe" in message and "ffmpeg" in message.lower(),
          "the error names ffprobe and tells the user to install ffmpeg")
    check("install" in message.lower(), "the error says to install it")


def phase_photo(call, photo: Path) -> None:
    scan = call("postkitty_scan", {"inputs": [str(photo)], "text": DRAFT, "platforms": ["instagram", "x"]},
                "photo-1-scan")
    expect_no_error(scan, "scan")
    inputs = scan.get("inputs", [])
    check(len(inputs) == 1 and inputs[0].get("kind") == "image", "the photo was probed as an image")
    people = inputs[0].get("people") if inputs else None
    print(f"people found in {photo.name}: {people}")
    check(isinstance(people, int) and people >= 2, f"the detector found people in the photo ({people})")
    if people != 5:
        print(f"::notice::{photo.name} is described as a photo of five people; the detector found {people}")
    check(not scan.get("notes"), f"scan has no notes ({scan.get('notes')})")
    planned = {t["id"] for t in scan.get("plan", [])}
    check({"instagram_feed", "x_image"} <= planned, f"plan covers instagram_feed and x_image ({sorted(planned)})")
    write = call("postkitty_write", {"job": scan["job"], "drafts": {"instagram": DRAFTS["threads"], "x": DRAFTS["threads"]},
                                   "alt_text": {photo.name: "Five people standing in a row in a bright office."}},
                "photo-2-write")
    expect_no_error(write, "write")
    check(write.get("alt_text_unmatched") is None, "alt text matched the input file")
    make = call("postkitty_make", {"job": scan["job"], "targets": ["instagram", "x"]}, "photo-3-make")
    expect_no_error(make, "make")
    job_dir = Path(make["job_dir"])
    check_rendered(job_dir, make.get("targets", []), {"instagram_feed", "x_image"}, video=False, max_duration=0)
    check((job_dir / "board.html").is_file(), "board.html written")
    verify = call("postkitty_check", {"job": scan["job"]}, "photo-4-check")
    expect_no_error(verify, "check")
    check(verify.get("all_pass") is True, "postkitty_check passes every ready file")


def phase_video(call, clip: Path) -> None:
    scan = call("postkitty_scan", {"inputs": [str(clip)], "text": DRAFT,
                                   "platforms": ["tiktok", "youtube", "instagram"]}, "video-1-scan")
    expect_no_error(scan, "scan")
    inputs = scan.get("inputs", [])
    check(len(inputs) == 1 and inputs[0].get("kind") == "video", "the clip was probed as a video")
    people = inputs[0].get("people") if inputs else None
    print(f"people tracked in {clip.name}: {people}, shots: {inputs[0].get('shots') if inputs else None}")
    check(isinstance(people, int) and people >= 2, f"two people were tracked in the clip ({people})")
    check(not scan.get("notes"), f"scan has no notes ({scan.get('notes')})")
    targets = ["tiktok", "youtube_shorts", "instagram_reel"]
    make = call("postkitty_make", {"job": scan["job"], "targets": targets}, "video-2-make")
    expect_no_error(make, "make")
    job_dir = Path(make["job_dir"])
    source = ffprobe(clip)
    check_rendered(job_dir, make.get("targets", []), set(targets), video=True, max_duration=source["duration"] + 0.5)
    check((job_dir / "board.html").is_file(), "board.html written")
    for layout in ("speaker", "pad"):
        redo = call("postkitty_redo", {"job": scan["job"], "target": "tiktok", "layout": layout}, f"video-3-redo-{layout}")
        expect_no_error(redo, f"redo {layout}")
        rows = redo.get("targets", [])
        check_rendered(job_dir, rows, {"tiktok"}, video=True, max_duration=source["duration"] + 0.5)
        mode = (rows[0].get("layout") or {}).get("mode") if rows else None
        check(mode == layout, f"redo tiktok used the {layout} layout (got {mode})")
    verify = call("postkitty_check", {"job": scan["job"]}, "video-4-check")
    expect_no_error(verify, "check")
    check(verify.get("all_pass") is True, "postkitty_check passes every ready file")


def main(argv: list[str]) -> int:
    phase = argv[1] if len(argv) > 1 else ""
    if phase not in ("text", "novideo", "photo", "video"):
        print(__doc__)
        return 2
    call = boot()
    if phase == "text":
        phase_text(call)
    elif phase == "novideo":
        phase_novideo(call, Path(argv[2]))
    elif phase == "photo":
        phase_photo(call, Path(argv[2]))
    elif phase == "video":
        phase_video(call, Path(argv[2]))
    print()
    if _failures:
        print(f"{len(_failures)} check(s) failed in phase {phase}:")
        for item in _failures:
            print("  - " + item)
        return 1
    print(f"phase {phase}: every check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
