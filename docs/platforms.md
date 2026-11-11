# Platforms and limits

Every size and limit postkitty checks, with the page it came from and the date it was checked. This page is built
from [data/platforms.yaml](../data/platforms.yaml) by `python docs/build_platforms.py`, so change the data there.

A **required** limit keeps a file out of `ready/` until it passes, and a failure starts a repair. An **advised**
limit is a recommendation: a file that misses it still passes, with a note on the review board. A source marked
secondary is a third-party page, used where the platform publishes no number of its own.

Each file lands in `ready/<platform>/` under the name shown with its target. Photos are saved as JPEG, or as PNG
when the source has transparency and the platform takes PNG.

## Instagram

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 2,200 characters | required | 2026-11-07 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
| Text | Hashtags, at most | 5 | required | 2026-11-08 | [socialmediatoday.com](https://www.socialmediatoday.com/news/instagram-implements-new-limits-on-hashtag-use/808309/), secondary |
| Text | Mentions, at most | 20 | required | 2026-11-07 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
| `instagram_reel`, video, `ready/instagram/reel.mp4` | Output size | 1080×1920 | required | | |
|  | Container | mp4, mov | required | 2026-11-07 | [postman.com](https://www.postman.com/meta/instagram/folder/830j7my/reels-publishing) |
|  | Video codec | h264, hevc | required | 2026-11-07 | [postman.com](https://www.postman.com/meta/instagram/folder/830j7my/reels-publishing) |
|  | Audio sample rate | 48 kHz | required | 2026-11-07 | [postman.com](https://www.postman.com/meta/instagram/folder/830j7my/reels-publishing) |
|  | Frame rate, at least | 23 fps | required | 2026-11-07 | [postman.com](https://www.postman.com/meta/instagram/folder/830j7my/reels-publishing) |
|  | Frame rate, at most | 60 fps | required | 2026-11-07 | [postman.com](https://www.postman.com/meta/instagram/folder/830j7my/reels-publishing) |
|  | Length, at least | 3 s | required | 2026-11-07 | [postman.com](https://www.postman.com/meta/instagram/folder/830j7my/reels-publishing) |
|  | Length, at most | 900 s | required | 2026-11-07 | [postman.com](https://www.postman.com/meta/instagram/folder/830j7my/reels-publishing) |
|  | File size, at most | 1 GB | required | 2026-11-07 | [postman.com](https://www.postman.com/meta/instagram/folder/830j7my/reels-publishing) |
|  | Video bitrate, at most | 25 Mbps | required | 2026-11-07 | [postman.com](https://www.postman.com/meta/instagram/folder/830j7my/reels-publishing) |
|  | Audio bitrate, at most | 128 kbps | required | 2026-11-07 | [postman.com](https://www.postman.com/meta/instagram/folder/830j7my/reels-publishing) |
|  | Keep clear of the edges | top 14%, bottom 35%, side 6% | advised | 2026-11-07 | [illumin.service-now.com](https://illumin.service-now.com/kb/en/meta-instagram-reels-creative-specs?id=kb_article_view&sysparm_article=KB0015971), secondary |
| `instagram_feed`, photo, `ready/instagram/feed.jpg` | Output size | 1080×1350 | required | | |
|  | Format | jpeg | required | 2026-11-07 | [postman.com](https://www.postman.com/meta/instagram/overview) |
|  | Aspect ratio, from and to | 3:4, 1.91:1 | advised | 2026-11-07 | [knowledge.hubspot.com](https://knowledge.hubspot.com/social/image-size-requirements-for-social-posts), secondary |
| `instagram_story`, photo or video, `ready/instagram/story.jpg or .mp4` | Output size | 1080×1920 | required | | |
|  | Length, at most | 60 s | advised | 2026-11-07 | [knowledge.hubspot.com](https://knowledge.hubspot.com/social/image-size-requirements-for-social-posts), secondary |
|  | Keep clear of the edges | top 14%, bottom 20%, side 0% | advised | 2026-11-07 | [illumin.service-now.com](https://illumin.service-now.com/kb/en/meta-instagram-stories-creative-specs?id=kb_article_view&sysparm_article=KB0015970), secondary |

## TikTok

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 2,200 UTF-16 units | required | 2026-11-08 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post) |
| `tiktok`, video, `ready/tiktok/tiktok.mp4` | Output size | 1080×1920 | required | | |
|  | Container | mp4, webm, mov | required | 2026-11-07 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | Video codec | h264, hevc, vp8, vp9 | required | 2026-11-07 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | Frame rate, at least | 23 fps | required | 2026-11-07 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | Frame rate, at most | 60 fps | required | 2026-11-07 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | Shorter side, at least | 360 px | required | 2026-11-07 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | Longer side, at most | 4,096 px | required | 2026-11-07 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | Length, at most | 600 s | required | 2026-11-07 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | File size, at most | 4 GB | required | 2026-11-07 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |

## YouTube Shorts

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 100 characters | advised | 2026-11-08 | [support.google.com](https://support.google.com/youtube/answer/57407) |
| `youtube_shorts`, video, `ready/youtube/shorts.mp4` | Output size | 1080×1920 | required | | |
|  | Length, at most | 180 s | required | 2026-11-08 | [support.google.com](https://support.google.com/youtube/answer/15424877) |
|  | Video bitrate, at most | 8 Mbps | advised | 2026-11-07 | [support.google.com](https://support.google.com/youtube/answer/1722171) |

## X

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 280 weighted characters | required | 2026-11-08 | [github.com](https://github.com/twitter/twitter-text/blob/master/config/v3.json) |
| `x_video`, video, `ready/x/video.mp4` | Output size | 1920×1080 | required | | |
|  | Length, at most | 140 s (accounts without Premium) | required | 2026-11-07 | [help.x.com](https://help.x.com/en/using-x/x-videos) |
|  | File size, at most | 512 MB | required | 2026-11-07 | [help.x.com](https://help.x.com/en/using-x/x-videos) |
| `x_image`, photo, `ready/x/image.jpg` | Output size | 1600×900 | required | | |
|  | Format | jpeg, png, gif | required | 2026-11-07 | [help.x.com](https://help.x.com/en/using-x/posting-gifs-and-pictures) |
|  | File size, at most | 5 MB | required | 2026-11-07 | [help.x.com](https://help.x.com/en/using-x/posting-gifs-and-pictures) |

## LinkedIn

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 3,000 characters | required | 2026-11-08 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a528176) |
| `linkedin_video`, video, `ready/linkedin/video.mp4` | Output size | 1080×1350 | required | | |
|  | Length, at least | 3 s | required | 2026-11-07 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | Length, at most | 900 s | required | 2026-11-07 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | File size, at least | 75 KB | required | 2026-11-07 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | File size, at most | 5 GB | required | 2026-11-07 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | Frame rate, at least | 10 fps | required | 2026-11-07 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | Frame rate, at most | 60 fps | required | 2026-11-07 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | Video bitrate, at most | 30 Mbps | required | 2026-11-07 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | Aspect ratio, at least | 0.4167 (1:2.4) | required | 2026-11-07 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | Aspect ratio, at most | 2.4 | required | 2026-11-07 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
| `linkedin_image`, photo, `ready/linkedin/image.jpg` | Output size | 1080×1080 | required | | |
|  | Aspect ratio, one of | 1:1, 1.91:1, 4:5 | advised | 2026-11-08 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a426534) |

## Threads

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 500 characters | required | 2026-11-08 | [about.fb.com](https://about.fb.com/news/2023/07/introducing-threads-new-app-text-sharing/) |
| `threads_video`, video, `ready/threads/video.mp4` | Output size | 1080×1920 | required | | |
|  | Length, at most | 300 s | required | 2026-11-08 | [about.fb.com](https://about.fb.com/news/2023/07/introducing-threads-new-app-text-sharing/) |
| `threads_image`, photo, `ready/threads/image.jpg` | Output size | 1080×1350 | required | | |

## Bluesky

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 300 graphemes | required | 2026-11-08 | [github.com](https://github.com/bluesky-social/atproto/blob/main/packages/api/lexicons/app/bsky/feed/post.json) |
| Text | File size, at most | 3,000 UTF-8 bytes | required | 2026-11-08 | [github.com](https://github.com/bluesky-social/atproto/blob/main/packages/api/lexicons/app/bsky/feed/post.json) |
| `bluesky_video`, video, `ready/bluesky/video.mp4` | Output size | 1080×1920 | required | | |
|  | File size, at most | 300 MB | required | 2026-11-07 | [github.com](https://github.com/bluesky-social/atproto/blob/main/packages/api/lexicons/app/bsky/embed/video.json) |
|  | Length, at most | 600 s (not specified in the app.bsky.embed.video lexicon; client constant) | advised | 2026-11-08 | [github.com](https://github.com/bluesky-social/social-app/blob/main/src/lib/constants.ts) |
| `bluesky_image`, photo, `ready/bluesky/image.jpg` | Output size | 1080×1350 | required | | |
|  | File size, at most | 2 MB | required | 2026-11-07 | [github.com](https://github.com/bluesky-social/atproto/blob/main/packages/api/lexicons/app/bsky/embed/images.json) |

## Facebook

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 63,206 characters (official character-limit help page not reachable for re-verification; value carried from seed data, treated as secondary) | advised | 2026-11-08 | [facebook.com](https://www.facebook.com/help/), secondary |
| `facebook_reel`, video, `ready/facebook/reel.mp4` | Output size | 1080×1920 | required | | |
| `facebook_feed`, photo, `ready/facebook/feed.jpg` | Output size | 1080×1350 | required | | |
