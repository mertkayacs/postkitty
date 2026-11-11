import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

from postkitty import register, schemas, tools
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
    assert "tiktok" in ctx.commands["postkitty"]("")


def test_manifest_is_consistent():
    assert MANIFEST["name"] == "postkitty" and MANIFEST["manifest_version"] == 2 and MANIFEST["api_version"] == 1
    assert MANIFEST["version"] == __version__ and MANIFEST["license"] == "MIT"
    assert re.fullmatch(r">=\d+\.\d+\.\d+", MANIFEST["requires_hermes"])
    for dep in MANIFEST["python_dependencies"]:
        assert re.search(r">=[\d.]+,<[\d.]+", dep), dep
    assert not any("ruamel" in dep for dep in MANIFEST["python_dependencies"])
    assert set(MANIFEST["config_schema"]) == {"output_dir", "default_platforms", "loudness_lufs"}


def test_skill_frontmatter_and_size():
    skill = (ROOT / "skills/postkitty/SKILL.md").read_text()
    front = YAML(typ="safe").load(skill.split("---")[1])
    assert front["name"] == "postkitty" and len(front["description"]) <= 60 and front["description"].endswith(".")
    assert len(skill.splitlines()) < 250
    for tool in MANIFEST["provides_tools"]:
        assert tool in skill


def test_skill_uses_vision_and_does_not_recheck_generated_files():
    skill = (ROOT / "skills/postkitty/SKILL.md").read_text()

    assert "Never call `postkitty_check` on files made by `postkitty_make` or `postkitty_redo`." in skill
    assert "only for files the user brings from elsewhere" in skill
    assert "under 180 words plus the file list" in skill
    assert "If no vision tool is available" in skill
    assert "`speaker` cuts to whoever is talking" in skill
    assert "two other choices exist" in skill

    readme = (ROOT / "README.md").read_text()
    assert "a cut to whoever is speaking, or the whole wide shot." in readme


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


def test_copy_schema_documents_accepted_key_types():
    properties = schemas.SCHEMAS["postkitty_write"]["parameters"]["properties"]

    assert "target id" in properties["drafts"]["description"]
    assert "input file name or ready file path" in properties["alt_text"]["description"]


def test_tool_descriptions_tell_the_agent_when_to_use_each_tool():
    describe = {name: schema["description"] for name, schema in schemas.SCHEMAS.items()}

    assert "only wants a draft fixed" in describe["postkitty_scan"]
    assert "every later copy change" in describe["postkitty_write"]
    assert "For copy changes call postkitty_write instead." in describe["postkitty_redo"]
    assert "already checked" in describe["postkitty_check"]
