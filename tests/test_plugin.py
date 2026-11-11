import ast
import json
import re
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

from postkitty import command, register, schemas, tools
from postkitty.engine import __version__
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = YAML(typ="safe").load((ROOT / "plugin.yaml").read_text())


class FakeCtx:
    def __init__(self):
        self.tools, self.skills, self.commands = {}, {}, {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = (toolset, schema, handler)

    def register_skill(self, name, path, description=""):
        self.skills[name] = Path(path)

    def register_command(self, name, handler, description="", args_hint=""):
        self.commands[name] = handler

    def register_cli_command(self, name, help, setup_fn, handler_fn=None, description=""):
        self.cli = {name: (setup_fn, handler_fn)}

    def get_config(self, key, default=None):
        return default


def test_register_wires_tools_skill_and_command():
    ctx = FakeCtx()
    register(ctx)
    assert set(ctx.tools) == set(MANIFEST["provides_tools"]) and len(ctx.tools) == 5
    for name, (toolset, schema, handler) in ctx.tools.items():
        assert toolset == "postkitty" and schema["name"] == name and schema["parameters"]["type"] == "object"
        assert len(schema["description"]) > 80 and callable(handler)
    assert ctx.skills["postkitty"].is_file() and "postkitty" in ctx.commands
    assert "tiktok" in ctx.commands["postkitty"]("") and callable(ctx.cli["postkitty"][1])


def test_register_works_on_a_hermes_without_cli_commands():
    class OlderCtx:
        def __init__(self):
            self.tools, self.commands = {}, {}

        def register_tool(self, name, **kwargs):
            self.tools[name] = kwargs

        def register_skill(self, *args, **kwargs):
            pass

        def register_command(self, name, handler, **kwargs):
            self.commands[name] = handler

        def get_config(self, key, default=None):
            return default

    older = OlderCtx()
    register(older)
    assert len(older.tools) == 5 and "postkitty" in older.commands


def test_manifest_is_consistent():
    assert MANIFEST["name"] == "postkitty" and MANIFEST["manifest_version"] == 2 and MANIFEST["api_version"] == 1
    assert MANIFEST["license"] == "MIT"
    assert re.fullmatch(r">=\d+\.\d+\.\d+", MANIFEST["requires_hermes"])
    for dep in MANIFEST["python_dependencies"]:
        assert re.search(r">=[\d.]+,<[\d.]+", dep), dep
    assert set(MANIFEST["config_schema"]) == {"output_dir", "default_platforms", "loudness_lufs"}


def test_the_declared_dependencies_are_exactly_the_packages_the_code_imports():
    packages = {"cv2": "opencv-contrib-python-headless", "numpy": "numpy", "PIL": "pillow", "regex": "regex",
                "ruamel": "ruamel.yaml"}
    imported = set()
    for path in [*ROOT.glob("*.py"), *ROOT.glob("engine/**/*.py")]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
    hermes = {"agent", "plugins"}  # the two guarded imports of the Hermes adapter
    third_party = imported - set(sys.stdlib_module_names) - hermes
    declared = {re.split(r"[<>=!~ ]", dep, maxsplit=1)[0].lower() for dep in MANIFEST["python_dependencies"]}
    assert {packages[name] for name in third_party} == declared


def test_version_and_dependencies_agree_everywhere():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    skill = YAML(typ="safe").load((ROOT / "skills/postkitty/SKILL.md").read_text().split("---")[1])
    assert MANIFEST["version"] == __version__ == project["version"] == str(skill["version"])
    assert project["dependencies"] == MANIFEST["python_dependencies"]
    assert re.fullmatch(r">=3\.\d+", project["requires-python"])


def test_skill_frontmatter_and_size():
    skill = (ROOT / "skills/postkitty/SKILL.md").read_text()
    front = YAML(typ="safe").load(skill.split("---")[1])
    assert front["name"] == "postkitty" and len(front["description"]) <= 60 and front["description"].endswith(".")
    assert len(skill.splitlines()) < 250
    for tool in MANIFEST["provides_tools"]:
        assert tool in skill


def test_every_tool_named_in_the_skill_the_command_text_and_the_schemas_is_registered():
    registered = set(MANIFEST["provides_tools"])
    assert set(schemas.SCHEMAS) == set(tools.HANDLERS) == registered
    skill = (ROOT / "skills/postkitty/SKILL.md").read_text()
    described = json.dumps(schemas.SCHEMAS)
    for text in (skill, command.OVERVIEW, described):
        assert set(re.findall(r"postkitty_[a-z]+", text)) <= registered
    assert set(re.findall(r"postkitty_[a-z]+", skill)) == registered


def test_the_skill_table_names_only_arguments_the_schemas_have():
    skill = (ROOT / "skills/postkitty/SKILL.md").read_text()
    rows = [line.split("|") for line in skill.splitlines() if line.startswith("| `postkitty_")]
    assert len(rows) == len(schemas.SCHEMAS)
    for row in rows:
        tool = row[1].strip().strip("`")
        named = set(re.findall(r"`([a-z_]+)`", row[3]))
        assert named and named <= set(schemas.SCHEMAS[tool]["parameters"]["properties"]), tool


def test_no_em_dashes_or_emoji_in_shipped_text():
    for path in [*ROOT.glob("*.py"), *ROOT.glob("engine/**/*.py"), *ROOT.glob("skills/*/SKILL.md"), ROOT / "plugin.yaml"]:
        text = path.read_text(encoding="utf-8")
        assert "—" not in text, path
        assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", text), path


def test_plugin_import_and_text_flow_never_load_cv2_numpy_or_pillow(tmp_path):
    code = textwrap.dedent(
        f"""
        import importlib.abc, importlib.util, json, sys
        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] in {{"cv2", "numpy", "PIL"}}:
                    raise ImportError("blocked: " + name)
        sys.meta_path.insert(0, Block())
        root = {str(ROOT)!r}
        spec = importlib.util.spec_from_file_location("postkitty", root + "/__init__.py", submodule_search_locations=[root])
        mod = importlib.util.module_from_spec(spec); sys.modules["postkitty"] = mod; spec.loader.exec_module(mod)
        from postkitty import tools
        class Ctx:
            def register_tool(self, **k): pass
            def register_skill(self, *a, **k): pass
            def register_command(self, *a, **k): pass
            def get_config(self, key, default=None): return {str(tmp_path / "out")!r} if key == "output_dir" else default
        mod.register(Ctx())
        scan = json.loads(tools.scan({{"text": "hello world #hi"}}))
        copy = json.loads(tools.write({{"job": scan["job"], "drafts": {{"x": "hello"}}}}))
        assert "error" not in scan and copy["all_ok"], (scan, copy)
        bad = [m for m in sys.modules if m.split(".")[0] in {{"cv2", "numpy", "PIL"}}]
        assert not bad, bad
        print("clean")
        """
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert done.stdout.strip() == "clean", done.stderr + done.stdout


def test_tool_results_are_json_strings():
    assert isinstance(tools.scan({}), str) and isinstance(json.loads(tools.check({})), dict)


def test_every_schema_parameter_is_described_and_every_required_one_exists():
    for name, schema in schemas.SCHEMAS.items():
        properties = schema["parameters"]["properties"]
        assert set(schema["parameters"].get("required", [])) <= set(properties), name
        for key, prop in properties.items():
            assert prop.get("description"), (name, key)
