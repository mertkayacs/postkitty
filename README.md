![postkitty: one post in, every platform out](docs/banner.png)

# postkitty

**One post in. Every platform out.**

postkitty is a [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin. You hand Hermes a post the way you
have it: a draft, a few photos, a landscape video. postkitty turns it into a folder of files that are ready to upload
to Instagram, TikTok, YouTube Shorts, X, LinkedIn, Threads, Bluesky and Facebook, and it checks every file against the
limits each platform publishes before it calls anything ready.

It runs on your machine. There are no API keys and nothing is uploaded. Hermes's own model reads the post and writes the
copy; postkitty does the parts a model should not guess at: finding faces, framing, rendering, counting characters the
way each platform counts them, and checking the result.

One of the best free and open source plugins for Hermes Agent on social media content creation!

[![CI](https://github.com/mertkayacs/postkitty/actions/workflows/ci.yml/badge.svg)](https://github.com/mertkayacs/postkitty/actions/workflows/ci.yml)
License: MIT. Site: [postkitty.mertkayacs.com](https://postkitty.mertkayacs.com)

![Center crops lose people. postkitty keeps them.](docs/before-after.jpg)

## What it does

**Video.** A landscape clip becomes a vertical Reel, TikTok and Short that follows the person talking. When two people
sit too far apart to share one vertical frame, it switches to a split screen with one person per panel. It trims to each
platform's length limit, picks a sharp cover frame, and encodes to the codecs, frame rates and bitrates each platform
accepts.

**Photos.** Every crop keeps every face in frame. When people do not fit the shape (five colleagues in a 4:5 post), it
crops tight around the group and fills the rest with a soft blur of the same photo instead of cutting someone off.
Location and camera metadata are stripped from every photo.

**Text.** Hermes reads your draft and the media, works out what the post is about and who it is for, and writes copy
for each platform in your voice. postkitty counts it with each platform's own rule (X's weighted characters, Bluesky's
graphemes, TikTok's UTF-16 units), splits a thread when a post is too long, and shows where each platform cuts the text
behind "more".

**Review.** You get a review board: every file in a frame of its real shape, the copy with counts, the advice, and every
check with a link to the platform page it comes from. Ask for a change ("keep him in frame on the LinkedIn video") and
Hermes re-renders just that file.

![The review board](docs/board.png)

## Install

```bash
hermes plugins install mertkayacs/postkitty --enable
```

You need Hermes Agent 0.22.7 or newer and `ffmpeg` with `ffprobe` on your PATH (`brew install ffmpeg`,
`sudo apt install ffmpeg`). Hermes asks before it installs the Python packages postkitty needs: OpenCV (headless, with
the contrib modules), NumPy, Pillow and regex.

## Use it

Talk to Hermes as you would to a colleague:

> Make this episode post ready for Instagram, TikTok, YouTube Shorts, LinkedIn and X. podcast.mp4 is a clip from the
> episode and team.jpg is our team. My draft: New episode of Two Builders is out...

Hermes loads the bundled `postkitty:postkitty` skill and works through five steps: scan the files, understand the post,
write and fit the copy, make the files, and show you the board. A job folder appears next to your files:

```text
postkitty/20261108-0519-podcast/
  ready/
    instagram/  reel.mp4  reel_cover.jpg  feed.jpg  story.mp4  post.txt
    tiktok/     tiktok.mp4  tiktok_cover.jpg  post.txt
    youtube/    shorts.mp4  shorts_cover.jpg  post.txt
    x/          video.mp4  image.jpg  post.txt
    linkedin/   video.mp4  image.jpg  post.txt
  board.html          review board (open in any browser)
  board-inline.html   the same board as one self-contained file, built for Hermes Desktop's ::preview
  contact.png         one image of every output, for chat apps
  advice.md           topic, audience, ranked platforms and tips
  manifest.json       every file, every check, every repair
```

Only files that pass every hard check go into `ready/`. A file that fails is repaired in code (a lower bitrate, a trim,
a padded frame instead of a cut) and checked again; if it still fails, it stays out of `ready/` and the board says why.

Type `/postkitty` in any Hermes chat to see every target with its size and main limits.

## Tools

| Tool | What it does |
|---|---|
| `postkitty_scan` | Reads the inputs: faces, people, shots, speech, text counts. Proposes a layout for every target and returns facts the agent uses for advice. |
| `postkitty_copy` | Stores the agent's advice and checks each platform's copy with that platform's counting rule. Splits threads. Reports overflow instead of truncating. |
| `postkitty_make` | Renders every target, runs the checks, repairs what fails, writes the board, the contact sheet and the manifest. |
| `postkitty_redo` | Re-renders one target with a different focus, layout, trim or cover, from the cached analysis. |
| `postkitty_check` | Checks any file against a platform target, including files postkitty did not make. |

## Platforms

| Target | Size | Some of the limits checked |
|---|---|---|
| Instagram Reel | 1080 x 1920 | 3 s to 15 min, 23 to 60 fps, H.264 or HEVC, AAC 48 kHz, up to 1 GB |
| Instagram feed | 1080 x 1350 | JPEG |
| Instagram Story | 1080 x 1920 | photo or video |
| TikTok | 1080 x 1920 | up to 10 min, 23 to 60 fps, 360 to 4096 px |
| YouTube Shorts | 1080 x 1920 | up to 3 min |
| X video, image | 1920 x 1080, 1600 x 900 | 2 min 20 s and 512 MB without Premium; images up to 5 MB |
| LinkedIn video, image | 1080 x 1350, 1080 x 1080 | 3 s to 15 min, 10 to 60 fps, up to 30 Mbps, aspect 1:2.4 to 2.4:1 |
| Threads video, image | 1080 x 1920, 1080 x 1350 | video up to 5 min |
| Bluesky video, image | 1080 x 1920, 1080 x 1350 | images under 2,000,000 bytes |
| Facebook Reel, feed | 1080 x 1920, 1080 x 1350 | |

Copy limits: X 280 weighted characters, Bluesky 300 graphemes and 3,000 bytes, Threads 500, LinkedIn 3,000, Instagram
2,200 with at most 30 hashtags and 20 mentions, TikTok 2,200 UTF-16 units.

Each limit lives in [`data/platforms.yaml`](data/platforms.yaml) with its source link, the kind of source (official
help page, API reference, ad spec or secondary) and the date it was checked. A limit from an official or API source can
block a file. Anything weaker, or anything we could not confirm at the source, only produces an advisory note.

## What runs on your machine

postkitty reads only the files you name, writes only inside its job folder and its own data folder, and keeps no
history beyond what is in those folders. It sends no telemetry.

- It runs `ffmpeg` and `ffprobe` as subprocesses to read and render media.
- The first time it needs to find faces it downloads one file: the YuNet face detector (`face_detection_yunet_2023mar.onnx`,
  232,589 bytes, MIT) from the [OpenCV Zoo](https://github.com/opencv/opencv_zoo) repository at a pinned commit, and
  verifies its SHA-256 before use. Face detection then runs locally on the CPU. Detections are cached by file hash, so
  the same video is never scanned twice.
- If [caire](https://github.com/esimov/caire) is on your PATH and you ask for seam carving, postkitty uses it; otherwise
  a slower built-in version runs. Seam carving is never chosen automatically.
- The copy, the advice and any alt text come from whatever model your Hermes is set up with. postkitty itself makes no
  network calls besides the one model download above.

## Configuration

Set these on the plugin's settings page in Hermes Desktop, or under `plugins.entries.postkitty.settings` in
`config.yaml`:

| Key | Default | Meaning |
|---|---|---|
| `output_dir` | empty | Where job folders go. Empty means `./postkitty` in the session's working folder. |
| `default_platforms` | empty | Platforms to make when you do not name any. Empty means every target that fits the input. |
| `loudness_lufs` | -14 | Integrated loudness target for rendered video. |

## Development

```bash
python -m pytest -q
ruff check .
```

The test suite never runs the face detector: a guard in `tests/conftest.py` swaps in a stand-in, and media tests use
synthetic clips and recorded detections. GitHub Actions runs the same suite on Python 3.11 and 3.12, a separate job with
the real YuNet detector, and `hermes plugins validate` against a pinned Hermes release.

## Credits

Possy, the kitten, is the mascot. Built on [OpenCV](https://opencv.org) and the
[YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) face detector, [FFmpeg](https://ffmpeg.org),
[Pillow](https://python-pillow.org), [NumPy](https://numpy.org), the counting rules of
[twitter-text](https://github.com/twitter/twitter-text) and the [AT Protocol lexicons](https://github.com/bluesky-social/atproto),
and optionally [caire](https://github.com/esimov/caire) by Endre Simo. People in the demo media are AI-generated.

MIT licensed. Made by [Mert Kaya](https://mertkayacs.com).
