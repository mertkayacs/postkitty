"""Repair loop driver. The image and video lanes register strategies through ``register``."""

from __future__ import annotations

from collections.abc import Callable

from ..platforms import TargetSpec
from .checks import Check, RenderResult, failures, run_checks

Strategy = Callable[[RenderResult, TargetSpec, Check, dict], "RenderResult | None"]

MAX_ROUNDS = 3
_STRATEGIES: dict[str, Strategy] = {}


def register(check_id: str, fn: Strategy) -> None:
    _STRATEGIES[check_id] = fn


def check_and_repair(
    result: RenderResult, target: TargetSpec, rerender: dict
) -> tuple[RenderResult, list[Check], list[dict]]:
    """Run the checks, repair failing hard checks, and re-check, for at most three rounds.

    ``rerender`` is passed to every strategy untouched (override keys, work dir and so on). A
    strategy returns the new ``RenderResult`` or ``None`` when it cannot help.
    """
    repairs: list[dict] = []
    checks = run_checks(result, target)
    for _ in range(MAX_ROUNDS):
        todo = [check for check in failures(checks) if check.id in _STRATEGIES]
        if not todo:
            break
        progress = False
        for check in todo:
            strategy = _STRATEGIES[check.id]
            action = getattr(strategy, "action_name", None) or getattr(strategy, "__name__", "repair")
            try:
                updated = strategy(result, target, check, rerender)
            except Exception as exc:
                repairs.append({"check": check.id, "action": action, "ok": False, "error": str(exc)})
                continue
            if updated is not None:
                result = updated
                progress = True
            repairs.append({"check": check.id, "action": action, "ok": updated is not None})
        checks = run_checks(result, target)
        if not progress:
            break
    return result, checks, repairs
