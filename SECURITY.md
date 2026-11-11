# Security

## Report a problem

Please report a vulnerability in private: open the repository's **Security** tab on GitHub and choose **Report a vulnerability**. Say what you did, what happened, and which version you ran. Keep the details out of public issues until a fix is released.

The latest release is the supported version.

## What postkitty touches

postkitty runs on your machine as a Hermes Agent plugin. This is everything it reaches:

| Area | What it does |
|---|---|
| Network | One download: the YuNet face detector, fetched from the OpenCV Zoo repository on GitHub the first time a photo or a video is scanned. The address is pinned to one commit, and the file is used only when its size and SHA-256 match the values in `engine/detect/models.py`. There is no other request and no telemetry. |
| Files it reads | The photos, videos and subtitle files whose paths you give it. They are never changed. |
| Files it writes | The job folder (`./postkitty` in the session's working folder, or the `output_dir` setting) and the plugin's data folder in the Hermes home, `plugin-data/postkitty/`, which holds the model and cached detections. |
| Commands it runs | `ffmpeg` and `ffprobe`, with file paths passed as arguments and never through a shell. The seam layout runs `caire` when it is installed. |
| Background processes | None. Every process ends with the tool call that started it. |
| Credentials | None. It needs no API key and stores no account data. |
| Posting | None. It never posts, uploads or schedules anything. |

Output photos are saved without location or camera metadata.

Your draft text is sent to the model your Hermes is set up with, by Hermes, as in any chat. The plugin does not send it anywhere.

## In scope

- A crafted photo, video or subtitle file that makes postkitty read or write outside the job folder and its data folder, or run a command.
- A way to make it use a face model that fails the checksum.
- A job id or a file name that escapes the output folder.

The hosted playground at postkitty.mertkayacs.com runs the same engine. Report problems with it the same way.
