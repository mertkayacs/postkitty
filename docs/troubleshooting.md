# Troubleshooting

Start here. Type this in a Hermes chat:

```text
/postkitty doctor
```

It checks Python, ffmpeg and ffprobe, caption support, OpenCV, Pillow and the other Python packages, the face model and the output folder. Each problem gets one fix line, and the last line says what works now: text, photos, video, captions. From a terminal, `hermes postkitty doctor` prints the same report. The sections below cover the messages you can meet in a chat.

- [The tools do not show up after installing](#the-tools-do-not-show-up-after-installing)
- [ffmpeg is missing](#ffmpeg-is-missing)
- [A media step was skipped](#a-media-step-was-skipped)
- [The face model could not be downloaded](#the-face-model-could-not-be-downloaded)
- [Captions cannot be burned in](#captions-cannot-be-burned-in)
- [A target failed](#a-target-failed)
- [Other messages](#other-messages)
- [Report a problem](#report-a-problem)

## The tools do not show up after installing

Hermes loads a plugin's tools when a chat starts. Open a new chat after the install.

If they are still missing, check that the plugin is on:

```sh
hermes plugins list
hermes plugins enable postkitty
```

## ffmpeg is missing

```text
ffprobe was not found. Install ffmpeg (which provides ffprobe) and retry.
```

Video needs `ffmpeg` and `ffprobe` on your PATH. Text and photos work without them.

```sh
sudo apt install ffmpeg     # Debian, Ubuntu
brew install ffmpeg         # macOS with Homebrew
```

On Windows, install a build from [ffmpeg.org](https://ffmpeg.org/download.html) and add its `bin` folder to your PATH. Then start Hermes again so it sees the new PATH.

## A media step was skipped

The result of a scan has a `notes` list. A note names the input and the reason a step did not run, and Hermes passes it on. In a make result the same thing shows as a target with the status `skipped` and a `reason`.

| The reason says | What to do |
|---|---|
| `Photos cannot be made here: the Python package ... is missing` (or `Videos cannot be made here`) | The install did not finish. Run `hermes plugins install postkitty --force` and answer yes to the Python packages. |
| A download or network error | See the next section. |
| ffprobe or ffmpeg | See the section above. |

The text part of a job still works while a media step is skipped: the drafts are counted and saved.

## The face model could not be downloaded

```text
The face model is not on this machine and the download failed (...). postkitty fetches it once
from github.com (about 230 KB): connect to the internet and ask again, or save <address> into <folder>.
Text posts work without it.
```

The first scan of a photo or a video downloads the face detector, one small file from the OpenCV Zoo repository on GitHub. Offline, or behind a proxy or a firewall, that request fails.

Two ways to fix it:

1. Connect, or allow HTTPS requests to `github.com` and the hosts it redirects to, then ask again. The file is kept, so this happens once.
2. Fetch the file on another machine and save it into the folder the message names. postkitty checks the file's size and SHA-256 before it uses it, and downloads a fresh copy when they do not match.

## Captions cannot be burned in

```text
this ffmpeg build has no libass, so it cannot burn captions in; install an ffmpeg build with libass
or leave out the captions override
```

Captions are drawn by ffmpeg's `ass` filter, which only exists in builds that include libass. `/postkitty doctor` shows it on the Captions row.

- **Debian and Ubuntu:** the `ffmpeg` package includes libass.
- **macOS with Homebrew:** the `ffmpeg` formula comes without libass. Install `ffmpeg-full` and put it first on your PATH:

  ```sh
  brew install ffmpeg-full
  export PATH="$(brew --prefix ffmpeg-full)/bin:$PATH"
  ```

- **Windows:** pick a build whose feature list names libass.

Messages about the subtitle file itself say what to change:

| Message | What to do |
|---|---|
| `captions must be an .srt or .vtt file` | Convert the subtitles to SubRip (`.srt`) or WebVTT (`.vtt`). |
| `captions file not found` | Give the full path of the file. |
| `is not UTF-8 text` | Save the file as UTF-8 and ask again. |
| `has no captions` | The file is empty or holds no text. Check that you gave the right one. |
| `cannot read the caption time` | A time in the file is malformed. The message quotes it. |

## A target failed

A target with the status `failed` did not pass a required check, and the repairs could not fix it. Its file is kept under `work/failed/` and is not copied to `ready/`. The `problems` list says which checks failed.

| The problem says | What to do |
|---|---|
| A subject is cut, or subjects leave the frame | Ask for the whole wide shot (`pad`), or put the focus on one person. |
| The duration is below its minimum | The clip is shorter than the platform accepts. Use a longer clip or leave that platform out. |
| The duration, the file size or the bitrate exceeds its maximum | Ask for a shorter trim. `/postkitty tiktok` shows the limits of one platform. |

When a redo fails, the earlier file that passed stays in `ready/`, and the result names it under `kept`.

## Other messages

Every error comes with a hint that says what to do next: scan again, fix the argument, or run `/postkitty doctor`. Hermes acts on most of them by itself. These are the ones you may be asked about.

| Message | Meaning | What to do |
|---|---|---|
| `input file not found` | The path does not point to a file. | Give the full path, starting from `/` or the drive. |
| `unsupported input type` | The file is not a photo or a video postkitty reads. | Use JPEG, PNG, WebP or GIF for photos and MP4, MOV or WebM for video. |
| `is an animated image` | An animated GIF, WebP or PNG is neither a photo nor a video here. | Export the frame you want as JPEG or PNG, or give a video. |
| `HEIC and AVIF photos need the pillow-heif package` | Pillow cannot open the photo. | Export the photo as JPEG. |
| `has no video stream` | The file holds audio only. | Give a video file. |
| `unknown platform or target` | A name was misspelled. | The message lists the valid names. |
| `takes video; the inputs are photos` | The platform you named has no target for this kind of file. | Add a video, or name a platform that takes photos. |
| `changed since the scan` | The file was edited or replaced after the scan. | Ask Hermes to scan it again. |
| `focus person is not present` | You asked for a person number higher than the number of people found. | The message gives the count. |
| `trim starts at ... but the video is ... long` | The trim begins after the clip ends. | Give a start time inside the clip. |
| `cover_at ... is outside the trim` | The cover time lies outside the trimmed part. | Pick a time between the trim's start and end. |
| `is HDR video and this ffmpeg build has no zscale filter` | The clip is HDR and this ffmpeg cannot convert it. | Install an ffmpeg build with libzimg, or export the clip as SDR. |
| `ffmpeg failed while rendering` | ffmpeg stopped with an error. The message ends with ffmpeg's own last lines. | Try the clip in a player. If it plays, report the message. |
| `trim, cover_at and captions apply to video only` | The target is made from a photo. | Leave those three out for photo targets. |
| `this job is text only, so there is nothing to render again` | A change to a photo or a video was asked for in a job that has only text. | Give a photo or a video and start again. |

## Report a problem

Open an issue at [github.com/mertkayacs/postkitty/issues](https://github.com/mertkayacs/postkitty/issues) with the message you got, the output of `/postkitty doctor`, and what you asked for. `manifest.json` in the job folder holds every check of the run and helps a lot. It contains the paths of your files, so read it before you share it.

For a security problem, follow [SECURITY.md](../SECURITY.md).
