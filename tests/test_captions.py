from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from engine.photo.framing import Box
from engine.video import render as video_make
from engine.video.captions import Captions, ass_document, load_captions
from engine.video.render import VideoPlan, export_cover, plan_video, render_video
from engine.video.scan import VideoScan


@dataclass(frozen=True)
class Spec:
    value: Any


@dataclass(frozen=True)
class Target:
    id: str
    width: int
    height: int
    limits: dict[str, Spec] = field(default_factory=dict)

    @property
    def aspect(self) -> float:
        return self.width / self.height


@dataclass(frozen=True)
class InputInfo:
    path: Path
    sha256: str
    width: int
    height: int
    duration: float
    fps: float
    has_audio: bool = False


REEL = Target("instagram_reel", 1080, 1920, {"safe_area": Spec({"top": 0.14, "bottom": 0.35, "side": 0.06})})


def _dialogue(document: str) -> list[tuple[str, str, str]]:
    rows = [line.split(",", 9) for line in document.splitlines() if line.startswith("Dialogue:")]
    return [(row[1], row[2], row[9]) for row in rows]


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_srt_and_vtt_give_the_same_cues(tmp_path: Path) -> None:
    srt = _write(
        tmp_path / "talk.srt",
        "1\n00:00:01,250 --> 00:00:02,500\n<i>Hello</i> {\\an8}there\nfriend\n\n"
        "2\n00:01:03,000 --> 00:01:04,000\nSecond &amp; last\n",
    )
    vtt = _write(
        tmp_path / "talk.vtt",
        "WEBVTT - demo\nKind: captions\n\nNOTE made by hand\n\nSTYLE\n::cue { color: red }\n\n"
        "intro\n00:01.250 --> 00:02.500 line:0 position:50%\n<v Ann>Hello</v> <00:01.500><c.loud>there</c>\nfriend\n\n"
        "01:03.000 --> 00:01:04.000\nSecond &amp; last\n",
    )

    expected = ((1.25, 2.5, "Hello there friend"), (63.0, 64.0, "Second & last"))
    assert load_captions(srt).cues == expected
    assert load_captions(vtt).cues == expected
    assert load_captions(str(srt)).file == srt


def test_windows_line_ends_bom_and_utf16_are_read(tmp_path: Path) -> None:
    text = "1\r\n00:00:00,000 --> 00:00:01,000\r\nMerhaba dünya\r\n\r\n"
    (tmp_path / "bom.srt").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    (tmp_path / "wide.srt").write_bytes(text.encode("utf-16"))

    assert load_captions(tmp_path / "bom.srt").cues == ((0.0, 1.0, "Merhaba dünya"),)
    assert load_captions(tmp_path / "wide.srt").cues == ((0.0, 1.0, "Merhaba dünya"),)


def test_unusable_caption_files_say_what_is_wrong(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="captions file not found"):
        load_captions(tmp_path / "missing.srt")
    with pytest.raises(ValueError, match=r"must be an \.srt or \.vtt file"):
        load_captions(_write(tmp_path / "notes.txt", "hello"))
    with pytest.raises(ValueError, match=r"must be an \.srt or \.vtt file"):
        load_captions(tmp_path)
    with pytest.raises(ValueError, match="empty.srt has no captions"):
        load_captions(_write(tmp_path / "empty.srt", ""))
    with pytest.raises(ValueError, match="empty.vtt has no captions"):
        load_captions(_write(tmp_path / "empty.vtt", "WEBVTT\n\nNOTE nothing here\n"))
    with pytest.raises(ValueError, match="bad.srt: cannot read the caption time '00:00:xx,000'"):
        load_captions(_write(tmp_path / "bad.srt", "1\n00:00:xx,000 --> 00:00:02,000\nHi\n"))
    with pytest.raises(ValueError, match="bad.vtt: cannot read the caption time ''"):
        load_captions(_write(tmp_path / "bad.vtt", "WEBVTT\n\n00:01.000 -->\nHi\n"))
    (tmp_path / "latin.srt").write_bytes("1\n00:00:00,000 --> 00:00:01,000\nM\xfcnchen\n".encode("latin-1"))
    with pytest.raises(ValueError, match="latin.srt is not UTF-8 text"):
        load_captions(tmp_path / "latin.srt")


def test_overlapping_cues_show_one_at_a_time(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "overlap.srt",
        "1\n00:00:03,000 --> 00:00:06,000\nlater\n\n"
        "2\n00:00:01,000 --> 00:00:04,000\nfirst\n\n"
        "3\n00:00:03,000 --> 00:00:05,000\nsame start\n\n"
        "4\n00:00:07,000 --> 00:00:07,000\nno time\n",
    )

    assert load_captions(path).cues == ((1.0, 3.0, "first"), (3.0, 6.0, "same start later"))


def test_cue_times_follow_the_trim_and_stop_at_its_ends() -> None:
    captions = Captions(
        Path("talk.srt"),
        ((0.0, 4.0, "before"), (9.0, 12.0, "cut at the start"), (12.0, 13.0, "inside"), (19.5, 25.0, "cut at the end"),
         (30.0, 31.0, "after")),
    )

    document, shown = ass_document(captions, REEL, (10.0, 20.0))

    assert shown == 3
    assert _dialogue(document) == [
        ("0:00:00.00", "0:00:02.00", "cut at the start"),
        ("0:00:02.00", "0:00:03.00", "inside"),
        ("0:00:09.50", "0:00:10.00", "cut at the end"),
    ]
    assert ass_document(captions, REEL, (5.0, 8.0))[1] == 0


def test_long_cue_becomes_two_line_screens_inside_the_safe_width() -> None:
    words = " ".join(f"word{index}" for index in range(40))
    document, shown = ass_document(Captions(Path("talk.srt"), ((0.0, 8.0, words),)), REEL, (0.0, 8.0))

    # 1080 wide with 6% side margins at font size 70 holds 22 letters per line.
    assert "Style: Default,Arial,70," in document
    assert ",2,65,65,672,1" in document
    screens = _dialogue(document)
    assert shown == len(screens) > 4
    assert [end for _, end, _ in screens[:-1]] == [start for start, _, _ in screens[1:]]
    assert screens[0][0] == "0:00:00.00" and screens[-1][1] == "0:00:08.00"
    lines = [line for _, _, text in screens for line in text.split("\\N")]
    assert all(text.count("\\N") <= 1 for _, _, text in screens)
    assert all(len(line) <= 22 for line in lines)
    assert " ".join(lines) == words


def test_unspaced_cjk_and_long_links_are_cut_to_the_line_width() -> None:
    cjk = "字" * 50
    link = "https://example.com/" + "a" * 60
    document, _ = ass_document(Captions(Path("talk.srt"), ((0.0, 4.0, cjk), (4.0, 8.0, link))), REEL, (0.0, 8.0))

    lines = [line for _, _, text in _dialogue(document) for line in text.split("\\N")]
    # A CJK character is as wide as two Latin letters.
    assert all(len(line) <= 11 for line in lines if "字" in line)
    assert all(len(line) <= 22 for line in lines)
    assert "".join(lines) == cjk + link


def test_ass_control_characters_in_caption_text_stay_text() -> None:
    captions = Captions(Path("talk.srt"), ((0.0, 2.0, r"C:\New {tag} \N"),))

    (_, _, text), = _dialogue(ass_document(captions, REEL, (0.0, 2.0))[0])

    # A word joiner after the backslash stops libass from reading \N as a line break.
    assert text == "C:\\\u2060New \\{tag\\} \\\u2060N"


def _clip(path: Path, size: str = "270x480", duration: float = 2.0) -> InputInfo:
    subprocess.run(
        [
            "nice", "-n", "10", "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
            "-i", f"color=c=black:s={size}:r=10:d={duration}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
        ],
        check=True,
        capture_output=True,
    )
    width, height = (int(value) for value in size.split("x"))
    return InputInfo(path, "caption-source", width, height, duration, 10.0)


def _gray_frame(path: Path, at: float, width: int, height: int) -> np.ndarray:
    frame = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(path), "-frames:v", "1",
            "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    return np.frombuffer(frame.stdout, dtype=np.uint8).reshape((height, width))


def _full_frame_plan(info: InputInfo, target: Target, captions: Captions | None, trim: tuple[float, float]) -> VideoPlan:
    frames = round((trim[1] - trim[0]) * info.fps)
    return VideoPlan(
        target.id, "crop", trim, trim[0], "", [Box(0.0, 0.0, float(info.width), float(info.height))] * frames,
        captions=captions,
    )


def test_render_burns_captions_inside_the_safe_area_at_the_trimmed_time(tmp_path: Path) -> None:
    # The folder name holds every character that needs escaping in an ffmpeg filter graph.
    work = tmp_path / "it's a [job], 50%; x=1:2"
    info = _clip(tmp_path / "source.mp4", duration=4.0)
    target = Target("instagram_reel", 270, 480, REEL.limits)
    captions = Captions(tmp_path / "talk.srt", ((0.0, 1.5, "EARLY WORDS"), (2.5, 3.5, "LATE WORDS HERE"),))
    plan = _full_frame_plan(info, target, captions, (2.0, 4.0))

    result = render_video(info, plan, target, tmp_path / "out.mp4", work)

    assert result.extra["captions"] == {"file": str(tmp_path / "talk.srt"), "shown": 1}
    assert _gray_frame(result.file, 0.2, 270, 480).max() < 40
    shown = _gray_frame(result.file, 1.0, 270, 480)
    rows, columns = np.where(shown > 150)
    # Safe area: 6% at each side, nothing in the bottom 35% or the top 14%.
    assert rows.size > 50
    assert rows.max() < 480 * 0.65 and rows.min() > 480 * 0.14
    assert columns.min() >= 270 * 0.06 - 1 and columns.max() <= 270 * 0.94 + 1
    assert _gray_frame(export_cover(info, plan, target, tmp_path / "cover.jpg"), 0.0, 270, 480).max() < 40


def test_captions_outside_the_trim_render_a_clean_video_and_say_so(tmp_path: Path) -> None:
    from engine.video.checks import check_video

    info = _clip(tmp_path / "source.mp4")
    target = Target("instagram_reel", 270, 480)
    captions = Captions(tmp_path / "talk.srt", ((5.0, 6.0, "NEVER SHOWN"),))
    plain = render_video(info, _full_frame_plan(info, target, None, (0.0, 2.0)), target, tmp_path / "a.mp4", tmp_path / "w")
    late = render_video(info, _full_frame_plan(info, target, captions, (0.0, 2.0)), target, tmp_path / "b.mp4", tmp_path / "w")

    assert late.extra["captions"]["shown"] == 0
    assert "captions" not in plain.extra
    assert len(list((tmp_path / "w" / "render").glob("reuse-*.mp4"))) == 1
    advisory = {check.id: check for check in check_video(late, target)}["captions.shown"]
    assert (advisory.status, advisory.hard) == ("advisory", False)
    assert "captions.shown" not in {check.id for check in check_video(plain, target)}


def test_changed_caption_text_is_rendered_again(tmp_path: Path) -> None:
    info = _clip(tmp_path / "source.mp4")
    target = Target("instagram_reel", 270, 480)
    for words in ("ONE", "TWO", "TWO"):
        captions = Captions(tmp_path / "talk.srt", ((0.0, 2.0, words),))
        render_video(info, _full_frame_plan(info, target, captions, (0.0, 2.0)), target, tmp_path / "out.mp4", tmp_path / "w")

    assert len(list((tmp_path / "w" / "render").glob("reuse-*.mp4"))) == 2


def _plan_with(tmp_path: Path, override: dict[str, Any]) -> VideoPlan:
    scan = VideoScan(scenes=[(0.0, 4.0)], tracks=[], faces={"sample_fps": 5.0, "frames": []}, audio_rms=[])
    info = InputInfo(tmp_path / "unused.mp4", "plan", 270, 480, 4.0, 10.0)
    return plan_video(info, scan, Target("instagram_reel", 270, 480), {"cover_at": 1.0, **override})


def test_plan_reads_the_captions_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write(tmp_path / "talk.vtt", "WEBVTT\n\n00:00.000 --> 00:01.000\nHi\n")

    assert _plan_with(tmp_path, {}).captions is None
    assert _plan_with(tmp_path, {"captions": str(path)}).captions == Captions(path, ((0.0, 1.0, "Hi"),))
    with pytest.raises(FileNotFoundError, match="captions file not found"):
        _plan_with(tmp_path, {"captions": str(tmp_path / "gone.srt")})
    monkeypatch.setattr(video_make, "has_filter", lambda name: name != "ass")
    with pytest.raises(ValueError, match="this ffmpeg build has no libass"):
        _plan_with(tmp_path, {"captions": str(path)})
