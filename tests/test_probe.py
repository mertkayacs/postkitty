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


def test_unreadable_heic_tells_the_user_what_to_do(tmp_path):
    photo = tmp_path / "IMG_0001.heic"
    photo.write_bytes(b"not a heic file")
    with pytest.raises(probe.ProbeError, match="pillow-heif"):
        probe.probe(photo, "in1")


def test_truncated_jpeg_fails_at_probe(tmp_path):
    # The header of a cut-off upload still parses, so the failure used to surface later as an unexpected error.
    whole = tmp_path / "whole.jpg"
    Image.radial_gradient("L").resize((640, 480)).save(whole, quality=95)
    data = whole.read_bytes()
    truncated = tmp_path / "truncated.jpg"
    truncated.write_bytes(data[: len(data) // 2])
    with pytest.raises(probe.ProbeError, match="Could not read image"):
        probe.probe(truncated, "in1")


def test_still_gif_is_an_image_and_animated_gif_is_refused(tmp_path):
    # x_image lists gif as an allowed format, so a still GIF must probe as an image.
    still = tmp_path / "still.gif"
    Image.new("RGB", (40, 30), "red").save(still)
    info = probe.probe(still, "in1")
    assert (info.kind, info.width, info.height) == ("image", 40, 30)

    animated = tmp_path / "anim.gif"
    frames = [Image.new("RGB", (40, 30), color) for color in ("red", "blue")]
    frames[0].save(animated, save_all=True, append_images=frames[1:], duration=100, loop=0)
    with pytest.raises(probe.ProbeError, match="animated GIF"):
        probe.probe(animated, "in1")


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
