"""Job directories, ids, manifest IO and advice files."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from . import __version__

MANIFEST_SCHEMA = "postkitty.manifest/1"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class Job:
    id: str
    root: Path
    created: str

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def advice_path(self) -> Path:
        return self.root / "advice.md"

    @property
    def work(self) -> Path:
        return self.root / "work"

    @property
    def ready(self) -> Path:
        return self.root / "ready"


def slugify(seed: str, limit: int = 32) -> str:
    slug = _SLUG_RE.sub("-", str(seed).lower()).strip("-")
    if len(slug) > limit:
        slug = slug[:limit].rstrip("-")
    return slug or "post"


def agent_cwd() -> Path:
    try:
        from agent.runtime_cwd import resolve_agent_cwd

        return Path(resolve_agent_cwd())
    except Exception:
        return Path.cwd()


def default_out_dir(configured: str = "") -> Path:
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_absolute() else agent_cwd() / path
    return agent_cwd() / "postkitty"


def job_path(out_dir: Path, job_id: str) -> Path:
    return Path(out_dir).expanduser() / job_id


def job_exists(out_dir: Path, job_id: str) -> bool:
    return (job_path(out_dir, job_id) / "manifest.json").is_file()


def _created_stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _ensure_dirs(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for relative in ("ready", "work", "work/faces", "work/scenes", "work/render", "work/failed"):
        (root / relative).mkdir(parents=True, exist_ok=True)


def _unique_root(out_dir: Path, base_id: str) -> Path:
    candidate = job_path(out_dir, base_id)
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = job_path(out_dir, f"{base_id}-{index}")
        if not candidate.exists():
            return candidate
        index += 1


def create_job(
    out_dir: Path,
    inputs: Iterable[str | Path] = (),
    text: str = "",
    job_id: str | None = None,
) -> Job:
    """Create (or reopen) a job directory and write its initial manifest."""
    out = Path(out_dir).expanduser()
    if job_id:
        clean_id = slugify(job_id, limit=80)
        root = job_path(out, clean_id)
        if not root.exists():
            _ensure_dirs(root)
            manifest = manifest_template(clean_id, created=_created_stamp())
            save_manifest(Job(id=clean_id, root=root, created=manifest["created"]), manifest)
        else:
            _ensure_dirs(root)
        job = Job(id=clean_id, root=root, created=_load_created(root))
        manifest = load_manifest(job)
        manifest.setdefault("schema", MANIFEST_SCHEMA)
        manifest.setdefault("created", job.created)
        manifest["version"] = __version__
        save_manifest(job, manifest)
        return job

    first = next(iter(inputs), None)
    seed = Path(str(first)).stem if first is not None else (text.strip().split(" ")[0] if text.strip() else "post")
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    base_id = f"{stamp}-{slugify(seed)}"
    root = _unique_root(out, base_id)
    clean_id = root.name
    _ensure_dirs(root)
    created = _created_stamp()
    job = Job(id=clean_id, root=root, created=created)
    save_manifest(job, manifest_template(clean_id, created=created))
    return job


def _load_created(root: Path) -> str:
    try:
        data = read_json(root / "manifest.json")
        return str(data.get("created") or _created_stamp())
    except Exception:
        return _created_stamp()


def open_job(out_dir: Path, job_id: str) -> Job:
    clean_id = slugify(job_id, limit=80)
    root = job_path(out_dir, clean_id)
    if not root.is_dir():
        raise FileNotFoundError(f"job {clean_id!r} not found in {out_dir}")
    return Job(id=clean_id, root=root, created=_load_created(root))


def manifest_template(job_id: str, created: str | None = None) -> dict:
    return {
        "schema": MANIFEST_SCHEMA,
        "job": job_id,
        "created": created or _created_stamp(),
        "version": __version__,
        "inputs": [],
        "text": {},
        "advice": {},
        "copy": {},
        "targets": [],
    }


def read_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return data


def write_json(path: Path, data: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), prefix=path.name, suffix=".tmp", delete=False
    )
    try:
        with handle:
            json.dump(data, handle, indent=2, ensure_ascii=False, sort_keys=False)
            handle.write("\n")
        os.replace(handle.name, path)
    except Exception:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise
    return path


def load_manifest(job: Job) -> dict:
    if not job.manifest_path.is_file():
        return manifest_template(job.id, created=job.created)
    data = read_json(job.manifest_path)
    data.setdefault("schema", MANIFEST_SCHEMA)
    data.setdefault("job", job.id)
    data["version"] = __version__
    return data


def save_manifest(job: Job, manifest: dict) -> Path:
    manifest = dict(manifest)
    manifest["schema"] = MANIFEST_SCHEMA
    manifest["job"] = job.id
    manifest.setdefault("created", job.created)
    manifest["version"] = __version__
    return write_json(job.manifest_path, manifest)


def ready_dir(job: Job, platform: str) -> Path:
    path = job.ready / platform
    path.mkdir(parents=True, exist_ok=True)
    return path


def work_path(job: Job, *parts: str) -> Path:
    path = job.work.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_advice(job: Job, advice: dict) -> Path:
    lines = ["# Post advice", ""]
    sections = (
        ("topic", "Topic"),
        ("audience", "Audience"),
        ("tone", "Tone"),
        ("key_message", "Key message"),
    )
    for key, title in sections:
        value = advice.get(key)
        if value:
            lines.extend([f"## {title}", "", str(value).strip(), ""])

    ranking = advice.get("ranking") or []
    if isinstance(ranking, list) and ranking:
        lines.extend(["## Platform ranking", ""])
        for index, item in enumerate(ranking, start=1):
            if isinstance(item, dict):
                platform = str(item.get("platform") or "").strip()
                reason = str(item.get("reason") or "").strip()
                lines.append(f"{index}. {platform} - {reason}" if reason else f"{index}. {platform}")
            else:
                lines.append(f"{index}. {item}")
        lines.append("")

    tips = advice.get("tips") or []
    if isinstance(tips, list) and tips:
        lines.extend(["## Tips", ""])
        lines.extend(f"- {str(tip).strip()}" for tip in tips if str(tip).strip())
        lines.append("")

    job.advice_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return job.advice_path
