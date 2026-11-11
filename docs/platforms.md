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
| Text | Length | 2,200 characters | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
| Text | Hashtags, at most | 5 (Instagram's @creators account, 18 December 2025; the Graph API reference still lists 30) | required | 2026-11-11 | [instagram.com](https://www.instagram.com/p/DSalTolEbvf/) |
| Text | Mentions, at most | 20 | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
| `instagram_reel`, video, `ready/instagram/reel.mp4` | Output size | 1080×1920 | required | | |
|  | Container | mp4, mov | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
|  | Video codec | h264, hevc | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
|  | Audio sample rate | 48 kHz | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
|  | Frame rate, at least | 23 fps | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
|  | Frame rate, at most | 60 fps | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
|  | Length, at least | 3 s | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
|  | Length, at most | 900 s | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
|  | File size, at most | 300 MB | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
|  | Video bitrate, at most | 25 Mbps | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
|  | Audio bitrate, at most | 128 kbps | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
|  | Keep clear of the edges | top 14%, bottom 35%, side 6% | advised | 2026-11-11 | [facebook.com](https://www.facebook.com/business/ads-guide/update/video/instagram-reels) |
| `instagram_feed`, photo, `ready/instagram/feed.jpg` | Output size | 1080×1350 | required | | |
|  | Format | jpeg | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
|  | File size, at most | 8 MB | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
|  | Aspect ratio, from and to | 4:5, 1.91:1 | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
| `instagram_story`, photo or video, `ready/instagram/story.jpg or .mp4` | Output size | 1080×1920 | required | | |
|  | Length, at most | 60 s (story videos published through the API) | advised | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/) |
|  | Keep clear of the edges | top 14%, bottom 35%, side 6% | advised | 2026-11-11 | [facebook.com](https://www.facebook.com/business/ads-guide/update/image/instagram-story) |

## TikTok

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 2,200 UTF-16 units | required | 2026-11-11 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post) |
| `tiktok`, video, `ready/tiktok/tiktok.mp4` | Output size | 1080×1920 | required | | |
|  | Container | mp4, webm, mov | required | 2026-11-11 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | Video codec | h264, hevc, vp8, vp9 | required | 2026-11-11 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | Frame rate, at least | 23 fps | required | 2026-11-11 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | Frame rate, at most | 60 fps | required | 2026-11-11 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | Shorter side, at least | 360 px | required | 2026-11-11 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | Longer side, at most | 4,096 px | required | 2026-11-11 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | Length, at most | 600 s (the API maximum; every creator can post 3 minutes, some accounts 5 or 10) | required | 2026-11-11 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | File size, at most | 4 GB | required | 2026-11-11 | [developers.tiktok.com](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide) |
|  | Keep clear of the edges | top 12.5%, bottom 34.4%, left 11.1%, right 27.8% (TikTok's in-feed template (720x1280): top 160, bottom 440, left 80, right 80 plus an icon column 120 wide beside the lower 720, so right is 200) | advised | 2026-11-11 | [ads.tiktok.com](https://ads.tiktok.com/resources/help/article/tiktok-auction-in-feed-ads) |

## YouTube Shorts

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 100 characters | required | 2026-11-11 | [support.google.com](https://support.google.com/youtube/answer/57407) |
| `youtube_shorts`, video, `ready/youtube/shorts.mp4` | Output size | 1080×1920 | required | | |
|  | Length, at most | 180 s | required | 2026-11-11 | [support.google.com](https://support.google.com/youtube/answer/15424877) |
|  | Video bitrate, at most | 8 Mbps (1080p SDR at 24 to 30 fps; YouTube recommends 12 Mbps at 48 to 60 fps) | advised | 2026-11-11 | [support.google.com](https://support.google.com/youtube/answer/1722171) |
|  | Keep clear of the edges | top 15%, bottom 35%, left 4.4%, right 17.8% (Google's drawing for vertical video ads (1080x1920): top 288, bottom 672, left 48, right 192) | advised | 2026-11-11 | [support.google.com](https://support.google.com/google-ads/answer/13547298) |

## X

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 280 weighted characters | required | 2026-11-11 | [github.com](https://github.com/twitter/twitter-text/blob/master/config/v3.json) |
| `x_video`, video, `ready/x/video.mp4` | Output size | 1920×1080 | required | | |
|  | Length, at most | 140 s (accounts without Premium; the X API media guide lists 20 minutes for a default account) | required | 2026-11-11 | [help.x.com](https://help.x.com/en/using-x/x-videos) |
|  | File size, at most | 512 MB (accounts without Premium; the X API media guide lists 8 GB for a default account) | required | 2026-11-11 | [help.x.com](https://help.x.com/en/using-x/x-videos) |
| `x_image`, photo, `ready/x/image.jpg` | Output size | 1600×900 | required | | |
|  | Format | jpeg, png, gif, webp | required | 2026-11-11 | [docs.x.com](https://docs.x.com/x-api/media/quickstart/best-practices) |
|  | File size, at most | 5 MB | required | 2026-11-11 | [docs.x.com](https://docs.x.com/x-api/media/quickstart/best-practices) |

## LinkedIn

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 3,000 characters | required | 2026-11-11 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a528176) |
| `linkedin_video`, video, `ready/linkedin/video.mp4` | Output size | 1080×1350 | required | | |
|  | Length, at least | 3 s | required | 2026-11-11 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | Length, at most | 900 s | required | 2026-11-11 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | File size, at least | 75 KB | required | 2026-11-11 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | File size, at most | 5 GB | required | 2026-11-11 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | Frame rate, at least | 10 fps | required | 2026-11-11 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | Frame rate, at most | 60 fps | required | 2026-11-11 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | Video bitrate, at most | 30 Mbps | required | 2026-11-11 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | Aspect ratio, at least | 0.4167 (1:2.4) | required | 2026-11-11 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
|  | Aspect ratio, at most | 2.4 | required | 2026-11-11 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a7174587) |
| `linkedin_image`, photo, `ready/linkedin/image.jpg` | Output size | 1080×1080 | required | | |
|  | Aspect ratio, one of | 1:1, 1.91:1, 4:5 | advised | 2026-11-11 | [linkedin.com](https://www.linkedin.com/help/linkedin/answer/a426534) |

## Threads

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 500 characters, with every emoji counted as its UTF-8 bytes | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/threads/overview) |
| `threads_video`, video, `ready/threads/video.mp4` | Output size | 1080×1920 | required | | |
|  | Container | mp4, mov | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/threads/overview) |
|  | Video codec | h264, hevc | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/threads/overview) |
|  | Frame rate, at least | 23 fps | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/threads/overview) |
|  | Frame rate, at most | 60 fps | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/threads/overview) |
|  | Length, at most | 300 s | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/threads/overview) |
|  | File size, at most | 1 GB | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/threads/overview) |
| `threads_image`, photo, `ready/threads/image.jpg` | Output size | 1080×1350 | required | | |
|  | Format | jpeg, png | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/threads/overview) |
|  | File size, at most | 8 MB | required | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/threads/overview) |

## Bluesky

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 300 graphemes | required | 2026-11-11 | [github.com](https://github.com/bluesky-social/atproto/blob/main/packages/api/lexicons/app/bsky/feed/post.json) |
| Text | Size, at most | 3,000 UTF-8 bytes | required | 2026-11-11 | [github.com](https://github.com/bluesky-social/atproto/blob/main/packages/api/lexicons/app/bsky/feed/post.json) |
| `bluesky_video`, video, `ready/bluesky/video.mp4` | Output size | 1080×1920 | required | | |
|  | File size, at most | 300 MB | required | 2026-11-11 | [github.com](https://github.com/bluesky-social/atproto/blob/main/packages/api/lexicons/app/bsky/embed/video.json) |
|  | Length, at most | 600 s (not specified in the app.bsky.embed.video lexicon; client constant) | advised | 2026-11-11 | [github.com](https://github.com/bluesky-social/social-app/blob/main/src/lib/constants.ts) |
| `bluesky_image`, photo, `ready/bluesky/image.jpg` | Output size | 1080×1350 | required | | |
|  | File size, at most | 2 MB | required | 2026-11-11 | [github.com](https://github.com/bluesky-social/atproto/blob/main/packages/api/lexicons/app/bsky/embed/images.json) |

## Facebook

| Applies to | Limit | Value | Kind | Checked | Source |
|---|---|---|---|---|---|
| Text | Length | 63,206 characters (not confirmed on a Facebook help or developer page; value carried from seed data) | advised | 2026-11-11 | [facebook.com](https://www.facebook.com/help/), secondary |
| `facebook_reel`, video, `ready/facebook/reel.mp4` | Output size | 1080×1920 | required | | |
|  | Aspect ratio, one of | 9:16 (1080 x 1920 recommended, 540 x 960 minimum) | advised | 2026-11-11 | [developers.facebook.com](https://developers.facebook.com/docs/video-api/guides/reels-publishing) |
|  | Keep clear of the edges | top 14%, bottom 35%, side 6% | advised | 2026-11-11 | [facebook.com](https://www.facebook.com/business/ads-guide/update/video/facebook-facebook-reels) |
| `facebook_feed`, photo, `ready/facebook/feed.jpg` | Output size | 1080×1350 | required | | |
|  | Aspect ratio, one of | 4:5 | advised | 2026-11-11 | [facebook.com](https://www.facebook.com/business/ads-guide/update/image/facebook-feed) |
