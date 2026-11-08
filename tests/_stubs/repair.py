from __future__ import annotations

from collections.abc import Callable
from typing import Any

REPAIRS: dict[str, Callable[..., Any]] = {}


def register(check_id: str, fn: Callable[..., Any]) -> None:
    REPAIRS[check_id] = fn
