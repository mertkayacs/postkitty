"""Tests for the review board lane (engine/board.py).

Builds a fake job with Pillow images, a tiny ffmpeg video and a manifest that
covers every target status, then checks write_board's outputs.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image
from postkitty.engine.board.board import layout_note, write_board

CAP = 6 * 1024 * 1024


def _make_image(path: Path, size: tuple[int, int], color: str) -> None:
    Image.new("RGB", size, color).save(path, quality=90)


def _make_video(path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
         "color=c=blue:s=160x90:r=10:d=2", "-pix_fmt", "yuv420p",
         str(path)],
        check=True, capture_output=True,
    )


def _manifest(job_dir: Path) -> dict:
    ready = job_dir / "ready"
    (ready / "instagram").mkdir(parents=True, exist_ok=True)
    (ready / "x").mkdir(parents=True, exist_ok=True)
    (ready / "threads").mkdir(parents=True, exist_ok=True)
    (ready / "bluesky").mkdir(parents=True, exist_ok=True)
    _make_image(ready / "instagram" / "feed.jpg", (1080, 1350), "orange")
    _make_image(ready / "instagram" / "reel_cover.jpg", (1080, 1920), "pink")
    _make_video(ready / "instagram" / "reel.mp4")
    _make_video(ready / "threads" / "post.mp4")
    return {
        "schema": "postkitty.manifest/1",
        "job": "demo-job",
        "created": "2026-11-08T12:00:00+00:00",
        "version": "0.1.0",
        "inputs": [{"id": "in1", "path": "in.jpg", "kind": "video", "sha256": "abc",
                    "width": 160, "height": 90, "duration": 10.0, "fps": 10.0,
                    "has_audio": False}],
        "advice": {
            "topic": "Launch <script>alert(1)</script>",
            "audience": "testers",
            "tone": "dry",
            "key_message": "The board escapes everything.",
            "ranking": [{"platform": "instagram", "reason": "visual first"},
                        {"platform": "x", "reason": "fast text"}],
            "tips": ["Keep it short", "Check the fold"],
        },
        "copy": {
            "instagram": {"parts": ["Caption one", "Caption two"],
                          "counts": [10, 11], "unit": "codepoints", "limit": 2200, "ok": True},
            "threads": {"parts": ["Thread part one <script>", "Thread part two"],
                        "counts": [19, 17], "unit": "codepoints", "limit": 500, "ok": True},
        },
        "alt_text": {"instagram_reel": "A giraffe eating leaves."},
        "targets": [
            {
                "id": "instagram_feed", "platform": "instagram", "kind": "image",
                "status": "ready", "input": "in1",
                "file": "ready/instagram/feed.jpg", "width": 1080, "height": 1350,
                "layout": {"mode": "crop", "note": ""},
                "checks": [
                    {"id": "image.dimensions", "target": "instagram_feed", "status": "pass",
                     "hard": True, "measured": {"width": 1080, "height": 1350},
                     "expected": {"width": 1080, "height": 1350},
                     "message": "The file is 1080x1350; instagram_feed requires 1080x1350.",
                     "source_url": "https://example.com/spec", "source_scope": "api",
                     "checked_on": "2026-11-07"},
                ],
                "repairs": [],
            },
            {
                "id": "instagram_reel", "platform": "instagram", "kind": "video",
                "status": "repaired", "input": "in1",
                "file": "ready/instagram/reel.mp4", "cover": "ready/instagram/reel_cover.jpg",
                "width": 1080, "height": 1920, "duration": 41.0,
                "layout": {"mode": "split", "note": "Split: two speakers cannot share 9:16"},
                "trim": [0.0, 41.0],
                "checks": [
                    {"id": "video.duration_max", "target": "instagram_reel", "status": "advisory",
                     "hard": False, "measured": 41.0, "expected": 60,
                     "message": "The video is 41.0 s; the maximum is 60 s.",
                     "source_url": "https://example.com/spec", "source_scope": "official",
                     "checked_on": "2026-11-07"},
                ],
                "repairs": [{"check": "video.bytes_max", "action": "lowered bitrate", "ok": True}],
                "render_seconds": 12.3,
            },
            {
                "id": "x_video", "platform": "x", "kind": "video", "status": "failed",
                "input": "in1", "file": None, "width": 1920, "height": 1080, "duration": 150.0,
                "layout": {"mode": "crop", "note": ""},
                "checks": [
                    {"id": "video.duration_max", "target": "x_video", "status": "fail",
                     "hard": True, "measured": 150.0, "expected": 140,
                     "message": "The video is 150.0 s; the maximum is 140 s.",
                     "source_url": "https://help.x.com/en/using-x/x-videos",
                     "source_scope": "official", "checked_on": "2026-11-07"},
                ],
                "repairs": [],
            },
            {
                "id": "threads_video", "platform": "threads", "kind": "video",
                "status": "ready", "input": "in1",
                "file": "ready/threads/post.mp4", "width": 1080, "height": 1920, "duration": 30.0,
                "layout": {"mode": "pad", "note": ""},
                "checks": [],
                "repairs": [],
            },
            {
                "id": "bluesky_image", "platform": "bluesky", "kind": "image",
                "status": "skipped", "input": "in1", "file": None, "width": 1080,
                "height": 1350, "layout": {"mode": "auto", "note": ""},
                "checks": [],
                "repairs": [],
            },
        ],
    }


def _ready_files(job_dir: Path) -> list[str]:
    out = []
    ready = job_dir / "ready"
    for path in sorted(ready.rglob("*")):
        if path.is_file():
            out.append(path.relative_to(job_dir).as_posix())
    return out


def test_write_board_produces_all_deliverables(tmp_path):
    job_dir = tmp_path / "job"
    manifest = _manifest(job_dir)
    paths = write_board(job_dir, manifest)
    assert set(paths) == {"board", "board_inline", "contact", "board_inline_size"}
    for key in ("board", "board_inline", "contact"):
        assert Path(paths[key]).is_file()
    assert paths["contact"].endswith("contact.png")
    assert isinstance(paths["board_inline_size"], int)
    assert paths["board_inline_size"] > 0
    assert paths["board_inline_size"] <= CAP

    with Image.open(paths["contact"]) as im:
        assert im.size[0] == 1600

    html = Path(paths["board"]).read_text(encoding="utf-8")
    inline_html = Path(paths["board_inline"]).read_text(encoding="utf-8")

    # Injected markup must never appear raw; escaped form must be present.
    assert "<script>alert" not in html and "<script>alert" not in inline_html
    assert "&lt;script&gt;" in html and "&lt;script&gt;" in inline_html

    # Every ready/ file is referenced in board.html.
    for rel in _ready_files(job_dir):
        assert rel in html, f"{rel} missing from board.html"

    # Hard failures impossible to miss; advisory items present and calm.
    assert 'role="alert"' in html
    assert "The video is 150.0 s; the maximum is 140 s." in html
    assert "advisory" in html.lower()
    assert "<details class=\"checks\" open>" in html

    # Media, layout note, repairs and actions.
    assert "ready/instagram/reel.mp4" in html
    assert 'controls muted playsinline preload="metadata"' in html
    assert "lowered bitrate" in html.lower()
    assert "Split: two speakers cannot share 9:16" in html
    assert 'data-hermes-send=' in html
    assert ">Open</a>" in html and "Adjust" in html
    assert "Focus person" not in html  # the fake input has no people count

    # Previews are never cropped: exact aspect, object-fit contain.
    assert "--ar: 1080 / 1350" in html and "--ar: 1080 / 1920" in html
    css = (Path(__file__).resolve().parent.parent / "engine" / "board" / "templates" / "board.css")
    css_text = css.read_text(encoding="utf-8")
    assert "object-fit: contain" in css_text and "object-fit: cover" not in css_text
    assert "aspect-ratio: var(--ar)" in css_text

    # Copy: one card per platform, each caption exactly once.
    assert html.count(">Caption one") == 1
    assert html.count("Part 1 of 2") == 2  # instagram and threads, once each
    assert "Copy text" in html and "Instagram" in html
    assert "10 of 2200 characters" in html
    assert 'data-copy-caption' not in html

    # Alt text sits under its card.
    assert "A giraffe eating leaves." in html

    # Inline board is self-contained: data URIs, no video element.
    assert "data:image/jpeg;base64," in inline_html
    assert "<video" not in inline_html
    assert "reel.mp4" in inline_html


def test_check_values_are_human_readable():
    from postkitty.engine.board.board import checks_html
    checks = [
        {"id": "video.container", "status": "pass", "hard": True,
         "measured": ["mov", "mp4"], "expected": ["mp4", "mov"], "message": "ok"},
        {"id": "video.fps_min", "status": "pass", "hard": True, "measured": 24.0,
         "expected": 23, "message": "m", "source_url": "https://www.postman.com/meta/x",
         "checked_on": "2026-11-07"},
        {"id": "video.fps_max", "status": "pass", "hard": True, "measured": 24.0,
         "expected": 60, "message": "m"},
        {"id": "video.bytes_max", "status": "pass", "hard": True, "measured": 11763243,
         "expected": 1000000000, "message": "m"},
        {"id": "video.bitrate_max", "status": "pass", "hard": True, "measured": 6138492,
         "expected": 25000000, "message": "m"},
    ]
    out = checks_html(checks)
    assert "4 checks passed" in out
    assert "measured 24 fps" in out and "limit 23 to 60 fps" in out
    assert "measured mov, mp4" in out
    assert "11.8 MB" in out and "6.1 Mbps" in out
    assert "source (" in out and "Meta" in out and "checked 7 Nov 2026" in out
    assert "[" not in out.replace("[]", "")
    assert "<details class=\"checks\" open>" not in out


def test_skipped_check_is_not_shown_as_passed():
    from postkitty.engine.board.board import checks_html
    checks = [
        {"id": "image.width", "status": "pass", "hard": True, "measured": 1080, "expected": 1080,
         "message": "The image width is exact."},
        {"id": "frame.subjects_inside", "status": "skipped", "hard": False, "measured": None,
         "expected": 1.0, "message": "Subject framing data is unavailable for this file."},
    ]
    out = checks_html(checks)
    assert "Everyone stays inside the frame." not in out
    assert "Subject framing data is unavailable for this file." in out
    assert '<span class="dot skipped">' in out
    assert "1 check passed, 1 skipped" in out
    assert "2 checks passed" not in out


def test_speaker_layout_note_is_readable() -> None:
    assert layout_note({"mode": "speaker", "note": "cuts to whoever is talking"}) == (
        "Follows the speaker: cuts to whoever is talking."
    )


def test_adjust_menu_only_offers_what_applies(tmp_path):
    job_dir = tmp_path / "job"
    manifest = _manifest(job_dir)
    manifest["inputs"][0]["people"] = 2
    manifest["targets"][1]["layout"] = {"mode": "crop", "note": ""}
    html = Path(write_board(job_dir, manifest)["board"]).read_text(encoding="utf-8")
    assert "Focus person 1" in html and "Focus person 2" in html
    assert "Focus person 3" not in html
    assert "Split screen" in html  # vertical reel target with two people
    assert "Trim" in html


def test_platform_names_are_cased(tmp_path):
    from postkitty.engine.board.board import platform_name
    assert platform_name("tiktok") == "TikTok"
    assert platform_name("youtube") == "YouTube"
    assert platform_name("x") == "X"
    assert platform_name("linkedin") == "LinkedIn"


def test_contact_sheet_keeps_thumbnail_aspect_and_centers_it(tmp_path):
    import numpy as np
    from postkitty.engine.board.board import TEMPLATES, write_contact_png
    job_dir = tmp_path / "job"
    (job_dir / "ready" / "x").mkdir(parents=True)
    _make_image(job_dir / "ready" / "x" / "image.jpg", (1920, 1080), "orange")
    manifest = {"job": "wide", "created": "", "targets": [
        {"id": "x_image", "platform": "x", "kind": "image", "status": "ready",
         "file": "ready/x/image.jpg", "width": 1920, "height": 1080}]}

    path = write_contact_png(job_dir, manifest, TEMPLATES / "pucci-mark-64.png")

    with Image.open(path) as sheet:
        pixels = np.asarray(sheet.convert("RGB")).astype(int)
    orange = (pixels[..., 0] > 230) & (100 < pixels[..., 1]) & (pixels[..., 1] < 200) & (pixels[..., 2] < 60)
    rows, columns = np.nonzero(orange)
    width = columns.max() - columns.min() + 1
    height = rows.max() - rows.min() + 1
    assert abs(width / height - 16 / 9) < 0.05
    assert width > 300
    tile_center = 40 + ((1600 - 80 - 48) // 3) / 2
    assert abs((columns.max() + columns.min()) / 2 - tile_center) < 3


def test_missing_media_file_gets_an_empty_frame(tmp_path):
    job_dir = tmp_path / "job"
    manifest = _manifest(job_dir)
    manifest["targets"].append(
        {"id": "linkedin_image", "platform": "linkedin", "kind": "image", "status": "ready",
         "input": "in1", "file": "ready/linkedin/image.jpg", "width": 1080, "height": 1080,
         "layout": {"mode": "crop", "note": ""}, "checks": [], "repairs": []})
    paths = write_board(job_dir, manifest)
    html = Path(paths["board"]).read_text(encoding="utf-8")
    inline_html = Path(paths["board_inline"]).read_text(encoding="utf-8")
    assert 'src=""' not in inline_html
    assert 'src="ready/linkedin/image.jpg"' not in html
    assert 'href="ready/linkedin/image.jpg"' in html


def test_write_board_handles_empty_job(tmp_path):
    job_dir = tmp_path / "job"
    manifest = {"schema": "postkitty.manifest/1", "job": "empty",
                "created": "2026-11-08T12:00:00+00:00", "targets": []}
    paths = write_board(job_dir, manifest)
    for key in ("board", "board_inline", "contact"):
        assert Path(paths[key]).is_file()
    assert Path(paths["contact"]).stat().st_size > 0


HOSTILE = '<script>alert("x")</script> & "quotes" \'single\' <img src=x onerror=alert(1)> Üç 写真'


def _hostile_manifest(job_dir: Path) -> dict:
    """Every string a user or the model controls carries markup, quotes, an ampersand and non-ASCII letters."""
    manifest = _manifest(job_dir)
    manifest["job"] = f"job {HOSTILE}"
    manifest["inputs"][0]["path"] = f"/photos/{HOSTILE}.jpg"
    manifest["advice"] = {"topic": "", "audience": HOSTILE, "tone": HOSTILE, "key_message": HOSTILE,
                          "ranking": [{"platform": HOSTILE, "reason": HOSTILE}], "tips": [HOSTILE]}
    manifest["copy"]["instagram"] = {"parts": [HOSTILE, HOSTILE], "counts": [9, 9], "unit": HOSTILE, "limit": 2200,
                                     "ok": True}
    manifest["alt_text"] = {"instagram_feed": HOSTILE}
    for target in manifest["targets"]:
        target["layout"] = {"mode": "crop", "note": HOSTILE}
        target["repairs"] = [{"check": HOSTILE, "action": HOSTILE, "ok": False}]
        target["checks"] = [{"id": HOSTILE, "status": "fail", "hard": True, "measured": HOSTILE, "expected": HOSTILE,
                             "message": HOSTILE, "source_url": f"https://example.com/?q={HOSTILE}",
                             "checked_on": HOSTILE}]
    manifest["targets"][-1].update(status=HOSTILE, reason=HOSTILE)
    return manifest


def test_every_user_controlled_string_is_escaped(tmp_path):
    job_dir = tmp_path / "job"
    paths = write_board(job_dir, _hostile_manifest(job_dir))
    for key in ("board", "board_inline"):
        html = Path(paths[key]).read_text(encoding="utf-8")
        body = html[html.index("<body>"):html.rindex("<script>")]
        assert "<script" not in body and "<img src=x" not in body and "onerror=alert(1)>" not in body
        assert 'alert("x")' not in body and "'single'" not in body
        assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; &quot;quotes&quot; &#x27;single&#x27;" in body
        assert "Üç 写真" in body


def test_the_board_loads_nothing_from_the_network(tmp_path):
    import re

    job_dir = tmp_path / "job"
    paths = write_board(job_dir, _manifest(job_dir))
    for key in ("board", "board_inline"):
        html = Path(paths[key]).read_text(encoding="utf-8")
        loads = re.findall(r"""(?:src|poster|srcset)=["']([^"']*)|url\(([^)]*)\)|@import\s+([^;]+)|<link[^>]*href=["']([^"']*)""", html)
        remote = [value for match in loads for value in match if value.strip("\"' ").startswith(("http", "//"))]
        assert remote == []


def test_a_skipped_target_says_why(tmp_path):
    job_dir = tmp_path / "job"
    manifest = _manifest(job_dir)
    manifest["targets"][-1] = {"id": "bluesky_image", "platform": "bluesky", "kind": "image", "input": "in1",
                               "override": {}, "status": "skipped", "checks": [], "repairs": [],
                               "reason": "The image engine needs the Python package 'cv2'."}
    html = Path(write_board(job_dir, manifest)["board"]).read_text(encoding="utf-8")
    assert "The image engine needs the Python package &#x27;cv2&#x27;." in html


def test_the_logo_carries_no_mascot_wording_and_no_repeated_ids(tmp_path):
    import re

    job_dir = tmp_path / "job"
    html = Path(write_board(job_dir, _manifest(job_dir))["board"]).read_text(encoding="utf-8")
    assert "mascot" not in html.lower() and 'aria-label="postkitty"' in html
    ids = re.findall(r"""\sid=["']([^"']+)""", html)
    assert len(ids) == len(set(ids))


def test_long_unbroken_advice_text_wraps_inside_its_card():
    css = (Path(__file__).resolve().parent.parent / "engine" / "board" / "templates" / "board.css").read_text(encoding="utf-8")
    advice = css[css.index(".advice {"):css.index("}", css.index(".advice {"))]
    assert "overflow-wrap: anywhere" in advice
    assert ".advice > div { min-width: 0;" in css
