"""Tool schemas: the names, descriptions and parameters Hermes shows the model.

They are sent with every turn, so each description leads with when to call the tool and stays short.
"""

from __future__ import annotations

from .engine.pipeline import LAYOUTS

_JOB = {"type": "string", "description": 'The job id postkitty_scan returned, for example "20261111-1847-team".'}
_OVERRIDE_PROPS = {
    "layout": {"type": "string", "enum": list(LAYOUTS),
               "description": "crop keeps the subject, split stacks two people (video), speaker cuts to whoever is "
                              "talking (video), seam narrows the background so two people fit (photo), pad keeps the "
                              "whole frame on a blurred fill, auto lets postkitty choose."},
    "focus": {"type": "string",
              "description": 'What to keep in frame: auto, person:N (1 is the leftmost person), left, center, right, '
                             'or x:0.0-1.0 for a horizontal position. Example: "person:2".'},
    "trim": {"type": "array", "items": {"type": "number"},
             "description": "[start, end] in seconds, video only. Example: [3, 33]."},
    "cover_at": {"type": "number", "description": "Time of the cover frame in seconds, video only. Example: 4.5."},
}

SCHEMAS = {
    "postkitty_scan": {
        "name": "postkitty_scan",
        "description": (
            "Always the first call for a social media post, also when the user only wants a draft fixed or asks "
            "what to post where. Give the user's photos, one landscape video, their draft text, or any mix; text "
            "alone works. It opens a job, finds the people and shots, plans a framing for each platform target and "
            "returns the job id, the plan, fit facts (sizes, character counts, limits), notes and the path of a "
            "preview image. It renders nothing and never posts or uploads. Load the skill postkitty:postkitty "
            "(skill_view) before the first call for the full workflow."),
        "parameters": {"type": "object", "properties": {
            "inputs": {"type": "array", "items": {"type": "string"},
                       "description": 'Paths of photos or one video, absolute or relative to the working directory. '
                                      'Example: ["/home/me/team.jpg"].'},
            "text": {"type": "string", "description": "The user's draft exactly as they wrote it."},
            "platforms": {"type": "array", "items": {"type": "string"},
                          "description": 'Platform names (instagram, tiktok, youtube, x, linkedin, threads, bluesky, '
                                         'facebook) or target ids such as x_image. Leave out for every target that '
                                         'fits the inputs. Example: ["x", "linkedin"].'},
            "job": {"type": "string",
                    "description": "Only to scan again into an existing job: its job id. Leave out for a new post."}}},
    },
    "postkitty_write": {
        "name": "postkitty_write",
        "description": (
            "Second call, and the call for every later copy change (shorter, another tone or hook, other hashtags, "
            "a thread). Give the drafts you wrote per platform, your advice and the alt text. It counts each draft "
            "with that platform's real rule (X weighted, Bluesky graphemes, TikTok UTF-16, Instagram hashtags and "
            "mentions), splits over-limit X, Threads and Bluesky text into a numbered thread, and writes post.txt, "
            "thread.txt, alt.txt and advice.md into the job. It returns ok, count, limit and overflow per platform: "
            "rewrite and call again until every platform is ok. Platforms you leave out keep their text. It never "
            "rewrites text itself."),
        "parameters": {"type": "object", "required": ["job"], "properties": {
            "job": _JOB,
            "drafts": {"type": "object",
                       "description": 'Platform name or target id -> the draft, or a list of posts for a thread. '
                                      'Example: {"x": "We shipped today.", "linkedin": "Today we shipped ..."}.',
                       "additionalProperties": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}},
            "advice": {"type": "object", "description": "Your reading of the post, stored as advice.md.", "properties": {
                "topic": {"type": "string"}, "audience": {"type": "string"}, "tone": {"type": "string"},
                "key_message": {"type": "string"},
                "ranking": {"type": "array", "items": {"type": "object"},
                            "description": 'Best platform first: [{"platform": "linkedin", "reason": "..."}].'},
                "tips": {"type": "array", "items": {"type": "string"}}}},
            "alt_text": {"type": "object",
                         "description": 'Target id, input id, input file name or ready file path -> alt text that '
                                        'describes only what is visible. Example: {"instagram_feed": "Four people '
                                        'at a desk."}.',
                         "additionalProperties": {"type": "string"}},
            "split_threads": {"type": "boolean",
                              "description": "false keeps over-limit X, Threads and Bluesky text as one failing post. "
                                             "Default true."}}},
    },
    "postkitty_make": {
        "name": "postkitty_make",
        "description": (
            "Third call. Renders every planned photo and video target, checks each file against the platform's "
            "published limits, repairs what fails and writes the review board. Give the job id; add targets or "
            "overrides only when the user asked for a subset or a specific framing. It returns one row per target "
            "(status ready, repaired, failed or skipped, the file, problems, advisory notes) plus media_line and "
            "preview_directive to show the user. Only ready and repaired files are ready to upload. A text-only job "
            "has nothing to render: make then lists the text files already in ready/."),
        "parameters": {"type": "object", "required": ["job"], "properties": {
            "job": _JOB,
            "targets": {"type": "array", "items": {"type": "string"},
                        "description": 'Only these target ids or platforms. Example: ["tiktok", "instagram"].'},
            "overrides": {"type": "object",
                          "description": 'Target id -> the keys to change. Example: {"tiktok": {"layout": "speaker"}}.',
                          "additionalProperties": {"type": "object", "properties": _OVERRIDE_PROPS}}}},
    },
    "postkitty_redo": {
        "name": "postkitty_redo",
        "description": (
            "Renders one photo or video target again after the user asks for a change: another layout, another "
            "person in focus, a trim or another cover frame. Give the job, the target and only the keys that "
            "change; earlier changes to that target stay. It reuses the scan, runs every check again and returns "
            "the same rows as postkitty_make. For copy changes call postkitty_write instead."),
        "parameters": {"type": "object", "required": ["job", "target"], "properties": {
            "job": _JOB,
            "target": {"type": "string", "description": 'A target id from the make rows, for example "tiktok" or "x_image".'},
            **_OVERRIDE_PROPS}},
    },
    "postkitty_check": {
        "name": "postkitty_check",
        "description": (
            "Checks a file the user brings from elsewhere against one platform target without rendering, for "
            "example 'will this upload to TikTok?'. Give path and target. It returns pass and the checks that "
            "fail or advise. Files made by postkitty_make or postkitty_redo are already checked; give job alone "
            "only when the user asks to check a job's ready files again."),
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string",
                     "description": 'The file to check, absolute or relative to the working directory. '
                                    'Example: "/home/me/clip.mp4".'},
            "target": {"type": "string",
                       "description": 'A target id such as x_image, or a platform name when it has one target for '
                                      'that kind of file, for example "tiktok".'},
            "job": {"type": "string", "description": "A job id, to check every ready file of that job again."}}},
    },
}
