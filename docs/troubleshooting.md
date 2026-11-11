# Troubleshooting

Start here. Type this in a Hermes chat:

```text
/postkitty doctor
```

It checks Python, ffmpeg and ffprobe, OpenCV, Pillow, the face model and the output folder, and prints one fix line for each problem. The sections below cover the messages you can meet in a chat.

- [The tools do not show up after installing](#the-tools-do-not-show-up-after-installing)
- [ffmpeg is missing](#ffmpeg-is-missing)
- [A media step was skipped](#a-media-step-was-skipped)
- [The face model could not be downloaded](#the-face-model-could-not-be-downloaded)
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
| The video or image engine needs a Python package | The install did not finish. Run `hermes plugins install postkitty --force` and answer yes to the Python packages. |
| A download or network error | See the next section. |
| ffprobe or ffmpeg | See the section above. |

The text part of a job still works while a media step is skipped: the drafts are counted and saved.

## The face model could not be downloaded

The first scan of a photo or a video downloads the face detector, one small file from the OpenCV Zoo repository on GitHub. Behind a proxy or a firewall that request can fail, and the scan note carries the network error.

Two ways to fix it:

1. Allow HTTPS requests to `github.com` and the hosts it redirects to for that one download, then scan again. The file is kept, so this happens once.
2. Fetch the file on another machine and put it in the model folder yourself. The address is `YUNET_URL` in [engine/detect/models.py](../engine/detect/models.py), and the folder is `plugin-data/postkitty/models/` in your Hermes home. postkitty verifies the file's checksum before it uses it.

```text
YuNet model checksum mismatch: <path>
```

The file in the model folder is damaged or is another file. Delete it and scan again.

## A target failed

A target with the status `failed` did not pass a required check, and the repairs could not fix it. Its file is kept under `work/failed/` and is not copied to `ready/`. The `problems` list says which checks failed.

| The problem says | What to do |
|---|---|
| A subject is cut, or subjects leave the frame | Ask for the whole wide shot (`pad`), or put the focus on one person. |
| The duration is below its minimum | The clip is shorter than the platform accepts. Use a longer clip or leave that platform out. |
| The duration, the file size or the bitrate exceeds its maximum | Ask for a shorter trim. `/postkitty tiktok` shows the limits of one platform. |

When a redo fails, the earlier file that passed stays in `ready/`, and the result names it under `kept`.

## Other messages

| Message | Meaning | What to do |
|---|---|---|
| `input file not found` | The path does not point to a file. | Give the full path, starting from `/` or the drive. |
| `unsupported input type` | The file is not a photo or a video postkitty reads. | Use JPEG, PNG, WebP or GIF for photos and MP4, MOV or WebM for video. |
| `is an animated GIF` | An animated GIF is neither a photo nor a video here. | Export one frame as JPEG or PNG, or give a video. |
| `HEIC and AVIF photos need the pillow-heif package` | Pillow cannot open the photo. | Export the photo as JPEG. |
| `has no video stream` | The file holds audio only. | Give a video file. |
| `unknown platform or target` | A name was misspelled. | The message lists the valid names. |
| `takes video; the inputs are photos` | The platform you named has no target for this kind of file. | Add a video, or name a platform that takes photos. |
| `changed since the scan` | The file was edited or replaced after the scan. | Ask Hermes to scan it again. |
| `focus person is not present` | You asked for a person number higher than the number of people found. | The message gives the count. |
| `trim must be inside the source duration` | A trim time lies outside the clip. | Give times inside the clip. |
| `cover_at must be inside the trim` | The cover time lies outside the trimmed part. | Pick a time between the trim's start and end. |
| `trim and cover_at apply to video only` | The target is made from a photo. | Leave those two out for photo targets. |

## Report a problem

Open an issue at [github.com/mertkayacs/postkitty/issues](https://github.com/mertkayacs/postkitty/issues) with the message you got, the output of `/postkitty doctor`, and what you asked for. `manifest.json` in the job folder holds every check of the run and helps a lot. It contains the paths of your files, so read it before you share it.

For a security problem, follow [SECURITY.md](../SECURITY.md).
