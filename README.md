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
  <a href="#quick-start"><img alt="Install" src="https://img.shields.io/badge/Install-B9472E?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZyBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIj48cGF0aCBkPSJNMTIgMjJWMTIiLz48cGF0aCBkPSJtMTYgMTcgMiAyIDQtNCIvPjxwYXRoIGQ9Ik0yMSAxMS4xMjdWOGEyIDIgMCAwIDAtMS0xLjczbC03LTRhMiAyIDAgMCAwLTIgMGwtNyA0QTIgMiAwIDAgMCAzIDh2OGEyIDIgMCAwIDAgMSAxLjcyOWw3IDRhMiAyIDAgMCAwIDIgLjAwMWwxLjMyLS43NTMiLz48cGF0aCBkPSJNMy4yOSA3IDEyIDEybDguNzEtNSIvPjxwYXRoIGQ9Im03LjUgNC4yNyA4Ljk5NyA1LjE0OCIvPjwvZz48L3N2Zz4%3D&logoColor=white"></a>
  <a href="https://postkitty.mertkayacs.com/media/postkitty-launch.mp4?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=video-badge"><img alt="Launch video" src="https://img.shields.io/badge/Launch%20video-B9472E?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48cGF0aCBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIiBkPSJNNSA1YTIgMiAwIDAgMSAzLjAwOC0xLjcyOGwxMS45OTcgNi45OThhMiAyIDAgMCAxIC4wMDMgMy40NThsLTEyIDdBMiAyIDAgMCAxIDUgMTl6Ii8%2BPC9zdmc%2B&logoColor=white"></a>
  <a href="https://postkitty.mertkayacs.com/?utm_source=github&utm_medium=readme&utm_campaign=postkitty-repo&utm_content=website-badge"><img alt="Website" src="https://img.shields.io/badge/Website-1E2A44?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZyBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIxMCIvPjxwYXRoIGQ9Ik0xMiAyYTE0LjUgMTQuNSAwIDAgMCAwIDIwYTE0LjUgMTQuNSAwIDAgMCAwLTIwTTIgMTJoMjAiLz48L2c%2BPC9zdmc%2B&logoColor=white"></a>
  <a href="https://github.com/NousResearch/hermes-agent"><img alt="Hermes Agent" src="https://img.shields.io/badge/Hermes%20Agent-1E2A44?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgd2lkdGg9IjI0IiBoZWlnaHQ9IjI0Ij48ZyBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIj48cGF0aCBkPSJNMTIgOFY0SDgiLz48cmVjdCB3aWR0aD0iMTYiIGhlaWdodD0iMTIiIHg9IjQiIHk9IjgiIHJ4PSIyIi8%2BPHBhdGggZD0iTTIgMTRoMiIvPjxwYXRoIGQ9Ik0yMCAxNGgyIi8%2BPHBhdGggZD0iTTE1IDEzdjIiLz48cGF0aCBkPSJNOSAxM3YyIi8%2BPC9nPjwvc3ZnPg%3D%3D&logoColor=white"></a>
</p>

<p align="center">
  <img src="docs/assets/readme/hero.jpg" alt="The postkitty review board for one podcast post: the Instagram Reel, feed photo, Story and TikTok files, each marked Ready with its size, layout note, alt text and passed checks." width="960">
</p>

postkitty by Mert Kaya is a plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent). It is for anyone who posts the same thing to several platforms and does not want to rewrite, resize, trim and recount it by hand. You give Hermes a draft, some photos and a landscape video, or only the draft. You get back your text fixed and rewritten for each platform, upload-ready files, advice on where to post, and a review board that shows every file before you upload it.

postkitty is free and open source under the MIT license.

One of the best free and open source plugins for Hermes Agent on automatic multi social media content editing.

---

## Your draft, fixed for every platform

Paste a rough draft. postkitty fixes the spelling, grammar and punctuation, smooths out clumsy sentences and keeps your voice. Then it writes a version for each platform and counts it the way that platform does, so nothing gets cut off. This is one real run.

**Your draft**

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

Threads and Instagram got their own versions in the same run.

### Ask for a change

Ask in plain words. This was the next message in the same session:

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

You can also ask for a shorter or longer version, another hook or tone, or other hashtags. Every new version is counted again before it goes into `ready/`.

<details>
<summary><b>It works in your language: the same post in Turkish and German</b></summary>

**Turkish draft**

> two builders'ın yeni bölümü çıktı!! maya ve sam uygulamamızı bir hafta sonunda nasıl yayınladığımızı anlatıyo, neleri kestik gece 2de ne bozuldu ve lansman paylaşımları neden koddan uzun sürdü. kendi başına bir şey geliştiren herkez için şimdiye kadarki en faydalı bölüm bence

**X** · 270 of 280 weighted characters

> Two Builders'ın yeni bölümü çıktı! Maya ve Sam, uygulamamızı bir hafta sonunda nasıl yayınladığımızı anlatıyor: neleri kestik, gece 2'de ne bozuldu, lansman paylaşımları neden koddan uzun sürdü. Kendi başına geliştiren herkes için şimdiye kadarki en faydalı bölüm bence.

**German draft**

> neue folge von two builders ist drausen!! maya und sam erzählen wie wir unsere app an einem wochenende gelauncht haben, was wir gestrichen haben was um 2 uhr nachts kaputt ging und warum die launch posts länger gedauert haben als der code. ehrlich die nützlichste folge bis jetzt für alle die alleine was bauen

**X** · 235 of 280 weighted characters

> Neue Folge von Two Builders ist da. Maya und Sam erzählen, wie wir unsere App an einem Wochenende gelauncht haben: was wir gestrichen haben, was um 2 Uhr nachts kaputt ging und warum die Launch-Posts länger gedauert haben als der Code.

</details>

<sub>The copy comes from the model your Hermes uses. These runs used Claude Sonnet 5.5, and postkitty counted and checked every version.</sub>

## What it does

Each platform has its own sizes, length limits and way of counting characters. postkitty handles all of that on your machine, with no API keys, and nothing is uploaded.

- <img src="docs/assets/readme/icons/type.svg" width="18" height="18" alt=""> **Text.** Fixes spelling, grammar and clumsy sentences, then writes a version for each platform. Each one is counted with that platform's own rule, such as weighted characters on X, graphemes on Bluesky and UTF-16 units on TikTok. Long posts can become threads.
- <img src="docs/assets/readme/icons/scan-face.svg" width="18" height="18" alt=""> **Photos.** Every crop is planned around the faces the YuNet detector finds. A wide group photo gets a blurred band so nobody is cut off. Location and camera metadata are removed.
- <img src="docs/assets/readme/icons/video.svg" width="18" height="18" alt=""> **Video.** A landscape clip becomes a vertical video that follows the person talking, or a split screen when two people talk. Each clip is trimmed to the platform's length and gets a cover frame.
- <img src="docs/assets/readme/icons/list-checks.svg" width="18" height="18" alt=""> **Checks.** Every file is checked against the platform's published limits. Failures are repaired, and only passing files go into `ready/`.
- <img src="docs/assets/readme/icons/message-square-text.svg" width="18" height="18" alt=""> **Advice.** Hermes ranks the platforms for your post and saves the topic, audience and tips in `advice.md`.
- <img src="docs/assets/readme/icons/layout-grid.svg" width="18" height="18" alt=""> **One board to review.** `board.html` shows every file in a frame of its real shape, with its copy, alt text and checks. Ask for a change and Hermes makes only that file again.
- <img src="docs/assets/readme/icons/lock.svg" width="18" height="18" alt=""> **Private by default.** postkitty reads only the files you name and writes only inside its job folder and its own data folder. It sends no telemetry.

## A quick tour

<p align="center">
  <picture>
    <source srcset="docs/assets/readme/tour.webp" type="image/webp">
    <img src="docs/assets/readme/tour.jpg" alt="A short loop of postkitty reframing landscape clips for vertical video: the frame follows a potter as she moves, two podcast hosts become a split screen, then scenes from public-domain films and cartoons get the same treatment." width="900">
  </picture>
</p>

### Ask in plain words

Name the platforms and your files and paste the draft. Hermes calls the postkitty tools and replies with the platforms ranked for your post.

<p align="center"><img src="docs/assets/readme/hermes.jpg" alt="A Hermes terminal session: a request to get an episode post ready for five platforms, the postkitty_scan, postkitty_copy and postkitty_make calls with their times, and the ranked platforms in the reply." width="720"></p>

### Every face stays in frame

A center crop of this team photo cuts off the two people at the edges. The postkitty feed image keeps all five.

<p align="center"><img src="docs/assets/readme/faces.jpg" alt="The original team photo with the center-crop area marked, the 4:5 center crop that cuts off the two people at the edges, and the postkitty 4:5 image that keeps all five people." width="720"></p>

### See where it fits

The board opens with the audience and tone of your post, the platforms ranked for it, and tips.

<p align="center"><img src="docs/assets/readme/advice.jpg" alt="The advice panel of the review board: the post's topic, audience and tone, a ranked list of Instagram, TikTok, YouTube, LinkedIn and X with a reason for each, and tips." width="720"></p>

<p align="center"><sub>The board and terminal shots come from one real run on a demo podcast clip and team photo. The people in the demo footage and photos are AI-generated.</sub></p>

## Platforms

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

Text alone works too: paste a draft and name the platforms.

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
