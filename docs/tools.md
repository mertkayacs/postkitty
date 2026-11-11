# Tools, command and settings

postkitty gives Hermes five tools. Hermes calls them in order: scan, write, make, then redo for each change. check stands apart, for files that came from somewhere else.

| Tool | What it does |
|---|---|
| [`postkitty_scan`](#postkitty_scan) | Reads the inputs and plans. Renders nothing. |
| [`postkitty_write`](#postkitty_write) | Counts each platform's text with its real rule and writes the text files. |
| [`postkitty_make`](#postkitty_make) | Renders, checks, repairs and builds the review board. |
| [`postkitty_redo`](#postkitty_redo) | Changes one photo or video output. |
| [`postkitty_check`](#postkitty_check) | Checks a file postkitty did not make. |

Every tool returns JSON. A result with an `error` key carries one sentence that says what is wrong and a `hint` that says what to do. No tool posts, uploads or schedules anything.

## postkitty_scan

The first call for every post, including a post that is only text. It opens a job folder, reads each file, finds people and shots, and plans a framing for every target.

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `inputs` | list of strings | none | Absolute paths of photos or videos. |
| `text` | string | none | The draft post. |
| `platforms` | list of strings | every target that fits the inputs, or the `default_platforms` setting | Platform names (`instagram`, `tiktok`, `youtube`, `x`, `linkedin`, `threads`, `bluesky`, `facebook`) or target ids such as `instagram_reel`. |
| `job` | string | a new job | The id of a job to reuse. |

Give at least one input or a text.

| Result key | Meaning |
|---|---|
| `job`, `job_dir` | The job id for every later call, and the folder it lives in. |
| `inputs` | One entry per file: kind, size, duration, frame rate, and the number of `people` and `shots` found. |
| `plan` | One entry per target: the proposed `layout` with a `note`, and for video the `trim` and `cover_at`. |
| `fit` | Per platform: target sizes, limits, and whether the draft fits. |
| `text` | Counts for the draft: characters, X weighted characters, graphemes, UTF-16 units, UTF-8 bytes, hashtags, mentions and links. |
| `peek` | The path of a preview image: the photo, or a strip of frames from the video. |
| `notes` | One line for each media step that was skipped, with the reason. |

## postkitty_write

Takes the versions Hermes wrote, counts each one the way its platform counts, and writes the text files into `ready/`. Hermes calls it again with a rewritten draft until every platform is `ok`, and again for every later change to the text.

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `job` | string | required | The job id from scan. |
| `drafts` | object | none | Platform name or target id mapped to the text. A list of strings is a thread. |
| `advice` | object | none | `topic`, `audience`, `tone`, `key_message`, `ranking` (a list of `{platform, reason}`) and `tips`. |
| `alt_text` | object | none | Target id, input file name or ready file path mapped to the alt text. |
| `split_threads` | boolean | `true` | Split X, Threads and Bluesky text over the limit into a numbered thread. |

Only the drafts in the call are replaced. The others stay as they are.

| Result key | Meaning |
|---|---|
| `all_ok` | `true` when every draft passes its hard limits. |
| `platforms` | Per platform: `ok`, `unit`, `limit`, `count`, `overflow`, `split`, the `parts` with their counts, `hashtags`, `mentions`, `notes` and the `files` written. |
| `platforms.<name>.enforcement` | `hard` when the platform rejects longer text, `recommendation` when the limit is advice. |
| `platforms.<name>.fold` | An estimate of the part a feed shows before "more". X has no fold. |
| `advice` | The path of `advice.md`. |
| `alt_text_unmatched` | Alt text keys that matched no target. |

Counting units:

| Unit | Used by | What counts as one |
|---|---|---|
| `codepoints` | Instagram, LinkedIn, Threads, Facebook, YouTube titles | One Unicode character. |
| `x_weighted` | X | The twitter-text rule: Latin, Greek, Cyrillic and Arabic letters count 1, Chinese, Japanese and Korean characters count 2, an emoji counts 2 and a link counts 23. |
| `graphemes` | Bluesky | One character as a reader sees it, so an emoji built from several code points counts 1. |
| `utf16` | TikTok | One UTF-16 code unit, so an emoji counts 2 or more. |

Files written: `ready/<platform>/post.txt` for a single post, `thread.txt` for a thread, `alt.txt` for alt text, and `advice.md` in the job folder.

## postkitty_make

Renders every planned target, checks each file against the platform's limits, repairs failures, and copies only passing files into `ready/`. Then it builds the review board.

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `job` | string | required | The job id from scan. |
| `targets` | list of strings | every planned target | Target ids or platform names to render. |
| `overrides` | object | none | Target id mapped to any of `layout`, `focus`, `trim`, `cover_at`, `captions`. |

The override keys:

| Key | Values | Applies to |
|---|---|---|
| `layout` | `crop`, `split`, `speaker`, `seam`, `pad`, `auto` | Photos and video. `speaker` is video only, `seam` is photos only. |
| `focus` | `auto`, `person:N`, `left`, `center`, `right`, `x:0.0` to `x:1.0` | Photos and video. |
| `trim` | `[start, end]` in seconds | Video. |
| `cover_at` | a time in seconds, inside the trim | Video. |
| `captions` | the absolute path of an `.srt` or `.vtt` file | Video. The subtitles are burned in. When none falls inside the trim, the video is made without them and the row carries an advisory. |

[Layouts](layouts.md) explains each layout and focus value.

| Result key | Meaning |
|---|---|
| `targets` | One row per target: `target`, `status`, `file`, `cover`, `size`, `layout`, and when they apply `problems`, `advisory`, `repairs`, `kept` and `reason`. |
| `board`, `board_inline`, `contact` | Paths of the review board, a single-file copy of it, and an image with every file on it. |
| `media_line`, `preview_directive` | Two strings Hermes passes on unchanged so the chat shows the result. |

A job with text only has nothing to render. make then returns an empty `targets` list, a `note`, and the text `files` already in `ready/`.

### Status values

| Status | Meaning | Where the file is |
|---|---|---|
| `ready` | The file passed every hard check as rendered. | `ready/<platform>/` |
| `repaired` | A check failed, a repair fixed it, and the file passed. `repairs` names what was done. | `ready/<platform>/` |
| `failed` | The file still fails after the repairs. `problems` lists the failing checks. If an earlier version passed, it stays in `ready/` and `kept` names it. | `work/failed/` |
| `skipped` | The engine for this kind of media could not load. `reason` says why. | nowhere |

Only `ready` and `repaired` files are safe to upload. An `advisory` is a recommendation from the platform that the file misses, such as a safe area. It does not block the file.

## postkitty_redo

Makes one target again after a request for a change. It reuses the scan, so faces are not detected a second time.

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `job` | string | required | The job id. |
| `target` | string | required | The target id, for example `tiktok`. |
| `layout`, `focus`, `trim`, `cover_at`, `captions` | as in make | none | The keys to change. Give at least one. |

The result has the same shape as make, with one row. The change is stored with the job, so a later make keeps it. Text changes go through `postkitty_write`.

## postkitty_check

Checks a file from anywhere against one target, without rendering.

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `path` | string | none | The file to check. |
| `target` | string | none | The target id to check it against. Required with `path`. |
| `job` | string | none | Given alone, checks the ready files of that job again. |

| Result key | Meaning |
|---|---|
| `pass` | `true` when no hard check fails. |
| `checks` | The checks that did not pass, each with `id`, `status`, `measured`, `expected`, `message` and the `source_url` of the limit. `"all checks pass"` when there are none. |

Files made by make and redo are already checked, so Hermes uses this tool for outside files.

## The /postkitty command

Type it in any Hermes chat. It answers from the plugin, without the model.

| Command | Shows |
|---|---|
| `/postkitty` | What postkitty does, example requests, and every target with its size and main limits. |
| `/postkitty tiktok` | The targets and limits of one platform. Several names work: `/postkitty x bluesky`. |
| `/postkitty doctor` | A check of your setup: Python, ffmpeg and ffprobe, caption support, OpenCV, Pillow and the other Python packages, the face model and the output folder. Each problem gets one fix line, and the last line says what works now: text, photos, video, captions. |

## Settings

Three settings, all optional. Change them on the plugin's page in the Hermes Desktop app (Settings, then Plugins), or in `config.yaml`:

```yaml
plugins:
  entries:
    postkitty:
      settings:
        output_dir: ~/posts
        default_platforms: [instagram, tiktok, linkedin]
        loudness_lufs: -14
```

| Key | Type | Default | Meaning |
|---|---|---|---|
| `output_dir` | string | empty | Where job folders are written. Empty means `./postkitty` in the session's working folder. A relative path is taken from that folder. |
| `default_platforms` | list | empty | Platforms to make when a request names none. Empty means every platform that fits the input. |
| `loudness_lufs` | number | `-14` | Integrated loudness target for video audio, in LUFS. |
