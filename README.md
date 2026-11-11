<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/svg/postkitty-logo-on-dark.svg">
    <img src="docs/brand/svg/postkitty-logo-on-light.svg" alt="postkitty" width="300">
  </picture>
</p>

<h1 align="center">One post in.<br>Every platform out.</h1>

<p align="center">
  A Hermes Agent plugin for your text, photos and video. It fixes and rewrites your draft for each platform, keeps every face in frame, and checks every file before you post.<br>
  <b>Eight platforms, every file checked, all on your machine.</b>
</p>

<p align="center">
  <a href="https://github.com/mertkayacs/postkitty/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/mertkayacs/postkitty/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-3b82f6?style=flat-square"></a>
  <img alt="Python 3.11 or newer" src="https://img.shields.io/badge/Python%203.11%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <a href="https://github.com/NousResearch/hermes-agent"><img alt="Hermes Agent plugin" src="https://img.shields.io/badge/Hermes%20Agent-plugin-1E2A44?style=flat-square"></a>
  <img alt="8 platforms" src="https://img.shields.io/badge/platforms-8-B9472E?style=flat-square">
  <a href="https://github.com/mertkayacs/postkitty"><img alt="GitHub stars" src="https://img.shields.io/github/stars/mertkayacs/postkitty?style=flat-square&logo=github&color=8A6D3B"></a>
</p>

<p align="center">
  <a href="#install"><img alt="Install" src="https://img.shields.io/badge/Install-B9472E?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZyBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIj48cGF0aCBkPSJNMTIgMjJWMTIiLz48cGF0aCBkPSJtMTYgMTcgMiAyIDQtNCIvPjxwYXRoIGQ9Ik0yMSAxMS4xMjdWOGEyIDIgMCAwIDAtMS0xLjczbC03LTRhMiAyIDAgMCAwLTIgMGwtNyA0QTIgMiAwIDAgMCAzIDh2OGEyIDIgMCAwIDAgMSAxLjcyOWw3IDRhMiAyIDAgMCAwIDIgLjAwMWwxLjMyLS43NTMiLz48cGF0aCBkPSJNMy4yOSA3IDEyIDEybDguNzEtNSIvPjxwYXRoIGQ9Im03LjUgNC4yNyA4Ljk5NyA1LjE0OCIvPjwvZz48L3N2Zz4%3D&logoColor=white"></a>
  <a href="https://postkitty.mertkayacs.com/media/explainer.mp4?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=video-badge"><img alt="Watch the video" src="https://img.shields.io/badge/Watch%20the%20video-B9472E?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48cGF0aCBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIiBkPSJNNSA1YTIgMiAwIDAgMSAzLjAwOC0xLjcyOGwxMS45OTcgNi45OThhMiAyIDAgMCAxIC4wMDMgMy40NThsLTEyIDdBMiAyIDAgMCAxIDUgMTl6Ii8%2BPC9zdmc%2B&logoColor=white"></a>
  <a href="https://postkitty.mertkayacs.com/try/?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=try-badge"><img alt="Try it" src="https://img.shields.io/badge/Try%20it-1E2A44?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZyBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIj48cGF0aCBkPSJNMTQgNC4xIDEyIDYiLz48cGF0aCBkPSJtNS4xIDgtMi45LS44Ii8%2BPHBhdGggZD0ibTYgMTItMS45IDIiLz48cGF0aCBkPSJNNy4yIDIuMiA4IDUuMSIvPjxwYXRoIGQ9Ik05LjAzNyA5LjY5YS40OTguNDk4IDAgMCAxIC42NTMtLjY1M2wxMSA0LjVhLjUuNSAwIDAgMS0uMDc0Ljk0OWwtNC4zNDkgMS4wNDFhMSAxIDAgMCAwLS43NC43MzlsLTEuMDQgNC4zNWEuNS41IDAgMCAxLS45NS4wNzR6Ii8%2BPC9nPjwvc3ZnPg%3D%3D&logoColor=white"></a>
  <a href="https://postkitty.mertkayacs.com/docs/?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=docs-badge"><img alt="Docs" src="https://img.shields.io/badge/Docs-1E2A44?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZyBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIj48cGF0aCBkPSJNMTIgNXYxNiIvPjxwYXRoIGQ9Ik0yMC4wMDEgMTlBMiAyIDAgMDAyMiAxN1Y1YTIgMiAwIDAwLTEuOTk5LTJMMTYgMy4wMDJBNSA1IDAgMDAxMiA1YTUgNSAwIDAwLTQtMkg0YTIgMiAwIDAwLTIgMnYxMmEyIDIgMCAwMDEuOTk5IDJIOGE1IDUgMCAwMTQgMiA1IDUgMCAwMTQtMnoiLz48L2c%2BPC9zdmc%2B&logoColor=white"></a>
  <a href="https://postkitty.mertkayacs.com/?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=website-badge"><img alt="Website" src="https://img.shields.io/badge/Website-1E2A44?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZyBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIxMCIvPjxwYXRoIGQ9Ik0xMiAyYTE0LjUgMTQuNSAwIDAgMCAwIDIwYTE0LjUgMTQuNSAwIDAgMCAwLTIwTTIgMTJoMjAiLz48L2c%2BPC9zdmc%2B&logoColor=white"></a>
  <a href="https://github.com/NousResearch/hermes-agent"><img alt="Hermes Agent" src="https://img.shields.io/badge/Hermes%20Agent-1E2A44?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZyBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIj48cGF0aCBkPSJNMTIgOFY0SDgiLz48cmVjdCB3aWR0aD0iMTYiIGhlaWdodD0iMTIiIHg9IjQiIHk9IjgiIHJ4PSIyIi8%2BPHBhdGggZD0iTTIgMTRoMiIvPjxwYXRoIGQ9Ik0yMCAxNGgyIi8%2BPHBhdGggZD0iTTE1IDEzdjIiLz48cGF0aCBkPSJNOSAxM3YyIi8%2BPC9nPjwvc3ZnPg%3D%3D&logoColor=white"></a>
</p>

postkitty by Mert Kaya is a plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent) that turns one post (a draft, a photo, a landscape video, or only text) into a folder of upload-ready files for Instagram, TikTok, YouTube Shorts, X, LinkedIn, Threads, Bluesky and Facebook, each one checked against that platform's published limits and repaired when it fails.

One of the best free and open source plugins for Hermes Agent on automatic multi social media content editing.

[![Watch the postkitty video: one film scene with a box around each face, and the Instagram Reel, TikTok and X files made from it](docs/explainer-poster.jpg)](https://postkitty.mertkayacs.com/media/explainer.mp4?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=video-poster)

---

## What the plugin does on your machine

- <img src="docs/assets/readme/icons/scan-face.svg" width="18" height="18" alt=""> **Finds the faces in a photo and tracks them through a video.** Crops and vertical clips are built around those people, so they stay in frame.
- <img src="docs/assets/readme/icons/video.svg" width="18" height="18" alt=""> **Renders with ffmpeg.** You get upload files at each platform's size, trimmed to its length, and every video comes with a cover frame.
- <img src="docs/assets/readme/icons/type.svg" width="18" height="18" alt=""> **Counts text the way each platform does.** X is counted by the rules of its own twitter-text library, where a link is 23 characters and an emoji 2. Threads counts every emoji as its UTF-8 bytes, Bluesky counts graphemes and TikTok counts UTF-16 units.
- <img src="docs/assets/readme/icons/list-checks.svg" width="18" height="18" alt=""> **Checks every file against the platform's published limits and repairs what fails.** Only passing files reach `ready/`.
- <img src="docs/assets/readme/icons/layout-grid.svg" width="18" height="18" alt=""> **Builds a review board,** one page that shows every file with its text, alt text and checks.
- <img src="docs/assets/readme/icons/square-terminal.svg" width="18" height="18" alt=""> **Works without the model too.** `/postkitty` shows every size and limit, checks your setup and checks a file. `hermes postkitty` does the same from a terminal and makes the files, for scripts and cron jobs.

The words come from the model your Hermes uses: the rewritten drafts, the advice on where to post, and the alt text. The rest is code in this repository.

![A landscape podcast frame with a box around each of the two hosts, and the vertical clip made from it: one host in the top half, the other in the bottom half.](docs/assets/readme/split-screen.jpg)

## Install

```sh
hermes plugins install postkitty
```

Answer yes when Hermes asks to install the Python packages and to turn the plugin on. Then open a new chat, because Hermes loads a plugin's tools when a chat starts.

## What you need

- **Hermes Agent 0.22.7 or newer**, running on Python 3.11 or newer.
- **Five Python packages:** OpenCV, NumPy, Pillow, regex and ruamel.yaml. Hermes installs them during the install step.
- **ffmpeg with ffprobe, for video only.** Text and photos work without it. A Hermes set up with the official installer brings its own ffmpeg: on Windows and most Linux systems there is nothing to install, and on macOS that copy comes without ffprobe, so run `brew install ffmpeg` once. Burning in captions needs an ffmpeg build with libass and one font on the machine, which a bare server or a container may not have.

To check all of it, type this in a Hermes chat. It prints one fix line for each thing that is missing.

```text
/postkitty doctor
```

## Say this to your Hermes

Hermes can do the install for you. Send these two messages, the second one in a new chat.

```text
Install the postkitty plugin for me: run `hermes plugins install postkitty --yes-deps --enable` in the terminal. When it finishes, tell me to open a new chat so its tools load.
```

```text
Use postkitty to turn this into posts for X, LinkedIn and Instagram and fix my wording: [your draft, or the path to a photo or video]
```

## What it can do

Each line starts with a request you can paste, followed by what comes back.

- **Text.** "Fix my wording and write this for X, LinkedIn and Threads: [your draft]"

  Your draft comes back with the spelling and grammar fixed, in one version per platform, each counted to fit. A long post can become a thread.

- **Photos.** "Make team.jpg ready for Instagram and Bluesky, and keep everyone in the picture."

  One image per feed, framed around the people in it, with location and camera metadata removed.

- **Video.** "Turn talk.mp4 into vertical clips for TikTok, Reels and Shorts."

  Vertical clips that follow the person on screen. Two people get a split screen, a cut to whoever is talking, or the whole wide shot.

- **Captions.** "Burn the subtitles from talk.srt into the TikTok clip."

  The lines of your `.srt` or `.vtt` file are drawn into the video, clear of the platform's buttons.

- **Checks.** "Will this file upload to TikTok? [path to the file]"

  A pass or a fail against TikTok's limits, with every failing check named. This works for files postkitty did not make.

postkitty never posts, uploads or schedules anything. You upload the files in `ready/` yourself.

![The postkitty review board for one podcast post: the Instagram Reel, feed photo, Story and TikTok files, each marked Ready with its size, layout note, alt text and passed checks.](docs/assets/readme/hero.jpg)

*The review board of one real run on a demo podcast clip and team photo. The people in the demo footage and photos are AI-generated.*

## How to ask

- Name the platforms: "for Instagram and TikTok" tells postkitty which files to make.
- Give the path of the photo or the video and paste your draft. One job takes one photo, one video, or one of each.
- Tell it who has to stay in frame, for example "keep everyone in the picture" or "focus on the person on the left".
- With two people on camera, name the layout: a split screen, a cut to whoever is talking, or the whole wide shot.
- A trim and a cover frame need times: "use 0:12 to 0:48 and take the cover at 0:20".
- Ask for a change in plain words afterwards: "shorter for X" or "more formal on LinkedIn". Hermes redoes only that part.

[docs/how-to-ask.md](docs/how-to-ask.md) is the full guide, with a vague request next to a clear one for each case.

## Platforms

- **Instagram.** Reel and Story 1080×1920, feed photo 1080×1350. Text up to 2,200 characters and 5 hashtags.
- **TikTok.** Video 1080×1920. Text up to 2,200 UTF-16 units.
- **YouTube Shorts.** Short 1080×1920. Title up to 100 characters.
- **X.** Video 1920×1080, image 1600×900. Text up to 280 weighted characters, where a link counts 23.
- **LinkedIn.** Video 1080×1350, image 1080×1080. Text up to 3,000 characters.
- **Threads.** Video 1080×1920, image 1080×1350. Text up to 500 characters, with every emoji counted as its UTF-8 bytes.
- **Bluesky.** Video 1080×1920, image 1080×1350. Text up to 300 graphemes.
- **Facebook.** Reel 1080×1920, feed photo 1080×1350. Text up to 63,206 characters.

[docs/platforms.md](docs/platforms.md) lists every limit with the page it came from and the date it was checked. The data lives in [data/platforms.yaml](data/platforms.yaml).

## Try it in the browser

Paste a draft or drop a photo or a video at [postkitty.mertkayacs.com/try](https://postkitty.mertkayacs.com/try/?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=try-link) and get the result for each platform, with nothing to install.

The same engine answers over HTTP at `https://postkitty.mertkayacs.com/api`. [docs/api.md](docs/api.md) has the endpoints, and the [docs site](https://postkitty.mertkayacs.com/docs/?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=docs-link) carries every guide in English, Turkish and German.

## Documentation

- [How to ask](docs/how-to-ask.md): requests that get the right result the first time
- [Tools](docs/tools.md): the five tools, the `/postkitty` and `hermes postkitty` commands and the settings
- [Layouts](docs/layouts.md): crop, split, speaker, seam, pad and focus, with examples
- [Platforms](docs/platforms.md): every size and limit with its source
- [HTTP API](docs/api.md): the hosted API behind the playground
- [Architecture](docs/architecture.md): how the code is organised and how a job runs
- [Troubleshooting](docs/troubleshooting.md): what each failure message means and what to do

## Good to know

<details>
<summary><b>What it touches on your machine</b></summary>

postkitty touches these things on your machine:

- **Network:** one download. The first time a photo or a video is scanned, postkitty fetches the YuNet face detector from the OpenCV Zoo repository on GitHub, pinned to one commit, and checks its size and SHA-256 before using it. It makes no other request and sends no telemetry.
- **Files it reads:** the photos, videos and subtitle files you name. It leaves them unchanged.
- **Files it writes:** the job folder (`./postkitty` in the session's working folder unless you set another one) and its own data folder in the Hermes home, `plugin-data/postkitty/`, which holds the face model and cached detections. Nothing is written into the plugin's install folder.
- **Commands it runs:** `ffmpeg` and `ffprobe`, only while a tool call is working. The seam layout uses `caire` when it is installed.
- **Background processes:** none.
- **Credentials:** none. It needs no API key and stores no account data.
- **The model:** your draft goes to the model your Hermes is set up with, as in any Hermes chat. That model writes the text, the advice and the alt text.

[SECURITY.md](SECURITY.md) says how to report a security problem.

</details>

<details>
<summary><b>Where are my files?</b></summary>

Each job gets its own folder. The files to upload are under `ready/`, one folder per platform.

```text
postkitty/20261111-0930-talk/
  ready/
    instagram/   reel.mp4  reel_cover.jpg  feed.jpg  post.txt  alt.txt
    tiktok/      tiktok.mp4  tiktok_cover.jpg  post.txt
    x/           video.mp4  video_cover.jpg  thread.txt
  board.html     the review board
  advice.md      the platforms ranked for this post, with tips
  contact.png    every file on one image
  manifest.json  what was made, with every check
  work/          caches and intermediate renders
```

</details>

<details>
<summary><b>Which tools does Hermes call?</b></summary>

Hermes calls five tools, in this order. [docs/tools.md](docs/tools.md) has their arguments and results.

1. `postkitty_scan` reads your photo or video and your draft, and plans a framing for each platform. It renders nothing.
2. `postkitty_write` counts each platform's text with its real rule and writes the text files.
3. `postkitty_make` renders every file, checks it, repairs failures and builds the review board.
4. `postkitty_redo` makes one photo or video output again with another layout, focus, trim, cover frame or captions.
5. `postkitty_check` checks a file postkitty did not make against one platform.

</details>

<details>
<summary><b>Which commands work without the model?</b></summary>

postkitty has commands that answer from the plugin, with no model involved.

In a Hermes chat:

- `/postkitty` shows what it does, example requests and every target with its size and limits.
- `/postkitty tiktok` shows one platform.
- `/postkitty doctor` checks your setup and prints one fix line for each problem.
- `/postkitty check clip.mp4 tiktok` checks a file against a target.

In a terminal, for scripts, cron jobs and release automation:

```sh
hermes postkitty make clip.mp4 --text-file post.txt --platforms tiktok,x
hermes postkitty check clip.mp4 --target tiktok
hermes postkitty platforms
hermes postkitty doctor
```

`hermes postkitty make` uses your text as written: it counts and splits it for each platform and does not rewrite it. It exits with 0 only when every file is ready. [docs/tools.md](docs/tools.md#the-hermes-postkitty-terminal-command) has the options and the exit codes.

</details>

<details>
<summary><b>Which settings can I change?</b></summary>

postkitty has three settings. Change them on the plugin's settings page in Hermes, or under `plugins.entries.postkitty.settings` in `config.yaml`.

- **`output_dir`**, empty by default: where job folders go. Empty means `./postkitty` in the session's working folder.
- **`default_platforms`**, empty by default: the platforms to make when you name none. Empty means every platform that fits the input.
- **`loudness_lufs`**, -14 by default: the loudness target for video audio, from -70 to -5.

</details>

<details>
<summary><b>A real run: one draft, rewritten for X, Bluesky and LinkedIn</b></summary>

This is one real run: a rough draft, and what came back for X, Bluesky and LinkedIn.

**The draft**

> new episode of two builders is out!! maya and sam talks about how we shiped our app in one weekend, what we cut what broke at 2am and why the launch posts took longer then the code lol. its honestly the most usefull episode we did so far for anyone building on there own

**X** · 245 of 280 weighted characters

> New episode of Two Builders is out. Maya and Sam talk about how we shipped our app in one weekend: what we cut, what broke at 2am, and why the launch posts took longer than the code. Our most useful episode so far if you're building on your own.

**Bluesky** · 221 of 300 graphemes

> New Two Builders episode is out. Maya and Sam on shipping our app in one weekend: what we cut, what broke at 2am, and why the launch posts took longer than the code. Our most useful one yet if you're building on your own.

**LinkedIn** · 319 of 3,000 characters

> New episode of Two Builders is out.
>
> Maya and Sam talk about how we shipped our app in one weekend: what we cut, what broke at 2am, and why the launch posts took longer than the code.
>
> It's honestly the most useful episode we've done so far, especially if you're building on your own.
>
> #BuildInPublic #Startups #Podcast

The next message in the same chat asked for a change:

> Make the LinkedIn post more formal, and turn the X post into a thread of two posts.

**X thread, post 1** · 98 of 280 weighted characters

> New episode of Two Builders is out. Maya and Sam talk about how we shipped our app in one weekend.

**X thread, post 2** · 146 of 280 weighted characters

> What we cut, what broke at 2am, and why the launch posts took longer than the code. Our most useful episode so far if you're building on your own.

**LinkedIn, more formal** · 337 of 3,000 characters

> We have released a new episode of Two Builders.
>
> Maya and Sam discuss how we shipped our app in one weekend: what we cut, what broke at 2am, and why the launch posts took longer to produce than the code.
>
> It is the most useful episode we have made so far, particularly for anyone building on their own.
>
> #BuildInPublic #Startups #Podcast

<details>
<summary><b>It works in your language: the same post in Turkish and German</b></summary>

The same post works in other languages. Here it is in Turkish and in German.

**Turkish draft**

> two builders'ın yeni bölümü çıktı!! maya ve sam uygulamamızı bir hafta sonunda nasıl yayınladığımızı anlatıyo, neleri kestik gece 2de ne bozuldu ve lansman paylaşımları neden koddan uzun sürdü. kendi başına bir şey geliştiren herkez için şimdiye kadarki en faydalı bölüm bence

**X** · 270 of 280 weighted characters

> Two Builders'ın yeni bölümü çıktı! Maya ve Sam, uygulamamızı bir hafta sonunda nasıl yayınladığımızı anlatıyor: neleri kestik, gece 2'de ne bozuldu, lansman paylaşımları neden koddan uzun sürdü. Kendi başına geliştiren herkes için şimdiye kadarki en faydalı bölüm bence.

**German draft**

> neue folge von two builders ist drausen!! maya und sam erzählen wie wir unsere app an einem wochenende gelauncht haben, was wir gestrichen haben was um 2 uhr nachts kaputt ging und warum die launch posts länger gedauert haben als der code. ehrlich die nützlichste folge bis jetzt für alle die alleine was bauen

**X** · 235 of 280 weighted characters

> Neue Folge von Two Builders ist da. Maya und Sam erzählen, wie wir unsere App an einem Wochenende gelauncht haben: was wir gestrichen haben, was um 2 Uhr nachts kaputt ging und warum die Launch-Posts länger gedauert haben als der Code.

</details>

*The text in these runs comes from the model Hermes used, Claude Sonnet 5.5. postkitty counted and checked every version.*

</details>

<details>
<summary><b>How do I update or remove it?</b></summary>

To update or remove postkitty, use the Hermes plugin commands:

```sh
hermes plugins update postkitty
hermes plugins remove postkitty
```

Your job folders stay where they are when you remove the plugin.

</details>

<details>
<summary><b>What is postkitty built on?</b></summary>

postkitty is built on [OpenCV](https://opencv.org) and the [YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) face detector, [FFmpeg](https://ffmpeg.org), [Pillow](https://python-pillow.org) and [NumPy](https://numpy.org), with the counting rules of [twitter-text](https://github.com/twitter/twitter-text) and the [AT Protocol lexicons](https://github.com/bluesky-social/atproto). Seam carving can use [caire](https://github.com/esimov/caire) by Endre Simo.

[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) lists the material this repository takes from other projects, with the licence of each.

</details>

## Development

```sh
python -m pytest -q
ruff check .
```

The tests use synthetic clips and a stand-in face detector, so they download nothing. GitHub Actions runs them on Linux, macOS and Windows, and installs the plugin into a brand-new Hermes on every change.

- `plugin.yaml`, `__init__.py`: the manifest and `register(ctx)`
- `schemas.py`, `tools.py`: what Hermes sees, and the handlers behind it
- `command.py`: the `/postkitty` command
- `engine/`: the library, with `pipeline`, `photo`, `video`, `text`, `verify` and `board`
- `data/platforms.yaml`: every size and limit, with its source
- `skills/postkitty/SKILL.md`: the workflow Hermes follows

[docs/architecture.md](docs/architecture.md) explains the layers and the life of a job. [CONTRIBUTING.md](CONTRIBUTING.md) covers setup, style and how to add a platform, and [CHANGELOG.md](CHANGELOG.md) lists what changed in each release.

If postkitty is useful to you, a star helps other people find it.

## License

[MIT](LICENSE). postkitty is built by [Mert Kaya](https://mertkayacs.com/?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=license-author) ([@mertkayaai](https://x.com/mertkayaai) on X, [@mertkayacs](https://github.com/mertkayacs) on GitHub) at Eschatia Labs, an independent, non-profit open-source AI research lab. Photos behind the screenshots are credited in [docs/assets/readme/CREDITS.md](docs/assets/readme/CREDITS.md).

Material from other projects is listed with its licences in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

[![views](https://hits.sh/github.com/mertkayacs/postkitty.svg?view=today-total&style=flat-square&label=views&color=B9472E&labelColor=1E2A44)](https://postkitty.mertkayacs.com/?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=views-badge)
