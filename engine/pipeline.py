"""The postkitty pipeline: scan, write, make, redo and check as plain functions, a dict in and a dict out.

This is the public Python API and it needs no Hermes. Call ``configure`` once, then the steps in order.
Bad arguments raise ``ValueError``, ``KeyError``, ``FileNotFoundError`` or ``probe.ProbeError``. A media
kind whose modules or packages are missing raises ``Unavailable``.

Media engines (photo, video, board) are imported inside the steps, so importing this module loads
neither OpenCV, NumPy nor Pillow, and a missing engine module only disables its own media kind.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from . import advise, platforms, probe
from . import job as jobs
from .text import fit as copyfit
from .verify import checks, repair

ALIASES = {"twitter": "x", "ig": "instagram", "insta": "instagram", "yt": "youtube",
           "shorts": "youtube", "fb": "facebook", "bsky": "bluesky"}
LAYOUTS = ("crop", "split", "speaker", "seam", "pad", "auto")
OVERRIDE_KEYS = ("layout", "focus", "trim", "cover_at")
_ENGINES = {
    "image": ("detect.faces", "photo.render", "photo.checks"),
    "video": ("detect.faces", "video.scan", "video.render", "video.checks"),
}
_SETTINGS: dict[str, Any] = {}


class Unavailable(Exception):
    """A media engine module is missing or lacks a dependency."""


def configure(*, output_dir: str | os.PathLike[str] | None = None, default_platforms: list[str] | None = None,
              loudness_lufs: float | None = None) -> None:
    """Set where job folders go, the platforms a scan uses when it names none, and the video loudness target.

    A setting left as ``None`` keeps its value. An empty ``output_dir`` falls back to the
    ``POSTKITTY_OUTPUT_DIR`` environment variable, then to ``./postkitty``.
    """
    for key, value in (("output_dir", output_dir), ("default_platforms", default_platforms),
                       ("loudness_lufs", loudness_lufs)):
        if value is not None:
            _SETTINGS[key] = value


def _setting(key: str, default: Any) -> Any:
    return _SETTINGS.get(key) or default


def _out_dir() -> Path:
    return jobs.default_out_dir(str(_setting("output_dir", "") or os.environ.get("POSTKITTY_OUTPUT_DIR", "")))


def _engine(kind: str) -> SimpleNamespace:
    """Import one media engine lazily. Raises ``Unavailable`` when a module or dependency is missing."""
    mods = {}
    for name in _ENGINES[kind]:
        try:
            mods[name.rpartition(".")[2]] = importlib.import_module(f".{name}", __package__)
        except ModuleNotFoundError as exc:
            missing = exc.name or name
            if missing.endswith(f"engine.{name}"):
                raise Unavailable(f"The {kind} engine is not available yet ({name} is missing).") from exc
            raise Unavailable(f"The {kind} engine needs the Python package {missing!r}.") from exc
    return SimpleNamespace(**mods)


def _platform_names(names: Any) -> list[str]:
    """Normalize platform names or target ids; unknown names raise ``ValueError``."""
    known = set(platforms.platform_names()) | set(platforms.target_ids())
    out = []
    for raw in names or []:
        name = ALIASES.get(str(raw).strip().lower(), str(raw).strip().lower())
        if name not in known:
            raise ValueError(f"unknown platform or target {raw!r}; use one of {sorted(known)}")
        out.append(name)
    return out


def _list_arg(args: dict, key: str) -> list:
    """An optional list argument; a bare string or any other type is a clear error, never iterated."""
    value = args.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"argument '{key}' must be a list, got {type(value).__name__}")
    return value


def _dict_arg(args: dict, key: str) -> dict:
    value = args.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"argument '{key}' must be an object, got {type(value).__name__}")
    return value


def _str_arg(args: dict, key: str) -> str:
    value = args.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"argument '{key}' must be a string, got {type(value).__name__}")
    return value


def _bool_arg(args: dict, key: str, default: bool) -> bool:
    value = args.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"argument '{key}' must be true or false, got {type(value).__name__}")
    return value


def _input_path(raw: Any) -> Path:
    path = Path(str(raw)).expanduser()
    if path.is_dir():
        raise ValueError(f"{raw} is a directory; give the image or video file itself")
    return path


def _open_job(args: dict) -> jobs.Job:
    if not args.get("job"):
        raise ValueError("'job' is required; run postkitty_scan first")
    return jobs.open_job(_out_dir(), str(args["job"]))


def _infos(manifest: dict) -> list[probe.InputInfo]:
    keys = {f.name for f in dataclasses.fields(probe.InputInfo)}
    return [probe.InputInfo(**{**{k: v for k, v in e.items() if k in keys}, "path": Path(e["path"])})
            for e in manifest.get("inputs", [])]


def _rel(job: jobs.Job, path: Path) -> str:
    return Path(path).resolve().relative_to(job.root.resolve()).as_posix()


# ------------------------------------------------------------------ media

class _LazyDetector:
    """Builds the real detector (and fetches its weights) only when a frame actually needs detecting."""

    def __init__(self, factory: Any):
        self._factory = factory
        self._real: Any = None

    def _get(self) -> Any:
        if self._real is None:
            self._real = self._factory()
        return self._real

    @property
    def name(self) -> str:
        return self._get().name

    def detect(self, image: Any) -> Any:
        return self._get().detect(image)


def _shared_faces_dir(eng: SimpleNamespace) -> Path:
    """Detections are cached by content hash across jobs, next to the model cache."""
    override = os.environ.get("POSTKITTY_FACES_CACHE")
    if override:
        return Path(override)
    return importlib.import_module(".detect.models", __package__).model_cache_dir().parent / "faces"



class _Media:
    """Per-call cache of detections and scans, so a make over many targets scans each input once."""

    def __init__(self, job: jobs.Job):
        self.job = job
        self._detector: Any = None
        self._scans: dict[str, Any] = {}

    def detector(self, eng: SimpleNamespace) -> Any:
        if self._detector is None:
            self._detector = _LazyDetector(lambda: eng.faces.get_detector(self.job.work / "faces"))
        return self._detector

    def scan(self, info: probe.InputInfo) -> tuple[SimpleNamespace, Any]:
        eng = _engine(info.kind)
        if info.id not in self._scans:
            job_faces = self.job.work / "faces" / f"{info.sha256}.json"
            shared = _shared_faces_dir(eng) / f"{info.sha256}.json"
            if shared.is_file() and not job_faces.is_file():
                job_faces.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(shared, job_faces)
            if info.kind == "image":
                self._scans[info.id] = eng.faces.detect_image(info, self.detector(eng), self.job.work / "faces")
            else:
                self._scans[info.id] = eng.scan.scan_video(info, self.detector(eng), self.job.work)
            if job_faces.is_file() and not shared.is_file():
                shared.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(job_faces, shared)
        return eng, self._scans[info.id]


    def plan(self, info: probe.InputInfo, target: platforms.TargetSpec, override: dict | None) -> Any:
        eng, scan = self.scan(info)
        if info.kind == "image":
            return eng.render.plan_image(info, scan, target, override)
        return eng.render.plan_video(info, scan, target, override)


def _mode(plan: Any) -> str:
    """Layout mode of an image Layout (``mode``) or a VideoPlan (``layout``)."""
    return getattr(plan, "mode", None) or getattr(plan, "layout", None) or "auto"


def _plan_summary(info: probe.InputInfo, plan: Any, target: platforms.TargetSpec) -> dict:
    if plan is None:
        return advise.plan_hint(info, target)
    out = {"layout": _mode(plan), "note": _plan_note(info, plan)}
    if getattr(plan, "trim", None):
        out.update(trim=list(plan.trim), cover_at=getattr(plan, "cover_at", None))
    return out


def _plan_note(info: probe.InputInfo, plan: Any) -> str:
    windows = getattr(plan, "windows", None)
    if windows and _mode(plan) == "crop" and all(
        not isinstance(window, (list, tuple))
        and abs(window.x) <= 1.0
        and abs(window.y) <= 1.0
        and window.w >= info.width - 1.0
        and window.h >= info.height - 1.0
        for window in windows
    ):
        return "Same shape as the source; the full frame is kept."
    return getattr(plan, "note", "")


def _stem(target: platforms.TargetSpec) -> str:
    prefix = target.platform + "_"
    return target.id[len(prefix):] if target.id.startswith(prefix) else target.id


def _render(media: _Media, info: probe.InputInfo, target: platforms.TargetSpec, override: dict,
            masters: dict) -> tuple[checks.RenderResult, Any, Callable[[dict], checks.RenderResult]]:
    """Plan and render one target. Returns the result, the plan and a re-render callback for repairs."""
    eng, _ = media.scan(info)
    render_dir = media.job.work / "render"
    render_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".mp4" if info.kind == "video" else (".png" if info.has_alpha else ".jpg")

    def fresh() -> Path:
        return render_dir / f"{target.id}-{len(list(render_dir.glob(target.id + '-*')))}{suffix}"

    def render(plan: Any, out: Path) -> checks.RenderResult:
        if info.kind == "image":
            return eng.render.render_image(info, plan, target, out)
        return eng.render.render_video(
            info, plan, target, out, media.job.work, loudness_lufs=float(_setting("loudness_lufs", -14))
        )

    def rerender(extra: dict) -> checks.RenderResult:
        return render(media.plan(info, target, {**override, **(extra or {})}), fresh())

    plan = media.plan(info, target, override)
    # A transparent photo becomes PNG or JPEG depending on the target's formats and byte cap, so only targets that
    # share both may share its render. Opaque photos always become JPEG and share freely.
    output = [getattr(target.limits.get(name), "value", None) for name in ("formats", "bytes_max")] \
        if info.kind == "image" and info.has_alpha else []
    key = json.dumps([info.id, target.width, target.height, _mode(plan), list(getattr(plan, "trim", None) or []),
                      override, output], default=str, sort_keys=True)
    out = fresh()
    if key in masters:
        shutil.copy2(masters[key].file, out)
        return dataclasses.replace(masters[key], target=target.id, file=out), plan, rerender
    masters[key] = render(plan, out)
    return masters[key], plan, rerender


def _entry(job: jobs.Job, info: probe.InputInfo, target: platforms.TargetSpec, override: dict,
           media: _Media, masters: dict, previous: dict | None = None) -> dict:
    started = time.monotonic()
    entry: dict[str, Any] = {"id": target.id, "platform": target.platform, "kind": info.kind,
                             "input": info.id, "override": override}
    try:
        result, plan, rerender = _render(media, info, target, override, masters)
    except Unavailable as exc:
        return {**entry, "status": "skipped", "checks": [], "repairs": [], "reason": str(exc)}
    result, found, repairs = repair.check_and_repair(
        result, target, {"overrides": dict(override), "render": rerender, "job": job, "info": info})
    ok = checks.hard_pass(found)
    layout = dict(result.layout or {"mode": _mode(plan)})
    layout["note"] = _plan_note(info, plan)
    entry.update(checks=[c.to_dict() for c in found], repairs=repairs, width=result.width, height=result.height,
                 duration=result.duration, layout=layout,
                 trim=list(getattr(plan, "trim", []) or []) or None, subjects_inside=result.subjects_inside)
    if ok:
        folder = jobs.ready_dir(job, target.platform)
        for pattern in (f"{_stem(target)}.*", f"{_stem(target)}_cover.*"):
            for stale in folder.glob(pattern):
                stale.unlink()
        dest = folder / f"{_stem(target)}{result.file.suffix}"
        shutil.copy2(result.file, dest)
        entry["file"] = _rel(job, dest)
        entry["status"] = "repaired" if any(r["ok"] for r in repairs) else "ready"
        if info.kind == "video":
            cover = dest.with_name(f"{dest.stem}_cover.jpg")
            try:
                media.scan(info)[0].render.export_cover(info, plan, target, cover)
                entry["cover"] = _rel(job, cover)
            except Exception as exc:
                entry["cover_error"] = str(exc)
    else:
        dest = job.work / "failed" / f"{target.id}{result.file.suffix}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(result.file, dest)
        entry["status"] = "failed"
        entry["failed_file"] = _rel(job, dest)
        kept = (previous or {}).get("file")
        if kept and (job.root / kept).is_file():
            entry["kept"] = kept  # the earlier passing file stays in ready/ until a render succeeds
    entry["render_seconds"] = round(time.monotonic() - started, 2)
    return entry


def _write_board(job: jobs.Job, manifest: dict) -> dict:
    try:
        board = importlib.import_module(".board.board", __package__)
    except ModuleNotFoundError as exc:
        if (exc.name or "").endswith("engine.board.board"):
            return {"board_note": "The review board is not available yet."}
        raise
    return {k: str(v) for k, v in board.write_board(job.root, manifest).items()}


def _table(entries: list[dict]) -> list[dict]:
    rows = []
    for e in entries:
        bad = [c["message"] for c in e.get("checks", []) if c["status"] == "fail" and c["hard"]]
        advisory = [c["message"] for c in e.get("checks", []) if c["status"] == "advisory"]
        rows.append({k: v for k, v in {
            "target": e["id"], "status": e["status"], "file": e.get("file"), "cover": e.get("cover"),
            "size": f"{e['width']}x{e['height']}" if e.get("width") else None, "layout": e.get("layout"),
            "problems": bad or None, "advisory": advisory or None,
            "repairs": [f"{r['check']}: {r['action']}" for r in e.get("repairs", []) if r["ok"]] or None,
            "kept": e.get("kept"), "reason": e.get("reason")}.items() if v is not None})
    return rows


def _verify_unchanged(info: probe.InputInfo) -> None:
    """Cached detections are keyed by content hash, so a rewritten or missing input must not be rendered."""
    if not info.path.is_file():
        raise FileNotFoundError(f"input {info.id} is missing ({info.path}); run postkitty_scan again")
    if probe.sha256_file(info.path) != info.sha256:
        raise ValueError(f"input {info.id} ({info.path.name}) changed since the scan; run postkitty_scan again")


def _build(job: jobs.Job, ids: list[str], overrides: dict) -> dict:
    """Render ``ids``; overrides stored by earlier redo or make calls stay and new ones merge over them."""
    manifest = jobs.load_manifest(job)
    infos = _infos(manifest)
    scan = jobs.read_json(job.work / "scan.json")
    planned = {t["id"]: t["input"] for t in scan.get("targets", [])}
    by_id = {i.id: i for i in infos}
    for info in {planned[tid] for tid in ids if tid in planned}:
        _verify_unchanged(by_id[info])
    old = {t["id"]: t for t in manifest.get("targets", [])}
    media, masters, built = _Media(job), {}, []
    for tid in ids:
        if tid not in planned:
            raise ValueError(f"target {tid!r} is not planned in this job; planned: {sorted(planned)}")
        override = {**old.get(tid, {}).get("override", {}), **(overrides.get(tid) or {})}
        if by_id[planned[tid]].kind == "image" and {"trim", "cover_at"} & set(override):
            raise ValueError(f"{tid} is made from a photo; trim and cover_at apply to video only")
        built.append(_entry(job, by_id[planned[tid]], platforms.get_target(tid), override, media, masters,
                            old.get(tid)))
    merged = {**old, **{e["id"]: e for e in built}}
    manifest["targets"] = [merged[t["id"]] for t in scan["targets"] if t["id"] in merged]
    jobs.save_manifest(job, manifest)
    board = _write_board(job, manifest)
    return {"job": job.id, "job_dir": str(job.root), "targets": _table(built), **board}


# ------------------------------------------------------------------ scan

def scan(args: dict) -> dict:
    """Open a job, probe the inputs, detect people and plan a framing per target. Renders nothing."""
    paths = [str(p) for p in _list_arg(args, "inputs")]
    text = _str_arg(args, "text")
    if not paths and not text.strip():
        raise ValueError("give at least one input file or a draft text")
    wanted = _platform_names(_list_arg(args, "platforms") or _setting("default_platforms", []))
    infos, notes = [], []
    for index, path in enumerate(paths, start=1):
        infos.append(probe.probe(_input_path(path), f"in{index}"))  # before create_job: a bad path leaves no folder
    job = jobs.create_job(_out_dir(), paths, text, args.get("job"))
    manifest = jobs.load_manifest(job)
    if [e.get("sha256") for e in manifest.get("inputs", [])] != [i.sha256 for i in infos]:
        _drop_targets(job, manifest)
    media, entries = _Media(job), []
    peek = None
    for info in infos:
        entry = {k: getattr(info, k) for k in ("id", "kind", "sha256", "width", "height", "duration", "fps",
                                               "has_audio", "rotation", "has_alpha")}
        entry["path"] = str(info.path)
        try:
            if info.kind == "image" and peek is None:
                peek = _image_peek(job, info)
            eng, found = media.scan(info)
            if info.kind == "video":
                entry.update(people=len(found.tracks), shots=len(found.scenes))
                if peek is None:
                    peek = str(_engine("video").scan.make_peek(info, found, job.work / "peek.jpg"))
            else:
                # The same faces that photo.render lets focus person:N select: strong detections only.
                faces = found["frames"][0]["faces"] if found.get("frames") else []
                entry["people"] = sum(float(face.get("score", 0.0)) >= eng.faces.SUBJECT_MIN_SCORE for face in faces)
        except Exception as exc:
            notes.append(f"{info.id}: {exc}")
        entries.append(entry)
    manifest["inputs"] = entries
    manifest["text"] = {"source": "scan", "chars": len(text)} if text else {}
    kinds = {i.kind for i in infos}
    targets = platforms.targets_for(kinds, wanted) if kinds else []
    if kinds:
        notes.extend(_kind_mismatch_notes(wanted, kinds))
    plans = []
    for target in targets:
        info = advise.source_for(infos, target)
        if info is None:
            continue
        try:
            plan = _plan_summary(info, media.plan(info, target, None), target)
        except Exception:
            plan = _plan_summary(info, None, target)
        plans.append({"id": target.id, "input": info.id, "size": f"{target.width}x{target.height}", **plan})
    jobs.write_json(job.work / "scan.json", {"targets": plans, "inputs": entries, "peek": peek, "notes": notes})
    jobs.save_manifest(job, manifest)
    return {"job": job.id, "job_dir": str(job.root), "inputs": entries, "plan": plans,
            "fit": advise.fit_facts(infos, text or None, wanted or None, plans),
            "text": copyfit.text_stats(text) if text else None, "peek": peek, "notes": notes}


def _kind_mismatch_notes(wanted: list[str], kinds: set[str]) -> list[str]:
    """One note per requested platform or target that has nothing to make from the input kinds."""
    have = " and ".join(sorted("photos" if kind == "image" else "videos" for kind in kinds))
    notes = []
    for name in wanted:
        if name in platforms.platform_names():
            takes = {t.kind for t in platforms.get_platform(name).targets.values()}
        else:
            takes = {platforms.get_target(name).kind}
        if "image_or_video" in takes or takes & kinds:
            continue
        notes.append(f"{name} takes {'video' if takes == {'video'} else 'photos'}; the inputs are {have}")
    return notes


def _drop_targets(job: jobs.Job, manifest: dict) -> None:
    """A reused job with other inputs: every rendered target is stale, so remove its files and entries."""
    for entry in manifest.get("targets", []):
        for key in ("file", "cover", "failed_file"):
            if entry.get(key):
                (job.root / entry[key]).unlink(missing_ok=True)
    manifest["targets"] = []


def _image_peek(job: jobs.Job, info: probe.InputInfo) -> str:
    out = job.work / "peek.jpg"
    thumb = _engine("image").render.load_srgb(info.path).convert("RGB")
    thumb.thumbnail((1280, 1280))
    thumb.save(out, quality=85)
    return str(out)


# ------------------------------------------------------------------ write

def write(args: dict) -> dict:
    """Count each draft with its platform's rule, split threads and write the text files into ``ready/``."""
    job = _open_job(args)
    manifest = jobs.load_manifest(job)
    split = _bool_arg(args, "split_threads", True)
    advice = _dict_arg(args, "advice")
    if advice:
        manifest["advice"] = advice
        jobs.write_advice(job, advice)
    result: dict[str, Any] = {}
    drafts, draft_notes = _platform_drafts(_dict_arg(args, "drafts"))
    unknown = _write_alt(job, manifest, _dict_arg(args, "alt_text"))  # may reject keys before any draft is written
    for name, draft in drafts.items():
        report = copyfit.fit(name, draft, split_threads=split)
        rules = copyfit.rules_for(name)
        folder = jobs.ready_dir(job, name)
        for stale in ("post.txt", "thread.txt"):
            (folder / stale).unlink(missing_ok=True)
        files = []
        if report.ok or not rules.hard:
            target = "post.txt" if len(report.parts) == 1 else "thread.txt"
            (folder / target).write_text("\n\n---\n\n".join(report.parts) + "\n", encoding="utf-8")
            files.append(_rel(job, folder / target))
        manifest.setdefault("copy", {})[name] = {
            "parts": report.parts, "counts": report.counts, "unit": report.unit, "limit": report.limit, "ok": report.ok}
        details = {"ok": report.ok, "enforcement": "hard" if rules.hard else "recommendation",
                   "unit": report.unit, "limit": report.limit, "count": max(report.counts),
                   "overflow": report.overflow, "split": report.split,
                   "parts": [{"text": t, "count": c} for t, c in zip(report.parts, report.counts, strict=True)],
                   "hashtags": report.hashtags, "mentions": report.mentions,
                   "notes": report.notes + draft_notes.get(name, []), "files": files}
        if name != "x":
            details.update(fold=report.fold,
                           fold_note=f"about {report.fold_limit} characters show before 'more' (advisory)")
        result[name] = details
    jobs.save_manifest(job, manifest)
    return {"job": job.id, "all_ok": all(r["ok"] or r["enforcement"] != "hard" for r in result.values()),
            "platforms": result, "advice": str(job.advice_path) if advice else None,
            "alt_text_unmatched": unknown or None}


def _platform_drafts(drafts: dict) -> tuple[dict[str, Any], dict[str, list[str]]]:
    chosen: dict[str, tuple[int, str, Any]] = {}
    notes: dict[str, list[str]] = {}
    platform_names = set(platforms.platform_names())
    for raw, draft in drafts.items():
        (name,) = _platform_names([raw])
        if not (isinstance(draft, str) and draft.strip()) and not (
            isinstance(draft, list) and draft and all(isinstance(part, str) and part.strip() for part in draft)
        ):
            raise ValueError(f"draft for {raw!r} must be a non-empty string, or a list of non-empty strings for a thread")
        is_platform = name in platform_names
        platform = name if is_platform else platforms.platform_for_target(name)
        priority = int(is_platform)
        previous = chosen.get(platform)
        if previous and priority != previous[0]:
            target = previous[1] if priority else name
            notes[platform] = [f"Used the {platform} platform draft instead of the {target} target draft."]
        elif previous and not priority and previous[1] != name:
            notes[platform] = [f"Used the {name} target draft for {platform}; the {previous[1]} draft was ignored."]
        if previous is None or priority >= previous[0]:
            chosen[platform] = (priority, name, draft)
    return {platform: item[2] for platform, item in chosen.items()}, notes


def _write_alt(job: jobs.Job, manifest: dict, alt: dict) -> list[str]:
    by_platform: dict[str, dict[str, str]] = {}
    unknown = []
    sources: dict[str, str] = {}
    for key, text in alt.items():
        matches = _alt_matches(job, manifest, key)
        if not matches:
            unknown.append(key)
            continue
        for platform, target_id in matches:
            if target_id in sources:
                raise ValueError(f"alt text for {target_id} was given twice ({sources[target_id]!r} and {key!r}); keep one")
            sources[target_id] = key
            by_platform.setdefault(platform, {})[target_id] = str(text).strip()
    manifest.setdefault("alt_text", {}).update({k: v for d in by_platform.values() for k, v in d.items()})
    for platform, items in by_platform.items():
        lines = "\n\n".join(f"{key}:\n{text}" for key, text in items.items())
        (jobs.ready_dir(job, platform) / "alt.txt").write_text(lines + "\n", encoding="utf-8")
    return unknown


def _alt_matches(job: jobs.Job, manifest: dict, key: str) -> list[tuple[str, str]]:
    """Resolve an alt text key to ``(platform, target_id)`` pairs: a target id, an input file name (every
    target made from it), or a ready file by path or name. A bare name found for several targets is an error."""
    try:
        return [(platforms.platform_for_target(key), platforms.get_target(key).id)]
    except KeyError:
        pass
    entries = manifest.get("targets", [])
    if not entries and (job.work / "scan.json").is_file():
        entries = jobs.read_json(job.work / "scan.json").get("targets", [])
    input_ids = {item["id"] for item in manifest.get("inputs", []) if Path(item["path"]).name == key}
    matches = [(platforms.platform_for_target(item["id"]), item["id"])
               for item in entries if item.get("input") in input_ids]
    if matches:
        return matches
    key_path = Path(key).expanduser()
    by_name: list[tuple[str, str]] = []
    for item in manifest.get("targets", []):
        if not item.get("file"):
            continue
        ready_path = (job.root / item["file"]).resolve()
        if key_path.is_absolute() and key_path.resolve() == ready_path:
            return [(item["platform"], item["id"])]
        if key_path.name == ready_path.name:
            by_name.append((item["platform"], item["id"]))
    if not key_path.is_absolute() and len(key_path.parts) == 1 and job.ready.is_dir():
        for folder in job.ready.iterdir():
            target_id = _target_for_ready_file(folder.name, key) if (folder / key).is_file() else None
            if target_id and (folder.name, target_id) not in by_name:
                by_name.append((folder.name, target_id))
    if len(by_name) > 1:
        ids = ", ".join(target_id for _, target_id in by_name)
        raise ValueError(f"alt text key {key!r} matches several targets ({ids}); use the target id")
    return by_name


def _target_for_ready_file(platform: str, name: str) -> str | None:
    """``ready/x/image.jpg`` belongs to ``x_image``: the ready stem is the target id without its platform prefix."""
    for target in platforms.load_platforms().get(platform, platforms.PlatformSpec(platform, platform)).targets.values():
        if _stem(target) == Path(name).stem:
            return target.id
    return None


# ------------------------------------------------------------------ make, redo, check

def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_focus(value: Any) -> None:
    if not isinstance(value, str):
        raise ValueError(f"focus must be a string, got {type(value).__name__}")
    if value in {"auto", "left", "center", "right"}:
        return
    if value.startswith("person:"):
        if not value.removeprefix("person:").isdigit() or int(value.removeprefix("person:")) < 1:
            raise ValueError("focus person must be a positive integer, for example person:1")
        return
    if value.startswith("x:"):
        try:
            if 0.0 <= float(value.removeprefix("x:")) <= 1.0:
                return
        except ValueError:
            pass
        raise ValueError("focus x must be between 0 and 1, for example x:0.3")
    raise ValueError(f"focus {value!r} is not auto, person:N, left, center, right or x:0.0-1.0")


def _override(args: dict) -> dict:
    """The override keys of ``args`` with their values checked, so a bad value is an argument error."""
    out = {k: args[k] for k in OVERRIDE_KEYS if args.get(k) not in (None, "")}
    layouts = list(LAYOUTS)
    if "layout" in out and out["layout"] not in layouts:
        raise ValueError(f"layout must be one of {layouts}, got {out['layout']!r}")
    if "focus" in out:
        _check_focus(out["focus"])
    trim = out.get("trim")
    if trim is not None and not (isinstance(trim, list) and len(trim) == 2 and all(_is_number(v) for v in trim)
                                 and 0 <= trim[0] < trim[1]):
        raise ValueError(f"trim must be [start, end] in seconds with 0 <= start < end, got {trim!r}")
    if "cover_at" in out and not (_is_number(out["cover_at"]) and out["cover_at"] >= 0):
        raise ValueError(f"cover_at must be a time in seconds, got {out['cover_at']!r}")
    return out


def _overrides(raw: dict, planned: list[str]) -> dict:
    """Validate ``postkitty_make`` overrides: planned target ids (aliases allowed) mapped to known keys."""
    out = {}
    for key, value in raw.items():
        (tid,) = _platform_names([key])
        if tid not in planned:
            raise ValueError(f"override target {key!r} is not planned in this job; planned: {planned}")
        if not isinstance(value, dict):
            raise ValueError(f"override for {key!r} must be an object with layout, focus, trim or cover_at")
        unknown = sorted(set(value) - set(OVERRIDE_KEYS))
        if unknown:
            raise ValueError(f"unknown override key(s) {unknown} for {key!r}; use {list(OVERRIDE_KEYS)}")
        out[tid] = _override(value)
    return out


def make(args: dict) -> dict:
    """Render the planned targets, check and repair each file, and build the review board."""
    job = _open_job(args)
    targets, overrides = _list_arg(args, "targets"), _dict_arg(args, "overrides")
    scan_doc = jobs.read_json(job.work / "scan.json") if (job.work / "scan.json").is_file() else {}
    planned = [t["id"] for t in scan_doc.get("targets", [])]
    if not planned and jobs.load_manifest(job).get("inputs"):
        why = "; ".join(scan_doc.get("notes", [])) or "no requested platform fits the input kinds"
        raise ValueError(f"no media targets were planned ({why}); run postkitty_scan again with other platforms")
    if not planned:
        files = sorted(_rel(job, p) for p in job.ready.rglob("*.txt")) if job.ready.is_dir() else []
        return {"job": job.id, "job_dir": str(job.root), "targets": [], "files": files,
                "note": "This job is text only, so there is nothing to render; the copy files listed are already "
                        "in ready/. Run postkitty_scan with input files to get media targets."}
    ids = planned
    if targets:
        wanted = _platform_names(targets)
        ids = [t for t in planned if t in wanted or platforms.get_target(t).platform in wanted]
        if not ids:
            raise ValueError(f"none of {wanted} is planned in this job; planned: {planned}")
    return _build(job, ids, _overrides(overrides, planned))


def redo(args: dict) -> dict:
    """Render one target again with another layout, focus, trim or cover frame."""
    job = _open_job(args)
    if not args.get("target"):
        raise ValueError("argument 'target' is required; give the target id, for example tiktok")
    (target,) = _platform_names([args["target"]])
    override = _override(args)
    if not override:
        raise ValueError("give at least one of layout, focus, trim, cover_at")
    return _build(job, [target], {target: override})


def check(args: dict) -> dict:
    """Check one file against a target, or every ready file of a job, without rendering."""
    if args.get("path"):
        path = _input_path(args["path"]).resolve()
        job = _open_job(args) if args.get("job") else _job_for_ready_path(path)
        entry = _entry_for_path(job, path) if job else None
        target_id = args.get("target") or (entry or {}).get("id")
        framed = entry if entry and target_id == entry["id"] else None
        return _check_file(path, target_id, (framed or {}).get("layout"), _subjects_inside(framed))
    job = _open_job(args)
    out = {}
    for entry in jobs.load_manifest(job).get("targets", []):
        if entry.get("file"):
            out[entry["id"]] = _check_file(
                job.root / entry["file"], entry["id"], entry.get("layout"), _subjects_inside(entry)
            )
    if not out:
        return {"job": job.id, "targets": {}, "all_pass": False,
                "note": "This job has no ready media to check; run postkitty_make first."}
    return {"job": job.id, "targets": out, "all_pass": all(v["pass"] for v in out.values())}


def _job_for_ready_path(path: Path) -> jobs.Job | None:
    for parent in path.parents:
        if parent.name == "ready" and (parent.parent / "manifest.json").is_file():
            return jobs.open_job(parent.parent.parent, parent.parent.name)
    return None


def _entry_for_path(job: jobs.Job, path: Path) -> dict | None:
    for entry in jobs.load_manifest(job).get("targets", []):
        if entry.get("file") and (job.root / entry["file"]).resolve() == path:
            return entry
    return None


def _subjects_inside(entry: dict | None) -> float | None:
    if not entry:
        return None
    if "subjects_inside" in entry:
        return entry["subjects_inside"]
    for check in entry.get("checks", []):
        if check.get("id") == "frame.subjects_inside" and check.get("status") != "skipped":
            return check.get("measured")
    return None


def _check_file(path: Path, target_id: Any, layout: dict | None, subjects_inside: float | None = None) -> dict:
    if not target_id:
        raise ValueError("'target' is required with 'path'")
    (tid,) = _platform_names([target_id])
    target = platforms.get_target(tid)
    info = probe.probe(path, "check")
    if target.kind in {"image", "video"} and info.kind != target.kind:
        this = "a video" if info.kind == "video" else "a photo"
        raise ValueError(f"{path.name} is {this}; {tid} takes {'videos' if target.kind == 'video' else 'photos'}")
    try:
        _engine(info.kind)  # registers the media checkers when the engine exists
    except Unavailable:
        pass
    result = checks.RenderResult(target=tid, file=info.path, width=info.width, height=info.height,
                                 duration=info.duration, bytes=info.path.stat().st_size, layout=layout or {},
                                 subjects_inside=subjects_inside, extra={})
    found = checks.run_checks(result, target)
    for item in found:
        if item.id == "frame.subjects_inside" and item.status == "skipped":
            item.message = "Subject framing was skipped because this file was not made by postkitty."
    return {"target": tid, "file": str(info.path), "pass": checks.hard_pass(found),
            "checks": [c.to_dict() for c in found if c.status != "pass"] or "all checks pass"}
