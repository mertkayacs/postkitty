# Changelog

All notable changes to postkitty are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-11-11

### Fixed

- **Captions on a machine without fonts.** ffmpeg draws no caption text there and still exits cleanly, so a video came out without its captions while the result said they were burned in. A bare server or a container is where this happens. postkitty now draws the caption text once before it renders. No font at all stops the call with the reason. Text that no installed font has fails that target and names the characters. A symbol that no font has, an emoji for example, is left out and listed in the result. `/postkitty doctor` checks for a font on its Captions row.
- **Cover frames.** When the cover frame of a finished video cannot be made, the row says so in its advice. The reason was stored and never shown.
- **Setup check.** `/postkitty doctor` prints a fix once when it settles several rows. Without ffmpeg, the same install line appeared three times.

### Changed

- Captions of a split sit on the seam between the two people. At the bottom of the frame they covered the lower face.
- The README and the troubleshooting page say what the ffmpeg that Hermes brings covers: on Windows and most Linux systems there is nothing to install for video, and on macOS ffprobe has to be added.

## [1.0.0] - 2026-11-11

### Changed

- **Breaking:** the tool `postkitty_copy` is now `postkitty_write`. The five tools read as five verbs: scan, write, make, redo, check. The old name has no alias, so open a new chat after updating and Hermes picks up the new one.
- The code is split into a thin Hermes adapter (`schemas.py`, `tools.py`, `command.py`) and an engine library grouped by job: `detect`, `photo`, `video`, `text`, `verify` and `board`. Tool arguments and results kept their shape.
- Every error carries a `hint` that says what to do next, and a misspelled argument is an error that lists the real ones.
- A target that cannot be rendered is a `failed` row with a `reason`, and the other targets keep their files.
- One job is made from one photo and one video. With several photos, the scan result says which one is used.
- File paths may be relative to the session's working folder.
- Five Python packages are declared, in `plugin.yaml` and in `pyproject.toml`: `ruamel.yaml` is new, and Pillow has to be 10.1 or newer.
- The engine no longer imports Hermes. The adapter passes it the session's working folder and the plugin's data folder.

### Added

- Captions. Give `postkitty_make` or `postkitty_redo` the path of an `.srt` or `.vtt` file, and the subtitles are burned into the video inside the platform's caption-safe area. `none` removes them again.
- `/postkitty doctor`, a setup check for Python, ffmpeg and ffprobe, caption support, the Python packages, the face model and the output folder, with one fix line for each problem.
- `/postkitty check <file> [target]`, which checks a file against a target without the model.
- `hermes postkitty`, a terminal command with `make`, `check`, `platforms` and `doctor` for scripts, cron jobs and release automation. It needs no model, so `make` counts and splits the text as written and does not rewrite it.
- `engine.pipeline`, a public Python API with `configure()` and `scan`, `write`, `make`, `redo` and `check` as plain functions that take a dict and return a dict.
- Documentation under `docs/`: how to ask, the tool reference, layouts, platform limits with their sources, the HTTP API, the architecture and troubleshooting.
- `CONTRIBUTING.md`, `SECURITY.md`, `THIRD_PARTY_NOTICES.md` and this changelog.

### Fixed

- **Text.** X is counted by a port of twitter-text, so links, file names that read as links, and emoji count exactly as X counts them. Threads counts every emoji as its UTF-8 bytes. Bluesky's 3,000-byte cap applies to each post of a thread, and the 100-character YouTube title limit is enforced. The preview of what a feed shows before "more" is cut on whole characters. A draft that cannot become a thread gets a note that says what to do.
- **Photos and video.** A focus position (`left`, `center`, `right` or `x:`) is kept as asked, and the result says who is outside the frame. `person:N` frames that one person. Split panels stay inside the photo, CMYK photos are converted through their colour profile, and outputs carry no comment or colour profile from the source. A photo with no face is framed on OpenCV builds without the saliency module too.
- **Video.** A clip is cut only for a hard length limit, and a trim that runs past the end stops at the last frame. HDR sources are tone-mapped to SDR, surround sound is mixed down to stereo, and anamorphic clips are measured at their display size. ffmpeg runs without the `nice` binary, a job folder with a quote in its path renders, and a failed ffmpeg run or repair is reported in plain words.
- **Inputs.** A phone JPEG that holds a second picture is read as a still photo. An animated WebP or PNG is refused as an animated image, as an animated GIF is.
- **Jobs.** Two scans can no longer share a job folder. Job and platform folders stay inside the output folder, a damaged manifest is named in the error with the way out, and finished renders are pruned from `work/`.
- **Face model.** An offline machine gets an answer at once, with the address and the folder for a manual download. A cached model that fails its checksum is replaced by a fresh download.
- **Review board.** A skipped target says why, long unbroken text wraps inside its card, and the contact sheet keeps its badges inside their tiles.
- **Platform data.** Every limit was checked again at the platform's own page on 2026-11-11. The Instagram Reel file cap is 300 MB (it was 1 GB). Instagram feed photos, Threads videos and Threads photos have a file size cap now, and Threads video is checked for container, codec and frame rate. `data/platforms.yaml` is validated when it loads, and a limit without a source is rejected.

## [0.1.0] - 2026-11-08

First release.

### Added

- Five tools for Hermes Agent: `postkitty_scan`, `postkitty_copy`, `postkitty_make`, `postkitty_redo` and `postkitty_check`, with a skill that describes the workflow.
- Targets for Instagram, TikTok, YouTube Shorts, X, LinkedIn, Threads, Bluesky and Facebook, with every limit and its source in `data/platforms.yaml`.
- Photo layouts `crop`, `split`, `seam` and `pad`, planned around the faces the YuNet detector finds.
- Video layouts `crop`, `split`, `speaker` and `pad`, with a trim to each platform's length and a cover frame.
- Text counting with each platform's rule (X weighted characters, Bluesky graphemes, TikTok UTF-16 units) and thread splitting for X, Threads and Bluesky.
- Checks against the platform limits, repairs for failing files, and a review board for every job.
- The `/postkitty` command, which lists every target with its size and main limits.
