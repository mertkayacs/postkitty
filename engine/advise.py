"""Deterministic fit facts per platform. The model writes the advice; this module supplies numbers."""

from __future__ import annotations

from collections.abc import Iterable

from . import platforms
from .probe import InputInfo
from .text import fit as copyfit


def source_for(infos: Iterable[InputInfo], target) -> InputInfo | None:
    """The first input a target should be made from: video for video, image for image, else either."""
    by_kind: dict[str, InputInfo] = {}
    for info in infos:
        by_kind.setdefault(info.kind, info)
    if target.kind in by_kind:
        return by_kind[target.kind]
    return (by_kind.get("video") or by_kind.get("image")) if target.kind == "image_or_video" else None


def _layout_hint(info: InputInfo | None, target) -> tuple[str, str]:
    if info is None or not info.height:
        return "auto", "No source media yet."
    source_aspect = info.width / info.height
    delta = abs(source_aspect - target.aspect) / target.aspect
    if delta <= 0.05:
        return "crop", "The source aspect already matches this target."
    if target.aspect < 0.9 and source_aspect > 1.15:
        return "pad", "The source is landscape and this target is vertical; expect a crop or a split layout."
    if delta <= 0.35:
        return "crop", "A crop of the source fits this target's aspect."
    return "pad", "The source aspect is far from this target; expect padding or a split layout."


def _trim(info: InputInfo | None, target) -> list[float] | None:
    if info is None or info.kind != "video" or info.duration is None:
        return None
    duration_max = target.limits.get("duration_max")
    if duration_max is not None and info.duration > float(duration_max.value):
        return [0.0, float(duration_max.value)]
    return [0.0, round(float(info.duration), 3)]


def plan_hint(info: InputInfo | None, target) -> dict:
    """A fallback plan the media lanes replace with their own geometry."""
    layout, note = _layout_hint(info, target)
    trim = _trim(info, target)
    if trim and info and info.duration and trim[1] < info.duration:
        note = f"{note} Trim the first {trim[1]:.1f} s or pick a better window.".strip()
    if info is not None and info.kind == "video":
        for key, measured, unit in (("duration_min", info.duration, "s"), ("fps_min", info.fps, "fps")):
            spec = target.limits.get(key)
            if spec is not None and measured is not None and measured < float(spec.value):
                note = f"{note} The source is {measured:g} {unit}; {target.id} needs at least {float(spec.value):g} {unit}."
    return {
        "layout": layout,
        "note": note,
        "trim": trim,
        "cover_at": 0.0 if info and info.kind == "video" else None,
    }


def _text_facts(platform: str, text: str) -> dict:
    report = copyfit.fit(platform, text, split_threads=True)
    facts = {
        "unit": report.unit,
        "unit_words": copyfit.unit_words(report.unit),
        "limit": report.limit,
        "count": max(report.counts) if report.counts else 0,
        "ok": report.ok,
        "overflow": report.overflow,
        "split": report.split,
        "parts": len(report.parts),
        "fold_chars": report.fold_chars,
    }
    if report.hashtags or report.mentions:
        facts["hashtags"] = report.hashtags
        facts["mentions"] = report.mentions
    return facts


def fit_facts(
    infos: Iterable[InputInfo],
    text: str | None = None,
    wanted: list[str] | None = None,
    plans: Iterable[dict] | None = None,
) -> dict[str, dict]:
    """Per-platform target facts: sizes, aspect match, trim and text fit. ``wanted`` limits platforms or target ids."""
    info_list = list(infos)
    wanted_set = set(wanted or [])
    planned_layouts = {plan["id"]: plan["layout"] for plan in plans or []}

    result: dict[str, dict] = {}
    for name, platform in platforms.load_platforms().items():
        targets: list[dict] = []
        if wanted_set and name not in wanted_set and not wanted_set & set(platform.targets):
            continue
        for target in platform.targets.values():
            if wanted_set and name not in wanted_set and target.id not in wanted_set:
                continue
            source = source_for(info_list, target)
            if source is None:
                continue
            hint = plan_hint(source, target)
            entry = {
                "id": target.id,
                "kind": target.kind,
                "width": target.width,
                "height": target.height,
                "aspect": round(target.aspect, 4),
                "source_aspect": (
                    round(source.width / source.height, 4)
                    if source is not None and source.height
                    else None
                ),
                "layout_hint": planned_layouts.get(target.id, hint["layout"]),
                "note": hint["note"],
            }
            trim = hint.get("trim")
            if trim:
                entry["trim"] = trim
            for key in ("duration_max", "duration_min", "fps_min"):
                spec = target.limits.get(key)
                if spec is not None:
                    entry[key] = spec.value
            targets.append(entry)

        if not targets and not text:
            continue
        facts: list[str] = []
        if text:
            text_facts = _text_facts(name, text)
            entry_text = text_facts
            if text_facts["split"]:
                facts.append(
                    f"Copy is over the limit of {text_facts['limit']} {text_facts['unit_words']} and splits into a "
                    f"thread of {text_facts['parts']} posts (longest {text_facts['count']})."
                )
            elif text_facts["ok"]:
                facts.append(
                    f"Copy fits: {text_facts['count']} of {text_facts['limit']} {text_facts['unit_words']}."
                )
            else:
                facts.append(
                    f"Copy is over the limit of {text_facts['limit']} {text_facts['unit_words']} by "
                    f"{text_facts['overflow']}."
                )
        else:
            entry_text = None
        for target in targets:
            facts.append(
                f"{target['id']}: {target['width']}x{target['height']} {target['kind']}; "
                f"{target['note']}"
            )
        result[name] = {
            "label": platform.label,
            "targets": targets,
            "text": entry_text,
            "facts": facts,
        }
    return result


def free_text_platforms() -> list[str]:
    return list(platforms.load_platforms())
