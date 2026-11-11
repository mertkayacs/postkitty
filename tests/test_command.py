"""The /postkitty slash command and the ``hermes postkitty`` terminal command, both without the model."""

import argparse

from PIL import Image
from postkitty import cli, command, tools


def parse(*argv):
    parser = argparse.ArgumentParser(prog="hermes postkitty")
    cli.setup(parser)
    return parser.parse_args(list(argv))


def wide_photo(folder, name="wide shot.jpg"):
    path = folder / name
    Image.new("RGB", (1600, 900), "teal").save(path)
    return path


def test_slash_check_says_the_verdict_in_plain_words(out_dir, tmp_path):
    photo = wide_photo(tmp_path)
    assert command.handle(f"check {photo} x").startswith("wide shot.jpg passes every check that blocks an upload for x_image.")
    assert command.handle(f'check "{photo}" tiktok') == "wide shot.jpg is a photo; tiktok takes videos"
    assert command.handle("check").startswith("Usage: /postkitty check")
    assert "not found" in command.handle(f"check {tmp_path / 'nope.mp4'} tiktok")


def test_slash_check_asks_for_the_target_and_falls_back_to_a_usage_line(out_dir, tmp_path, monkeypatch):
    photo = wide_photo(tmp_path)
    asked = {}

    class Ctx:
        def ask_choice(self, question, choices):
            asked.update(question=question, choices=choices)
            return "x_image"

        def get_config(self, key, default=None):
            return default

    monkeypatch.setattr(tools, "_CTX", Ctx())
    assert "for x_image." in command.handle(f"check {photo}")
    assert "x_image" in asked["choices"] and "tiktok" not in asked["choices"] and "wide shot.jpg" in asked["question"]
    monkeypatch.setattr(tools, "_CTX", None)  # an older Hermes has no ask_choice
    usage = command.handle(f"check {photo}")
    assert usage.startswith("Usage: /postkitty check") and "x_image" in usage


def test_slash_overview_and_one_platform():
    overview = command.handle("")
    header, _, listing = overview.partition("Targets (size, main limits):")
    assert header.startswith("postkitty: one post in, every platform out.")
    assert "never posts,\nuploads or schedules" in header and header.count("\n  ") == 5
    assert "https://postkitty.mertkayacs.com/docs/" in header and "/postkitty check <file> [target]" in header
    assert "tiktok: 1080x1920 video" in listing and "X: text 280 x_weighted" in listing
    one = command.handle("tiktok")
    assert one.startswith("TikTok:") and "Try saying" not in one
    assert command.handle("zzz") == "No matching platform."


def test_cli_make_counts_the_text_as_given_and_exits_zero_when_everything_is_ready(out_dir, capsys):
    assert cli.run(parse("make", "--text", "Hello from the terminal", "--platforms", "x,bluesky")) == 0
    out = capsys.readouterr().out
    assert "x text" in out and "ready/x/post.txt" in out and "bluesky text" in out and "job folder:" in out
    assert cli.run(parse("make", "--text", "word " * 900, "--platforms", "linkedin")) == 1
    assert "linkedin text" in (out := capsys.readouterr().out) and "over by 1500 codepoints" in out


def test_cli_make_renders_every_target_with_the_layout_given(out_dir, tmp_path, capsys, stub_image_engine):
    photo = wide_photo(tmp_path, "team.jpg")
    assert cli.run(parse("make", str(photo), "--platforms", "x", "--layout", "pad", "--out", str(tmp_path / "jobs"))) == 0
    out = capsys.readouterr().out
    assert "x_image" in out and "ready/x/image.jpg" in out and str(tmp_path / "jobs") in out
    assert stub_image_engine[-1] == ("x_image", "pad")


def test_cli_check_and_platforms(out_dir, tmp_path, capsys):
    photo = wide_photo(tmp_path)
    assert cli.run(parse("check", str(photo), "--target", "x")) == 0
    assert "passes" in capsys.readouterr().out
    assert cli.run(parse("check", str(photo), "--target", "tiktok")) == 2
    assert "takes videos" in capsys.readouterr().err
    assert cli.run(parse("check", str(photo))) == 2
    assert "Give --target" in capsys.readouterr().err
    assert cli.run(parse("platforms", "tiktok")) == 0
    assert capsys.readouterr().out.startswith("TikTok:")
    assert cli.run(parse("platforms")) == 0
    assert "Try saying" not in (listing := capsys.readouterr().out) and "tiktok: 1080x1920 video" in listing
    assert cli.run(parse()) == 2


def test_doctor_shows_the_setup_check_from_the_chat_and_the_terminal(out_dir, capsys):
    chat = command.handle("doctor")
    assert chat.startswith("```\npostkitty doctor") and "Output folder" in chat and str(out_dir) in chat
    code = cli.run(parse("doctor"))
    rows = capsys.readouterr().out.splitlines()
    assert "Output folder" in "\n".join(rows) and code == (1 if any(row.startswith("no ") for row in rows) else 0)
