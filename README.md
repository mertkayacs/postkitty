<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/svg/postkitty-logo-on-dark.svg">
    <img src="docs/brand/svg/postkitty-logo-on-light.svg" alt="postkitty" width="300">
  </picture>
</p>

<h1 align="center">One post in.<br>Every platform out.</h1>

<p align="center">
  A Hermes Agent plugin that turns a draft, your photos and a landscape video into posts ready to upload.<br>
  <b>Eight platforms. Faces stay in frame, every file is checked, and it all runs on your machine.</b>
</p>

<p align="center">
  <a href="https://github.com/mertkayacs/postkitty/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/mertkayacs/postkitty/ci.yml?branch=main&style=flat-square&label=CI"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-3b82f6?style=flat-square"></a>
  <img alt="Python 3.11 or newer" src="https://img.shields.io/badge/Python%203.11%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <a href="https://github.com/NousResearch/hermes-agent"><img alt="Hermes Agent plugin" src="https://img.shields.io/badge/Hermes%20Agent-plugin-1E2A44?style=flat-square"></a>
  <img alt="8 platforms" src="https://img.shields.io/badge/platforms-8-B9472E?style=flat-square">
  <a href="https://github.com/mertkayacs/postkitty"><img alt="GitHub stars" src="https://img.shields.io/github/stars/mertkayacs/postkitty?style=flat-square&logo=github&color=8A6D3B"></a>
</p>

<p align="center">
  <a href="#quick-start"><img alt="Install" src="https://img.shields.io/badge/Install-B9472E?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZyBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIj48cGF0aCBkPSJNMTIgMjJWMTIiLz48cGF0aCBkPSJtMTYgMTcgMiAyIDQtNCIvPjxwYXRoIGQ9Ik0yMSAxMS4xMjdWOGEyIDIgMCAwIDAtMS0xLjczbC03LTRhMiAyIDAgMCAwLTIgMGwtNyA0QTIgMiAwIDAgMCAzIDh2OGEyIDIgMCAwIDAgMSAxLjcyOWw3IDRhMiAyIDAgMCAwIDIgLjAwMWwxLjMyLS43NTMiLz48cGF0aCBkPSJNMy4yOSA3IDEyIDEybDguNzEtNSIvPjxwYXRoIGQ9Im03LjUgNC4yNyA4Ljk5NyA1LjE0OCIvPjwvZz48L3N2Zz4%3D&logoColor=white"></a>
  <a href="https://postkitty.mertkayacs.com/media/postkitty-launch.mp4?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=video-badge"><img alt="Launch video" src="https://img.shields.io/badge/Launch%20video-B9472E?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48cGF0aCBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIiBkPSJNNSA1YTIgMiAwIDAgMSAzLjAwOC0xLjcyOGwxMS45OTcgNi45OThhMiAyIDAgMCAxIC4wMDMgMy40NThsLTEyIDdBMiAyIDAgMCAxIDUgMTl6Ii8%2BPC9zdmc%2B&logoColor=white"></a>
  <a href="https://postkitty.mertkayacs.com/?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=website-badge"><img alt="Website" src="https://img.shields.io/badge/Website-1E2A44?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZyBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIxMCIvPjxwYXRoIGQ9Ik0xMiAyYTE0LjUgMTQuNSAwIDAgMCAwIDIwYTE0LjUgMTQuNSAwIDAgMCAwLTIwTTIgMTJoMjAiLz48L2c%2BPC9zdmc%2B&logoColor=white"></a>
  <a href="https://github.com/NousResearch/hermes-agent"><img alt="Hermes Agent" src="https://img.shields.io/badge/Hermes%20Agent-1E2A44?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZyBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIj48cGF0aCBkPSJNMTIgOFY0SDgiLz48cmVjdCB3aWR0aD0iMTYiIGhlaWdodD0iMTIiIHg9IjQiIHk9IjgiIHJ4PSIyIi8%2BPHBhdGggZD0iTTIgMTRoMiIvPjxwYXRoIGQ9Ik0yMCAxNGgyIi8%2BPHBhdGggZD0iTTE1IDEzdjIiLz48cGF0aCBkPSJNOSAxM3YyIi8%2BPC9nPjwvc3ZnPg%3D%3D&logoColor=white"></a>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/hero-dark.webp">
    <img src="docs/assets/readme/hero-light.webp" alt="The postkitty review board for one podcast post: the Instagram Reel, feed photo, Story and TikTok files, each marked Ready with its size, layout note, alt text and passed checks." width="960">
  </picture>
</p>

postkitty by Mert Kaya is a plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent). It is for anyone who posts the same thing to several platforms and does not want to resize, trim and recount it by hand. You give Hermes a draft, some photos and a landscape video. You get back a folder of upload-ready files, copy for each platform, advice on where to post, and a review board that shows every file before you upload it.

postkitty is free and open source under the MIT license.

One of the best free and open source plugins for Hermes Agent on automatic multi social media content editing.

---

## Why postkitty

Each platform has its own sizes, length limits and way of counting characters. postkitty handles all of that on your machine, with no API keys, and nothing is uploaded.

|  |  |
|---|---|
| <img src="docs/assets/readme/icons/scan-face.svg" width="18" height="18" alt=""> **Faces stay in frame** | Every crop is planned around the faces the YuNet detector finds. A clip of two people talking becomes a split screen, and a wide group photo gets a blurred band so nobody is cut off. |
| <img src="docs/assets/readme/icons/list-checks.svg" width="18" height="18" alt=""> **Checked before it is ready** | Every file is checked against the platform's published limits. Failures are repaired, and only passing files go into `ready/`. |
| <img src="docs/assets/readme/icons/type.svg" width="18" height="18" alt=""> **Copy counted the platform's way** | Each draft is counted with its platform's own rule, such as weighted characters on X, graphemes on Bluesky and UTF-16 units on TikTok. Long posts are split into threads. |
| <img src="docs/assets/readme/icons/message-square-text.svg" width="18" height="18" alt=""> **Advice on where to post** | Hermes ranks the platforms for your post and saves the topic, audience and tips in `advice.md`. |
| <img src="docs/assets/readme/icons/layout-grid.svg" width="18" height="18" alt=""> **One board to review** | `board.html` shows every file in a frame of its real shape, with its copy, alt text and checks. Ask for a change and Hermes makes only that file again. |
| <img src="docs/assets/readme/icons/lock.svg" width="18" height="18" alt=""> **Private by default** | postkitty reads only the files you name and writes only inside its job folder and its own data folder. It sends no telemetry, and photos lose their location and camera metadata. |

## A quick tour

<p align="center">
  <img src="docs/assets/readme/tour.webp" alt="A short loop of postkitty reframing landscape clips for vertical video: the frame follows a potter as she moves, two podcast hosts become a split screen, then scenes from public-domain films and cartoons get the same treatment." width="900">
</p>

<table>
  <tr>
    <td width="50%" valign="top">
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/hermes-dark.webp">
        <img src="docs/assets/readme/hermes-light.webp" alt="A Hermes terminal session: a request to get an episode post ready for five platforms, the postkitty_scan, postkitty_copy and postkitty_make calls with their times, and the ranked platforms in the reply.">
      </picture>
      <h3>Ask in plain words</h3>
      Name the platforms and your files and paste the draft. Hermes calls the postkitty tools and replies with the platforms ranked for your post.
    </td>
    <td width="50%" valign="top">
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/faces-dark.webp">
        <img src="docs/assets/readme/faces-light.webp" alt="The original team photo with the center-crop area marked, the 4:5 center crop that cuts off the two people at the edges, and the postkitty 4:5 image that keeps all five people.">
      </picture>
      <h3>Every face stays in frame</h3>
      A center crop of this team photo cuts off the two people at the edges. The postkitty feed image keeps all five.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/copy-dark.webp">
        <img src="docs/assets/readme/copy-light.webp" alt="The Copy section of the review board: the Instagram draft at 216 of 2200 characters with a marker where the feed cuts it off, and the TikTok draft at 128 of 2200 UTF-16 units.">
      </picture>
      <h3>Copy for every platform</h3>
      Each draft shows its count against the platform's limit and where the feed cuts it off, with a button to copy it.
    </td>
    <td width="50%" valign="top">
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="docs/assets/readme/advice-dark.webp">
        <img src="docs/assets/readme/advice-light.webp" alt="The advice panel of the review board: the post&#x27;s topic, audience and tone, a ranked list of Instagram, TikTok, YouTube, LinkedIn and X with a reason for each, and tips.">
      </picture>
      <h3>See where it fits</h3>
      The board opens with the audience and tone of your post, the platforms ranked for it, and tips.
    </td>
  </tr>
</table>

<p align="center"><sub>The board and terminal shots come from one real run on a demo podcast clip and team photo. The people in the demo footage and photos are AI-generated.</sub></p>

## Features

| Output | What it is |
|---|---|
| Video | A landscape clip becomes a vertical video that follows the person talking, or a split screen for two people. Trimmed to each platform's length, with a cover frame. |
| Photos | Every crop keeps every face in frame. Location and camera metadata are removed. |
| Copy | A draft for each platform, counted with that platform's own rule. Long posts are split into threads. |
| Advice | Topic, audience, a ranking of platforms and tips, saved as `advice.md`. |
| Checks | Every file is checked against the platform's published limits and repaired when it fails. Only passing files go into `ready/`. |
| Review board | Every file in a frame of its real shape, with its copy and checks, in one page you open in a browser. |

Ask for a change ("keep him in frame on the LinkedIn video") and Hermes re-renders just that file.

### Platforms

| Platform | Files | Copy limit |
|---|---|---|
| Instagram | Reel and Story 1080×1920, feed photo 1080×1350 | 2,200 characters, 30 hashtags |
| TikTok | Video 1080×1920 | 2,200 UTF-16 units |
| YouTube Shorts | Short 1080×1920 | Title up to 100 characters |
| X | Video 1920×1080, image 1600×900 | 280 weighted characters |
| LinkedIn | Video 1080×1350, image 1080×1080 | 3,000 characters |
| Threads | Video 1080×1920, image 1080×1350 | 500 characters |
| Bluesky | Video 1080×1920, image 1080×1350 | 300 graphemes |
| Facebook | Reel 1080×1920, feed photo 1080×1350 | 63,206 characters |

<sub>Every limit in [data/platforms.yaml](data/platforms.yaml) links to the page it came from and the date it was checked, last in November 2026.</sub>

## Quick start

Install the plugin and turn it on:

```sh
hermes plugins install mertkayacs/postkitty --enable
```

Then talk to Hermes:

```text
Make this post ready for Instagram, TikTok, YouTube Shorts and LinkedIn.
clip.mp4 is the video, team.jpg is our team.
My draft: New episode is out...
```

postkitty needs Hermes Agent 0.22.7 or newer and `ffmpeg` with `ffprobe` on your PATH. Type `/postkitty` in a Hermes chat to list every target with its size and main limits.

## Launch video

<p align="center"><a href="https://postkitty.mertkayacs.com/media/postkitty-launch.mp4?utm_source=github&amp;utm_medium=readme&amp;utm_campaign=postkitty-repo&amp;utm_content=video-poster"><img src="docs/launch-poster.jpg" width="720" alt="Watch the postkitty launch video"></a></p>

## FAQ

<details>
<summary><b>Does anything leave my machine?</b></summary>

postkitty reads only the files you name and writes only inside its job folder and its own data folder. It sends no telemetry. The one download is the YuNet face detector, fetched once from the OpenCV Zoo and verified before use. The copy and advice come from the model your Hermes is set up with.
</details>

<details>
<summary><b>Which tools does Hermes call?</b></summary>

Hermes calls five tools, in this order.

| Tool | What it does |
| --- | --- |
| `postkitty_scan` | Reads your photos, videos and draft, and plans a framing for each platform. |
| `postkitty_copy` | Stores the advice and the drafts, and checks each draft with its platform's counting rule. |
| `postkitty_make` | Renders every file, checks it, repairs failures and writes the review board. |
| `postkitty_redo` | Re-renders one platform with a different focus, layout, trim or cover frame. |
| `postkitty_check` | Checks any file against one platform, including files postkitty did not make. |

</details>

<details>
<summary><b>Which settings can I change?</b></summary>

Set these on the plugin's settings page in Hermes, or under `plugins.entries.postkitty.settings` in `config.yaml`.

| Key | Default | Meaning |
| --- | --- | --- |
| `output_dir` | empty | Where job folders go. Empty means `./postkitty` in the session's working folder. |
| `default_platforms` | empty | Platforms to make when you name none. Empty means every platform that fits the input. |
| `loudness_lufs` | -14 | Loudness target for video audio. |

</details>

<details>
<summary><b>Can it check files it did not make?</b></summary>

Yes. `postkitty_check` checks any photo or video against one platform's limits, wherever the file came from.
</details>

<details>
<summary><b>What is postkitty built on?</b></summary>

[OpenCV](https://opencv.org) and the [YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) face detector, [FFmpeg](https://ffmpeg.org), [Pillow](https://python-pillow.org) and [NumPy](https://numpy.org), with the counting rules of [twitter-text](https://github.com/twitter/twitter-text) and the [AT Protocol lexicons](https://github.com/bluesky-social/atproto). Seam carving can use [caire](https://github.com/esimov/caire) by Endre Simo. The people in the demo photos are AI-generated.

</details>

## Development

```sh
python -m pytest -q
ruff check .
```

The tests use synthetic clips and a stand-in face detector. GitHub Actions runs them on Python 3.11 and 3.12.

If postkitty is useful to you, a ⭐ helps other people find it.

## License

[MIT](LICENSE). postkitty is built by [Mert Kaya](https://mertkayacs.com/?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=license-author) ([@mertkayaai](https://x.com/mertkayaai) on X, [@mertkayacs](https://github.com/mertkayacs) on GitHub) at Eschatia Labs, an independent, non-profit open-source AI research lab. Photos behind the screenshots are credited in [docs/assets/readme/CREDITS.md](docs/assets/readme/CREDITS.md).

[![views](https://hits.sh/github.com/mertkayacs/postkitty.svg?view=today-total&style=flat-square&label=views&color=B9472E&labelColor=1E2A44)](https://postkitty.mertkayacs.com/?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=views-badge)
