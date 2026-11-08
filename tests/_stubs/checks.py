from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
