from __future__ import annotations

from pathlib import Path

import numpy as np

from engine.speakers import cached_activity, mouth_activity, speaker_segments, speech_activity


def _speaker_at(segments: list[tuple[float, float, int]], t: float) -> int:
    return next(person for start, end, person in segments if start <= t < end)


def test_alternating_turns_cut_promptly_and_cover_the_range() -> None:
    times = np.arange(0.0, 12.0, 0.1)
    activity = np.full((len(times), 2), 1.0)
    expected = [(0.0, 3.0, 0), (3.0, 6.0, 1), (6.0, 9.0, 0), (9.0, 12.0, 1)]
    for start, end, person in expected:
        activity[(times >= start) & (times < end), person] = 10.0

    segments = speaker_segments(times, activity, np.ones(len(times), dtype=bool))
    cuts = [start for start, _, _ in segments[1:]]

    assert len(cuts) == 3
    assert all(0.0 <= cut - expected[index + 1][0] <= 0.6 for index, cut in enumerate(cuts))
    assert segments[0][0] == 0.0
    assert segments[-1][1] == 12.0
    assert all(left[1] == right[0] for left, right in zip(segments, segments[1:], strict=False))
    assert all(end - start >= 1.2 - 1e-9 for start, end, _ in segments[:-1])


def test_equal_overlap_does_not_cut() -> None:
    times = np.arange(0.0, 5.0, 0.1)
    activity = np.column_stack((np.full(len(times), 8.0), np.ones(len(times))))
    activity[times >= 2.0] = 8.0

    assert speaker_segments(times, activity, np.ones(len(times), dtype=bool)) == [(0.0, 5.0, 0)]


def test_brief_interjection_does_not_cut() -> None:
    times = np.arange(0.0, 5.0, 0.1)
    activity = np.column_stack((np.full(len(times), 8.0), np.ones(len(times))))
    activity[(times >= 2.0) & (times < 2.3), 1] = 20.0

    assert speaker_segments(times, activity, np.ones(len(times), dtype=bool)) == [(0.0, 5.0, 0)]


def test_silence_holds_the_current_speaker() -> None:
    times = np.arange(0.0, 6.0, 0.1)
    activity = np.column_stack((np.full(len(times), 8.0), np.ones(len(times))))
    activity[times >= 2.0] = (1.0, 12.0)
    speech = np.ones(len(times), dtype=bool)
    speech[(times >= 2.0) & (times < 4.0)] = False

    segments = speaker_segments(times, activity, speech)

    assert _speaker_at(segments, 3.0) == 0
    assert _speaker_at(segments, 4.6) == 1


def test_synthetic_clip_separates_mouth_turns_and_audio(speaker_media) -> None:
    info, scan = speaker_media.info, speaker_media.scan
    times, activity = mouth_activity(info.path, scan.tracks, 0.0, 9.0, info.width, info.height)
    speech = speech_activity(info.path, 0.0, 9.0, 15.0)
    segments = speaker_segments(times, activity, speech)

    first = (times >= 0.5) & (times < 3.0)
    second = (times >= 3.6) & (times < 6.0)
    tone = (times >= 0.5) & (times < 7.5)
    silence = (times >= 8.3) & (times < 8.9)
    assert np.count_nonzero(activity[first, 0] > activity[first, 1]) > np.count_nonzero(first) / 2
    assert np.count_nonzero(activity[second, 1] > activity[second, 0]) > np.count_nonzero(second) / 2
    assert np.count_nonzero(speech[tone]) > np.count_nonzero(tone) * 0.9
    assert np.count_nonzero(~speech[silence]) > np.count_nonzero(silence) * 0.9
    assert _speaker_at(segments, 1.0) == 0
    assert _speaker_at(segments, 4.5) == 1
    assert len([segment for segment in segments if 6.0 <= segment[0] < 8.0]) == 0


def test_clip_without_audio_uses_visual_activity(speaker_media) -> None:
    video_only = speaker_media.info.path.with_name("speaker-video-only.mp4")

    assert speech_activity(video_only, 0.0, 9.0, 15.0).all()


def test_scene_activity_cache_avoids_decoding_twice(speaker_media, tmp_path: Path, monkeypatch) -> None:
    from engine import speakers

    info, scan = speaker_media.info, speaker_media.scan
    first = cached_activity(
        info.path, info.sha256, scan.tracks, 0.0, 9.0, info.width, info.height, tmp_path
    )

    def fail(*args, **kwargs):
        raise AssertionError("cached activity decoded the source again")

    monkeypatch.setattr(speakers, "mouth_activity", fail)
    monkeypatch.setattr(speakers, "speech_activity", fail)
    second = cached_activity(
        info.path, info.sha256, scan.tracks, 0.0, 9.0, info.width, info.height, tmp_path
    )

    assert all(np.array_equal(left, right) for left, right in zip(first, second, strict=True))


def test_mouth_region_follows_mouth_landmarks_in_profile() -> None:
    from engine.speakers import _mouth_region
    from engine.video_scan import TrackPoint

    # A face turned to the left: the mouth corners sit near the left edge of the face box.
    face = TrackPoint(
        t=0.0, x=1000.0, y=200.0, w=120.0, h=180.0, score=0.9,
        landmarks=((1020.0, 260.0), (1045.0, 260.0), (1008.0, 300.0), (1015.0, 335.0), (1035.0, 335.0)),
    )
    rows, cols = _mouth_region(face, 1.0, 1.0, 1920, 1080)
    assert cols.start <= 1015 and cols.stop >= 1035
    assert (cols.start + cols.stop) / 2 < face.x + face.w / 2 - 20
    assert rows.start < 335 + 0.04 * face.h < rows.stop

    frontal = TrackPoint(t=0.0, x=1000.0, y=200.0, w=120.0, h=180.0, score=0.9)
    rows, cols = _mouth_region(frontal, 1.0, 1.0, 1920, 1080)
    assert abs((cols.start + cols.stop) / 2 - (frontal.x + frontal.w / 2)) <= 1
