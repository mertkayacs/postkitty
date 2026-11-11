# How to ask

You talk to Hermes in plain words, and Hermes calls the postkitty tools. A request works the first time when it carries three things: the platforms, the files, and the draft.

```text
Make this ready for Instagram, TikTok and LinkedIn.
The video is /home/me/talk.mp4 and the photo is /home/me/team.jpg.
My draft: we shipped the app in one weekend, here is what broke...
```

Each section below puts a vague request next to a clear one and says what postkitty does with the clear one.

- [Name the platforms](#name-the-platforms)
- [Give the files](#give-the-files)
- [Say who stays in frame](#say-who-stays-in-frame)
- [Pick a layout](#pick-a-layout)
- [Set the trim and the cover frame](#set-the-trim-and-the-cover-frame)
- [Set the tone and the language](#set-the-tone-and-the-language)
- [Ask for a thread or a single post](#ask-for-a-thread-or-a-single-post)
- [Add captions](#add-captions)
- [Ask for a change](#ask-for-a-change)
- [Ask whether a file will upload](#ask-whether-a-file-will-upload)

## Name the platforms

| Vague | Clear |
|---|---|
| "Get this ready for social media." | "Get this ready for Instagram, TikTok and YouTube Shorts." |

postkitty plans one file for each target of the platforms you name. Instagram has three targets (Reel, feed photo, Story), X and LinkedIn have a video and an image, and so on. When you name no platform, it plans every target that fits your files, which can be more than you want.

The names it knows are Instagram, TikTok, YouTube, X, LinkedIn, Threads, Bluesky and Facebook. "Twitter", "IG", "Shorts", "FB" and "Bsky" work too. To get one target only, say it: "only the Instagram Reel".

If you always post to the same places, set `default_platforms` once ([settings](tools.md#settings)).

## Give the files

| Vague | Clear |
|---|---|
| "Use the video I recorded yesterday." | "The video is /home/me/talk.mp4." |

postkitty reads files by their full path. A photo gives you image targets and a video gives you video targets, so a request for TikTok needs a video and a request for a feed photo needs a photo. You can give both in one request.

It reads JPEG, PNG, WebP, BMP, TIFF and still GIF images, and MP4, MOV, M4V, WebM, MKV, AVI and MTS video. HEIC and AVIF photos need the `pillow-heif` package. An animated GIF is refused with a hint to export one frame or give a video.

Text alone works: paste the draft and name the platforms.

## Say who stays in frame

| Vague | Clear |
|---|---|
| "Make it look good." | "Keep everyone in the picture." |
| "Fix the crop." | "Focus on the person on the left in the TikTok clip." |

postkitty frames each file around the faces it finds, and a check fails the file when one of them is cut. A photo with no face is framed around its most prominent subject. You can choose the focus yourself:

| You say | Focus value | What it does |
|---|---|---|
| "the person on the left", "the second person" | `person:1`, `person:2` | Frames that person. People are numbered from 1, left to right, as they first appear. |
| "keep the left side", "the middle", "the right side" | `left`, `center`, `right` | Anchors the crop to that side of the frame. |
| "a bit left of the middle" | `x:0.4` | Anchors the crop at a point from 0.0 (left edge) to 1.0 (right edge). |
| nothing | `auto` | Frames the people it found. |

If you ask for a person who is not there, postkitty answers with the number of people it found.

## Pick a layout

| Vague | Clear |
|---|---|
| "Make the podcast clip vertical." | "Make the podcast clip vertical and cut to whoever is talking." |

A landscape clip of two people cannot show both in one vertical crop, so there are three ways to make it, and you choose:

| You say | Layout | Result |
|---|---|---|
| "split screen" | `split` | One person in the top half, the other in the bottom half. This is what you get when you say nothing. |
| "cut to whoever is talking" | `speaker` | A full-height crop that switches to the person who is speaking. |
| "keep the whole wide shot" | `pad` | The whole frame, centred on a blurred fill. |
| "follow her", "crop to him" | `crop` | A crop that follows one person. |

For photos the words are the same, with one more: "squeeze the background" (`seam`) removes background between two people so both fit. `speaker` is for video only.

When a video cannot support the layout you asked for, postkitty uses a crop and says so in the result. A split needs two people in one shot. On a photo, a split needs exactly two people and a vertical target, and postkitty tells you when it cannot make one. [Layouts](layouts.md) shows each layout with a picture.

## Set the trim and the cover frame

| Vague | Clear |
|---|---|
| "Use the good part." | "Use 0:12 to 0:48 of the clip and take the cover frame at 0:20." |

Give times as minutes and seconds or as seconds. A trim that runs past the end of the clip stops at the end. The cover frame has to sit inside the trim.

When you give no times, postkitty keeps the whole clip if it fits the platform's maximum length. A longer clip is cut to that maximum, and postkitty picks the window with the most faces on screen and the most sound. The cover is the sharpest frame that shows a face and sits away from a scene cut.

Trim and cover apply to video. On a photo target postkitty refuses them with a message.

## Set the tone and the language

| Vague | Clear |
|---|---|
| "Write a caption." | "Write this for LinkedIn in a formal tone and for X in a casual one. Keep it in Turkish." |

Hermes writes one version per platform in your voice and your language, fixes spelling and grammar, and keeps your facts. It adds no names, numbers or claims that are not in your material. postkitty then counts every version with that platform's rule and reports the overflow when one is too long, so Hermes can shorten it.

Say what you want changed in words a person would use: shorter, longer, more formal, another first line, other hashtags, no hashtags. For YouTube the text is the Shorts title.

## Ask for a thread or a single post

| Vague | Clear |
|---|---|
| "This is too long for X." | "This is too long for one X post. Turn it into a thread." |
| | "Keep it to one post on X, shorten it." |

X, Threads and Bluesky text over the limit can be split into a numbered thread. postkitty splits at sentence ends, keeps every link whole, and numbers the posts (`1/3`, `2/3`, `3/3`). A thread is saved as `thread.txt`, a single post as `post.txt`.

Say which one you want. When you say nothing, Hermes shortens the text until it fits one post. On the other platforms a long text is always shortened.

## Add captions

| Vague | Clear |
|---|---|
| "Add subtitles." | "Burn the subtitles from /home/me/talk.srt into the TikTok clip." |

postkitty draws the lines of an `.srt` or `.vtt` file into the video: white text with a dark outline, at most two lines at a time, at the bottom of the area the platform keeps clear of its buttons. The times follow your trim, and the cover frame stays free of captions.

It does not transcribe speech, so you bring the subtitle file. Give its full path and say which clips get captions. Captions need an ffmpeg build with libass, and [Troubleshooting](troubleshooting.md#captions-cannot-be-burned-in) says how to get one.

## Ask for a change

| Vague | Clear |
|---|---|
| "I don't like it, try again." | "In the TikTok clip, focus on the person on the right." |
| "The text is off." | "Make the X post shorter and drop the hashtags on LinkedIn." |

Name the file or the platform and the one thing to change. Hermes then makes only that file again, or rewrites only that text, and everything else stays as it is. If the new version of a file fails its checks, the earlier passing file stays in `ready/` and the result says so.

Changes you can ask for on a photo or a video: another layout, another person in focus, a trim, another cover frame, captions. On text: shorter or longer, another tone or first line, other hashtags, a thread or a single post.

If you swap the photo or the video itself, say so. Hermes then starts a new job, since the old plan belongs to the old file.

## Ask whether a file will upload

| Vague | Clear |
|---|---|
| "Is this video OK?" | "Will /home/me/final.mp4 upload as an Instagram Reel?" |

Name the file and the kind of post. postkitty measures the file (size, length, format, frame rate, bitrate and more, depending on the platform) and answers pass or fail with each failing check. It works for files made anywhere.

Files that postkitty made are checked before they reach `ready/`, so there is no need to ask about those.
