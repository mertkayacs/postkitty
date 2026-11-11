# Tools, command and settings

postkitty gives Hermes five tools. Hermes calls them in order: scan, write, make, then redo for each change. check stands apart, for files that came from somewhere else.

| Tool | What it does |
|---|---|
| [`postkitty_scan`](#postkitty_scan) | Reads the inputs and plans. Renders nothing. |
| [`postkitty_write`](#postkitty_write) | Counts each platform's text with its real rule and writes the text files. |
| [`postkitty_make`](#postkitty_make) | Renders, checks, repairs and builds the review board. |
| [`postkitty_redo`](#postkitty_redo) | Changes one photo or video output. |
| [`postkitty_check`](#postkitty_check) | Checks a file postkitty did not make. |

Every tool returns JSON. A result with an `error` key carries one sentence that says what is wrong and a `hint` that says what to do next: scan again, fix the argument, or run `/postkitty doctor`. A misspelled argument is an error that lists the real ones. File paths may be absolute or relative, and a relative path starts at the session's working folder. No tool posts, uploads or schedules anything.

## postkitty_scan

The first call for every post, including a post that is only text. It opens a job folder, reads each file, finds people and shots, and plans a framing for every target.

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `inputs` | list of strings | none | The path of one photo, of one video, or of one of each. With several photos or several videos, every target is made from the first of its kind, and a note names the file that is used. |
| `text` | string | none | The draft post. |
| `platforms` | list of strings | every target that fits the inputs, or the `default_platforms` setting | Platform names (`instagram`, `tiktok`, `youtube`, `x`, `linkedin`, `threads`, `bluesky`, `facebook`) or target ids such as `instagram_reel`. |
| `job` | string | a new job | The id of a job to reuse. |

Give at least one input or a text.

| Result key | Meaning |
|---|---|
| `job`, `job_dir` | The job id for every later call, and the folder it lives in. |
| `inputs` | One entry per file: kind, size, duration, frame rate, the number of `people` and `shots` found, and `used`, which is `true` when a target is made from the file. |
| `plan` | One entry per target: the proposed `layout` with a `note`, and for video the `trim` and `cover_at`. |
| `fit` | Per platform: target sizes, limits, and whether the draft fits. |
| `text` | Counts for the draft: characters, X weighted characters, graphemes, UTF-16 units, UTF-8 bytes, hashtags, mentions and links. |
| `peek` | The path of a preview image: the photo, or a strip of frames from the video. |
| `notes` | One line for each thing to tell the user: a media step that was skipped and why, a file given twice, or which photo a job with several photos uses. |

## postkitty_write

Takes the versions Hermes wrote, counts each one the way its platform counts, and writes the text files into `ready/`. Hermes calls it again with a rewritten draft until every platform is `ok`, and again for every later change to the text.

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `job` | string | required | The job id from scan. |
| `drafts` | object | none | Platform name or target id mapped to the text. A list of strings is a thread. |
| `advice` | object | none | `topic`, `audience`, `tone`, `key_message`, `ranking` (a list of `{platform, reason}`) and `tips`. |
| `alt_text` | object | none | Target id, input id (`in1`), input file name or ready file path mapped to the alt text. |
| `split_threads` | boolean | `true` | Split X, Threads and Bluesky text over the limit into a numbered thread. |

Give at least one of `drafts`, `advice` and `alt_text`. Only the drafts in the call are replaced. The others stay as they are.

| Result key | Meaning |
|---|---|
| `all_ok` | `true` when every draft passes its hard limits. |
| `platforms` | Per platform: `ok`, `unit`, `limit`, `count`, `overflow`, `split`, the `parts` with their counts, `hashtags`, `mentions`, `notes` and the `files` written. |
| `platforms.<name>.enforcement` | `hard` when the platform rejects longer text, `recommendation` when the limit is advice. Facebook's is the one recommendation. |
| `platforms.<name>.fold` | An estimate of the part a feed shows before "more". X has no fold. |
| `advice` | The path of `advice.md`. |
| `alt_text_unmatched` | Alt text keys that matched no target. |

Counting units:

| Unit | Used by | What counts as one |
|---|---|---|
| `codepoints` | Instagram, LinkedIn, Facebook, YouTube titles | One Unicode character. |
| `x_weighted` | X | A port of twitter-text: Latin, Greek, Cyrillic and Arabic letters count 1, Chinese, Japanese and Korean characters count 2, an emoji counts 2 and a link counts 23. A file name such as `README.md` counts as a link, because `.md` is a country domain. |
| `threads` | Threads | One per character, and every emoji as its UTF-8 bytes. |
| `graphemes` | Bluesky | One character as a reader sees it, so an emoji built from several code points counts 1. |
| `utf16` | TikTok | One UTF-16 code unit, so an emoji counts 2 or more. |

Bluesky also caps every post at 3,000 UTF-8 bytes, and in a thread the cap applies to each post.

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
| `captions` | the path of an `.srt` or `.vtt` file, or `none` | Video. The subtitles are burned in, and the row reports `captions` with the `file` and the number of caption screens `shown`. `none` removes captions set earlier. When no caption falls inside the trim, the video is made without them and the row carries an advisory. |

[Layouts](layouts.md) explains each layout and focus value.

| Result key | Meaning |
|---|---|
| `targets` | One row per target: `target`, `status`, `file`, `cover`, `size`, `layout`, and when they apply `problems`, `advisory`, `repairs`, `kept` and `reason`. |
| `board`, `board_inline`, `contact` | Paths of the review board, a single-file copy of it, and an image with every file on it. When the board cannot be written, `board_note` says so and the files are still returned. |
| `media_line`, `preview_directive` | Two strings Hermes passes on unchanged so the chat shows the result. |

A job with text only has nothing to render. make then returns an empty `targets` list, a `note`, and the text `files` already in `ready/`.

### Status values

| Status | Meaning | Where the file is |
|---|---|---|
| `ready` | The file passed every hard check as rendered. | `ready/<platform>/` |
| `repaired` | A check failed, a repair fixed it, and the file passed. `repairs` names what was done. | `ready/<platform>/` |
| `failed` | The file still fails after the repairs, and `problems` lists the failing checks. Or the target could not be rendered, for example with a focus on a person who is not there, and `reason` says why. The other targets keep their files. If an earlier version passed, it stays in `ready/` and `kept` names it. | `work/failed/` |
| `skipped` | The engine for this kind of media could not load. `reason` says why. | nowhere |

Only `ready` and `repaired` files are safe to upload. An `advisory` does not block the file. It reports a recommendation of the platform that the file misses, such as a safe area or a recommended length, or people left outside a photo by a focus position you chose.

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
| `target` | string | none | The target id to check it against. A platform name works when that platform has one target for this kind of file (`x` with a photo is `x_image`). Required with `path`. |
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
| `/postkitty check clip.mp4 tiktok` | Whether a file passes a target's checks, in plain words: the verdict, what to fix, and what is only advice. Leave the target out and postkitty asks which one, or lists the targets that take the file. |
| `/postkitty doctor` | A check of your setup: Python, ffmpeg and ffprobe, caption support, OpenCV, Pillow and the other Python packages, the face model and the output folder. Each problem gets one fix line, and the last line says what works now: text, photos, video, captions. |

## The hermes postkitty terminal command

The same engine runs from a terminal, with no chat and no model. This is the path for scripts, cron jobs and release automation. Because no model is involved, `make` uses your text as written: it counts it and splits it for each platform, and it does not rewrite it.

```sh
hermes postkitty make clip.mp4 --text-file post.txt --platforms tiktok,x
hermes postkitty check clip.mp4 --target tiktok
hermes postkitty platforms tiktok
hermes postkitty doctor
```

| Command | What it does | Exit code |
|---|---|---|
| `hermes postkitty make [FILES...]` | Scans the files, writes the text files, renders and checks every target, and prints one line per text and per target, then the job folder. | `0` when every text and every target is ready or repaired, `1` otherwise |
| `hermes postkitty check FILE` | Checks a file against one target and prints the verdict. | `0` when the file passes, `1` when it fails |
| `hermes postkitty platforms [name]` | Lists every target with its size and limits, or those of one platform. | `0` |
| `hermes postkitty doctor` | Prints the setup check. | `0` when everything is in place, `1` otherwise |

A bad argument or a file that cannot be read exits with `2`.

Options of `make`:

| Option | Meaning |
|---|---|
| `--text TEXT` or `--text-file PATH` | The post text, or a UTF-8 file that holds it. Give one of the two. |
| `--platforms a,b` | Platform names separated by commas. Without it, every platform that fits the files. |
| `--layout NAME` | One layout for every target: `crop`, `split`, `speaker`, `seam`, `pad` or `auto`. |
| `--focus VALUE` | `auto`, `person:N`, `left`, `center`, `right` or `x:0.0` to `x:1.0`. |
| `--captions FILE` | An `.srt` or `.vtt` file to burn into every video target. |
| `--out DIR` | The folder for the job. Without it, the `output_dir` setting. |

`check` takes `--target ID`, a target id or a platform name. Without it, a file that fits one target is checked against that one. Otherwise the command lists the targets to choose from and exits with `2`.

The command is available in the `hermes` program on the machine where the plugin is installed and turned on. Hermes versions that cannot register terminal commands leave it out, and the tools and `/postkitty` work as before.

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
| `loudness_lufs` | number | `-14` | Integrated loudness target for video audio, in LUFS, from -70 to -5. |
