# Changelog

All notable changes to postkitty are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-11

### Changed

- **Breaking:** the tool `postkitty_copy` is now `postkitty_write`. The five tools read as five verbs: scan, write, make, redo, check. The old name has no alias, so open a new chat after updating and Hermes picks up the new one.
- The code is split into a thin Hermes adapter (`schemas.py`, `tools.py`, `command.py`) and an engine library grouped by job: `detect`, `photo`, `video`, `text`, `verify` and `board`. Tool arguments and results kept their shape.

### Added

- Captions. Give `postkitty_make` or `postkitty_redo` the path of an `.srt` or `.vtt` file, and the subtitles are burned into the video inside the platform's caption-safe area.
- `/postkitty doctor`, a setup check for Python, ffmpeg and ffprobe, OpenCV, Pillow, the face model and the output folder, with one fix line for each problem.
- `engine.pipeline`, a public Python API with `configure()` and `scan`, `write`, `make`, `redo` and `check` as plain functions that take a dict and return a dict.
- Documentation under `docs/`: how to ask, the tool reference, layouts, platform limits with their sources, the HTTP API, the architecture and troubleshooting.
- `CONTRIBUTING.md`, `SECURITY.md` and this changelog.

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
