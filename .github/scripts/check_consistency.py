"""Fail when the files that name the tools, the version or the dependencies disagree.

Tools: plugin.yaml provides_tools, schemas.SCHEMAS, tools.HANDLERS and the names register(ctx) registers.
Version: plugin.yaml, engine.__version__, the SKILL.md front matter, the newest CHANGELOG.md entry and,
when pyproject.toml has a [project] table, its version.
Dependencies: plugin.yaml python_dependencies and pyproject.toml [project] dependencies. Hermes reads the
pyproject list when it exists, and Hermes versions before that rule read the manifest, so both must say the same.

Run with the plugin's runtime dependencies installed: python .github/scripts/check_consistency.py
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tomllib
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]
_problems: list[str] = []


def check(condition: bool, message: str) -> None:
    print(("ok   " if condition else "FAIL ") + message)
    if not condition:
        _problems.append(message)


class RecordingContext:
    """Stands in for the Hermes plugin context: every method call is recorded and returns None."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, name: str):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return record


def load_plugin():
    spec = importlib.util.spec_from_file_location("postkitty", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["postkitty"] = module
    spec.loader.exec_module(module)
    return module


def same_requirement_lists(left: list[str], right: list[str]) -> bool:
    def normal(items: list[str]) -> list[str]:
        return sorted(re.sub(r"\s+", "", item).lower() for item in items)

    return normal(left) == normal(right)


def main() -> int:
    yaml = YAML(typ="safe")
    manifest = yaml.load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))
    plugin = load_plugin()
    schemas, tools, engine = (sys.modules[f"postkitty.{name}"] for name in ("schemas", "tools", "engine"))

    declared = list(manifest.get("provides_tools") or [])
    ctx = RecordingContext()
    plugin.register(ctx)
    registered = [kwargs.get("name", args[0] if args else None) for name, args, kwargs in ctx.calls if name == "register_tool"]
    check(len(set(declared)) == len(declared), f"plugin.yaml provides_tools has no duplicates ({declared})")
    check(sorted(registered) == sorted(declared),
          f"register(ctx) registers exactly the tools plugin.yaml declares (registered {sorted(registered)}, "
          f"declared {sorted(declared)})")
    check(sorted(schemas.SCHEMAS) == sorted(declared),
          f"schemas.SCHEMAS has exactly the declared tools ({sorted(schemas.SCHEMAS)})")
    check(sorted(tools.HANDLERS) == sorted(declared), f"tools.HANDLERS has exactly the declared tools ({sorted(tools.HANDLERS)})")
    for key, schema in schemas.SCHEMAS.items():
        check(schema.get("name") == key, f"the schema stored under {key} is named {key} (got {schema.get('name')})")

    version = str(manifest.get("version"))
    check(bool(re.fullmatch(r"\d+\.\d+\.\d+", version)), f"plugin.yaml version is MAJOR.MINOR.PATCH ({version})")
    check(engine.__version__ == version, f"engine.__version__ is {version} (got {engine.__version__})")
    skill = (ROOT / "skills" / "postkitty" / "SKILL.md").read_text(encoding="utf-8")
    front_matter = yaml.load(skill.split("---", 2)[1]) if skill.startswith("---") else {}
    check(str(front_matter.get("version")) == version,
          f"SKILL.md front matter version is {version} (got {front_matter.get('version')})")
    changelog = ROOT / "CHANGELOG.md"
    entries = changelog.read_text(encoding="utf-8") if changelog.is_file() else ""
    newest = re.search(r"^## \[?(\d+\.\d+\.\d+)\]?", entries, re.MULTILINE)
    check(newest is not None and newest.group(1) == version,
          f"the newest CHANGELOG.md entry is {version} (got {newest.group(1) if newest else 'no CHANGELOG.md entry'})")

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8")).get("project")
    if project is None:
        print("skip pyproject.toml has no [project] table; plugin.yaml python_dependencies is the only dependency list")
    else:
        check(str(project.get("version")) == version,
              f"pyproject.toml [project] version is {version} (got {project.get('version')})")
        check(same_requirement_lists(project.get("dependencies") or [], manifest.get("python_dependencies") or []),
              "pyproject.toml [project] dependencies equal plugin.yaml python_dependencies "
              f"({project.get('dependencies')} against {manifest.get('python_dependencies')})")

    print()
    if _problems:
        print(f"{len(_problems)} consistency check(s) failed:")
        for item in _problems:
            print("  - " + item)
        return 1
    print("every consistency check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
