"""Hermes refuses an unattended install when its security scan meets an invisible character in the plugin's code.

The scan grades each zero-width or direction character in a file outside the test tree as high. One high finding
turns the verdict to caution, and ``hermes plugins install mertkayacs/postkitty --yes-deps --enable`` run by an agent
or a script is then blocked. A string that needs such a character writes it as an escape, for example ``"\\u2060"``.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The characters and file types Hermes names in tools/skills_guard.py.
INVISIBLE = {chr(code) for code in (0x200B, 0x200C, 0x200D, 0x2060, 0x2062, 0x2063, 0x2064, 0xFEFF, 0x202A, 0x202B,
                                    0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069)}
SCANNED = {".md", ".txt", ".py", ".sh", ".bash", ".js", ".ts", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini",
           ".conf", ".html", ".css", ".xml"}
SKIPPED_FOLDERS = {"tests", ".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "postkitty", "work"}


def test_no_file_outside_the_tests_holds_an_invisible_character():
    found = []
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if not path.is_file() or path.suffix.lower() not in SCANNED or SKIPPED_FOLDERS & set(relative.parts[:-1]):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            found += [f"{relative}:{number} U+{ord(char):04X}" for char in sorted(INVISIBLE & set(line))]

    assert found == []
