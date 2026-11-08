from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CHECKERS: dict[str, Callable[..., Any]] = {}


@dataclass
class Check:
    id: str
    target: str
    status: str
    hard: bool
    measured: Any
    expected: Any
    message: str
    source_url: str | None = None
    source_scope: str | None = None
    checked_on: str | None = None


@dataclass
class RenderResult:
    target: str
    file: Path
    width: int
    height: int
    duration: float | None
    bytes: int
    layout: dict[str, Any]
    subjects_inside: float | None
    extra: dict[str, Any]


def register_checker(kind: str, fn: Callable[..., Any]) -> None:
    CHECKERS[kind] = fn
