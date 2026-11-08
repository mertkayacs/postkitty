import shutil
import subprocess

import pytest
from PIL import Image

from engine import probe

FFMPEG = shutil.which("ffmpeg")


def test_image_probe(tmp_path):
    path = tmp_path / "a.png"
    Image.new("RGBA", (40, 30), (255, 0, 0, 128)).save(path)
    info = probe.probe(path, "in1")
    assert (info.kind, info.width, info.height, info.has_alpha, info.has_audio) == ("image", 40, 30, True, False)
    assert info.duration is None and len(info.sha256) == 64


def test_image_exif_rotation_swaps_display_size(tmp_path):
    path = tmp_path / "r.jpg"
    image = Image.new("RGB", (40, 30), "blue")
    exif = Image.Exif()
    exif[274] = 6
    image.save(path, exif=exif)
    info = probe.probe(path, "in1")
    assert (info.width, info.height, info.rotation) == (30, 40, 90)


def test_sha256_is_stable(tmp_path):
    path = tmp_path / "a.jpg"
    Image.new("RGB", (8, 8), "red").save(path)
    assert probe.probe(path, "in1").sha256 == probe.sha256_file(path)


def test_missing_and_unsupported(tmp_path):
    with pytest.raises(FileNotFoundError):
        probe.probe(tmp_path / "nope.jpg", "in1")
    odd = tmp_path / "doc.pdf"
    odd.write_bytes(b"%PDF")
    with pytest.raises(probe.ProbeError, match="unsupported"):
        probe.probe(odd, "in1")


def test_corrupt_image(tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image")
    with pytest.raises(probe.ProbeError):
        probe.probe(bad, "in1")


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")
def test_video_probe(tmp_path):
    path = tmp_path / "v.mp4"
    subprocess.run([FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1",
                    "-f", "lavfi", "-i", "sine=d=1", "-shortest", "-pix_fmt", "yuv420p", str(path)], check=True)
    info = probe.probe(path, "in2")
    assert (info.kind, info.width, info.height, info.has_audio) == ("video", 160, 90, True)
    assert info.fps == pytest.approx(10, abs=0.5) and info.duration == pytest.approx(1, abs=0.3)
    assert info.has_alpha is False


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")
def test_rotated_phone_clip_reports_display_size(tmp_path):
    flat = tmp_path / "flat.mp4"
    subprocess.run([FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1",
                    "-pix_fmt", "yuv420p", str(flat)], check=True)
    path = tmp_path / "portrait.mp4"
    subprocess.run([FFMPEG, "-v", "error", "-display_rotation", "-90", "-i", str(flat), "-c", "copy", str(path)],
                   check=True)
    info = probe.probe(path, "in1")
    assert (info.width, info.height, info.rotation) == (90, 160, 270)


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")
def test_audio_file_with_cover_art_is_not_a_video(tmp_path):
    # A podcast export carries its cover as an attached picture, which ffprobe lists as a video stream.
    path = tmp_path / "podcast.mp4"
    subprocess.run([FFMPEG, "-v", "error", "-f", "lavfi", "-i", "sine=d=1", "-f", "lavfi",
                    "-i", "color=c=red:s=64x64:d=1", "-map", "0:a", "-map", "1:v", "-frames:v", "1",
                    "-c:a", "aac", "-c:v", "mjpeg", "-disposition:v", "attached_pic", str(path)], check=True)
    with pytest.raises(probe.ProbeError, match="no video stream"):
        probe.probe(path, "in1")


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")
def test_corrupt_video(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"\x00" * 64)
    with pytest.raises(probe.ProbeError):
        probe.probe(bad, "in1")
