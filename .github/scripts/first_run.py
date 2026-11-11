"""First-run check: call the postkitty tools the way Hermes does, from Hermes' own Python.

Run with the interpreter of the Hermes venv after `hermes plugins install mertkayacs/postkitty --enable`.
Plugins are loaded through Hermes' plugin manager and every tool goes through the tool registry, the
same path the agent loop takes (model_tools.handle_function_call -> tools.registry.registry.dispatch).

Phases (one per invocation, so ffmpeg can be installed in between):
  text                 scan a draft, fit drafts for x, linkedin, threads and bluesky, then read /postkitty
  novideo <clip>       scan a video while ffmpeg is missing; the error and /postkitty doctor say to install ffmpeg
  doctor               /postkitty doctor on a complete setup: text, photos, video and captions all work
  photo <image>        scan, write and make for instagram and x, then check the source photo and a made file by path
  video <clip>         scan, make for tiktok, youtube_shorts and instagram_reel, redo tiktok as speaker and pad,
                       burn captions from an .srt into youtube_shorts, check the source clip by path
Every tool result is written to $FIRST_RUN_LOG_DIR/<phase>-<step>.json.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
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
# Two cues inside the first seconds of the clip, with a gap between them where no caption shows.
CAPTIONS = """1
00:00:01,000 --> 00:00:03,000
postkitty burns this line in

2
00:00:04,500 --> 00:00:06,000
and this one after it
"""
CAPTION_AT, NO_CAPTION_AT = 2.0, 3.75
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
    from hermes_cli.plugin_command_dispatch import invoke_plugin_command
    from hermes_cli.plugins import discover_plugins, get_plugin_command_handler, get_plugin_manager
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

    def slash(raw_args: str) -> str:
        """The reply to ``/postkitty <raw_args>``: the registered handler, called through Hermes' command dispatcher."""
        handler = get_plugin_command_handler("postkitty")
        check(handler is not None, "the /postkitty command is registered")
        if handler is None:
            return ""
        reply = invoke_plugin_command(handler, raw_args, source="cli", session_id="first-run",
                                      session_key="first-run", platform="cli")
        if inspect.iscoroutine(reply):
            reply = asyncio.run(reply)
        command = f"/postkitty {raw_args}".strip()
        print(f"\n== {command} ==\n{reply}")
        check(isinstance(reply, str) and bool(reply.strip()), f"{command} replied with text")
        return reply if isinstance(reply, str) else ""

    return call, slash


def ffprobe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
         "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), {})
    return {"width": video.get("width"), "height": video.get("height"),
            "audio": any(s["codec_type"] == "audio" for s in data["streams"]),
            "duration": float(data.get("format", {}).get("duration") or 0)}


def has_line(text: str, pattern: str) -> bool:
    return re.search("^" + pattern, text, re.MULTILINE) is not None


def failing_checks(result: dict) -> set[str]:
    checks = result.get("checks")
    return {item.get("id") for item in checks if item.get("status") == "fail"} if isinstance(checks, list) else set()


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


def frame_at(video: Path, seconds: float, out: Path) -> Path:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-ss", f"{seconds}", "-i", str(video),
                    "-frames:v", "1", str(out)], check=True, capture_output=True)
    return out


def changed_rows(before: Path, after: Path) -> tuple[float, float, float]:
    """Share of pixels that differ clearly between two frames, and the top and bottom of that area as shares of the height."""
    import cv2  # the plugin's own dependency, present in the environment Hermes prepared at install
    import numpy as np

    first, second = (cv2.imread(str(path), cv2.IMREAD_GRAYSCALE) for path in (before, after))
    changed = cv2.absdiff(first, second) > 64
    rows = np.flatnonzero(changed.any(axis=1))
    if rows.size == 0:
        return 0.0, 0.0, 0.0
    height = changed.shape[0]
    return float(changed.mean()), float(rows[0] / height), float(rows[-1] / height)


def phase_text(call, slash) -> None:
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
    counts = [part.get("count") for part in x.get("parts", [])]
    check(x.get("ok") is True and all(count <= x.get("limit", 0) for count in counts),
          f"every X thread part fits the weighted limit ({counts} of {x.get('limit')})")
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
    advice = write.get("advice")
    check(bool(advice) and Path(advice).is_file(), f"advice file written ({advice})")
    overview = slash("")
    check("postkitty" in overview, "/postkitty says what postkitty is")
    tiktok = slash("tiktok")
    check("tiktok" in tiktok.lower() and "1080x1920" in tiktok, "/postkitty tiktok shows the TikTok target and its size")


def phase_novideo(call, slash, clip: Path) -> None:
    scan = call("postkitty_scan", {"inputs": [str(clip)], "text": DRAFT}, "novideo-1-scan")
    message = json.dumps(scan, ensure_ascii=False)
    check("error" in scan, "scanning a video without ffmpeg returns an error")
    check("ffprobe" in message and "ffmpeg" in message.lower(),
          "the error names ffprobe and tells the user to install ffmpeg")
    check("install" in message.lower(), "the error says to install it")
    report = slash("doctor")
    check(has_line(report, r"no\s+ffmpeg\s+not found$"), "/postkitty doctor reports ffmpeg as not found")
    check(has_line(report, r"\s+fix: Install ffmpeg"), "/postkitty doctor gives the ffmpeg install line")
    check(has_line(report, r"Works now: text, photos\. Not yet: video, captions\."),
          "/postkitty doctor says text and photos work and video and captions wait for ffmpeg")


def phase_doctor(slash) -> None:
    report = slash("doctor")
    check(report.startswith("postkitty doctor"), "/postkitty doctor prints the setup check")
    broken = [line for line in report.splitlines() if line.startswith("no ")]
    check(not broken, f"/postkitty doctor finds nothing to fix ({broken})")
    check(has_line(report, r"Works now: text, photos, video, captions\."),
          "/postkitty doctor says text, photos, video and captions all work")


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
    outside = call("postkitty_check", {"path": str(photo), "target": "instagram_feed"}, "photo-5-check-source")
    expect_no_error(outside, "check of the source photo")
    failing = failing_checks(outside)
    check(outside.get("pass") is False and "image.aspect" in failing,
          f"the uncropped source photo fails instagram_feed on its aspect ratio (failing: {sorted(failing)})")
    made = call("postkitty_check", {"path": str(job_dir / "ready" / "x" / "image.jpg"), "target": "x_image"},
                "photo-6-check-path")
    expect_no_error(made, "check of a made file by path")
    check(made.get("pass") is True, f"the made X image passes x_image when checked by path ({made.get('checks')})")


def check_captions(call, job: str, job_dir: Path, max_duration: float) -> None:
    """Burn an .srt into the finished YouTube Short and compare frames with the render that had no captions."""
    shorts = job_dir / "ready" / "youtube" / "shorts.mp4"
    plain = {t: frame_at(shorts, t, LOG_DIR / f"video-shorts-plain-{t}.png") for t in (CAPTION_AT, NO_CAPTION_AT)}
    srt = (LOG_DIR / "first-run.srt").resolve()
    srt.write_text(CAPTIONS, encoding="utf-8")
    redo = call("postkitty_redo", {"job": job, "target": "youtube_shorts", "captions": str(srt)}, "video-4-redo-captions")
    expect_no_error(redo, "redo with captions")
    rows = redo.get("targets", [])
    check_rendered(job_dir, rows, {"youtube_shorts"}, video=True, max_duration=max_duration)
    shown = (rows[0].get("captions") or {}).get("shown") if rows else None
    check(shown == 2, f"redo reports both caption cues as burned in (captions.shown={shown})")
    if not shorts.is_file():
        return
    share, top, bottom = changed_rows(plain[CAPTION_AT], frame_at(shorts, CAPTION_AT, LOG_DIR / "video-shorts-cue.png"))
    check(share >= 0.002, f"caption text is visible in the frame at {CAPTION_AT} s ({share:.2%} of the pixels changed)")
    check(0.4 <= top and bottom <= 0.9,
          f"the caption sits in the lower part of the frame, clear of the bottom edge ({top:.0%} to {bottom:.0%} of the height)")
    share, _, _ = changed_rows(plain[NO_CAPTION_AT], frame_at(shorts, NO_CAPTION_AT, LOG_DIR / "video-shorts-gap.png"))
    check(share <= 0.0005, f"no caption is drawn between the cues at {NO_CAPTION_AT} s ({share:.2%} of the pixels changed)")


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
    check_captions(call, scan["job"], job_dir, source["duration"] + 0.5)
    verify = call("postkitty_check", {"job": scan["job"]}, "video-5-check")
    expect_no_error(verify, "check")
    check(verify.get("all_pass") is True, "postkitty_check passes every ready file")
    outside = call("postkitty_check", {"path": str(clip), "target": "tiktok"}, "video-6-check-source")
    expect_no_error(outside, "check of the source clip")
    failing = failing_checks(outside)
    check(outside.get("pass") is False and {"video.width", "video.height"} <= failing,
          f"the landscape source clip fails tiktok on its size (failing: {sorted(failing)})")


def main(argv: list[str]) -> int:
    phase = argv[1] if len(argv) > 1 else ""
    if phase not in ("text", "novideo", "doctor", "photo", "video"):
        print(__doc__)
        return 2
    call, slash = boot()
    if phase == "text":
        phase_text(call, slash)
    elif phase == "novideo":
        phase_novideo(call, slash, Path(argv[2]))
    elif phase == "doctor":
        phase_doctor(slash)
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
