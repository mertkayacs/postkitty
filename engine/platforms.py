"""Load ``data/platforms.yaml`` into typed platform and target specs.

The file is checked while it loads. An unknown key, a missing field or a value of the wrong type raises
``ValueError`` with the place in the file, so a typo fails here and never during a render.
"""

from __future__ import annotations

import difflib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, NoReturn

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "platforms.yaml"

_SCHEMA = "postkitty.platforms/1"
_KINDS = ("image", "video", "image_or_video")
_ENFORCEMENTS = ("hard", "recommendation")
_SCOPES = ("api", "official", "ad", "secondary")
# The counting rules count_text in engine/text/fit.py implements.
_UNITS = ("codepoints", "utf16", "utf8_bytes", "graphemes", "x_weighted")

_SOURCE_FIELDS = ("source_url", "source_scope", "checked_on")
_SPEC_FIELDS = ("value", "unit", "enforcement", *_SOURCE_FIELDS, "note")
_PLAYBOOK_FIELDS = ("text", *_SOURCE_FIELDS)
_TEXT_LIMITS = ("limit", "bytes_max", "hashtags_max", "mentions_max")
_UNIT_LIMITS = ("limit", "bytes_max")
_LIST_LIMITS = ("formats", "containers", "video_codecs", "aspect_range", "aspect_options")
_NUMBER_LIMITS = (
    "audio_sample_rate", "fps_min", "fps_max", "duration_min", "duration_max", "bytes_min", "bytes_max",
    "video_bps_max", "audio_bps_max", "dimension_min", "dimension_max", "aspect_min", "aspect_max",
)
_TARGET_LIMITS = (*_LIST_LIMITS, *_NUMBER_LIMITS, "safe_area")
_SAFE_AREA_EDGES = ("top", "bottom", "side")


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
    """One output postkitty renders: its size, its kind and the limits its file must meet."""

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
    """One platform: its text limits and its targets."""

    name: str
    label: str
    text: dict[str, Spec] = field(default_factory=dict)
    targets: dict[str, TargetSpec] = field(default_factory=dict)


def _fail(where: str, problem: str) -> NoReturn:
    raise ValueError(f"{where}: {problem}")


def _one_of(value: Any, allowed: tuple[str, ...], where: str, name: str) -> None:
    if value not in allowed:
        _fail(where, f"{name} must be one of {', '.join(allowed)}, found {value!r}")


def _mapping(raw: Any, where: str, known: tuple[str, ...] | None = None) -> Mapping[str, Any]:
    """Return ``raw`` once it is a mapping that holds only ``known`` keys."""
    if not isinstance(raw, Mapping):
        _fail(where, f"expected a mapping, found {type(raw).__name__}")
    for key in raw:
        if known is not None and key not in known:
            close = difflib.get_close_matches(str(key), known, n=1)
            hint = f"did you mean {close[0]!r}?" if close else f"known keys: {', '.join(known)}"
            _fail(where, f"unknown key {key!r}; {hint}")
    return raw


def _check_date(value: Any, where: str) -> None:
    try:
        date.fromisoformat(str(value))
    except ValueError:
        _fail(where, f"checked_on must be a date like 2026-11-11, found {value!r}")


def _source(fields: Mapping[str, Any], where: str) -> None:
    for name in _SOURCE_FIELDS:
        if not fields.get(name):
            _fail(where, f"missing {name}")
    _one_of(fields["source_scope"], _SCOPES, where, "source_scope")
    _check_date(fields["checked_on"], where)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_value(key: str, value: Any, where: str) -> None:
    if key in _LIST_LIMITS:
        ok = isinstance(value, list) and bool(value) and all(isinstance(item, str) for item in value)
        expected = "a list of names"
    elif key == "safe_area":
        ok = (
            isinstance(value, Mapping)
            and bool(value)
            and set(value) <= set(_SAFE_AREA_EDGES)
            and all(_is_number(edge) and 0 <= edge < 0.5 for edge in value.values())
        )
        expected = "top, bottom and side fractions below 0.5"
    else:
        ok = _is_number(value) and value > 0
        expected = "a positive number"
    if not ok:
        _fail(where, f"value must be {expected}, found {value!r}")


def _spec(key: str, raw: Any, where: str) -> Spec:
    fields = _mapping(raw, where, _SPEC_FIELDS)
    if "value" not in fields:
        _fail(where, "missing value")
    _check_value(key, fields["value"], where)
    _one_of(fields.get("enforcement"), _ENFORCEMENTS, where, "enforcement")
    _source(fields, where)
    if fields["enforcement"] == "hard" and fields["source_scope"] == "secondary":
        _fail(where, "a limit from a secondary source must be a recommendation")
    return Spec(
        value=fields["value"],
        enforcement=fields["enforcement"],
        source_url=fields["source_url"],
        source_scope=fields["source_scope"],
        checked_on=str(fields["checked_on"]),
        note=fields.get("note"),
        unit=fields.get("unit"),
    )


def _text(platform: str, raw: Any) -> dict[str, Spec]:
    where = f"{platform}.text"
    text: dict[str, Spec] = {}
    for key, value in _mapping(raw, where, _TEXT_LIMITS).items():
        spec = _spec(key, value, f"{where}.{key}")
        if key in _UNIT_LIMITS:
            if spec.unit is None:
                _fail(f"{where}.{key}", "missing unit")
            _one_of(spec.unit, _UNITS, f"{where}.{key}", "unit")
        text[key] = spec
    return text


def _target(target_id: str, raw: Any, platform: str, label: str) -> TargetSpec:
    where = f"{platform}.targets.{target_id}"
    fields = _mapping(raw, where, ("kind", "width", "height", *_TARGET_LIMITS))
    kind = fields.get("kind")
    _one_of(kind, _KINDS, where, "kind")
    for side in ("width", "height"):
        size = fields.get(side)
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            _fail(where, f"{side} must be a positive whole number, found {size!r}")
        # Instagram, Threads and X require 4:2:0 video, which cannot have an odd width or height.
        if kind != "image" and size % 2:
            _fail(where, f"{side} must be even for video, found {size}")
    return TargetSpec(
        id=target_id,
        platform=platform,
        label=f"{label} {target_id.replace('_', ' ')}",
        kind=kind,
        width=fields["width"],
        height=fields["height"],
        limits={key: _spec(key, fields[key], f"{where}.{key}") for key in fields if key in _TARGET_LIMITS},
    )


def _platform(name: str, raw: Any) -> PlatformSpec:
    fields = _mapping(raw, name, ("label", "text", "playbook", "targets"))
    label = fields.get("label")
    if not isinstance(label, str) or not label:
        _fail(name, "missing label")
    playbook = fields.get("playbook", [])
    if not isinstance(playbook, list):
        _fail(f"{name}.playbook", f"expected a list, found {type(playbook).__name__}")
    for index, entry in enumerate(playbook):
        where = f"{name}.playbook[{index}]"
        if not _mapping(entry, where, _PLAYBOOK_FIELDS).get("text"):
            _fail(where, "missing text")
        _source(entry, where)
    targets = {
        target_id: _target(target_id, target_raw, name, label)
        for target_id, target_raw in _mapping(fields.get("targets", {}), f"{name}.targets").items()
    }
    return PlatformSpec(name=name, label=label, text=_text(name, fields.get("text", {})), targets=targets)


def _platforms(data: Any) -> dict[str, PlatformSpec]:
    document = _mapping(data, "document", ("schema", "checked_on", "platforms"))
    if document.get("schema") != _SCHEMA:
        _fail("schema", f"expected {_SCHEMA!r}, found {document.get('schema')!r}")
    _check_date(document.get("checked_on"), "document")
    platforms: dict[str, PlatformSpec] = {}
    owners: dict[str, str] = {}
    for name, raw in _mapping(document.get("platforms"), "platforms").items():
        platforms[name] = _platform(name, raw)
        for target_id in platforms[name].targets:
            # get_target looks a target up by id alone, so a second target with the same id could never be reached.
            if target_id in owners:
                _fail(f"{name}.targets.{target_id}", f"target id is already used by {owners[target_id]}")
            owners[target_id] = name
    return platforms


def load_platforms(path: Path | None = None) -> dict[str, PlatformSpec]:
    """Load and check the platform file and return ``{platform_name: PlatformSpec}``.

    Raises ``ValueError`` with the file name and the place in it when the file breaks its schema.
    """
    from ruamel.yaml import YAML

    path = Path(path) if path is not None else _DATA_FILE
    with path.open("r", encoding="utf-8") as handle:
        data = YAML(typ="safe").load(handle)
    try:
        return _platforms(data)
    except ValueError as exc:
        raise ValueError(f"{path.name}: {exc}") from None


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
    """The platform called ``name`` in any letter case; ``KeyError`` when there is none."""
    platforms = load_platforms()
    try:
        return platforms[str(name).strip().lower()]
    except KeyError as exc:
        raise KeyError(f"unknown platform {name!r}") from exc


def get_target(target_id: str) -> TargetSpec:
    """The target with ``target_id`` in any letter case; ``KeyError`` when there is none."""
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
