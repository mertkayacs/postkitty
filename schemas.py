"""Tool schemas: the names, descriptions and parameters Hermes shows the model."""

from __future__ import annotations

from .engine.pipeline import LAYOUTS

_OVERRIDE_PROPS = {
    "layout": {"type": "string", "enum": list(LAYOUTS),
               "description": "crop keeps the subject, split stacks two people, speaker cuts to whoever is talking, "
                              "seam carves width, pad keeps the whole frame on a blurred fill."},
    "focus": {"type": "string", "description": "auto, person:N (1 = leftmost), left, center, right or x:0.0-1.0."},
    "trim": {"type": "array", "items": {"type": "number"}, "description": "[start, end] seconds (video)."},
    "cover_at": {"type": "number", "description": "Cover frame time in seconds (video)."},
}

SCHEMAS = {
    "postkitty_scan": {
        "name": "postkitty_scan",
        "description": (
            "First step for any social post. Takes the user's photos, landscape videos and draft text, creates a "
            "job folder, detects people, shots and scenes, plans a framing per platform target and returns fit "
            "facts (sizes, character counts, limits) plus the path of a preview image to look at. Does not render "
            "anything. Works with text only. Also the first call when the user only wants a draft fixed or asks "
            "what to post where. Never posts or uploads. Load the skill postkitty:postkitty first "
            "(skill_view) for the full workflow."),
        "parameters": {"type": "object", "properties": {
            "inputs": {"type": "array", "items": {"type": "string"}, "description": "Absolute paths of images or videos."},
            "text": {"type": "string", "description": "The user's draft post, if any."},
            "platforms": {"type": "array", "items": {"type": "string"},
                          "description": "Platform names (instagram, tiktok, youtube, x, linkedin, threads, bluesky, "
                                         "facebook) or target ids. Default: every target that fits the inputs."},
            "job": {"type": "string", "description": "Reuse an existing job id."}}},
    },
    "postkitty_write": {
        "name": "postkitty_write",
        "description": (
            "Second step. Stores your advice and the per-platform drafts you wrote, counts each draft with that "
            "platform's real rule (X weighted, Bluesky graphemes and bytes, TikTok UTF-16, Instagram hashtags and "
            "mentions) and splits over-limit X, Threads and Bluesky text into a numbered thread. Writes advice.md "
            "and the post.txt, thread.txt and alt.txt files into ready/. Call it again with rewritten drafts until "
            "every platform reports ok. Also the tool for every later copy change (shorter, another tone or hook, "
            "other hashtags, a thread): call it with the same job and only the rewritten drafts; the others stay."),
        "parameters": {"type": "object", "required": ["job"], "properties": {
            "job": {"type": "string"},
            "advice": {"type": "object", "description": "topic, audience, tone, key_message, ranking "
                       "[{platform, reason}], tips [string].", "properties": {
                           "topic": {"type": "string"}, "audience": {"type": "string"}, "tone": {"type": "string"},
                           "key_message": {"type": "string"}, "tips": {"type": "array", "items": {"type": "string"}},
                           "ranking": {"type": "array", "items": {"type": "object"}}}},
            "drafts": {"type": "object",
                       "description": "Platform name or target id -> draft string, or list of strings for a thread.",
                       "additionalProperties": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}},
            "alt_text": {"type": "object",
                         "description": "Target id, input file name or ready file path -> alt text. "
                                        "Describe only what is visible.",
                         "additionalProperties": {"type": "string"}},
            "split_threads": {"type": "boolean", "description": "Split over-limit text into a thread. Default true."}}},
    },
    "postkitty_make": {
        "name": "postkitty_make",
        "description": (
            "Third step. Renders every planned target with its layout (crop, split, speaker, seam or pad), checks "
            "each file against the platform's published limits, repairs failures, and puts only passing files into "
            "ready/. Writes the review board and contact sheet. Returns a status table plus media_line and "
            "preview_directive strings to show the user. Only files with status ready or repaired are ready to "
            "upload. A text-only job has nothing to render: make then lists the copy files already in ready/."),
        "parameters": {"type": "object", "required": ["job"], "properties": {
            "job": {"type": "string"},
            "targets": {"type": "array", "items": {"type": "string"}, "description": "Subset of target ids or platforms."},
            "overrides": {"type": "object", "description": "Target id -> {layout, focus, trim, cover_at}.",
                          "additionalProperties": {"type": "object", "properties": _OVERRIDE_PROPS}}}},
    },
    "postkitty_redo": {
        "name": "postkitty_redo",
        "description": (
            "Re-render one photo or video target after the user asks for a change: another layout (split stacks "
            "two people, speaker cuts to whoever is talking, pad keeps the whole wide shot), another person in "
            "focus, a trim or another cover frame. Uses the cached scan, so it is fast. Same return shape as "
            "postkitty_make. For copy changes call postkitty_write instead."),
        "parameters": {"type": "object", "required": ["job", "target"], "properties": {
            "job": {"type": "string"}, "target": {"type": "string", "description": "Target id, for example tiktok."},
            **_OVERRIDE_PROPS}},
    },
    "postkitty_check": {
        "name": "postkitty_check",
        "description": (
            "Check a file the user brings from elsewhere against one platform target without rendering, for "
            "example 'will this upload to TikTok?'. Give path and target. Files made by postkitty_make or "
            "postkitty_redo are already checked; give job to re-check a job's ready files only when the user asks."),
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "target": {"type": "string"}, "job": {"type": "string"}}},
    },
}
