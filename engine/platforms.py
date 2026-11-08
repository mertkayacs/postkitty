"""Load ``data/platforms.yaml`` into typed platform and target specs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "platforms.yaml"


@dataclass
class Spec:
    """One numeric or structural limit plus where it came from."""

    value: Any
    enforcement: str
    source_url: str | None = None
    source_scope: str | None = None
    checked_on: str | None = None
    note: str | None = None
    unit: str | None = None


@dataclass
class TargetSpec:
    id: str
    platform: str
    label: str
    kind: str
    width: int
    height: int
    limits: dict[str, Spec] = field(default_factory=dict)

    @property
    def aspect(self) -> float:
        return self.width / self.height


@dataclass
class PlatformSpec:
    name: str
    label: str
    text: dict[str, Spec] = field(default_factory=dict)
    targets: dict[str, TargetSpec] = field(default_factory=dict)


def _spec(raw: Any, default_enforcement: str = "hard") -> Spec:
    if isinstance(raw, Mapping):
        return Spec(
            value=raw.get("value"),
            enforcement=str(raw.get("enforcement") or default_enforcement),
            source_url=raw.get("source_url"),
            source_scope=raw.get("source_scope"),
            checked_on=str(raw["checked_on"]) if raw.get("checked_on") else None,
            note=raw.get("note"),
            unit=raw.get("unit"),
        )
    return Spec(value=raw, enforcement=default_enforcement)


def _int_value(raw: Any) -> int:
    if isinstance(raw, Mapping):
        raw = raw.get("value")
    return int(raw)


def _load_yaml(path: Path) -> dict[str, Any]:
    from ruamel.yaml import YAML

    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a platforms document")
    return data


def load_platforms(path: Path | None = None) -> dict[str, PlatformSpec]:
    """Load the platform file and return ``{platform_name: PlatformSpec}``."""
    data = _load_yaml(Path(path) if path is not None else _DATA_FILE)
    raw_platforms = data.get("platforms") or {}
    if not isinstance(raw_platforms, Mapping):
        raise ValueError("platforms.yaml: 'platforms' must be a mapping")

    platforms: dict[str, PlatformSpec] = {}
    for name, raw in raw_platforms.items():
        if not isinstance(raw, Mapping):
            continue
        label = str(raw.get("label") or name)
        text = {
            str(key): _spec(value)
            for key, value in (raw.get("text") or {}).items()
        }
        targets: dict[str, TargetSpec] = {}
        for target_id, target_raw in (raw.get("targets") or {}).items():
            if not isinstance(target_raw, Mapping):
                continue
            limits = {
                str(key): _spec(value)
                for key, value in target_raw.items()
                if str(key) not in {"kind", "width", "height"}
            }
            targets[str(target_id)] = TargetSpec(
                id=str(target_id),
                platform=str(name),
                label=f"{label} {str(target_id).replace('_', ' ')}",
                kind=str(target_raw.get("kind") or "image"),
                width=_int_value(target_raw.get("width", 0)),
                height=_int_value(target_raw.get("height", 0)),
                limits=limits,
            )
        platforms[str(name)] = PlatformSpec(
            name=str(name), label=label, text=text, targets=targets
        )
    return platforms


def _all_targets(platforms: dict[str, PlatformSpec]) -> list[TargetSpec]:
    out: list[TargetSpec] = []
    for platform in platforms.values():
        out.extend(platform.targets.values())
    return out


def _kind_matches(kind: str, kinds: set[str]) -> bool:
    if kind == "image_or_video":
        return bool(kinds & {"image", "video"})
    return kind in kinds


def targets_for(
    kinds: set[str], wanted: list[str] | None = None
) -> list[TargetSpec]:
    """Targets that fit ``kinds``, limited to platform names or target ids in ``wanted``."""
    platforms = load_platforms()
    requested = [str(item).strip().lower() for item in (wanted or []) if str(item).strip()]
    explicit_ids = {item for item in requested if any(t.id == item for t in _all_targets(platforms))}
    explicit_platforms = {item for item in requested if item in platforms}

    selected: list[TargetSpec] = []
    for platform in platforms.values():
        for target in platform.targets.values():
            if requested:
                hit = target.id in explicit_ids or platform.name in explicit_platforms
                if not hit:
                    continue
                if target.id not in explicit_ids and not _kind_matches(target.kind, kinds):
                    continue
            elif not _kind_matches(target.kind, kinds):
                continue
            selected.append(target)
    return selected


def get_platform(name: str) -> PlatformSpec:
    platforms = load_platforms()
    try:
        return platforms[str(name).strip().lower()]
    except KeyError as exc:
        raise KeyError(f"unknown platform {name!r}") from exc


def get_target(target_id: str) -> TargetSpec:
    wanted = str(target_id).strip().lower()
    for target in _all_targets(load_platforms()):
        if target.id == wanted:
            return target
    raise KeyError(f"unknown target {target_id!r}")


def platform_for_target(target_id: str) -> str:
    return get_target(target_id).platform


def text_limits(platform: str) -> dict[str, Spec]:
    return get_platform(platform).text


def target_ids() -> list[str]:
    return [target.id for target in _all_targets(load_platforms())]


def platform_names() -> list[str]:
    return list(load_platforms())
