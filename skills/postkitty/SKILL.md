---
name: postkitty
description: Fix a draft and make checked files for every platform.
version: 0.1.0
author: Mert Kaya
license: MIT
metadata:
  hermes:
    tags: [social-media, video, images, copywriting]
    category: creative
---

# Postkitty Skill

Postkitty turns one post (photos, landscape video, a draft, or only text) into a folder of files that are ready to
upload to Instagram, TikTok, YouTube Shorts, X, LinkedIn, Threads, Bluesky and Facebook, each one checked against
that platform's published limits. You write the understanding, advice and copy. The tools do detection, framing,
rendering, counting, checking and repair. The tools decide whether a file passes, you never do. Nothing is posted
or uploaded.

## When to Use

- The user shares a photo, a video or a draft and wants it posted on one or several platforms.
- The user asks what to post where, how to word it, or whether a file will upload ("will this work on TikTok?").
- The user wants a landscape video turned into vertical clips, or a photo cropped for several feeds.

Do not use it to publish, schedule, or edit video content beyond framing, trimming and a cover frame.

## Prerequisites

- `ffmpeg` and `ffprobe` on PATH for video. If a tool reports them missing, tell the user to install ffmpeg.
- Media tools may report "not available"; text copy and counting still work. Say so and continue with copy.

## How to Run

Work through the five tools in order. Every tool returns JSON; an `error` key means fix the call or tell the user.

1. `postkitty_scan` with `inputs` (absolute paths), `text` (the draft), optional `platforms`.
2. Understand the post, then write advice and copy.
3. `postkitty_copy` with `job`, `advice`, `drafts`, `alt_text`. Repeat until every platform is `ok`.
4. `postkitty_make` with `job` (add `targets` or `overrides` only when needed).
5. `postkitty_redo` for each change the user asks for. Use `postkitty_check` only for files the user brings from elsewhere.

## Quick Reference

| Tool | Use it to | Key arguments |
|---|---|---|
| `postkitty_scan` | open a job, probe files, plan framing, get fit facts | `inputs`, `text`, `platforms` |
| `postkitty_copy` | count, split and store drafts, advice and alt text | `job`, `drafts`, `advice`, `alt_text` |
| `postkitty_make` | render, check, repair, build the board | `job`, `targets`, `overrides` |
| `postkitty_redo` | change one target | `job`, `target`, `layout`, `focus`, `trim`, `cover_at` |
| `postkitty_check` | check a file that postkitty did not make | `path` + `target` |

Layouts: `crop` follows the subject, `split` stacks two people in a vertical frame, `speaker` cuts to whoever is
talking, `seam` squeezes the background so two people fit, `pad` keeps the whole frame on a blurred fill. Focus:
`auto`, `person:N` (1 is the leftmost person), `left`, `center`, `right`, `x:0.0-1.0`.

## Procedure

### 1. Scan

Call `postkitty_scan` first, even for text only. Read `inputs` (kind, size, duration, `people`, `shots`), `plan`
(layout, trim and cover proposal per target), `fit` (per-platform facts) and `text` (character, X weighted,
grapheme, hashtag, mention and URL counts). Keep the `job` id for every later call. Read `notes` too: a note means
a media step was skipped and says why.

If a vision tool is available (`vision_analyze` or similar), inspect the scan's `peek` image and every photo input
before writing advice or alt text. The peek is a still or a keyframe strip of the user's media.
If no vision tool is available, say so once. Write alt text only from the user's words and facts reported by scan,
and never invent visual details.

### 2. Understand

Decide four things and keep them short: the topic, the audience, the tone, and the one key message. Take every fact
from the user's text, the media and the user's answers. Do not invent names, numbers, places, prices, dates or
claims. If a fact the post needs is missing, ask the user once or leave it out.

### 3. Advise

Rank the platforms that fit the material, with one concrete reason each, based on the material: a talking-head
video belongs on Reels, TikTok and Shorts, a long text-led thought on LinkedIn and Threads, a photo on Instagram
and Bluesky. For each platform note the angle, the hook (first line or first three seconds), hashtags in that
platform's norm (Instagram a few specific ones, LinkedIn two or three, X and Bluesky one or none, TikTok a few),
and what to trim. Use the `fit` facts for limits, never your memory.

Pass it as `advice`: `topic`, `audience`, `tone`, `key_message`, `ranking` (list of `{platform, reason}`), `tips`.

### 4. Write copy

One draft per platform, in the user's voice and language, plain and specific. Put the point before the "more" fold
(the `fold` text in the result shows what stays visible). Do not copy one text to every platform: shorten for X
and Bluesky, give LinkedIn room to explain, keep TikTok and Reels captions short with the hook first. For YouTube
the draft is the Shorts title.

Clean up the draft as you adapt it: fix spelling, grammar and punctuation, and rewrite clumsy or run-on sentences.
Keep the user's voice, language and facts.

Alt text goes in `alt_text`, keyed by target id (for example `instagram_feed`) or file name. Describe only what is
visible in the image or video: who or what, where, what happens, any text on screen. Do not guess identities,
emotions or context that is not in the frame. Keep it under about 200 characters.

Call `postkitty_copy`. For every platform with `ok: false`, rewrite the draft using the reported `overflow`,
`unit` and `limit`, then call again. Never truncate in the middle of a sentence. X, Threads and Bluesky text that is
over the limit is split into a numbered thread when `split_threads` is true (the default); accept the split only
when the user wants a thread, otherwise shorten the text. Hashtag and mention caps are hard limits.

### 5. Make

Call `postkitty_make`. Rendering can take a while for video; tell the user it is running. Read the table: a target
is ready to upload only when `status` is `ready` or `repaired`. For `failed` targets read `problems` and either
redo with a different layout or explain what blocks it. `skipped` means the media engine for that kind is not
available. Report every `advisory` honestly, for example a safe-area or bitrate recommendation.

`postkitty_make` and `postkitty_redo` already run every check and repair.
Never call `postkitty_check` on files made by `postkitty_make` or `postkitty_redo`.

### 6. Reply

Keep the reply under 180 words plus the file list. Use this order:

1. A short summary of what was made, repaired, failed or skipped.
2. The ranked platforms with one reason each.
3. "What to check before posting", containing only advisory items actually returned by the tools. Omit it when there
   are no advisories.
4. The job folder path from `job_dir`, then the file list. Upload files are under `ready/<platform>/`.
5. The exact `media_line` alone on its own line.
6. On Hermes Desktop, the exact `preview_directive` as its own paragraph so the review board opens.

If the result has no `media_line` or `preview_directive`, skip that line and do not invent one.

### 7. Redo

Offer concrete options: another person as the focus, another layout, a different trim or cover frame. When a target
uses `split`, tell the user once that two other choices exist: `speaker` cuts to whoever is talking, and `pad` keeps
the whole wide shot. Use `postkitty_redo` with `target` and only the keys that change. Person numbers count from 1,
left to right, in the first frame where they appear. After each redo, read the new status again and show the new
`media_line`. When a redo fails, the earlier passing file stays in `ready/` and the row names it in `kept`; say so.

For the copy, offer a shorter or longer version, another tone or hook, other hashtags, or a thread instead of one
post. For a copy change, rewrite only that platform's draft and call `postkitty_copy` again with the same `job`. The
other drafts stay as they are.

## Pitfalls

- Do not call a file ready, passing or uploadable unless the tool said `ready` or `repaired`.
- Do not post, upload or schedule anything, and do not offer to.
- Do not state platform limits from memory. Quote the numbers the tools return.
- Do not put facts in copy that are not in the user's material. This includes statistics, product claims and quotes.
- Do not run image or video work yourself with `terminal` (no ffmpeg or OpenCV calls). Use the tools.
- Use `postkitty_check` only for an external file when the user asks whether it will upload.
- Do not reuse a stale job after the user changes the inputs; run `postkitty_scan` again with `job` unset.
- A text-only job has no media targets; `postkitty_make` returns an empty table, a `note` and the copy `files`
  already in `ready/`. That is fine; list those files, do not search for them with `terminal`.

## Verification

- Every platform in `postkitty_copy` shows `ok: true` (or a recommendation-only limit with a note).
- Every target you call finished shows `ready` or `repaired` in the `postkitty_make` or `postkitty_redo` table.
- The reply contains the exact `media_line` string from the tool result.
