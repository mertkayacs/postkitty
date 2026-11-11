"""Check records, the checker registry and shared copy checks.

Media lanes register their own image and video checkers with ``register_checker``. This module
also contributes the generic file checks every target needs (existence, byte size, exact
dimensions, duration) so ``postkitty_check`` is useful before the media lanes load.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ..platforms import Spec, TargetSpec
from ..text import fit as copyfit

Status = Literal["pass", "fail", "advisory", "skipped"]

_VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}


@dataclass
class Check:
    id: str
    target: str
    status: Status
    hard: bool
    measured: Any
    expected: Any
    message: str
    source_url: str | None = None
    source_scope: str | None = None
    checked_on: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "target": self.target,
            "status": self.status,
            "hard": self.hard,
            "measured": self.measured,
            "expected": self.expected,
            "message": self.message,
            "source_url": self.source_url,
            "source_scope": self.source_scope,
            "checked_on": self.checked_on,
        }


@dataclass
class RenderResult:
    target: str
    file: Path
    width: int
    height: int
    duration: float | None
    bytes: int
    layout: dict = field(default_factory=dict)
    subjects_inside: float | None = None
    extra: dict = field(default_factory=dict)


Checker = Callable[[RenderResult, TargetSpec], list[Check]]

_CHECKERS: dict[str, list[Checker]] = {"image": [], "video": []}


def register_checker(kind: str, fn: Checker) -> None:
    if kind not in _CHECKERS:
        raise ValueError(f"unknown checker kind {kind!r}")
    _CHECKERS[kind].append(fn)


def _kind(result: RenderResult, target: TargetSpec) -> str:
    if target.kind in {"image", "video"}:
        return target.kind
    if result.file.suffix.lower() in _VIDEO_SUFFIXES:
        return "video"
    return "image"


def _status(failed: bool, hard: bool) -> Status:
    if not failed:
        return "pass"
    return "fail" if hard else "advisory"


def _spec_check(
    check_id: str,
    target: str,
    spec: Spec,
    measured: Any,
    expected: Any,
    message: str,
    failed: bool,
) -> Check:
    hard = spec.enforcement == "hard"
    return Check(
        id=check_id,
        target=target,
        status=_status(failed, hard),
        hard=hard,
        measured=measured,
        expected=expected,
        message=message,
        source_url=spec.source_url,
        source_scope=spec.source_scope,
        checked_on=spec.checked_on,
    )


def baseline_checks(result: RenderResult, target: TargetSpec, kind: str) -> list[Check]:
    """Generic file checks, used while no media lane has registered a checker for ``kind``."""
    checks: list[Check] = []
    path = Path(result.file)
    if not path.is_file():
        return [
            Check(
                id="file.exists",
                target=target.id,
                status="fail",
                hard=True,
                measured=str(path),
                expected="an existing file",
                message="The output file does not exist.",
            )
        ]

    bytes_max = target.limits.get("bytes_max")
    if bytes_max is not None:
        measured = result.bytes if result.bytes is not None else path.stat().st_size
        checks.append(
            _spec_check(
                f"{kind}.bytes_max",
                target.id,
                bytes_max,
                measured,
                bytes_max.value,
                f"The file is {measured} bytes; {target.id} allows {bytes_max.value}.",
                measured > int(bytes_max.value),
            )
        )

    if target.width and target.height:
        failed = result.width != target.width or result.height != target.height
        checks.append(
            Check(
                id=f"{kind}.dimensions",
                target=target.id,
                status=_status(failed, True),
                hard=True,
                measured={"width": result.width, "height": result.height},
                expected={"width": target.width, "height": target.height},
                message=(
                    f"The file is {result.width}x{result.height}; "
                    f"{target.id} requires {target.width}x{target.height}."
                ),
            )
        )

    duration_max = target.limits.get("duration_max")
    if duration_max is not None and result.duration is not None:
        checks.append(
            _spec_check(
                f"{kind}.duration_max",
                target.id,
                duration_max,
                round(result.duration, 3),
                duration_max.value,
                f"The video is {result.duration:.1f} s; the maximum is {duration_max.value} s.",
                result.duration > float(duration_max.value),
            )
        )

    duration_min = target.limits.get("duration_min")
    if duration_min is not None and result.duration is not None:
        checks.append(
            _spec_check(
                f"{kind}.duration_min",
                target.id,
                duration_min,
                round(result.duration, 3),
                duration_min.value,
                f"The video is {result.duration:.1f} s; the minimum is {duration_min.value} s.",
                result.duration < float(duration_min.value),
            )
        )
    return checks


def run_checks(result: RenderResult, target: TargetSpec) -> list[Check]:
    """Run the registered checkers for the result's kind; fall back to generic file checks."""
    kind = _kind(result, target)
    if not Path(result.file).is_file():
        return baseline_checks(result, target, kind)
    registered = _CHECKERS.get(kind, [])
    if registered:
        return [check for checker in registered for check in checker(result, target)]
    checks = baseline_checks(result, target, kind)
    checks.append(
        Check(
            id="media.checks",
            target=target.id,
            status="skipped",
            hard=False,
            measured=None,
            expected=f"{kind} checks",
            message=f"The detailed {kind} checks are not available yet; only size and duration were checked.",
        )
    )
    return checks


def hard_pass(checks: list[Check]) -> bool:
    return not any(check.hard and check.status == "fail" for check in checks)


def failures(checks: list[Check]) -> list[Check]:
    return [check for check in checks if check.hard and check.status == "fail"]


def copy_checks(platform: str, parts: list[str], rules: copyfit.TextRules) -> list[Check]:
    """Shared copy checks: limit per part, hashtag and mention caps, and UTF-8 bytes."""
    target = f"copy:{platform}"
    checks: list[Check] = []
    for index, part in enumerate(parts):
        count = copyfit.count_text(part, rules.unit)
        failed = count > rules.limit
        suffix = f" part {index + 1}" if len(parts) > 1 else ""
        checks.append(
            Check(
                id="copy.limit",
                target=target,
                status=_status(failed, True),
                hard=True,
                measured=count,
                expected=rules.limit,
                message=(
                    f"{platform} allows {rules.limit} {rules.unit}{suffix}; "
                    f"this draft uses {count}."
                ),
            )
        )

    joined = "\n\n".join(parts)
    if rules.hashtags_max is not None:
        count = copyfit.count_hashtags(joined)
        checks.append(
            Check(
                id="copy.hashtags_max",
                target=target,
                status=_status(count > rules.hashtags_max, True),
                hard=True,
                measured=count,
                expected=rules.hashtags_max,
                message=f"{platform} allows {rules.hashtags_max} hashtags; this draft has {count}.",
            )
        )
    if rules.mentions_max is not None:
        count = copyfit.count_mentions(joined)
        checks.append(
            Check(
                id="copy.mentions_max",
                target=target,
                status=_status(count > rules.mentions_max, True),
                hard=True,
                measured=count,
                expected=rules.mentions_max,
                message=f"{platform} allows {rules.mentions_max} mentions; this draft has {count}.",
            )
        )
    if rules.bytes_max is not None:
        count = max(len(part.encode("utf-8")) for part in parts)
        checks.append(
            Check(
                id="copy.bytes_max",
                target=target,
                status=_status(count > rules.bytes_max, True),
                hard=True,
                measured=count,
                expected=rules.bytes_max,
                message=f"{platform} allows {rules.bytes_max} UTF-8 bytes in one post; the longest post uses {count}.",
            )
        )
    return checks
