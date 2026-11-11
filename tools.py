"""Tool handlers. Every handler takes ``(args, **kwargs)``, returns a JSON string and never raises.

The work happens in ``engine.pipeline``. This module adds what only Hermes needs: the plugin settings
read from the plugin context, the JSON string and error wrapping, and the two lines Hermes acts on in a
reply.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import wraps
from typing import Any

from .engine import pipeline, probe

_CTX: Any = None


def configure(ctx: Any) -> None:
    global _CTX
    _CTX = ctx


def _config(key: str, default: Any) -> Any:
    if _CTX is None:
        return default
    try:
        return _CTX.get_config(key, default=default) or default
    except Exception:
        return default


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _message(exc: Exception) -> str:
    # str() of a KeyError is the repr of its key, which wraps a message in quotes.
    if isinstance(exc, KeyError) and exc.args and isinstance(exc.args[0], str):
        return exc.args[0]
    return str(exc)


def _safe(fn: Callable[[dict], Any]) -> Callable[..., str]:
    @wraps(fn)
    def handler(args: dict | None = None, **kwargs: Any) -> str:
        try:
            if not isinstance(args, dict):
                raise ValueError("tool arguments must be an object")
            if _CTX is not None:
                pipeline.configure(output_dir=_config("output_dir", ""),
                                   default_platforms=_config("default_platforms", []),
                                   loudness_lufs=_config("loudness_lufs", -14))
            return _json(fn(args))
        except pipeline.Unavailable as exc:
            return _json({"error": str(exc), "hint": "Text copy still works; this media kind is not available."})
        except (FileNotFoundError, KeyError, ValueError, probe.ProbeError) as exc:
            return _json({"error": _message(exc), "hint": "Check the arguments; run postkitty_scan first for a new job."})
        except Exception as exc:
            return _json({"error": f"{type(exc).__name__}: {exc}", "hint": "Unexpected failure; report it with the job id."})

    return handler


def _with_directives(result: dict) -> dict:
    """Add the lines Hermes acts on: ``MEDIA:`` attaches the contact sheet, ``::preview`` opens the board."""
    contact, inline = result.get("contact"), result.get("board_inline")
    if contact:
        result["media_line"] = f"MEDIA:{contact}"
    if inline:
        result["preview_directive"] = f'::preview{{file="{inline}"}}'
    return result


@_safe
def scan(args: dict) -> dict:
    return pipeline.scan(args)


@_safe
def write(args: dict) -> dict:
    return pipeline.write(args)


@_safe
def make(args: dict) -> dict:
    return _with_directives(pipeline.make(args))


@_safe
def redo(args: dict) -> dict:
    return _with_directives(pipeline.redo(args))


@_safe
def check(args: dict) -> dict:
    return pipeline.check(args)


HANDLERS = {"postkitty_scan": scan, "postkitty_write": write, "postkitty_make": make,
            "postkitty_redo": redo, "postkitty_check": check}
